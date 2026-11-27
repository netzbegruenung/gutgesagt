"""
Die Frage nach der Sichtbarkeit der Meilenstein-Abzeichen (#351): nur mit beiden
Schaltern, nur fuer die angemeldete Person selbst. Antworten geht auch ohne
Art.-9-Einwilligung (ein Nein ist Zuruecknehmen; ein Ja zeigt dann nichts).
"""

import datetime
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.usage import router as usage_router
from core.config import Settings
from dependencies import get_settings
from domain.abzeichen_sichtbarkeit import UnbekannterWortlaut
from repositories.abzeichen_sichtbarkeit_repository import Sichtbarkeit
from services import abzeichen_service as abzeichen_modul

URL = "/api/v1/usage/users/me/abzeichen-sichtbarkeit"
KIM = {"X-User": "kim-1"}


@pytest.fixture
def dienst(monkeypatch, art9_einwilligung_ohne_datenbank):
    dienst = Mock()
    dienst.sichtbarkeit = Mock(return_value=None)
    dienst.antworten = AsyncMock()
    monkeypatch.setattr(abzeichen_modul, "_service", dienst)
    return dienst


def _client(an: bool = True, punkte: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(usage_router, prefix="/api/v1/usage")
    app.dependency_overrides[get_settings] = lambda: Settings(
        spielgefuehl_buehne_aktiv=punkte
    )
    return TestClient(app)


@pytest.mark.parametrize("an,punkte", [(False, True), (True, False)])
def test_ohne_beide_schalter_lesen_aus_ja_409(dienst, an, punkte):
    client = _client(an=an, punkte=punkte)

    # Lesen fragt die Seite automatisch: 200 mit aktiv false statt 404 (Gateway-fail2ban)
    antwort = client.get(URL, headers=KIM)
    assert antwort.status_code == 200
    assert antwort.json()["aktiv"] is False
    assert antwort.json()["gefragt"] is False
    dienst.sichtbarkeit.assert_not_called()
    assert (
        client.put(
            URL, json={"zeigen": True, "wortlaut": "2026-11-09"}, headers=KIM
        ).status_code
        == 409
    )
    dienst.antworten.assert_not_called()


@pytest.mark.parametrize("an,punkte", [(False, True), (True, False)])
def test_ohne_schalter_nein_immer_speicherbar(dienst, monkeypatch, an, punkte):
    """Widerruf so einfach wie die Einwilligung, sonst gaelte ein altes Ja weiter."""
    repository = MagicMock()
    monkeypatch.setattr(
        "repositories.abzeichen_sichtbarkeit_repository._repository", repository
    )

    antwort = _client(an=an, punkte=punkte).put(
        URL, json={"zeigen": False, "wortlaut": "2026-11-09"}, headers=KIM
    )

    assert antwort.status_code == 204
    repository.antworten.assert_called_once_with("kim-1", False, "2026-11-09")
    dienst.vergessen.assert_called_once_with("kim-1")
    dienst.antworten.assert_not_called()


def test_im_spielgefuehl_modell_nein_speicherbar(dienst, monkeypatch):
    repository = MagicMock()
    monkeypatch.setattr(
        "repositories.abzeichen_sichtbarkeit_repository._repository", repository
    )
    app = FastAPI()
    app.include_router(usage_router, prefix="/api/v1/usage")
    app.dependency_overrides[get_settings] = lambda: Settings(
        spielgefuehl_buehne_aktiv=True,
    )

    antwort = TestClient(app).put(
        URL, json={"zeigen": False, "wortlaut": "2026-11-09"}, headers=KIM
    )

    assert antwort.status_code == 204
    repository.antworten.assert_called_once_with("kim-1", False, "2026-11-09")
    dienst.antworten.assert_not_called()


def test_ohne_schalter_nein_unbekannter_wortlaut_422(dienst, monkeypatch):
    repository = MagicMock()
    monkeypatch.setattr(
        "repositories.abzeichen_sichtbarkeit_repository._repository", repository
    )

    antwort = _client(an=False).put(
        URL, json={"zeigen": False, "wortlaut": "x"}, headers=KIM
    )

    assert antwort.status_code == 422
    repository.antworten.assert_not_called()


def test_nur_angemeldet(dienst):
    client = _client()

    assert client.get(URL).status_code == 401
    assert client.get(URL, headers={"X-User": "anonymous"}).status_code == 401
