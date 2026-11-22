"""
Die meistgenutzten Aussagen eines Themas, fuer "Alles zum Thema" auf der Ergebnisseite
(#754): Passt eine kurze Sucheingabe zu einem Thema (domain/themen_abgleich.py), stehen
oben dessen Aussagen, auch wenn die Suche selbst nichts findet.

Welche Aussagen: die mit dem Thema, die kuratiert sind (sichtbar, keine unbeantwortete
Suchanfrage; StatementRepository.kuratierte) und mindestens eine sichtbare Antwort haben.
Ein Klick auf eine Aussage sucht nach ihr; ohne Antwort fuehrte er ins Leere.

Meistgenutzt heisst: die Summe der Nutzung ihrer sichtbaren Antworten, dieselbe Zahl, die
an den Karten steht ("N× genutzt"). Bei Gleichstand die mit mehr Antworten, dann nach Text.

Die Rangliste je Thema haelt der Prozess ZWISCHENSPEICHER_SEKUNDEN lang: Jede kurze Suche
zum selben Thema fragte sonst PostgreSQL und Qdrant ueber alle Aussagen des Themas ab.
Eine eben gesperrte Aussage kann so bis dahin im Kasten stehen; ein Klick sucht nach ihr,
und die Suche zeigt sie nicht.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Protocol, Tuple

from domain.models.statement import AntwortKurz, StatementDbEntry
from domain.themen import NACH_SCHLUESSEL

IM_KASTEN = 5
"""So viele Aussagen zeigt der Kasten "Alles zum Thema" hoechstens."""

ALLE_HOECHSTENS = 50
"""So viele Aussagen liefert "Alle Aussagen zum Thema" hoechstens."""

ZWISCHENSPEICHER_SEKUNDEN = 120
_uhr = time.monotonic

# Thema -> (gueltig bis, Rangliste bis ALLE_HOECHSTENS, Zahl aller).
_zwischenspeicher: Dict[str, Tuple[float, List["AussageDesThemas"], int]] = {}


def zwischenspeicher_leeren() -> None:
    """Fuer Tests und nach Aenderungen, die sofort sichtbar sein sollen."""
    _zwischenspeicher.clear()


class _ThemenRepository(Protocol):
    def aussagen_mit_thema(self, thema: str) -> List[uuid.UUID]: ...


class _AussagenQuelle(Protocol):
    async def kuratierte(
        self, ids: Optional[Iterable[uuid.UUID]] = None
    ) -> List[StatementDbEntry]: ...

    async def sichtbare_antworten(self, ids: List[uuid.UUID]) -> List[AntwortKurz]: ...


Nutzung = Callable[[List[uuid.UUID]], Dict[str, int]]
"""Nutzung je Beitrag (ID als String), wie UsageTrackingRepository.get_usage_counts_batch."""


@dataclass(frozen=True)
class AussageDesThemas:
    statement_id: uuid.UUID
    text: str
    antworten: int
    nutzung: int


class ThemenAussagenService:
    def __init__(
        self,
        themen: _ThemenRepository,
        aussagen: _AussagenQuelle,
        nutzung: Nutzung,
    ):
        self._themen = themen
        self._aussagen = aussagen
        self._nutzung = nutzung

    async def meistgenutzte(
        self, thema: str, hoechstens: int = IM_KASTEN
    ) -> Tuple[List[AussageDesThemas], int]:
        """
        Die meistgenutzten Aussagen des Themas, hoechstens ``hoechstens`` (und nie
        mehr als ALLE_HOECHSTENS), und wie viele es insgesamt gibt. Unbekanntes
        Thema: keine.
        """
        if thema not in NACH_SCHLUESSEL:
            return [], 0
        eintrag = _zwischenspeicher.get(thema)
        if eintrag is None or eintrag[0] < _uhr():
            rangliste, anzahl = await self._rangliste(thema)
            eintrag = (_uhr() + ZWISCHENSPEICHER_SEKUNDEN, rangliste, anzahl)
            _zwischenspeicher[thema] = eintrag
        _, rangliste, anzahl = eintrag
        return rangliste[:hoechstens], anzahl

    async def _rangliste(self, thema: str) -> Tuple[List[AussageDesThemas], int]:
        # Die beiden PostgreSQL-Abfragen sind synchron: im Thread, nicht in der Schleife.
        ids = await asyncio.to_thread(self._themen.aussagen_mit_thema, thema)
        if not ids:
            return [], 0
        aussagen = await self._aussagen.kuratierte(ids)
        antwort_ids = list(
            dict.fromkeys(v.id for a in aussagen for v in a.replysuggestions)
        )
        sichtbar = {a.id for a in await self._aussagen.sichtbare_antworten(antwort_ids)}
        nutzung = (
            await asyncio.to_thread(self._nutzung, list(sichtbar)) if sichtbar else {}
        )

        ergebnis = []
        for aussage in aussagen:
            antworten = list(
                dict.fromkeys(
                    v.id for v in aussage.replysuggestions if v.id in sichtbar
                )
            )
            if not antworten:
                continue
            ergebnis.append(
                AussageDesThemas(
                    statement_id=aussage.id,
                    text=aussage.text.strip(),
                    antworten=len(antworten),
                    nutzung=sum(nutzung.get(str(i), 0) for i in antworten),
                )
            )
        ergebnis.sort(key=lambda a: (-a.nutzung, -a.antworten, a.text.casefold()))
        return ergebnis[:ALLE_HOECHSTENS], len(ergebnis)
