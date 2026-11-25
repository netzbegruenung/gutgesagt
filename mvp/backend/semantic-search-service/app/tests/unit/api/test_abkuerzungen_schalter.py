"""
Schalter "abkuerzungen" (App-Abkuerzungen im Manifest, #757): steht in GET
/api/v1/funktionen, ohne Admin-Wert aus, mit Admin-Wert und Obergrenze an, ohne
Obergrenze aus. Die Obergrenze ist von Haus aus an, weil nichts uebertragen wird.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.funktionen import router as funktionen_router
from core.config import Settings
from dependencies import get_settings
from services.schalter_service import SchalterService, schalter_service_setzen

pytestmark = pytest.mark.unit

URL = "/api/v1/funktionen"


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


def test_standard_aus(werte):
    antwort = _client().get(URL)

    assert antwort.status_code == 200
    assert antwort.json()["funktionen"]["abkuerzungen"] is False


def test_an_mit_admin_wert(werte):
    werte["abkuerzungen"] = True

    assert _client().get(URL).json()["funktionen"]["abkuerzungen"] is True


def test_obergrenze_aus_schlaegt_admin_wert(werte):
    werte["abkuerzungen"] = True

    antwort = _client(abkuerzungen_aktiv=False).get(URL)

    assert antwort.json()["funktionen"]["abkuerzungen"] is False


def test_obergrenze_standard_an():
    assert Settings().abkuerzungen_aktiv is True
