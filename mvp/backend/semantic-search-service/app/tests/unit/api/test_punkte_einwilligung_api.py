"""
Die Einwilligung "Punkte und Meilensteine" (#351): eine eigene, freiwillige
Einwilligung, nur angeboten mit eingeschalteten Punkten, nichts vorausgewaehlt,
Widerruf jederzeit und sofort wirksam.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.usage import router as usage_router
from core.config import Settings
from dependencies import get_settings
from domain.punkte_einwilligung import AKTUELLER_WORTLAUT, WORTLAUTE
from repositories.punkte_einwilligung_repository import PunkteEinwilligung

URL = "/api/v1/usage/users/me/punkte-einwilligung"
KIM = {"X-User": "kim-1"}


def _client(aktiv: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(usage_router, prefix="/api/v1/usage")
    app.dependency_overrides[get_settings] = lambda: Settings(
        spielgefuehl_buehne_aktiv=aktiv
    )
    return TestClient(app)


@pytest.fixture
def repo(punkte_einwilligung_ohne_datenbank):
    return punkte_einwilligung_ohne_datenbank


def test_ohne_punkte_wird_nichts_angeboten(repo):
    # Lesen fragen die Seiten automatisch: 200 mit aktiv false statt 404 (Gateway-fail2ban)
    antwort = _client(aktiv=False).get(URL, headers=KIM)
    assert antwort.status_code == 200
    assert antwort.json()["aktiv"] is False
    assert antwort.json()["eingewilligt"] is False
    repo.lesen.assert_not_called()
    antwort = _client(aktiv=False).put(
        URL, headers=KIM, json={"eingewilligt": True, "wortlaut": AKTUELLER_WORTLAUT}
    )
    # 409 statt 404: kein Treffer fuer den Gateway-fail2ban
    assert antwort.status_code == 409
    repo.antworten.assert_not_called()


def test_nur_angemeldet():
    assert _client().get(URL).status_code == 401


def test_die_frage_nutzt_den_wortlaut_2026_11_13():
    # #788, Jura 25.11.: Die Frage im Moment des Gewinns bringt keinen neuen Wortlaut.
    assert AKTUELLER_WORTLAUT == "2026-11-13"


def test_widerruf_speichert_und_nimmt_das_abzeichen_sofort(repo, monkeypatch):
    abzeichen = MagicMock()
    monkeypatch.setattr("api.v1.usage.get_abzeichen_service", lambda: abzeichen)

    antwort = _client().put(
        URL, headers=KIM, json={"eingewilligt": False, "wortlaut": AKTUELLER_WORTLAUT}
    )

    assert antwort.status_code == 204
    repo.antworten.assert_called_once_with("kim-1", False, AKTUELLER_WORTLAUT)
    abzeichen.vergessen.assert_called_once_with("kim-1")


def test_widerruf_haelt_ja_zur_rangliste_als_nein_fest(repo, rangliste_ohne_datenbank):
    """Sonst stuende die Person nach neuer Punkte-Einwilligung ungefragt in der Rangliste (#793)."""
    from domain.rangliste import AKTUELLER_WORTLAUT as RANGLISTE_WORTLAUT
    from repositories.rangliste_einwilligung_repository import RanglisteAntwort

    rangliste_ohne_datenbank.lesen.return_value = RanglisteAntwort(
        True, True, RANGLISTE_WORTLAUT, datetime(2026, 12, 1, tzinfo=timezone.utc)
    )

    antwort = _client().put(
        URL, headers=KIM, json={"eingewilligt": False, "wortlaut": AKTUELLER_WORTLAUT}
    )

    assert antwort.status_code == 204
    rangliste_ohne_datenbank.antworten.assert_called_once_with(
        "kim-1", False, False, RANGLISTE_WORTLAUT
    )


def test_einwilligen_laesst_die_rangliste_unberuehrt(repo, rangliste_ohne_datenbank):
    _client().put(
        URL, headers=KIM, json={"eingewilligt": True, "wortlaut": AKTUELLER_WORTLAUT}
    )

    rangliste_ohne_datenbank.antworten.assert_not_called()


def test_im_spielgefuehl_modell_nicht_mehr_angeboten(repo):
    """Mit Schalter spielgefuehl_buehne fragt die App nach dem Spielgefuehl, nicht hier."""
    app = FastAPI()
    app.include_router(usage_router, prefix="/api/v1/usage")
    app.dependency_overrides[get_settings] = lambda: Settings(
        spielgefuehl_buehne_aktiv=True,
    )
    client = TestClient(app)
    repo.lesen.return_value = PunkteEinwilligung(
        True, AKTUELLER_WORTLAUT, datetime(2026, 11, 13, tzinfo=timezone.utc)
    )

    antwort = client.get(URL, headers=KIM)

    assert antwort.json()["aktiv"] is False
    assert antwort.json()["eingewilligt"] is False
    repo.lesen.assert_not_called()
    antwort = client.put(
        URL, headers=KIM, json={"eingewilligt": True, "wortlaut": AKTUELLER_WORTLAUT}
    )
    assert antwort.status_code == 409
    repo.antworten.assert_not_called()


def _client_mit(**schalter) -> TestClient:
    app = FastAPI()
    app.include_router(usage_router, prefix="/api/v1/usage")
    app.dependency_overrides[get_settings] = lambda: Settings(**schalter)
    return TestClient(app)


@pytest.mark.parametrize(
    "schalter",
    [
        {},
        {"spielgefuehl_buehne_aktiv": True},
    ],
)
def test_widerruf_immer_speicherbar(repo, monkeypatch, schalter):
    """Widerruf so einfach wie die Einwilligung (Art. 7 Abs. 3 DSGVO), auch nach Not-Aus."""
    abzeichen = MagicMock()
    monkeypatch.setattr("api.v1.usage.get_abzeichen_service", lambda: abzeichen)

    antwort = _client_mit(**schalter).put(
        URL, headers=KIM, json={"eingewilligt": False, "wortlaut": AKTUELLER_WORTLAUT}
    )

    assert antwort.status_code == 204
    repo.antworten.assert_called_once_with("kim-1", False, AKTUELLER_WORTLAUT)
    abzeichen.vergessen.assert_called_once_with("kim-1")


def test_widerruf_unbekannter_wortlaut_422(repo):
    antwort = _client(aktiv=False).put(
        URL, headers=KIM, json={"eingewilligt": False, "wortlaut": "1999-01-01"}
    )

    assert antwort.status_code == 422
    repo.antworten.assert_not_called()


def test_widerruf_loescht_die_muster_hinweise(repo, muster_hinweise_ohne_datenbank):
    antwort = _client().put(
        URL, headers=KIM, json={"eingewilligt": False, "wortlaut": AKTUELLER_WORTLAUT}
    )

    assert antwort.status_code == 204
    muster_hinweise_ohne_datenbank.vergessen.assert_called_once_with("kim-1")


def test_einwilligen_laesst_die_muster_hinweise(repo, muster_hinweise_ohne_datenbank):
    _client().put(
        URL, headers=KIM, json={"eingewilligt": True, "wortlaut": AKTUELLER_WORTLAUT}
    )

    muster_hinweise_ohne_datenbank.vergessen.assert_not_called()


def test_widerruf_gilt_auch_wenn_das_loeschen_der_hinweise_scheitert(
    repo, muster_hinweise_ohne_datenbank
):
    muster_hinweise_ohne_datenbank.vergessen.side_effect = RuntimeError("weg")

    antwort = _client().put(
        URL, headers=KIM, json={"eingewilligt": False, "wortlaut": AKTUELLER_WORTLAUT}
    )

    assert antwort.status_code == 204
    repo.antworten.assert_called_once_with("kim-1", False, AKTUELLER_WORTLAUT)


def test_widerruf_stuft_das_spielgefuehl_auf_aus(repo, spielgefuehl_ohne_datenbank):
    """Sonst gaelte eine Stufe ueber aus nach dem Einschalten des neuen Modells weiter."""
    from domain.spielgefuehl import AKTUELLER_WORTLAUT as SPIELGEFUEHL_WORTLAUT
    from domain.spielgefuehl import Stufe
    from repositories.spielgefuehl_repository import SpielgefuehlAntwort

    spielgefuehl_ohne_datenbank.lesen.return_value = SpielgefuehlAntwort(
        Stufe.FUER_MICH,
        False,
        SPIELGEFUEHL_WORTLAUT,
        datetime(2026, 12, 1, tzinfo=timezone.utc),
    )

    antwort = _client().put(
        URL, headers=KIM, json={"eingewilligt": False, "wortlaut": AKTUELLER_WORTLAUT}
    )

    assert antwort.status_code == 204
    spielgefuehl_ohne_datenbank.antworten.assert_called_once_with(
        "kim-1", Stufe.AUS, False, SPIELGEFUEHL_WORTLAUT
    )
