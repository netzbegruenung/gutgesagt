"""
Die Rueckmeldung beim Anmelden (#349): "Seit deinem letzten Besuch wurden deine
Beitraege N-mal genutzt".

Wie die Nutzungsstatistik ohne Kennung in der Adresse: Die Person kommt aus
``X-User`` (gesetzt vom BFF), ein Pfad mit Kennung stuende im Zugriffslog.
POST, weil der Aufruf den gezeigten Stand fortschreibt.
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1 import usage as usage_module
from api.v1.usage import router as usage_router
from types import SimpleNamespace

from core.config import Settings
from core.logging import log_pseudonym
from dependencies import get_settings, get_unbeantwortete_aussagen_service
from repositories.einwurf_repository import get_einwurf_repository
from repositories.gesehene_nutzung_repository import get_gesehene_nutzung_repository
from services.unbeantwortete_aussagen_service import LIMIT_STANDARD

URL = "/api/v1/usage/users/me/besuch"


@pytest.fixture
def dienst():
    dienst = Mock()
    dienst.nutzung_seit_letztem_besuch = AsyncMock(return_value=4)
    return dienst


@pytest.fixture
def einwuerfe():
    repo = Mock()
    repo.count_von_anderen = Mock(
        side_effect=lambda person, nur_offene=False: 5 if nur_offene else 12
    )
    repo.count_ausformuliert_von_anderen = Mock(return_value=2)
    return repo


@pytest.fixture
def inhalte():
    repo = Mock()
    repo.count_neue_von_anderen = AsyncMock(return_value=6)
    return repo


@pytest.fixture
def gesehen():
    repo = Mock()
    repo.neue_einwuerfe_seit_letztem_besuch = Mock(return_value=3)
    repo.neues_echo_seit_letztem_besuch = Mock(side_effect=lambda _p, jetzt: jetzt)
    repo.schon_besucht = Mock(return_value=True)
    return repo


@pytest.fixture
def unbeantwortete():
    dienst = Mock()
    dienst.liste = AsyncMock(return_value=[object(), object()])
    return dienst


@pytest.fixture
def client(dienst, einwuerfe, gesehen, unbeantwortete, inhalte):
    app = FastAPI()
    app.include_router(usage_router, prefix="/api/v1/usage")
    app.dependency_overrides[get_einwurf_repository] = lambda: einwuerfe
    app.dependency_overrides[get_gesehene_nutzung_repository] = lambda: gesehen
    app.dependency_overrides[get_unbeantwortete_aussagen_service] = (
        lambda: unbeantwortete
    )

    with patch.object(
        usage_module, "get_usage_service", return_value=dienst
    ), patch.object(
        usage_module, "get_content_repository", return_value=inhalte
    ), patch.object(
        # Antworten auf eigene Aussagen (#760): eigene Tests in
        # test_antworten_hinweis_api.py; hier ohne eigene Aussagen
        usage_module.antworten_hinweis,
        "statement_repository",
        return_value=Mock(
            get_by_author=AsyncMock(return_value=[]),
            antworten_mit_autor=AsyncMock(return_value={}),
        ),
    ):
        yield TestClient(app)


class TestSeitLetztemBesuch:
    def test_besuch_nennt_nutzung_seit_letztem_besuch(self, client, dienst):
        antwort = client.post(URL, headers={"X-User": "kim-1"})

        assert antwort.status_code == 200
        assert antwort.json() == {
            "nutzung_seit_letztem_besuch": 4,
            "neue_einwuerfe": 3,
            "unbeantwortete_aussagen": 2,
            "unbeantwortete_aussagen_mehr": False,
            "ausformulierte_einwuerfe": 2,
            "neue_beitraege": 6,
            # Obergrenze aus (Standard, #760): keine Zahl
            "antworten_auf_eigene_aussagen": None,
            # Wirkungs-Echo aus (Standard, #790): keine Summe
            "neu_oeffentlich_gepostet": None,
            # Schon einmal da gewesen
            "erster_besuch": False,
        }
        dienst.nutzung_seit_letztem_besuch.assert_awaited_once_with("kim-1")

    @pytest.mark.parametrize("kopf", [{}, {"X-User": "anonymous"}])
    def test_besuch_ohne_anmeldung_401(self, client, dienst, kopf):
        antwort = client.post(URL, headers=kopf)

        assert antwort.status_code == 401
        dienst.nutzung_seit_letztem_besuch.assert_not_awaited()

    def test_besuch_ohne_kennung_in_der_adresse(self, client, dienst):
        antwort = client.post(
            "/api/v1/usage/users/bo-2/besuch", headers={"X-User": "kim-1"}
        )

        assert antwort.status_code in (404, 405)
        dienst.nutzung_seit_letztem_besuch.assert_not_awaited()

    def test_besuch_fehler_ohne_kennung_im_log(self, client, dienst, caplog):
        dienst.nutzung_seit_letztem_besuch.side_effect = RuntimeError("kaputt")

        antwort = client.post(URL, headers={"X-User": "kim-1"})

        assert antwort.status_code == 500
        assert log_pseudonym("kim-1") in caplog.text
        assert "kim-1" not in caplog.text


class TestErsterBesuch:
    """Beim allerersten Besuch kein "Seit deinem letzten Besuch" (Review 25.11.)."""

    def test_ohne_stand_ist_es_der_erste_besuch(self, client, gesehen):
        gesehen.schon_besucht.return_value = False

        antwort = client.post(URL, headers={"X-User": "kim-1"})

        assert antwort.status_code == 200
        assert antwort.json()["erster_besuch"] is True
        gesehen.schon_besucht.assert_called_once_with("kim-1")

    def test_prueft_vor_den_zahlen_die_den_stand_anlegen(self, client, gesehen):
        gesehen.schon_besucht.return_value = False

        client.post(URL, headers={"X-User": "kim-1"})

        assert [c[0] for c in gesehen.method_calls][0] == "schon_besucht"

    def test_fehler_gilt_als_wiederkehr_und_der_besuch_steht(self, client, gesehen):
        gesehen.schon_besucht.side_effect = RuntimeError("kaputt")

        antwort = client.post(URL, headers={"X-User": "kim-1"})

        assert antwort.status_code == 200
        assert antwort.json()["erster_besuch"] is False
        assert antwort.json()["nutzung_seit_letztem_besuch"] == 4


class TestSeitDeinemLetztenBesuch:
    """Startseite (Nutzerfuehrung 13.11.): Zaehlerstaende, kein Zeitpunkt."""

    def test_zaehlt_einwuerfe_anderer_gegen_den_gesehenen_stand(
        self, client, einwuerfe, gesehen
    ):
        client.post(URL, headers={"X-User": "kim-1"})

        einwuerfe.count_von_anderen.assert_any_call("kim-1")
        gesehen.neue_einwuerfe_seit_letztem_besuch.assert_called_once_with("kim-1", 12)

    def test_nie_negativ(self, client, gesehen):
        gesehen.neue_einwuerfe_seit_letztem_besuch.return_value = -5

        antwort = client.post(URL, headers={"X-User": "kim-1"})

        assert antwort.json()["neue_einwuerfe"] == 0

    def test_unbeantwortete_aus_der_liste_von_hier_fehlt_eine_antwort(
        self, client, unbeantwortete
    ):
        antwort = client.post(URL, headers={"X-User": "kim-1"})

        assert antwort.json()["unbeantwortete_aussagen"] == 2
        unbeantwortete.liste.assert_awaited_once_with(mit_themen=False)

    def test_fehler_bei_einwuerfen_und_aussagen_lassen_die_nutzung_stehen(
        self, client, einwuerfe, unbeantwortete, inhalte, caplog
    ):
        einwuerfe.count_von_anderen.side_effect = RuntimeError("kaputt")
        einwuerfe.count_ausformuliert_von_anderen.side_effect = RuntimeError("kaputt")
        unbeantwortete.liste.side_effect = RuntimeError("kaputt")
        inhalte.count_neue_von_anderen.side_effect = RuntimeError("kaputt")

        antwort = client.post(URL, headers={"X-User": "kim-1"})

        assert antwort.status_code == 200
        assert antwort.json() == {
            "nutzung_seit_letztem_besuch": 4,
            "neue_einwuerfe": 0,
            "unbeantwortete_aussagen": 0,
            "unbeantwortete_aussagen_mehr": False,
            "ausformulierte_einwuerfe": 0,
            "neue_beitraege": 0,
            # Obergrenze aus (Standard, #760): keine Zahl
            "antworten_auf_eigene_aussagen": None,
            # Wirkungs-Echo aus (Standard, #790): keine Summe
            "neu_oeffentlich_gepostet": None,
            "erster_besuch": False,
        }
        assert "kim-1" not in caplog.text

    def test_zeigt_hoechstens_so_viele_wie_offen_sind(self, client, gesehen):
        gesehen.neue_einwuerfe_seit_letztem_besuch.return_value = 9

        antwort = client.post(URL, headers={"X-User": "kim-1"})

        # Stand ueber alle Zustaende (12), offen bei anderen nur 5
        assert antwort.json()["neue_einwuerfe"] == 5

    def test_grenze_der_liste_heisst_mehr(self, client, unbeantwortete):
        unbeantwortete.liste.return_value = [object()] * LIMIT_STANDARD

        antwort = client.post(URL, headers={"X-User": "kim-1"})

        assert antwort.json()["unbeantwortete_aussagen"] == LIMIT_STANDARD
        assert antwort.json()["unbeantwortete_aussagen_mehr"] is True

    def test_nach_der_zeitgrenze_null_und_die_nutzung_steht(
        self, client, unbeantwortete, einwuerfe
    ):
        async def langsam(**_):
            await asyncio.sleep(1)
            return [object()]

        unbeantwortete.liste.side_effect = langsam
        einwuerfe.count_von_anderen.side_effect = lambda *a, **k: time.sleep(1) or 3

        # Mit offenem Client: Sonst schliesst die Testschleife nach der Anfrage und
        # wartet dabei auf den noch laufenden Thread, was der Server nicht tut.
        with client, patch.object(usage_module, "BESUCH_NEBENZAHLEN_TIMEOUT_S", 0.2):
            start = time.monotonic()
            antwort = client.post(URL, headers={"X-User": "kim-1"})
            dauer = time.monotonic() - start

        assert antwort.status_code == 200
        assert antwort.json()["nutzung_seit_letztem_besuch"] == 4
        assert antwort.json()["neue_einwuerfe"] == 0
        assert antwort.json()["unbeantwortete_aussagen"] == 0
        assert dauer < 0.9

    def test_zaehlt_parallel(self, client, dienst, unbeantwortete, einwuerfe):
        async def nutzung(_):
            await asyncio.sleep(0.4)
            return 4

        async def liste(**_):
            await asyncio.sleep(0.4)
            return [object()]

        dienst.nutzung_seit_letztem_besuch.side_effect = nutzung
        unbeantwortete.liste.side_effect = liste
        einwuerfe.count_von_anderen.side_effect = lambda *a, **k: time.sleep(0.4) or 3

        start = time.monotonic()
        antwort = client.post(URL, headers={"X-User": "kim-1"})
        dauer = time.monotonic() - start

        assert antwort.json()["unbeantwortete_aussagen"] == 1
        # Nacheinander waeren es ueber 1,2 s (Nutzung, Einwuerfe, Luecken)
        assert dauer < 1.0


class TestKachelnMitZeitraum:
    """
    Kacheln ohne Zaehlerstand (20.11.): eigene Einwuerfe, die andere ausformuliert
    haben, und neue Beitraege anderer, je in den letzten sieben Tagen. Dafuer wird
    nichts gespeichert.
    """

    def test_zaehlt_ab_sieben_tagen_vor_jetzt(self, client, einwuerfe, inhalte):
        vorher = datetime.now(timezone.utc)
        client.post(URL, headers={"X-User": "kim-1"})
        nachher = datetime.now(timezone.utc)

        person, seit = einwuerfe.count_ausformuliert_von_anderen.call_args.args
        assert person == "kim-1"
        assert vorher - timedelta(days=7) <= seit <= nachher - timedelta(days=7)
        person, seit_inhalte, typen = inhalte.count_neue_von_anderen.call_args.args
        assert person == "kim-1"
        assert seit_inhalte == seit
        # Die Typen von /content/recent, wie sie im Payload stehen
        assert set(typen) == {"commentary", "generic_text"}

    def test_speichert_dafuer_nichts(self, client, gesehen):
        client.post(URL, headers={"X-User": "kim-1"})

        # Der einzige Stand bleibt der der Einwuerfe (und der Nutzung im Dienst)
        assert [c[0] for c in gesehen.method_calls] == [
            "schon_besucht",
            "neue_einwuerfe_seit_letztem_besuch",
        ]

    def test_nie_negativ(self, client, einwuerfe, inhalte):
        einwuerfe.count_ausformuliert_von_anderen.return_value = -1
        inhalte.count_neue_von_anderen.return_value = -4

        antwort = client.post(URL, headers={"X-User": "kim-1"}).json()

        assert antwort["ausformulierte_einwuerfe"] == 0
        assert antwort["neue_beitraege"] == 0

    def test_suchindex_aus_kostet_nur_die_beitraege(self, client, caplog):
        with patch.object(
            usage_module, "get_content_repository", side_effect=RuntimeError("weg")
        ):
            antwort = client.post(URL, headers={"X-User": "kim-1"})

        assert antwort.status_code == 200
        assert antwort.json()["neue_beitraege"] == 0
        assert antwort.json()["ausformulierte_einwuerfe"] == 2
        assert antwort.json()["nutzung_seit_letztem_besuch"] == 4
        assert "kim-1" not in caplog.text


class TestWirkungsEcho:
    """#790: die Summe "oeffentlich gepostet" ueber die eigenen Beitraege, nur mit Schalter."""

    def test_mit_schalter_der_zuwachs_der_eigenen_beitraege(
        self, client, inhalte, gesehen, wirkung_ohne_datenbank
    ):
        eigene = [
            SimpleNamespace(id="11111111-1111-4111-8111-111111111111"),
            SimpleNamespace(id="22222222-2222-4222-8222-222222222222"),
        ]
        inhalte.getByAuthor = AsyncMock(return_value=eigene)
        wirkung_ohne_datenbank.je_beitrag.return_value = {
            "11111111-1111-4111-8111-111111111111": (3, 1),
            "22222222-2222-4222-8222-222222222222": (2, 0),
        }
        client.app.dependency_overrides[get_settings] = lambda: Settings(
            wirkungs_echo_aktiv=True
        )

        antwort = client.post(URL, headers={"X-User": "kim-1"})

        assert antwort.status_code == 200
        # Die Summe 5 geht als Stand an gesehene_nutzung, gezeigt wird der Zuwachs
        gesehen.neues_echo_seit_letztem_besuch.assert_called_once_with("kim-1", 5)
        assert antwort.json()["neu_oeffentlich_gepostet"] == 5
        assert inhalte.getByAuthor.await_args.kwargs["user_id"] == "kim-1"

    def test_ohne_neues_echo_keine_zahl(self, client, inhalte, gesehen):
        inhalte.getByAuthor = AsyncMock(return_value=[])
        gesehen.neues_echo_seit_letztem_besuch = Mock(return_value=0)
        client.app.dependency_overrides[get_settings] = lambda: Settings(
            wirkungs_echo_aktiv=True
        )

        antwort = client.post(URL, headers={"X-User": "kim-1"})

        assert antwort.json()["neu_oeffentlich_gepostet"] == 0

    def test_fehler_kostet_nur_die_summe(self, client, inhalte):
        inhalte.getByAuthor = AsyncMock(side_effect=RuntimeError("weg"))
        client.app.dependency_overrides[get_settings] = lambda: Settings(
            wirkungs_echo_aktiv=True
        )

        antwort = client.post(URL, headers={"X-User": "kim-1"})

        assert antwort.status_code == 200
        assert antwort.json()["neu_oeffentlich_gepostet"] == 0
        assert antwort.json()["nutzung_seit_letztem_besuch"] == 4
