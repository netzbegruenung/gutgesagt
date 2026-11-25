"""
Gartenansicht fuer alle (#783): je Thema die Zahl der Antworten und die Zahl der
Aussagen ohne Antwort. Nur Zahlen, fuer Besucher wie fuer Angemeldete; den Wortlaut der
Aussagen ohne Antwort sehen wie bisher nur Angemeldete in "Hier fehlt eine Antwort".

Antworten je Thema: die sichtbaren Antworten (Kommentare, Hintergrundinfos) an den
kuratierten Aussagen mit diesem Thema, dieselbe Grundlage wie "Alles zum Thema"
(services/themen_aussagen_service.py). Eine Antwort an zwei Aussagen desselben Themas
zaehlt einmal, an Aussagen zweier Themen in beiden.

Ohne Antwort je Thema: die Aussagen, die "Hier fehlt eine Antwort" zeigt
(services/unbeantwortete_aussagen_service.py), mit derselben Sichtbarkeit, auch der
Vormoderation: Eine Suchanfrage einer einzelnen Person oder eine nicht freigegebene
zaehlt nicht mit.

Personenbezug hat keine der Zahlen. Weil die Ansicht ohne Anmeldung offen ist, haelt
der Prozess das Ergebnis ZWISCHENSPEICHER_SEKUNDEN lang, statt bei jedem Aufruf
PostgreSQL und Qdrant ueber alle Aussagen zu fragen.
"""

import asyncio
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Protocol, Set, Tuple

from domain.models.statement import AntwortKurz, StatementDbEntry
from domain.themen import THEMEN

SCHALTER = "gartenansicht"

ZWISCHENSPEICHER_SEKUNDEN = 120

# Obergrenze fuer die Liste "Hier fehlt eine Antwort", wenn nur gezaehlt wird.
OHNE_ANTWORT_HOECHSTENS = 100000

_uhr = time.monotonic
_zwischenspeicher: Optional[Tuple[float, List["Beet"]]] = None


def zwischenspeicher_leeren() -> None:
    """Fuer Tests und nach Aenderungen, die sofort sichtbar sein sollen."""
    global _zwischenspeicher
    _zwischenspeicher = None


class _ThemenRepository(Protocol):
    def alle(self) -> Dict[uuid.UUID, List[str]]: ...


class _AussagenQuelle(Protocol):
    async def kuratierte(
        self, ids: Optional[Iterable[uuid.UUID]] = None
    ) -> List[StatementDbEntry]: ...

    async def sichtbare_antworten(self, ids: List[uuid.UUID]) -> List[AntwortKurz]: ...


class _OhneAntwortQuelle(Protocol):
    async def liste(self, limit: int = ..., thema=None, mit_themen: bool = ...): ...


@dataclass(frozen=True)
class Beet:
    schluessel: str
    antworten: int
    ohne_antwort: int


class GartenansichtService:
    def __init__(
        self,
        themen: _ThemenRepository,
        aussagen: _AussagenQuelle,
        ohne_antwort: _OhneAntwortQuelle,
    ):
        self._themen = themen
        self._aussagen = aussagen
        self._ohne_antwort = ohne_antwort

    async def beete(self) -> List[Beet]:
        """Je Thema der festen Liste ein Beet, in ihrer Reihenfolge (zwischengespeichert)."""
        global _zwischenspeicher
        if _zwischenspeicher is None or _zwischenspeicher[0] < _uhr():
            beete = await self._berechnen()
            _zwischenspeicher = (_uhr() + ZWISCHENSPEICHER_SEKUNDEN, beete)
        return _zwischenspeicher[1]

    async def _berechnen(self) -> List[Beet]:
        # Die PostgreSQL-Abfrage ist synchron: im Thread, nicht in der Schleife.
        zuordnung = await asyncio.to_thread(self._themen.alle)
        antworten = await self._antworten_je_thema(zuordnung)
        ohne = await self._ohne_antwort_je_thema()
        return [
            Beet(
                schluessel=t.schluessel,
                antworten=len(antworten.get(t.schluessel, ())),
                ohne_antwort=ohne.get(t.schluessel, 0),
            )
            for t in THEMEN
        ]

    async def _antworten_je_thema(
        self, zuordnung: Dict[uuid.UUID, List[str]]
    ) -> Dict[str, Set[uuid.UUID]]:
        if not zuordnung:
            return {}
        aussagen = await self._aussagen.kuratierte(list(zuordnung))
        antwort_ids = list(
            dict.fromkeys(v.id for a in aussagen for v in a.replysuggestions)
        )
        sichtbar = (
            {a.id for a in await self._aussagen.sichtbare_antworten(antwort_ids)}
            if antwort_ids
            else set()
        )
        je_thema: Dict[str, Set[uuid.UUID]] = defaultdict(set)
        for aussage in aussagen:
            ids = {v.id for v in aussage.replysuggestions if v.id in sichtbar}
            for thema in zuordnung.get(aussage.id, ()):
                je_thema[thema] |= ids
        return je_thema

    async def _ohne_antwort_je_thema(self) -> Dict[str, int]:
        liste = await self._ohne_antwort.liste(
            limit=OHNE_ANTWORT_HOECHSTENS, mit_themen=True
        )
        je_thema: Dict[str, int] = defaultdict(int)
        for aussage in liste:
            for thema in aussage.themen:
                je_thema[thema] += 1
        return je_thema
