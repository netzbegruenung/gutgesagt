"""
GET /api/v1/search/garten (#783): ohne Schalter leer mit aktiv false, ohne Abfrage, sonst je Thema Name,
Motiv und zwei Zahlen, fuer Besucher wie fuer Angemeldete, ohne Texte von Aussagen.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.garten import get_gartenansicht_service, router
from core.config import Settings
from dependencies import get_settings
from domain.themen import THEMEN
from services.gartenansicht_service import Beet
from services.schalter_service import SchalterService, schalter_service_setzen

pytestmark = pytest.mark.unit

URL = "/api/v1/search/garten"


class FalscherDienst:
    def __init__(self, fehler=None):
        self.gefragt = 0
        self.fehler = fehler

    async def beete(self):
        self.gefragt += 1
        if self.fehler:
            raise self.fehler
        return [
            Beet(t.schluessel, 3 if t.schluessel == "klima" else 0, 2 if i == 0 else 0)
            for i, t in enumerate(THEMEN)
        ]


@pytest.fixture
def werte():
    werte = {}
    schalter_service_setzen(
        SchalterService(
            admin_werte_lesen=lambda: dict(werte),
            admin_wert_setzen=lambda name, an, admin: werte.__setitem__(name, an),
        )
    )
    yield werte
    schalter_service_setzen(None)


def _client(dienst, obergrenze=True) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/search")
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[get_gartenansicht_service] = lambda: dienst
    return TestClient(app)


def test_besucher_sehen_je_thema_nur_zahlen(werte):
    werte["gartenansicht"] = True

    antwort = _client(FalscherDienst()).get(URL)

    assert antwort.status_code == 200
    beete = antwort.json()["beete"]
    assert len(beete) == len(THEMEN)
    erstes = beete[0]
    assert erstes["schluessel"] == THEMEN[0].schluessel
    assert erstes["name"] == THEMEN[0].name
    assert erstes["motiv"] == THEMEN[0].motiv
    assert erstes["ohne_antwort"] == 2
    assert set(erstes) == {"schluessel", "name", "motiv", "antworten", "ohne_antwort"}


def test_fehler_500_ohne_details(werte):
    werte["gartenansicht"] = True

    antwort = _client(FalscherDienst(RuntimeError("geheim"))).get(URL)

    assert antwort.status_code == 500
    assert "geheim" not in antwort.text
