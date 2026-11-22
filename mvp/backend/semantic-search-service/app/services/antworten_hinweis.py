"""
Antworten auf eigene Aussagen (#760, todo "Kachel Antworten auf deine eigenen Aussagen",
Folge #741): Wer Aussagen anlegt (``POST /statement/vorab``), sieht auf der Startseite,
wie viele Antworten anderer in den letzten Tagen dazugekommen sind, und unter
Meine Beitraege die eigenen Aussagen mit ihren Antworten.

Nichts Neues wird gespeichert. Alles kommt aus dem, was ohnehin an der Aussage steht:
ihre Antwortvorschlaege (``replysuggestions``) mit dem Zeitpunkt der Verknuepfung, und
an jeder Antwort Typ, Status und Autorin. "Neu" heisst wie bei den anderen 7-Tage-Kacheln
von "Seit deinem letzten Besuch": in den letzten ``BESUCH_ZEITRAUM_TAGE`` Tagen
verknuepft und nicht von der Person selbst (api/v1/usage.py). Ein Stand je Konto ("seit
dem letzten Besuch gesehen") braeuchte eine neue Spalte; darauf verzichtet die Kachel
und nennt stattdessen den Zeitraum.

Nur mit dem Schalter ``antworten_hinweis`` (services/schalter_service.py). Ist er aus,
fragt der Besuch nichts davon ab und die Liste antwortet 404.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

from domain.models.content_status import AUSGEBLENDET_WERTE
from domain.models.content_type import ContentType
from repositories.interfaces.statement_repository import IStatementRepository

SCHALTER = "antworten_hinweis"
# So viele eigene Aussagen liest der Hinweis hoechstens, die neuesten zuerst
AUSSAGEN_HOECHSTENS = 200


@dataclass(frozen=True)
class AntwortAufAussage:
    id: uuid.UUID
    content_type: ContentType
    titel: str
    verknuepft_am: datetime
    von_dir: bool
    neu: bool


@dataclass(frozen=True)
class EigeneAussage:
    id: uuid.UUID
    text: str
    created: datetime
    antworten: List[AntwortAufAussage] = field(default_factory=list)


def _utc(zeit: datetime) -> datetime:
    return zeit if zeit.tzinfo else zeit.replace(tzinfo=timezone.utc)


async def eigene_aussagen(
    person: str,
    repository: IStatementRepository,
    seit: datetime,
    mit_titeln: bool = True,
) -> List[EigeneAussage]:
    """
    Die sichtbaren eigenen Aussagen der Person, neueste zuerst, je mit ihren sichtbaren
    Antworten (neueste Verknuepfung zuerst). ``mit_titeln=False`` spart den Abruf der
    Titel, wenn nur gezaehlt wird (Besuch).
    """
    aussagen = await repository.get_by_author(
        person, limit=AUSSAGEN_HOECHSTENS, offset=0
    )
    aussagen = [
        a
        for a in aussagen
        if getattr(a.status, "value", a.status) not in AUSGEBLENDET_WERTE
    ]
    verknuepft = {
        vorschlag.id: _utc(vorschlag.created)
        for aussage in aussagen
        for vorschlag in aussage.replysuggestions
    }
    autoren = await repository.antwort_autoren(list(verknuepft))
    titel = {}
    typen = {}
    if mit_titeln and autoren:
        for kurz in await repository.sichtbare_antworten(list(autoren)):
            titel[kurz.id] = kurz.titel
            typen[kurz.id] = kurz.content_type
    seit = _utc(seit)
    ergebnis: List[EigeneAussage] = []
    for aussage in aussagen:
        antworten = []
        for vorschlag in aussage.replysuggestions:
            if vorschlag.id not in autoren:
                continue
            von_dir = autoren[vorschlag.id] == person
            am = _utc(vorschlag.created)
            antworten.append(
                AntwortAufAussage(
                    id=vorschlag.id,
                    content_type=typen.get(vorschlag.id, vorschlag.content_type),
                    titel=titel.get(vorschlag.id, ""),
                    verknuepft_am=am,
                    von_dir=von_dir,
                    neu=not von_dir and am >= seit,
                )
            )
        antworten.sort(key=lambda a: a.verknuepft_am, reverse=True)
        ergebnis.append(
            EigeneAussage(
                id=aussage.id,
                text=aussage.text,
                created=_utc(aussage.created),
                antworten=antworten,
            )
        )
    return ergebnis


def neue_antworten(aussagen: List[EigeneAussage]) -> int:
    """Wie viele Antworten anderer neu sind; eine Antwort auf zwei Aussagen zaehlt einmal."""
    return len({a.id for aussage in aussagen for a in aussage.antworten if a.neu})


def statement_repository(settings) -> IStatementRepository:
    """Das Aussagen-Repository; entsteht erst beim Aufruf (ein Ausfall kostet nur das)."""
    from repositories.implementations.qdrant.qdrant_repository_factory import (
        QdrantRepositoryFactory,
    )

    return QdrantRepositoryFactory().create_statement_repository(settings)
