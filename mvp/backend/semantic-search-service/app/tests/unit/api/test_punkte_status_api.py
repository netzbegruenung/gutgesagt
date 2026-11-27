"""
Der Schalter der Punkte, ohne Anmeldung lesbar (UX-Review B20): Das Frontend fragt
hier, statt punkte, meilensteine und abzeichen-sichtbarkeit auf ein 404 laufen zu lassen.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.usage import router as usage_router
from core.config import Settings
from dependencies import get_settings

URL = "/api/v1/usage/punkte/status"


def _client(punkte: bool, abzeichen: bool) -> TestClient:
    app = FastAPI()
    app.include_router(usage_router, prefix="/api/v1/usage")
    app.dependency_overrides[get_settings] = lambda: Settings(
        spielgefuehl_buehne_aktiv=punkte
    )
    return TestClient(app)


@pytest.mark.parametrize(
    "punkte, abzeichen, erwartet",
    [
        (
            False,
            False,
            {"aktiv": False, "abzeichen_sichtbar": False, "spielgefuehl_buehne": False},
        ),
        # Paket Spielgefuehl (Schalter-Umbau 27.11.): Punkte und Spielgefuehl zusammen,
        # Abzeichen am Namen nie
        (
            True,
            True,
            {"aktiv": True, "abzeichen_sichtbar": False, "spielgefuehl_buehne": True},
        ),
    ],
)
def test_status_folgt_den_schaltern(punkte, abzeichen, erwartet):
    antwort = _client(punkte, abzeichen).get(URL)

    assert antwort.status_code == 200
    assert antwort.json() == erwartet


def test_status_ohne_anmeldung_und_als_besucher_lesbar():
    client = _client(True, False)

    assert client.get(URL).status_code == 200
    assert client.get(URL, headers={"X-User": "anonymous"}).status_code == 200


def test_spielgefuehl_modell_keine_abzeichen_am_namen():
    app = FastAPI()
    app.include_router(usage_router, prefix="/api/v1/usage")
    app.dependency_overrides[get_settings] = lambda: Settings(
        spielgefuehl_buehne_aktiv=True,
    )
    client = TestClient(app)

    assert client.get(URL).json() == {
        "aktiv": True,
        "abzeichen_sichtbar": False,
        "spielgefuehl_buehne": True,
    }
    # Die Frage nach der Sichtbarkeit gibt es im neuen Modell nicht: lesen aus, Ja 409.
    sichtbarkeit = "/api/v1/usage/users/me/abzeichen-sichtbarkeit"
    assert (
        client.get(sichtbarkeit, headers={"X-User": "kim-1"}).json()["aktiv"] is False
    )
    antwort = client.put(
        sichtbarkeit,
        headers={"X-User": "kim-1"},
        json={"zeigen": True, "wortlaut": "2026-11-09"},
    )
    assert antwort.status_code == 409


def test_spielgefuehl_ohne_punkte_aus():
    """Ohne Punkte gibt es die Spielgefuehl-Frage nicht: der Status meldet das Modell
    aus (services/schalter_service.py, Gamification-Check 26.11., Befund 7)."""
    app = FastAPI()
    app.include_router(usage_router, prefix="/api/v1/usage")
    app.dependency_overrides[get_settings] = lambda: Settings(
        spielgefuehl_buehne_aktiv=False,
    )

    assert TestClient(app).get(URL).json() == {
        "aktiv": False,
        "abzeichen_sichtbar": False,
        "spielgefuehl_buehne": False,
    }
