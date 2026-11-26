"""
GET /api/v1/funktionen (#756): der wirksame Wert der oeffentlichen Schalter, ohne
Anmeldung. Ohne Admin-Wert aus, mit Admin-Wert und Obergrenze an, ohne Obergrenze aus;
Schalter ohne ``oeffentlich`` stehen nicht darin. Die Tests setzen einen eigenen
oeffentlichen Schalter ein, der an der Obergrenze von "gepostet" haengt.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import services.schalter_service as schalter_modul
from api.v1.funktionen import router as funktionen_router
from core.config import Settings
from dependencies import get_settings
from services.schalter_service import (
    SchalterService,
    Schalterart,
    schalter_service_setzen,
)

pytestmark = pytest.mark.unit

URL = "/api/v1/funktionen"


@pytest.fixture
def werte(monkeypatch):
    """Eigener Dienst ohne Eintraege und ein oeffentlicher Schalter "beispiel"."""
    monkeypatch.setitem(
        schalter_modul.SCHALTER,
        "beispiel",
        Schalterart(
            name="beispiel",
            feld="gepostet_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_GEPOSTET_AKTIV",
            erklaerung="Nur im Test",
            oeffentlich=True,
        ),
    )
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


def test_ohne_admin_wert_aus_und_ohne_anmeldung_lesbar(werte):
    antwort = _client(gepostet_aktiv=True).get(URL)

    assert antwort.status_code == 200
    assert antwort.json()["funktionen"]["beispiel"] is False


def test_an_mit_admin_wert_und_obergrenze(werte):
    werte["beispiel"] = True

    antwort = _client(gepostet_aktiv=True).get(URL)

    assert antwort.json()["funktionen"]["beispiel"] is True


def test_obergrenze_aus_schlaegt_admin_wert(werte):
    werte["beispiel"] = True

    antwort = _client(gepostet_aktiv=False).get(URL)

    assert antwort.json()["funktionen"]["beispiel"] is False


def test_nur_oeffentliche_schalter(werte):
    werte.update(gepostet=True, herkunft_pruefen=True)

    funktionen = (
        _client(gepostet_aktiv=True, herkunft_pruefen_aktiv=True).get(URL).json()
    )

    assert "gepostet" not in funktionen["funktionen"]
    assert "herkunft_pruefen" not in funktionen["funktionen"]


def test_punkte_oeffentlich_fuer_die_datenschutzerklaerung(werte):
    """Jura 26.11.: der Vorbehalt „noch nicht eingeschaltet“ haengt am wirksamen Wert."""
    werte.update(punkte=True)

    funktionen = _client(punkte_aktiv=True).get(URL).json()

    assert funktionen["funktionen"]["punkte"] is True
