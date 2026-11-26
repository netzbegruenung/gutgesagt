"""
Was die Person widerrufen kann (api/v1/widerrufbar.py): immer 200, auch ohne
Schalter, nur gespeicherte Antworten ueber Nein bzw. aus.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.widerrufbar import router
from domain.spielgefuehl import AKTUELLER_WORTLAUT, Stufe
from repositories.abzeichen_sichtbarkeit_repository import Sichtbarkeit
from repositories.punkte_einwilligung_repository import PunkteEinwilligung
from repositories.rangliste_einwilligung_repository import RanglisteAntwort
from repositories.spielgefuehl_repository import SpielgefuehlAntwort

pytestmark = pytest.mark.unit

URL = "/api/v1/usage/users/me/widerrufbar"
KIM = {"X-User": "kim-1"}
AM = datetime(2026, 11, 26, tzinfo=timezone.utc)


@pytest.fixture
def abzeichen(monkeypatch):
    repository = MagicMock()
    repository.lesen.return_value = None
    monkeypatch.setattr(
        "repositories.abzeichen_sichtbarkeit_repository._repository", repository
    )
    return repository


def _client() -> TestClient:
    # Keine Settings-Abhaengigkeit: Die Antwort haengt an keinem Schalter.
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/usage")
    return TestClient(app)


def test_nichts_gespeichert_alles_null(abzeichen):
    antwort = _client().get(URL, headers=KIM)

    assert antwort.status_code == 200
    assert antwort.json() == {
        "spielgefuehl": None,
        "punkte": None,
        "rangliste": None,
        "abzeichen": None,
    }


def test_gespeicherte_ja_mit_wortlaut(
    abzeichen,
    spielgefuehl_ohne_datenbank,
    punkte_einwilligung_ohne_datenbank,
    rangliste_ohne_datenbank,
):
    spielgefuehl_ohne_datenbank.lesen.return_value = SpielgefuehlAntwort(
        Stufe.FUER_MICH, False, AKTUELLER_WORTLAUT, AM
    )
    punkte_einwilligung_ohne_datenbank.lesen.return_value = PunkteEinwilligung(
        True, "2026-11-13", AM
    )
    rangliste_ohne_datenbank.lesen.return_value = RanglisteAntwort(
        True, False, "rangliste-2026-11-20", AM
    )
    abzeichen.lesen.return_value = Sichtbarkeit(True, "2026-11-09", AM)

    daten = _client().get(URL, headers=KIM).json()

    assert daten == {
        "spielgefuehl": {
            "stufe": "fuer_mich",
            "titel": "Nur für mich",
            "wortlaut": AKTUELLER_WORTLAUT,
        },
        "punkte": {"wortlaut": "2026-11-13"},
        "rangliste": {"wortlaut": "rangliste-2026-11-20"},
        "abzeichen": {"wortlaut": "2026-11-09"},
    }


def test_nein_und_aus_zeigen_nichts(
    abzeichen,
    spielgefuehl_ohne_datenbank,
    punkte_einwilligung_ohne_datenbank,
    rangliste_ohne_datenbank,
):
    spielgefuehl_ohne_datenbank.lesen.return_value = SpielgefuehlAntwort(
        Stufe.AUS, False, AKTUELLER_WORTLAUT, AM
    )
    punkte_einwilligung_ohne_datenbank.lesen.return_value = PunkteEinwilligung(
        False, "2026-11-13", AM
    )
    rangliste_ohne_datenbank.lesen.return_value = RanglisteAntwort(
        False, False, "rangliste-2026-11-20", AM
    )
    abzeichen.lesen.return_value = Sichtbarkeit(False, "2026-11-09", AM)

    daten = _client().get(URL, headers=KIM).json()

    assert set(daten.values()) == {None}


def test_ja_zu_frueherem_wortlaut_bleibt_widerrufbar(
    abzeichen, spielgefuehl_ohne_datenbank
):
    spielgefuehl_ohne_datenbank.lesen.return_value = SpielgefuehlAntwort(
        Stufe.RANGLISTE, True, "spielgefuehl-1999", AM, "Kluge Eule 11"
    )

    daten = _client().get(URL, headers=KIM).json()

    assert daten["spielgefuehl"] == {
        "stufe": "rangliste",
        "titel": "In der Saison-Rangliste mitspielen",
        # Unbekannt: der aktuelle, zu dem "aus" angenommen wird
        "wortlaut": AKTUELLER_WORTLAUT,
    }


def test_ohne_anmeldung_401(abzeichen):
    assert _client().get(URL).status_code == 401


def test_lesefehler_500_ohne_details(abzeichen):
    abzeichen.lesen.side_effect = RuntimeError("geheim")

    antwort = TestClient(_client().app, raise_server_exceptions=False).get(
        URL, headers=KIM
    )

    assert antwort.status_code == 500
    assert "geheim" not in antwort.text
