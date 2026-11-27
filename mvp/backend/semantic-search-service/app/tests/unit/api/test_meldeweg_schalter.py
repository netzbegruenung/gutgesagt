"""
Schalter "meldeweg_sichtbar" ("Melden" an jeder Beitragskarte und "Melden & Kontakt"
im Fuss): steht in GET /api/v1/funktionen, ohne Anmeldung lesbar und immer mit 200
(automatisch abgefragt, CODING_STANDARDS.md "Endpoints"). Obergrenze von Haus aus aus,
Gruppe Grundfunktionen, ohne Einschalt-Hinweis (Jura vorlaeufig ohne Bedingung).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.funktionen import router as funktionen_router
from core.config import Settings
from dependencies import get_settings
from services.schalter_service import (
    SCHALTER,
    SchalterService,
    oeffentliche_schalter,
    schalter_service_setzen,
)

pytestmark = pytest.mark.unit

URL = "/api/v1/funktionen"
NAME = "meldeweg_sichtbar"


@pytest.fixture
def werte():
    """Eigener Dienst ohne Eintraege: Admin-Werte gelten als aus."""
    werte = {}
    schalter_service_setzen(
        SchalterService(
            admin_werte_lesen=lambda: dict(werte),
            admin_wert_setzen=lambda name, an, admin: werte.__setitem__(name, an),
        )
    )
    yield werte
    schalter_service_setzen(None)


def _client(**obergrenzen) -> TestClient:
    app = FastAPI()
    app.include_router(funktionen_router, prefix=URL)
    app.dependency_overrides[get_settings] = lambda: Settings(**obergrenzen)
    return TestClient(app)


def test_obergrenze_von_haus_aus_aus(monkeypatch):
    monkeypatch.delenv("SEMANTIC_SEARCH_MELDEWEG_SICHTBAR_AKTIV", raising=False)

    assert Settings().meldeweg_sichtbar_aktiv is False


def test_obergrenze_ueber_umgebungsvariable(monkeypatch):
    monkeypatch.setenv("SEMANTIC_SEARCH_MELDEWEG_SICHTBAR_AKTIV", "true")

    assert Settings().meldeweg_sichtbar_aktiv is True


def test_registry_eintrag():
    art = SCHALTER[NAME]

    assert art.gruppe == "Grundfunktionen"
    assert art.umgebungsvariable == "SEMANTIC_SEARCH_MELDEWEG_SICHTBAR_AKTIV"
    assert art.einschalt_hinweis is None
    assert art.dsfa_hinweis is False
    assert NAME in oeffentliche_schalter()


def test_wartet_nicht_auf_recht():
    dienst = SchalterService(
        admin_werte_lesen=lambda: {}, admin_wert_setzen=lambda n, a, w: None
    )
    stand = {s.name: s for s in dienst.stand(Settings())}

    assert stand[NAME].dsfa_hinweis is None
    assert stand[NAME].wartet_auf_recht is False


def test_standard_aus_ohne_anmeldung_200(werte):
    antwort = _client().get(URL)

    assert antwort.status_code == 200
    assert antwort.json()["funktionen"][NAME] is False


def test_admin_wert_allein_schaltet_nicht_ein(werte):
    werte[NAME] = True

    assert _client().get(URL).json()["funktionen"][NAME] is False


def test_an_mit_obergrenze_und_admin_wert(werte):
    werte[NAME] = True

    antwort = _client(meldeweg_sichtbar_aktiv=True).get(URL)

    assert antwort.status_code == 200
    assert antwort.json()["funktionen"][NAME] is True
