"""
Konter-Probe (#786) gegen echtes Qdrant: Eine Aussage mit drei sichtbaren Kommentaren
in verschiedenen Stilen ergibt eine Probe, Stil und Zweck kommen aus dem gespeicherten
Kommentar. Die Nutzung (PostgreSQL) steht als Dict daneben; Schwellen und Gleichstand
pruefen die Unit-Tests des Service.
"""

import uuid

import pytest

from domain.models.commentary import Commentary, Stil, Zweck
from domain.models.content_origin import ContentOrigin
from domain.models.content_status import ContentStatus
from domain.models.content_type import ContentType
from domain.models.statement import Statement
from services.content.commentary_service import CommentaryService
from services.content.reference_service import ReferenceService
from services.content.statement_service import StatementService
from services.konter_probe_service import KonterProbeService, zwischenspeicher_leeren
from services.oft_genutzt_service import sichtbaren_beitrag_laden
from tests.integration.conftest import requires_qdrant

pytestmark = [pytest.mark.integration, requires_qdrant, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def leerer_zwischenspeicher():
    zwischenspeicher_leeren()
    yield
    zwischenspeicher_leeren()


async def _kommentar(service, stil, zweck=Zweck.KOMMENTARSPALTE) -> uuid.UUID:
    _, kommentar_id, _ = await service.add_commentary(
        Commentary(
            text=f"Die Pumpe rechnet sich, Stil {stil.value}. {uuid.uuid4()}",
            title=f"Antwort {stil.value}",
            references=[],
            style=stil,
            zweck=zweck,
        ),
        author="tester",
        status=ContentStatus.VISIBLE,
        origin=ContentOrigin.MANUALLY_CREATED,
    )
    return kommentar_id


async def test_aussage_mit_drei_stilen_ergibt_probe(
    integration_settings, real_repository_factory
):
    kommentare = CommentaryService(integration_settings, real_repository_factory)
    aussagen = StatementService(
        integration_settings, repository_factory=real_repository_factory
    )
    _, aussage_id, _ = await aussagen.add_statement(
        Statement(
            text=f"Wärmepumpen lohnen sich nie {uuid.uuid4()}", replysuggestions=[]
        ),
        "person-1",
        ContentStatus.VISIBLE,
        ContentOrigin.MANUALLY_CREATED,
    )
    sachlich = await _kommentar(kommentare, Stil.SACHLICH)
    humorvoll = await _kommentar(kommentare, Stil.HUMORVOLL)
    persoenlich = await _kommentar(kommentare, Stil.PERSOENLICH)
    # Fuer Gleichgesinnte: viel genutzt, zaehlt aber nicht.
    bissig = await _kommentar(kommentare, Stil.BISSIG, zweck=Zweck.EIGENE_LEUTE)
    for beitrag_id in (sachlich, humorvoll, persoenlich, bissig):
        await aussagen.beitrag_als_antwort_verknuepfen(
            beitrag_id, ContentType.COMMENTARY, 1.0, "tester", statement_id=aussage_id
        )
    nutzung = {sachlich: 3, humorvoll: 8, persoenlich: 1, bissig: 50}

    service = KonterProbeService(
        aussagen,
        lambda ids: {str(i): nutzung.get(i, 0) for i in ids},
        sichtbaren_beitrag_laden(
            integration_settings,
            real_repository_factory.create_content_repository(integration_settings),
            real_repository_factory,
            ReferenceService(integration_settings, real_repository_factory),
        ),
        lambda ids: {str(i): nutzung.get(i, 0) for i in ids},
    )
    proben = await service.proben(hoechstens=1000)

    [probe] = [p for p in proben if p.statement_id == aussage_id]
    assert {
        (str(a["id"]), a["result_type"], a["usage_count"]) for a in probe.antworten
    } == {
        (str(sachlich), "commentary", 3),
        (str(humorvoll), "commentary", 8),
        (str(persoenlich), "commentary", 1),
    }

    # Nach dem Aufbau des Vorrats gesperrt: Der naechste Abruf liefert die Probe
    # nicht mehr, obwohl der Vorrat zwischengespeichert ist.
    await real_repository_factory.create_content_repository(
        integration_settings
    ).update_status(humorvoll, ContentStatus.BLOCKED)
    proben = await service.proben(hoechstens=1000)
    assert aussage_id not in {p.statement_id for p in proben}
