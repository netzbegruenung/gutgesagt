"""
Themenvorschlaege (#401) ueber /themen/vorschlaege: nur fuer Angemeldete, nur ein
Vorschlag (nichts wird gespeichert), hoechstens drei bzw. zwei, und leer statt Fehler,
wenn der Vorschlag ausfaellt.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.statement import router as statement_router
from core.config import Settings
from dependencies import (
    get_aussage_themen_service,
    get_settings,
    get_themen_vorschlag_service,
)

URL = "/api/v1/statement/themen/vorschlaege"
ANGEMELDET = {"X-User": "person-1"}

app = FastAPI()
app.include_router(statement_router, prefix="/api/v1/statement")


@pytest.fixture
def vorschlag():
    service = MagicMock()
    service.vorschlagen = AsyncMock(return_value=["verkehr", "klima"])
    themen_service = MagicMock()
    app.dependency_overrides[get_themen_vorschlag_service] = lambda: service
    app.dependency_overrides[get_aussage_themen_service] = lambda: themen_service
    app.dependency_overrides[get_settings] = lambda: Settings(themen_vorschlaege=True)
    with patch(
        "api.v1.statement.themen_vorschlag_rate_limiter.is_rate_limited",
        AsyncMock(return_value=False),
    ):
        yield service, themen_service
    app.dependency_overrides.clear()


@pytest.mark.api
class TestThemenVorschlaege:
    def test_liefert_die_vorgeschlagenen_schluessel(self, vorschlag):
        service, _ = vorschlag

        resp = TestClient(app).post(
            URL, json={"text": "Das Tempolimit bringt nichts"}, headers=ANGEMELDET
        )

        assert resp.status_code == 200
        assert resp.json() == {"themen": ["verkehr", "klima"]}
        service.vorschlagen.assert_awaited_once_with("Das Tempolimit bringt nichts", 3)

    def test_beim_einwerfen_hoechstens_zwei(self, vorschlag):
        service, _ = vorschlag

        TestClient(app).post(
            URL, json={"text": "Text", "hoechstens": 2}, headers=ANGEMELDET
        )

        service.vorschlagen.assert_awaited_once_with("Text", 2)

    @pytest.mark.parametrize("hoechstens", [0, 4])
    def test_mehr_als_drei_oder_null_abgewiesen(self, vorschlag, hoechstens):
        resp = TestClient(app).post(
            URL, json={"text": "Text", "hoechstens": hoechstens}, headers=ANGEMELDET
        )

        assert resp.status_code == 422

    def test_zu_langer_text_abgewiesen(self, vorschlag):
        resp = TestClient(app).post(URL, json={"text": "x" * 5001}, headers=ANGEMELDET)

        assert resp.status_code == 422

    def test_nur_fuer_angemeldete(self, vorschlag):
        service, _ = vorschlag

        resp = TestClient(app).post(URL, json={"text": "Text"})

        assert resp.status_code == 401
        service.vorschlagen.assert_not_awaited()

    def test_speichert_nichts(self, vorschlag):
        _, themen_service = vorschlag

        TestClient(app).post(URL, json={"text": "Text"}, headers=ANGEMELDET)

        assert themen_service.method_calls == []

    def test_faellt_der_vorschlag_aus_leer_statt_fehler(self, vorschlag, caplog):
        service, _ = vorschlag
        service.vorschlagen = AsyncMock(side_effect=RuntimeError("geheimer Text"))

        resp = TestClient(app).post(
            URL, json={"text": "geheimer Text"}, headers=ANGEMELDET
        )

        assert resp.status_code == 200
        assert resp.json() == {"themen": []}
        assert "geheimer Text" not in caplog.text

    def test_standard_ist_aus(self):
        """Maintainer 22.11.2026: aus, bis es etwa 200 Zuordnungen von Hand gibt."""
        assert Settings().themen_vorschlaege is False

    def test_die_liste_sagt_ob_vorschlaege_an_sind(self, vorschlag):
        an = TestClient(app).get("/api/v1/statement/themen", headers=ANGEMELDET)
        app.dependency_overrides[get_settings] = lambda: Settings(
            themen_vorschlaege=False
        )
        aus = TestClient(app).get("/api/v1/statement/themen", headers=ANGEMELDET)

        assert an.json()["vorschlaege"] is True
        assert aus.json()["vorschlaege"] is False

    def test_abgeschaltet_leer_ohne_rechnen(self, vorschlag):
        service, _ = vorschlag
        app.dependency_overrides[get_settings] = lambda: Settings(
            themen_vorschlaege=False
        )

        resp = TestClient(app).post(URL, json={"text": "Text"}, headers=ANGEMELDET)

        assert resp.json() == {"themen": []}
        service.vorschlagen.assert_not_awaited()

    def test_rate_limit(self, vorschlag):
        with patch(
            "api.v1.statement.themen_vorschlag_rate_limiter.is_rate_limited",
            AsyncMock(return_value=True),
        ):
            resp = TestClient(app).post(URL, json={"text": "Text"}, headers=ANGEMELDET)

        assert resp.status_code == 429
