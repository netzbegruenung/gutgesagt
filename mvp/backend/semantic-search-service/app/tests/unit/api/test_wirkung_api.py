"""
Wirkungs-Echo (#790) und Danke (#791) an den Endpunkten: nur mit Schalter, eigene
Beitraege und Startkonten zaehlen nicht, ohne Konto nur mit dem Unterschalter.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1 import usage as usage_module
from api.v1.usage import router as usage_router
from core.config import Settings
from dependencies import get_beitrag_laden, get_nutzung_rate_limiter, get_settings
from domain.team_fortschritt import Art
from services import gepostet_service as gepostet_modul
from services.team_fortschritt_service import team_fortschritt_service_setzen
from services.beitrag_laden import BeitragUnlesbar

pytestmark = pytest.mark.unit

BEITRAG_ID = "11111111-1111-4111-8111-111111111111"
EIGENER_ID = "22222222-2222-4222-8222-222222222222"
UNLESBAR_ID = "33333333-3333-4333-8333-333333333333"
GEPOSTET = "/api/v1/usage/users/me/gepostet"
DANKE = f"/api/v1/usage/content/{BEITRAG_ID}/danke"
KIM = {"X-User": "kim-1"}
AUTORIN = "autorin-7"


@pytest.fixture
def wirkung():
    dienst = Mock()
    dienst.gepostet_melden.return_value = True
    dienst.danke_sagen.return_value = True
    with patch.object(usage_module, "get_wirkung_service", return_value=dienst):
        yield dienst


@pytest.fixture
def gepostet(monkeypatch, art9_einwilligung_ohne_datenbank):
    dienst = Mock()
    dienst.diese_woche.return_value = 6
    dienst.melden.return_value = 7
    monkeypatch.setattr(gepostet_modul, "_service", dienst)
    return dienst


def _client(**schalter) -> TestClient:
    app = FastAPI()
    app.include_router(usage_router, prefix="/api/v1/usage")
    werte = dict(gepostet_aktiv=True, startkonten="start-9")
    werte.update(schalter)
    app.dependency_overrides[get_settings] = lambda: Settings(**werte)

    async def laden(content_id):
        if str(content_id) == BEITRAG_ID:
            return SimpleNamespace(id=content_id, original_author=AUTORIN)
        if str(content_id) == EIGENER_ID:
            return SimpleNamespace(id=content_id, original_author="kim-1")
        if str(content_id) == UNLESBAR_ID:
            raise BeitragUnlesbar()
        return None

    app.dependency_overrides[get_beitrag_laden] = lambda: laden
    limiter = Mock(is_rate_limited=AsyncMock(return_value=False))
    app.dependency_overrides[get_nutzung_rate_limiter] = lambda: limiter
    return TestClient(app)


class TestWirkungsEcho:
    def test_mit_schalter_zaehlt_den_genannten_beitrag(self, gepostet, wirkung):
        antwort = _client(wirkungs_echo_aktiv=True).post(
            GEPOSTET, json={"content_id": BEITRAG_ID}, headers=KIM
        )

        assert antwort.status_code == 200
        assert antwort.json() == {
            "personen_diese_woche": 7,
            "beitrag_nennen": True,
            "angeboten": True,
        }
        gepostet.melden.assert_called_once_with("kim-1")
        (person, beitrag), _ = wirkung.gepostet_melden.call_args
        assert person == "kim-1" and str(beitrag) == BEITRAG_ID

    def test_ohne_schalter_wird_der_beitrag_verworfen(self, gepostet, wirkung):
        antwort = _client().post(GEPOSTET, json={"content_id": BEITRAG_ID}, headers=KIM)

        assert antwort.json() == {
            "personen_diese_woche": 7,
            "beitrag_nennen": False,
            "angeboten": True,
        }
        wirkung.gepostet_melden.assert_not_called()

    def test_stand_sagt_ob_der_beitrag_mitgehen_soll(self, gepostet, wirkung):
        an = _client(wirkungs_echo_aktiv=True).get(GEPOSTET, headers=KIM).json()
        aus = _client().get(GEPOSTET, headers=KIM).json()

        assert an["beitrag_nennen"] is True
        assert aus["beitrag_nennen"] is False

    def test_admin_wert_aus(self, gepostet, wirkung, schalter_admin_alle_an):
        schalter_admin_alle_an["wirkungs_echo"] = False
        antwort = _client(wirkungs_echo_aktiv=True).post(
            GEPOSTET, json={"content_id": BEITRAG_ID}, headers=KIM
        )

        assert antwort.json()["beitrag_nennen"] is False
        wirkung.gepostet_melden.assert_not_called()

    @pytest.mark.parametrize(
        "content_id", [EIGENER_ID, "44444444-4444-4444-8444-444444444444", "kaputt"]
    )
    def test_eigener_unbekannter_oder_kaputter_beitrag_zaehlt_nicht(
        self, gepostet, wirkung, content_id
    ):
        antwort = _client(wirkungs_echo_aktiv=True).post(
            GEPOSTET, json={"content_id": content_id}, headers=KIM
        )

        assert antwort.status_code == 200
        gepostet.melden.assert_called_once()
        wirkung.gepostet_melden.assert_not_called()

    def test_ohne_body_wie_bisher(self, gepostet, wirkung):
        antwort = _client(wirkungs_echo_aktiv=True).post(GEPOSTET, headers=KIM)

        assert antwort.status_code == 200
        wirkung.gepostet_melden.assert_not_called()

    def test_fehler_am_echo_kostet_die_wochenzahl_nicht(self, gepostet, wirkung):
        wirkung.gepostet_melden.side_effect = RuntimeError("weg")
        antwort = _client(wirkungs_echo_aktiv=True).post(
            GEPOSTET, json={"content_id": BEITRAG_ID}, headers=KIM
        )

        assert antwort.status_code == 200
        assert antwort.json()["personen_diese_woche"] == 7

    @pytest.mark.parametrize("scheitert", [None, "team", "echo"])
    def test_team_zaehler_und_echo_beide_ohne_einander_zu_stoeren(
        self, gepostet, wirkung, scheitert
    ):
        """
        "Ja, gepostet" hakt den Team-Wochenzaehler (#784) und das Wirkungs-Echo (#790)
        ein: beide laufen, und ein Fehler des einen kostet den anderen nicht.
        """
        team = Mock()
        if scheitert == "team":
            team.zaehlen.side_effect = RuntimeError("weg")
        if scheitert == "echo":
            wirkung.gepostet_melden.side_effect = RuntimeError("weg")
        team_fortschritt_service_setzen(team)
        try:
            antwort = _client(wirkungs_echo_aktiv=True).post(
                GEPOSTET, json={"content_id": BEITRAG_ID}, headers=KIM
            )
        finally:
            team_fortschritt_service_setzen(None)

        assert antwort.status_code == 200
        assert antwort.json()["personen_diese_woche"] == 7
        team.zaehlen.assert_called_once_with("kim-1", Art.GEPOSTET, "")
        wirkung.gepostet_melden.assert_called_once()

    def test_startkonto_wie_bisher_404(self, gepostet, wirkung):
        antwort = _client(wirkungs_echo_aktiv=True).post(
            GEPOSTET, json={"content_id": BEITRAG_ID}, headers={"X-User": "start-9"}
        )

        assert antwort.status_code == 404
        wirkung.gepostet_melden.assert_not_called()


class TestDanke:
    def test_ohne_schalter_404(self, wirkung, art9_einwilligung_ohne_datenbank):
        assert _client().post(DANKE, headers=KIM).status_code == 404
        wirkung.danke_sagen.assert_not_called()
        art9_einwilligung_ohne_datenbank.lesen.assert_not_called()

    def test_angemeldet_zaehlt_ueber_die_kennung(
        self, wirkung, art9_einwilligung_ohne_datenbank
    ):
        antwort = _client(danke_knopf_aktiv=True).post(DANKE, headers=KIM)

        assert antwort.status_code == 200
        assert antwort.json() == {"gezaehlt": True}
        (kennung, merkmal, beitrag), _ = wirkung.danke_sagen.call_args
        assert kennung == "kim-1" and merkmal is None and str(beitrag) == BEITRAG_ID

    def test_ohne_einwilligung_403(self, wirkung, art9_einwilligung_ohne_datenbank):
        art9_einwilligung_ohne_datenbank.lesen.return_value = None

        antwort = _client(danke_knopf_aktiv=True).post(DANKE, headers=KIM)

        assert antwort.status_code == 403
        assert antwort.json()["detail"] == "art9_einwilligung_fehlt"
        wirkung.danke_sagen.assert_not_called()

    def test_eigener_beitrag_zaehlt_nicht(
        self, wirkung, art9_einwilligung_ohne_datenbank
    ):
        antwort = _client(danke_knopf_aktiv=True).post(
            f"/api/v1/usage/content/{EIGENER_ID}/danke", headers=KIM
        )

        assert antwort.json() == {"gezaehlt": False}
        wirkung.danke_sagen.assert_not_called()

    def test_startkonto_zaehlt_nicht(self, wirkung, art9_einwilligung_ohne_datenbank):
        antwort = _client(danke_knopf_aktiv=True).post(
            DANKE, headers={"X-User": "start-9"}
        )

        assert antwort.json() == {"gezaehlt": False}
        wirkung.danke_sagen.assert_not_called()

    def test_unlesbarer_beitrag_zaehlt_nicht(
        self, wirkung, art9_einwilligung_ohne_datenbank
    ):
        antwort = _client(danke_knopf_aktiv=True).post(
            f"/api/v1/usage/content/{UNLESBAR_ID}/danke", headers=KIM
        )

        assert antwort.json() == {"gezaehlt": False}
        wirkung.danke_sagen.assert_not_called()

    def test_unbekannter_beitrag_404_kaputte_id_400(
        self, wirkung, art9_einwilligung_ohne_datenbank
    ):
        client = _client(danke_knopf_aktiv=True)

        assert (
            client.post(
                "/api/v1/usage/content/44444444-4444-4444-8444-444444444444/danke",
                headers=KIM,
            ).status_code
            == 404
        )
        assert (
            client.post("/api/v1/usage/content/x/danke", headers=KIM).status_code == 400
        )

    def test_ohne_konto_nur_mit_unterschalter(self, wirkung):
        assert _client(danke_knopf_aktiv=True).post(DANKE).status_code == 404
        assert (
            _client(danke_ohne_konto_aktiv=True).post(DANKE).status_code == 404
        ), "Unterschalter wirkt nur mit dem Danke-Knopf"
        wirkung.danke_sagen.assert_not_called()

    def test_ohne_konto_ueber_das_besuchermerkmal(self, wirkung):
        antwort = _client(danke_knopf_aktiv=True, danke_ohne_konto_aktiv=True).post(
            DANKE, headers={"X-Real-IP": "203.0.113.5"}
        )

        assert antwort.json() == {"gezaehlt": True}
        (kennung, merkmal, _beitrag), _ = wirkung.danke_sagen.call_args
        assert kennung is None
        assert merkmal

    def test_zweites_danke_am_tag_zaehlt_nicht(
        self, wirkung, art9_einwilligung_ohne_datenbank
    ):
        wirkung.danke_sagen.return_value = False

        antwort = _client(danke_knopf_aktiv=True).post(DANKE, headers=KIM)

        assert antwort.json() == {"gezaehlt": False}

    def test_rate_limit_429(self, wirkung, art9_einwilligung_ohne_datenbank):
        client = _client(danke_knopf_aktiv=True)
        limiter = Mock(is_rate_limited=AsyncMock(return_value=True))
        client.app.dependency_overrides[get_nutzung_rate_limiter] = lambda: limiter

        assert client.post(DANKE, headers=KIM).status_code == 429
        wirkung.danke_sagen.assert_not_called()

    def test_fehler_ohne_kennung_im_log(
        self, wirkung, art9_einwilligung_ohne_datenbank, caplog
    ):
        wirkung.danke_sagen.side_effect = RuntimeError("kaputt")

        antwort = _client(danke_knopf_aktiv=True).post(DANKE, headers=KIM)

        assert antwort.status_code == 500
        assert "kim-1" not in caplog.text
