"""
Antworten auf eigene Aussagen (#760): die Zahl im Besuch und die Liste "Meine Aussagen".
Ohne Datenbank und Suchindex; das Aussagen-Repository ist ersetzt. Schalter aus: keine
Abfrage, im Besuch null statt einer Zahl, Liste 404.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1 import usage as usage_module
from core.config import Settings
from dependencies import get_settings, get_unbeantwortete_aussagen_service
from domain.models.content_type import ContentType
from domain.models.statement import AntwortKurz
from repositories.einwurf_repository import get_einwurf_repository
from repositories.gesehene_nutzung_repository import get_gesehene_nutzung_repository
from services import antworten_hinweis
from services.schalter_service import SchalterService, schalter_service_setzen

pytestmark = pytest.mark.unit

ICH = {"X-User": "kim-1"}
JETZT = datetime.now(timezone.utc)
AUSSAGE = uuid.UUID("11111111-1111-4111-8111-111111111111")
ALT = uuid.UUID("22222222-2222-4222-8222-222222222222")
NEU_ANDERE = uuid.UUID("33333333-3333-4333-8333-333333333333")
NEU_ICH = uuid.UUID("44444444-4444-4444-8444-444444444444")
GESPERRT = uuid.UUID("55555555-5555-4555-8555-555555555555")
AUSSAGE2 = uuid.UUID("66666666-6666-4666-8666-666666666666")


def _vorschlag(id_, tage):
    return SimpleNamespace(
        id=id_,
        content_type=ContentType.COMMENTARY,
        created=JETZT - timedelta(days=tage),
    )


def _repository():
    repo = Mock()
    repo.get_by_author = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=AUSSAGE,
                text="Windräder töten Vögel",
                created=JETZT - timedelta(days=30),
                status="published",
                replysuggestions=[
                    _vorschlag(ALT, 20),
                    _vorschlag(NEU_ANDERE, 1),
                    _vorschlag(NEU_ICH, 1),
                    _vorschlag(GESPERRT, 1),
                ],
            ),
            # Dieselbe Antwort an einer zweiten Aussage zaehlt nur einmal
            SimpleNamespace(
                id=AUSSAGE2,
                text="Zweite Aussage",
                created=JETZT - timedelta(days=3),
                status="published",
                replysuggestions=[_vorschlag(NEU_ANDERE, 2)],
            ),
            SimpleNamespace(
                id=uuid.uuid4(),
                text="Gesperrte Aussage",
                created=JETZT,
                status="blocked",
                replysuggestions=[_vorschlag(uuid.uuid4(), 0)],
            ),
        ]
    )
    # GESPERRT fehlt: nicht sichtbar
    repo.antworten_mit_autor = AsyncMock(
        side_effect=lambda ids: {
            i: (
                AntwortKurz(
                    id=i, content_type=ContentType.COMMENTARY, titel=f"Titel {i}"
                ),
                a,
            )
            for i, a in {ALT: "bo-2", NEU_ANDERE: "bo-2", NEU_ICH: "kim-1"}.items()
            if i in ids
        }
    )
    return repo


@pytest.fixture
def werte(schalter_admin_alle_an):
    werte = {"antworten_hinweis": True}
    schalter_service_setzen(
        SchalterService(
            admin_werte_lesen=lambda: dict(werte),
            admin_wert_setzen=lambda n, a, w: werte.__setitem__(n, a),
        )
    )
    return werte


@pytest.fixture
def repo():
    return _repository()


@pytest.fixture
def client(repo):
    app = FastAPI()
    app.include_router(usage_module.router, prefix="/api/v1/usage")
    einwuerfe = Mock()
    einwuerfe.count_von_anderen = Mock(return_value=0)
    einwuerfe.count_ausformuliert_von_anderen = Mock(return_value=0)
    gesehen = Mock(neue_einwuerfe_seit_letztem_besuch=Mock(return_value=0))
    app.dependency_overrides[get_einwurf_repository] = lambda: einwuerfe
    app.dependency_overrides[get_gesehene_nutzung_repository] = lambda: gesehen
    app.dependency_overrides[get_unbeantwortete_aussagen_service] = lambda: Mock(
        liste=AsyncMock(return_value=[])
    )
    app.dependency_overrides[get_settings] = lambda: Settings()
    nutzung = Mock(nutzung_seit_letztem_besuch=AsyncMock(return_value=0))
    inhalte = Mock(count_neue_von_anderen=AsyncMock(return_value=0))
    with patch.object(
        usage_module, "get_usage_service", return_value=nutzung
    ), patch.object(
        usage_module, "get_content_repository", return_value=inhalte
    ), patch.object(
        usage_module.antworten_hinweis, "statement_repository", return_value=repo
    ):
        yield TestClient(app)


class TestBesuch:
    def test_an_zaehlt_neue_antworten_anderer(self, werte, client):
        antwort = client.post("/api/v1/usage/users/me/besuch", headers=ICH)

        assert antwort.status_code == 200
        assert antwort.json()["antworten_auf_eigene_aussagen"] == 1

    def test_fehler_kostet_nur_diese_zahl(self, werte, client, repo):
        repo.get_by_author.side_effect = RuntimeError("weg")
        antwort = client.post("/api/v1/usage/users/me/besuch", headers=ICH)

        assert antwort.status_code == 200
        assert antwort.json()["antworten_auf_eigene_aussagen"] == 0


class TestListe:
    def test_an_listet_eigene_aussagen_mit_antworten(self, werte, client):
        antwort = client.get("/api/v1/usage/users/me/aussagen", headers=ICH)

        assert antwort.status_code == 200
        daten = antwort.json()
        assert daten["zeitraum_tage"] == 7
        assert [a["text"] for a in daten["aussagen"]] == [
            "Windräder töten Vögel",
            "Zweite Aussage",
        ]
        antworten = daten["aussagen"][0]["antworten"]
        assert [(a["id"], a["neu"], a["von_dir"]) for a in antworten] == [
            (str(NEU_ANDERE), True, False),
            (str(NEU_ICH), False, True),
            (str(ALT), False, False),
        ]
        assert antworten[0]["titel"] == f"Titel {NEU_ANDERE}"
        # Keine Kennungen anderer Personen in der Antwort
        assert "bo-2" not in antwort.text

    def test_nur_angemeldet(self, werte, client):
        assert client.get("/api/v1/usage/users/me/aussagen").status_code == 401


def test_neue_antworten_ohne_titel_abruf():
    repo = _repository()
    aussagen = asyncio.run(
        antworten_hinweis.eigene_aussagen(
            "kim-1", repo, JETZT - timedelta(days=7), mit_titeln=False
        )
    )

    assert antworten_hinweis.neue_antworten(aussagen) == 1
    repo.antworten_mit_autor.assert_awaited_once()
    assert all(a.titel == "" for x in aussagen for a in x.antworten)
