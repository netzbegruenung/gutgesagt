"""
Zugriffsschutz und Caching der Metrics-Endpunkte.

Die MVP-Endpunkte und die Bilanz (#467) liefern Betriebskennzahlen (taegliche aktive Nutzer,
Suchvolumen, Vote-Verhaeltnisse) und waren ohne jede Auth-Dependency erreichbar.
/getMetrics bleibt bewusst oeffentlich -- es liefert nur Bestandszaehler und das
BFF fuehrt es als anonym erlaubt -- bekommt dafuer aber einen
TTL-Cache, weil es sonst unbegrenzt oft vier Qdrant-Counts ausloesen kann.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1 import metrics as metrics_module
from api.v1.metrics import router as metrics_router
from dependencies import (
    get_commentary_service,
    get_reference_service,
    get_settings,
    get_statement_service,
)

ADMIN_ONLY_PATHS = [
    "/api/v1/metrics/mvp-dashboard",
    "/api/v1/metrics/daily-active-users",
    "/api/v1/metrics/searches-per-user",
    "/api/v1/metrics/content-created",
    "/api/v1/metrics/usage-trend",
    "/api/v1/metrics/helpful-rate",
    "/api/v1/metrics/bilanz",
    "/api/v1/metrics/gepostet",
]


@pytest.fixture(autouse=True)
def zuwachs_schalter():
    """Schalter bestandszahl_zuwachs ohne Datenbank; von Haus aus aus, Tests setzen ihn."""
    with patch.object(
        metrics_module, "schalter_wirksam", return_value=False
    ) as schalter:
        yield schalter


@pytest.fixture
def client():
    """App nur mit dem Metrics-Router; die Content-Services sind gemockt."""
    app = FastAPI()
    app.include_router(metrics_router, prefix="/api/v1/metrics")

    statement_service = Mock()
    statement_service.count_curated = AsyncMock(return_value=11)
    # 15 Aussagen, davon 4 unbeantwortete Suchanfragen (Vormoderation).
    statement_service.count = AsyncMock(return_value=15)
    commentary_service = Mock()
    commentary_service.count = AsyncMock(return_value=22)
    reference_service = Mock()
    reference_service.count = AsyncMock(return_value=33)

    app.dependency_overrides[get_statement_service] = lambda: statement_service
    app.dependency_overrides[get_commentary_service] = lambda: commentary_service
    app.dependency_overrides[get_reference_service] = lambda: reference_service
    app.dependency_overrides[get_settings] = lambda: Mock()

    metrics_module._metrics_cache = None
    yield TestClient(app)
    metrics_module._metrics_cache = None


class TestAdminOnlyEndpoints:
    """Die Kennzahlen fuer Admins verlangen X-User plus X-Is-Admin."""

    @pytest.mark.parametrize("path", ADMIN_ONLY_PATHS)
    def test_anonymous_is_unauthorized(self, client, path):
        assert client.get(path).status_code == 401

    @pytest.mark.parametrize("path", ADMIN_ONLY_PATHS)
    def test_anonymous_user_header_is_unauthorized(self, client, path):
        response = client.get(path, headers={"X-User": "anonymous"})
        assert response.status_code == 401

    @pytest.mark.parametrize("path", ADMIN_ONLY_PATHS)
    def test_authenticated_non_admin_is_forbidden(self, client, path):
        response = client.get(path, headers={"X-User": "normalo"})
        assert response.status_code == 403

    @pytest.mark.parametrize("path", ADMIN_ONLY_PATHS)
    def test_forged_admin_header_alone_is_unauthorized(self, client, path):
        """
        X-Is-Admin ohne X-User reicht nicht. Beide Header werden am BFF gestrippt
        und aus den Claims neu gesetzt (IdentityHeaderTransform); hier ist nur
        festgehalten, dass die Dependency sich nicht allein auf das Flag verlaesst.
        """
        response = client.get(path, headers={"X-Is-Admin": "true"})
        assert response.status_code == 401


class TestGetMetricsStaysPublic:
    """
    /getMetrics muss ohne Anmeldung erreichbar bleiben: das BFF fuehrt es als
    anonym erlaubt (EndpointPolicy).
    """

    def test_anonymous_access_succeeds(self, client):
        with patch.object(metrics_module, "QdrantRepositoryFactory") as factory:
            repository = Mock()
            repository.count = AsyncMock(return_value=44)
            factory.return_value.create_content_repository.return_value = repository

            response = client.get("/api/v1/metrics/getMetrics")

        assert response.status_code == 200
        body = response.json()
        # 44 Eintraege ohne die 4 unbeantworteten Suchanfragen.
        assert body["content_count"] == 40
        assert body["statement_count"] == 11
        assert body["commentary_count"] == 22
        assert body["reference_count"] == 33

    def test_response_contains_only_computed_counts(self, client):
        """
        Kein Feld ist eine Konstante: die frueheren *_last_week-Felder,
        requested_commentary_count und active_users_count standen fest auf 0
        und sind entfallen.
        """
        with patch.object(metrics_module, "QdrantRepositoryFactory") as factory:
            repository = Mock()
            repository.count = AsyncMock(return_value=44)
            factory.return_value.create_content_repository.return_value = repository

            body = client.get("/api/v1/metrics/getMetrics").json()

        assert set(body) == {
            "content_count",
            "statement_count",
            "commentary_count",
            "reference_count",
            "zuwachs",
        }
        # Schalter bestandszahl_zuwachs aus: kein Zuwachs
        assert body["zuwachs"] is None


class TestGetMetricsCache:
    """Der TTL-Cache haelt die Qdrant-Last unabhaengig von der Aufrufzahl."""

    def test_repeated_calls_query_qdrant_once(self, client):
        with patch.object(metrics_module, "QdrantRepositoryFactory") as factory:
            repository = Mock()
            repository.count = AsyncMock(return_value=99)
            factory.return_value.create_content_repository.return_value = repository

            for _ in range(20):
                assert client.get("/api/v1/metrics/getMetrics").status_code == 200

            # Ohne Cache waeren es 20 Zaehlungen gewesen.
            assert repository.count.await_count == 1

    def test_expired_cache_is_refreshed(self, client):
        with patch.object(metrics_module, "QdrantRepositoryFactory") as factory:
            repository = Mock()
            repository.count = AsyncMock(return_value=99)
            factory.return_value.create_content_repository.return_value = repository

            assert client.get("/api/v1/metrics/getMetrics").status_code == 200

            # Zeitstempel kuenstlich altern lassen, statt 60 Sekunden zu warten.
            timestamp, payload = metrics_module._metrics_cache
            metrics_module._metrics_cache = (
                timestamp - metrics_module._METRICS_CACHE_TTL_SECONDS - 1,
                payload,
            )

            assert client.get("/api/v1/metrics/getMetrics").status_code == 200
            assert repository.count.await_count == 2

    def test_cached_response_matches_fresh_response(self, client):
        first = client.get("/api/v1/metrics/getMetrics").json()
        second = client.get("/api/v1/metrics/getMetrics").json()

        assert first == second


class TestGetMetricsCacheConcurrency:
    """
    Laeuft der Cache ab, waehrend viele Requests gleichzeitig anliegen, darf nur
    einer zaehlen -- sonst erzeugt genau der Moment die Spitze, die der Cache
    verhindern soll.
    """

    @pytest.mark.asyncio
    async def test_concurrent_requests_count_once(self):
        metrics_module._metrics_cache = None

        statement_service = Mock()
        statement_service.count_curated = AsyncMock(return_value=1)
        statement_service.count = AsyncMock(return_value=1)
        commentary_service = Mock()
        commentary_service.count = AsyncMock(return_value=2)
        reference_service = Mock()
        reference_service.count = AsyncMock(return_value=3)

        repository = Mock()

        async def slow_count():
            await asyncio.sleep(0.05)
            return 7

        repository.count = AsyncMock(side_effect=slow_count)

        with patch.object(metrics_module, "QdrantRepositoryFactory") as factory:
            factory.return_value.create_content_repository.return_value = repository

            results = await asyncio.gather(
                *[
                    metrics_module.get_metrics(
                        statement_service=statement_service,
                        commentary_service=commentary_service,
                        reference_service=reference_service,
                        settings=Mock(),
                    )
                    for _ in range(10)
                ]
            )

        assert repository.count.await_count == 1
        assert all(r.content_count == 7 for r in results)

        metrics_module._metrics_cache = None


def test_content_count_nie_negativ(client):
    """Faellt der Zaehler aller Eintraege aus (0), wird content_count nicht negativ."""
    with patch.object(metrics_module, "QdrantRepositoryFactory") as factory:
        repository = Mock()
        repository.count = AsyncMock(return_value=0)
        factory.return_value.create_content_repository.return_value = repository
        metrics_module._metrics_cache = None

        response = client.get("/api/v1/metrics/getMetrics")

    assert response.status_code == 200
    assert response.json()["content_count"] == 0


class TestGetMetricsZuwachs:
    """
    Zuwachs zur Bestandszahl (domain/bestandszahl.py): nur mit Schalter, genaue Zahl ab 3,
    darunter nur der Tag ohne Uhrzeit; ein Fehler laesst nur den Zuwachs weg.
    """

    def _abruf(self, client, angelegt_seit):
        with patch.object(metrics_module, "QdrantRepositoryFactory") as factory:
            repository = Mock()
            repository.count = AsyncMock(return_value=44)
            repository.angelegt_seit = angelegt_seit
            factory.return_value.create_content_repository.return_value = repository
            response = client.get("/api/v1/metrics/getMetrics")
        assert response.status_code == 200
        return response.json()

    def test_ab_drei_die_genaue_zahl(self, client, zuwachs_schalter):
        zuwachs_schalter.return_value = True
        angelegt_seit = AsyncMock(return_value=(12, []))

        body = self._abruf(client, angelegt_seit)

        assert body["zuwachs"] == {"neu_7_tage": 12, "zuletzt_ergaenzt": None}
        seit, typen, bis = angelegt_seit.await_args.args
        assert typen == ("commentary",)
        # Zeitpunkte nur fuer weniger als drei
        assert bis == 2
        assert zuwachs_schalter.call_args.args[0] == "bestandszahl_zuwachs"

    def test_unter_drei_nur_der_tag_in_deutscher_zeit(self, client, zuwachs_schalter):
        from datetime import datetime, timezone

        zuwachs_schalter.return_value = True
        # 23:30 UTC am 24.11. ist in Deutschland schon der 25.11.
        spaet = datetime(2026, 11, 24, 23, 30, tzinfo=timezone.utc)
        frueh = datetime(2026, 11, 22, 8, 0, tzinfo=timezone.utc)

        body = self._abruf(client, AsyncMock(return_value=(2, [frueh, spaet])))

        assert body["zuwachs"] == {"neu_7_tage": None, "zuletzt_ergaenzt": "2026-11-25"}

    def test_nichts_neu_kein_tag(self, client, zuwachs_schalter):
        zuwachs_schalter.return_value = True

        body = self._abruf(client, AsyncMock(return_value=(0, [])))

        assert body["zuwachs"] == {"neu_7_tage": None, "zuletzt_ergaenzt": None}

    def test_schalter_aus_fragt_nicht(self, client, zuwachs_schalter):
        angelegt_seit = AsyncMock(return_value=(12, []))

        body = self._abruf(client, angelegt_seit)

        assert body["zuwachs"] is None
        angelegt_seit.assert_not_awaited()

    def test_fehler_laesst_nur_den_zuwachs_weg(self, client, zuwachs_schalter):
        zuwachs_schalter.return_value = True

        body = self._abruf(client, AsyncMock(side_effect=RuntimeError("kaputt")))

        assert body["zuwachs"] is None
        assert body["commentary_count"] == 22
