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
from repositories.team_repository import OeffentlichAntwort

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


@pytest.fixture(autouse=True)
def team(monkeypatch):
    # Ohne Datenbank: die Antwort "Team öffentlich am Namen zeigen"
    repository = MagicMock()
    repository.oeffentlich_lesen.return_value = None
    monkeypatch.setattr("repositories.team_repository._repository", repository)
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
        "team_oeffentlich": None,
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
        True, False, "rangliste-2026-11-25", AM
    )
    abzeichen.lesen.return_value = Sichtbarkeit(True, "2026-11-09-b", AM)

    daten = _client().get(URL, headers=KIM).json()

    assert daten == {
        "spielgefuehl": {
            "stufe": "fuer_mich",
            "titel": "Nur für mich",
            "wortlaut": AKTUELLER_WORTLAUT,
        },
        "punkte": {"wortlaut": "2026-11-13"},
        "rangliste": {"wortlaut": "rangliste-2026-11-25"},
        "abzeichen": {"wortlaut": "2026-11-09-b"},
        "team_oeffentlich": None,
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
        False, False, "rangliste-2026-11-25", AM
    )
    abzeichen.lesen.return_value = Sichtbarkeit(False, "2026-11-09-b", AM)

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


def test_unbekannte_wortlaute_werden_durch_den_aktuellen_ersetzt(
    abzeichen, punkte_einwilligung_ohne_datenbank, rangliste_ohne_datenbank
):
    """Sonst scheiterte der Widerruf mit 422 (etwa nach einem Zurueckrollen)."""
    from domain import abzeichen_sichtbarkeit, punkte_einwilligung, rangliste

    punkte_einwilligung_ohne_datenbank.lesen.return_value = PunkteEinwilligung(
        True, "punkte-2099", AM
    )
    rangliste_ohne_datenbank.lesen.return_value = RanglisteAntwort(
        True, False, "rangliste-2099", AM
    )
    abzeichen.lesen.return_value = Sichtbarkeit(True, "abzeichen-2099", AM)

    daten = _client().get(URL, headers=KIM).json()

    assert daten["punkte"] == {"wortlaut": punkte_einwilligung.AKTUELLER_WORTLAUT}
    assert daten["rangliste"] == {"wortlaut": rangliste.AKTUELLER_WORTLAUT}
    assert daten["abzeichen"] == {"wortlaut": abzeichen_sichtbarkeit.AKTUELLER_WORTLAUT}


def test_team_oeffentlich_widerrufbar_auch_ohne_schalter(abzeichen, team):
    """
    Die Antwort haengt an keinem Schalter: auch bei teams_oeffentlich aus widerrufbar.
    Der Testclient hat keine Settings, der Endpunkt kann also keinen Schalter fragen.
    """
    from domain.teams import OEFFENTLICH_KENNUNG

    team.oeffentlich_lesen.return_value = OeffentlichAntwort(
        True, OEFFENTLICH_KENNUNG, AM
    )

    daten = _client().get(URL, headers=KIM).json()

    team.oeffentlich_lesen.assert_called_once_with("kim-1")
    assert daten["team_oeffentlich"] == {"wortlaut": OEFFENTLICH_KENNUNG}


def test_team_oeffentlich_zurueckgenommen_zeigt_nichts(abzeichen, team):
    team.oeffentlich_lesen.return_value = OeffentlichAntwort(
        False, "team-oeffentlich-2026-11-25", AM
    )

    assert _client().get(URL, headers=KIM).json()["team_oeffentlich"] is None


def test_team_oeffentlich_unbekannter_wortlaut_wird_ersetzt(abzeichen, team):
    """Sonst scheiterte PUT /teams/oeffentlich mit 422."""
    from domain.teams import OEFFENTLICH_KENNUNG

    team.oeffentlich_lesen.return_value = OeffentlichAntwort(True, "team-2099", AM)

    daten = _client().get(URL, headers=KIM).json()

    assert daten["team_oeffentlich"] == {"wortlaut": OEFFENTLICH_KENNUNG}
