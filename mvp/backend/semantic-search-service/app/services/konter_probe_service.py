"""
Konter-Probe (#786): ein Spruch, drei echte Antworten in verschiedenen Stilen. Wer
spielt, tippt, welche am besten wirkt, und sieht danach die echte Nutzung der drei.

Der Dienst liefert nur die Proben; der Tipp bleibt im Browser und kommt nie hier an.
Er speichert nichts und zaehlt nichts.

Welche Aussagen: kuratierte (sichtbar, keine unbeantwortete Suchanfrage;
StatementRepository.kuratierte) mit sichtbaren Kommentaren in mindestens drei
verschiedenen Stilen. Nur Kommentare fuer die Kommentarspalte: Gefragt wird, was bei
Mitlesenden wirkt, und "deutlich" (bissig) gibt es dort nicht. Je Stil zaehlt der
meistgenutzte Kommentar, von den Stilen die drei meistgenutzten. Damit das Ergebnis
etwas sagt, brauchen die drei zusammen MINDEST_NUTZUNG und die meistgenutzte muss
allein vorn liegen; bei Gleichstand gaebe es kein "laeuft am besten".

Nutzung ist dieselbe Zahl wie an der Karte ("N-mal genutzt",
UsageTrackingRepository.get_usage_counts_batch).

Den Vorrat haelt der Prozess ZWISCHENSPEICHER_SEKUNDEN lang: Er liest alle kuratierten
Aussagen und je Kandidat seine Kommentare. Eine eben gesperrte Antwort kann so bis
dahin in einer Probe stehen; die Karte selbst zeigt sie nur, solange sie sichtbar ist.
"""

import asyncio
import copy
import logging
import random
import time
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Protocol

from domain.models.statement import AntwortKurz, StatementDbEntry

logger = logging.getLogger(__name__)

ANTWORTEN_JE_PROBE = 3
"""So viele Antworten zeigt eine Probe: drei Stile zur Wahl."""

MINDEST_NUTZUNG = 6
"""So oft muessen die drei Antworten zusammen genutzt sein, damit der Tipp etwas sagt."""

PROBEN_HOECHSTENS = 10
"""So viele Proben liefert ein Abruf hoechstens; der Browser blaettert darin."""

KANDIDATEN_HOECHSTENS = 60
"""
So viele Aussagen werden hoechstens genauer geprueft (ihre Kommentare geladen), die
mit der meisten Nutzung zuerst. Begrenzt die Lesezugriffe je Aufbau des Vorrats.
"""

KOMMENTARE_JE_AUSSAGE_HOECHSTENS = 12
"""So viele Kommentare je Aussage werden hoechstens geladen, die meistgenutzten zuerst."""

ZWISCHENSPEICHER_SEKUNDEN = 300
_uhr = time.monotonic

KOMMENTAR = "commentary"
KOMMENTARSPALTE = "kommentarspalte"

BeitragLaden = Callable[[uuid.UUID], Awaitable[Optional[Dict[str, Any]]]]
"""Den sichtbaren Beitrag als Dict (oft_genutzt_service.sichtbaren_beitrag_laden)."""

Nutzung = Callable[[List[uuid.UUID]], Dict[str, int]]
"""Nutzung je Beitrag (ID als String), wie UsageTrackingRepository.get_usage_counts_batch."""


class _AussagenQuelle(Protocol):
    async def kuratierte(
        self, ids: Optional[Iterable[uuid.UUID]] = None
    ) -> List[StatementDbEntry]: ...

    async def sichtbare_antworten(self, ids: List[uuid.UUID]) -> List[AntwortKurz]: ...


@dataclass(frozen=True)
class KonterProbe:
    statement_id: uuid.UUID
    text: str
    # Die Beitraege als Dict wie von BeitragLaden, je mit usage_count; die
    # meistgenutzte zuerst. Die Reihenfolge fuer die Anzeige mischt proben().
    antworten: List[Dict[str, Any]]


# (gueltig bis, Vorrat)
_zwischenspeicher: List[Any] = []


def zwischenspeicher_leeren() -> None:
    """Fuer Tests und nach Aenderungen, die sofort sichtbar sein sollen."""
    _zwischenspeicher.clear()


def probe_aus_kommentaren(
    statement_id: uuid.UUID, text: str, kommentare: List[Dict[str, Any]]
) -> Optional[KonterProbe]:
    """
    Die Probe zu einer Aussage aus ihren sichtbaren Kommentaren (je mit usage_count),
    oder None, wenn die Aussage nicht passt: weniger als drei Stile, zu wenig Nutzung
    oder kein klarer Spitzenreiter.
    """
    je_stil: Dict[str, Dict[str, Any]] = {}
    for kommentar in kommentare:
        stil = kommentar.get("style")
        if not stil or (kommentar.get("zweck") or KOMMENTARSPALTE) != KOMMENTARSPALTE:
            continue
        stil = getattr(stil, "value", stil)
        bisher = je_stil.get(stil)
        if bisher is None or kommentar["usage_count"] > bisher["usage_count"]:
            je_stil[stil] = kommentar
    if len(je_stil) < ANTWORTEN_JE_PROBE:
        return None
    auswahl = sorted(je_stil.values(), key=lambda k: -k["usage_count"])[
        :ANTWORTEN_JE_PROBE
    ]
    if sum(k["usage_count"] for k in auswahl) < MINDEST_NUTZUNG:
        return None
    if auswahl[0]["usage_count"] == auswahl[1]["usage_count"]:
        return None
    return KonterProbe(statement_id=statement_id, text=text.strip(), antworten=auswahl)


class KonterProbeService:
    def __init__(
        self,
        aussagen: _AussagenQuelle,
        nutzung: Nutzung,
        beitrag_laden: BeitragLaden,
    ):
        self._aussagen = aussagen
        self._nutzung = nutzung
        self._beitrag_laden = beitrag_laden

    async def proben(
        self,
        hoechstens: int = PROBEN_HOECHSTENS,
        zufall: Optional[random.Random] = None,
    ) -> List[KonterProbe]:
        """
        Bis zu ``hoechstens`` Proben in zufaelliger Reihenfolge, die Antworten je Probe
        gemischt, damit die Reihenfolge den Spitzenreiter nicht verraet. Leer, wenn
        keine Aussage passt; dann zeigt die App keinen Einstieg.
        """
        zufall = zufall or random.Random()
        if not _zwischenspeicher or _zwischenspeicher[0] < _uhr():
            vorrat = await self._vorrat()
            _zwischenspeicher[:] = [_uhr() + ZWISCHENSPEICHER_SEKUNDEN, vorrat]
        vorrat: List[KonterProbe] = _zwischenspeicher[1]

        auswahl = zufall.sample(vorrat, min(hoechstens, len(vorrat)))
        proben = []
        for probe in auswahl:
            # Kopien: Der Aufrufer reichert die Dicts an, der Vorrat bleibt unberuehrt.
            antworten = [copy.deepcopy(a) for a in probe.antworten]
            zufall.shuffle(antworten)
            proben.append(
                KonterProbe(
                    statement_id=probe.statement_id,
                    text=probe.text,
                    antworten=antworten,
                )
            )
        return proben

    async def _vorrat(self) -> List[KonterProbe]:
        aussagen = await self._aussagen.kuratierte()
        antwort_ids = list(
            dict.fromkeys(v.id for a in aussagen for v in a.replysuggestions)
        )
        if not antwort_ids:
            return []
        kommentare = {
            a.id
            for a in await self._aussagen.sichtbare_antworten(antwort_ids)
            if getattr(a.content_type, "value", a.content_type) == KOMMENTAR
        }
        nutzung = (
            await asyncio.to_thread(self._nutzung, list(kommentare))
            if kommentare
            else {}
        )

        kandidaten = []
        for aussage in aussagen:
            eigene = list(
                dict.fromkeys(
                    v.id for v in aussage.replysuggestions if v.id in kommentare
                )
            )
            if len(eigene) < ANTWORTEN_JE_PROBE:
                continue
            eigene.sort(key=lambda i: -nutzung.get(str(i), 0))
            gesamt = sum(nutzung.get(str(i), 0) for i in eigene)
            if gesamt < MINDEST_NUTZUNG:
                continue
            kandidaten.append((gesamt, aussage, eigene))
        kandidaten.sort(key=lambda k: -k[0])

        vorrat = []
        for _, aussage, eigene in kandidaten[:KANDIDATEN_HOECHSTENS]:
            geladen = []
            for beitrag_id in eigene[:KOMMENTARE_JE_AUSSAGE_HOECHSTENS]:
                beitrag = await self._beitrag_laden(beitrag_id)
                if beitrag is None:
                    continue
                beitrag["usage_count"] = nutzung.get(str(beitrag_id), 0)
                geladen.append(beitrag)
            probe = probe_aus_kommentaren(aussage.id, aussage.text, geladen)
            if probe is not None:
                vorrat.append(probe)
        logger.debug(f"Konter-Probe: {len(vorrat)} passende Aussagen")
        return vorrat
