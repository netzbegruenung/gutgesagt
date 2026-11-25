"""
Einwilligungen im Moment des Gewinns (#788): Der Endpunkt liefert nur mit dem
Schalter einwilligung_im_gewinn etwas, nur fuer Angemeldete, und liest nur.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import repositories.einwilligungs_moment_repository as modul
from api.v1.einwilligungs_moment import router
from core.config import Settings
from dependencies import get_settings
from repositories.einwilligungs_moment_repository import EinwilligungsMoment

URL = "/api/v1/usage/users/me/einwilligungs-moment"
KIM = {"X-User": "kim-1"}


@pytest.fixture
def repo(monkeypatch):
    repository = MagicMock()
    monkeypatch.setattr(modul, "_repository", repository)
    return repository


def _client(aktiv: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/usage")
    app.dependency_overrides[get_settings] = lambda: Settings(
        einwilligung_im_gewinn_aktiv=aktiv
    )
    return TestClient(app)


def test_ohne_schalter_404_und_keine_abfrage(repo):
    antwort = _client(aktiv=False).get(URL, headers=KIM)

    assert antwort.status_code == 404
    repo.lesen.assert_not_called()


def test_nur_angemeldet(repo):
    assert _client().get(URL).status_code == 401
    assert _client().get(URL, headers={"X-User": "anonymous"}).status_code == 401
    repo.lesen.assert_not_called()


def test_liefert_die_fakten_der_person(repo):
    seit = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    repo.lesen.return_value = EinwilligungsMoment(
        abgestimmt=True, beantwortet=2, konto_seit=seit
    )

    antwort = _client().get(URL, headers=KIM)

    assert antwort.status_code == 200
    assert antwort.json() == {
        "abgestimmt": True,
        "beantwortet": 2,
        "konto_seit": "2026-11-20T09:00:00Z",
    }
    repo.lesen.assert_called_once_with("kim-1")


def test_ohne_konto_beginn(repo):
    repo.lesen.return_value = EinwilligungsMoment(False, 0, None)

    assert _client().get(URL, headers=KIM).json()["konto_seit"] is None


def test_lesefehler_500(repo):
    repo.lesen.side_effect = RuntimeError("weg")

    assert _client().get(URL, headers=KIM).status_code == 500
