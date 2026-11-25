"""
Schalter ``teamlink_vertrauenssatz``: der Vertrauenssatz auf der Begruessung eines
Teamlinks (Jura vorlaeufig 26.11., Punkt d). Eigene Obergrenze, von Haus aus aus,
oeffentlich (das Frontend blendet den Satz ueber GET /api/v1/funktionen ein), wirkt nur
mit ``teams``; die Admin-Seite zeigt die Jura-Bedingung fuers Einschalten.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.funktionen import router as funktionen_router
from core.config import Settings
from dependencies import get_settings
from services.schalter_service import (
    SCHALTER,
    TEAMS,
    ObergrenzeAus,
    SchalterService,
    oeffentliche_schalter,
    schalter_service_setzen,
)

pytestmark = pytest.mark.unit

NAME = "teamlink_vertrauenssatz"
OBERGRENZEN_AN = Settings(teams_aktiv=True, teamlink_vertrauenssatz_aktiv=True)


def _dienst(werte):
    # Ohne Cache: Die Tests aendern die Admin-Werte zwischen zwei Abrufen.
    return SchalterService(
        admin_werte_lesen=lambda: dict(werte),
        admin_wert_setzen=lambda name, an, admin: werte.__setitem__(name, an),
        cache_sekunden=0,
    )


def test_eigene_obergrenze_von_haus_aus_aus():
    art = SCHALTER[NAME]

    assert art.umgebungsvariable == "SEMANTIC_SEARCH_TEAMLINK_VERTRAUENSSATZ_AKTIV"
    assert art.feld == "teamlink_vertrauenssatz_aktiv"
    assert Settings.model_fields[art.feld].default is False
    with pytest.raises(ObergrenzeAus):
        _dienst({}).setzen(NAME, True, "admin-1", Settings(teams_aktiv=True))


def test_gruppe_teams_oeffentlich_und_jura_hinweis():
    art = SCHALTER[NAME]
    stand = {s.name: s for s in _dienst({}).stand(OBERGRENZEN_AN)}

    assert art.gruppe == TEAMS
    assert NAME in oeffentliche_schalter()
    assert stand[NAME].dsfa_hinweis == (
        "Vor dem Einschalten: Jura prüft teams.py (was Mitglieder voneinander sehen)."
    )
    assert stand[NAME].wartet_auf_recht is True


def test_ohne_admin_wert_aus_mit_admin_wert_an():
    assert _dienst({"teams": True}).wirksam(NAME, OBERGRENZEN_AN) is False
    assert _dienst({"teams": True, NAME: True}).wirksam(NAME, OBERGRENZEN_AN) is True


def test_nur_mit_teams():
    assert _dienst({"teams": False, NAME: True}).wirksam(NAME, OBERGRENZEN_AN) is False

    ohne_teams_obergrenze = Settings(teamlink_vertrauenssatz_aktiv=True)
    assert (
        _dienst({"teams": True, NAME: True}).wirksam(NAME, ohne_teams_obergrenze)
        is False
    )


@pytest.fixture
def werte():
    werte = {}
    schalter_service_setzen(_dienst(werte))
    yield werte
    schalter_service_setzen(None)


def _funktionen(settings: Settings) -> dict:
    app = FastAPI()
    app.include_router(funktionen_router, prefix="/api/v1/funktionen")
    app.dependency_overrides[get_settings] = lambda: settings
    antwort = TestClient(app).get("/api/v1/funktionen")
    assert antwort.status_code == 200
    return antwort.json()["funktionen"]


def test_funktionen_meldet_den_schalter_ohne_anmeldung(werte):
    """Aus heisst 200 mit false, nie 404 (#824): die Begruessung fragt beim Laden."""
    assert _funktionen(OBERGRENZEN_AN)[NAME] is False

    werte.update({"teams": True, NAME: True})
    assert _funktionen(OBERGRENZEN_AN)[NAME] is True
    assert _funktionen(Settings(teams_aktiv=True))[NAME] is False
