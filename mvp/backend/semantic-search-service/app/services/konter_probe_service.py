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

Fuer diese Auswahl zaehlt die entdoppelte Nutzung (je Person, Beitrag und Tag einmal,
#352; UsageTrackingRepository.get_nutzung_entdoppelt_batch): Eine einzelne Person soll
weder eine Probe noch einen Spitzenreiter herstellen. Angezeigt wird die Zahl der Karte
("N-mal genutzt", get_usage_counts_batch), frisch bei jedem Abruf. Weil der Browser den
Spitzenreiter an dieser Zahl abliest, entfaellt eine Probe, wenn dort nicht dieselbe
Antwort allein vorn liegt.

Den Vorrat haelt der Prozess ZWISCHENSPEICHER_SEKUNDEN lang, und zwar nur als IDs: je
Aussage die drei ausgewaehlten Antworten. Aufgebaut wird er unter einer Sperre, damit
nach dem Ablauf nur eine Anfrage alle kuratierten Aussagen und je Kandidat seine
Kommentare liest. Texte haelt er nicht: Jeder Abruf laedt Aussage und Antworten der
gezogenen Proben neu, und nur solange sie sichtbar sind. Ist eine gesperrt oder
geloescht, entfaellt die Probe sofort.
"""

import asyncio
import logging
import random
import time
import uuid
from dataclasses import dataclass
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Protocol,
    Tuple,
)

from domain.models.statement import AntwortKurz, StatementDbEntry

logger = logging.getLogger(__name__)

ANTWORTEN_JE_PROBE = 3
"""So viele Antworten zeigt eine Probe: drei Stile zur Wahl."""

MINDEST_NUTZUNG = 6
"""
So oft muessen die drei Antworten zusammen genutzt sein (entdoppelt), damit der Tipp
etwas sagt.
"""

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
"""
Nutzung je Beitrag (ID als String), wie UsageTrackingRepository.get_usage_counts_batch
(Anzeige) oder get_nutzung_entdoppelt_batch (Auswahl).
"""


class _AussagenQuelle(Protocol):
    async def kuratierte(
        self, ids: Optional[Iterable[uuid.UUID]] = None
    ) -> List[StatementDbEntry]: ...

    async def sichtbare_antworten(self, ids: List[uuid.UUID]) -> List[AntwortKurz]: ...


@dataclass(frozen=True)
class KonterProbe:
    statement_id: uuid.UUID
    text: str
    # Die Beitraege als Dict wie von BeitragLaden, je mit usage_count. Aus
    # probe_aus_kommentaren die meistgenutzte zuerst; proben() liefert sie gemischt.
    antworten: List[Dict[str, Any]]


@dataclass(frozen=True)
class _ProbeIds:
    """Eine Probe im Vorrat: nur IDs, keine Texte."""

    statement_id: uuid.UUID
    # Die drei Antworten, die nach entdoppelter Nutzung vorderste zuerst.
    antwort_ids: Tuple[uuid.UUID, ...]


# (gueltig bis, Vorrat als Liste von _ProbeIds)
_zwischenspeicher: List[Any] = []
# Ohne Sperre baute nach dem Ablauf jede gleichzeitige Anfrage den Vorrat neu auf
# (wie _metrics_cache_lock in api/v1/metrics.py).
_zwischenspeicher_sperre = asyncio.Lock()


def zwischenspeicher_leeren() -> None:
    """Fuer Tests und nach Aenderungen, die sofort in die Auswahl sollen."""
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
        nutzung_entdoppelt: Nutzung,
    ):
        """
        ``nutzung`` ist die angezeigte Zahl der Karte, ``nutzung_entdoppelt`` die fuer
        Auswahl und Spitzenreiter.
        """
        self._aussagen = aussagen
        self._nutzung = nutzung
        self._beitrag_laden = beitrag_laden
        self._nutzung_entdoppelt = nutzung_entdoppelt

    async def proben(
        self,
        hoechstens: int = PROBEN_HOECHSTENS,
        zufall: Optional[random.Random] = None,
    ) -> List[KonterProbe]:
        """
        Bis zu ``hoechstens`` Proben in zufaelliger Reihenfolge, die Antworten je Probe
        gemischt, damit die Reihenfolge den Spitzenreiter nicht verraet. Leer, wenn
        keine Aussage passt; dann zeigt die App keinen Einstieg.

        Aussage und Antworten jeder Probe werden bei jedem Abruf neu und nur sichtbar
        geladen; faellt eine weg, rueckt die naechste Probe aus dem Vorrat nach.
        """
        zufall = zufall or random.Random()
        vorrat: List[_ProbeIds] = await self._vorrat_zwischengespeichert()
        if not vorrat or hoechstens <= 0:
            return []

        reihenfolge = zufall.sample(vorrat, len(vorrat))
        proben: List[KonterProbe] = []
        while reihenfolge and len(proben) < hoechstens:
            stapel = reihenfolge[: hoechstens - len(proben)]
            reihenfolge = reihenfolge[len(stapel) :]
            proben.extend(await self._frisch(stapel, zufall))
        return proben

    async def _vorrat_zwischengespeichert(self) -> List[_ProbeIds]:
        if _zwischenspeicher and _zwischenspeicher[0] >= _uhr():
            return _zwischenspeicher[1]
        async with _zwischenspeicher_sperre:
            # Erneut pruefen: Waehrend des Wartens kann eine andere Anfrage ihn
            # bereits gefuellt haben.
            if _zwischenspeicher and _zwischenspeicher[0] >= _uhr():
                return _zwischenspeicher[1]
            vorrat = await self._vorrat()
            _zwischenspeicher[:] = [_uhr() + ZWISCHENSPEICHER_SEKUNDEN, vorrat]
            return vorrat

    async def _frisch(
        self, stapel: List[_ProbeIds], zufall: random.Random
    ) -> List[KonterProbe]:
        """Die Proben des Stapels mit frisch geladenen, sichtbaren Inhalten."""
        aussagen = {
            a.id: a
            for a in await self._aussagen.kuratierte(
                ids=[p.statement_id for p in stapel]
            )
        }
        stapel = [p for p in stapel if p.statement_id in aussagen]
        if not stapel:
            return []
        alle_ids = [i for p in stapel for i in p.antwort_ids]
        geladen = await asyncio.gather(*(self._beitrag_laden(i) for i in alle_ids))
        beitraege = dict(zip(alle_ids, geladen))
        nutzung = await asyncio.to_thread(self._nutzung, alle_ids)

        proben = []
        for ids in stapel:
            antworten = [beitraege[i] for i in ids.antwort_ids]
            if any(a is None for a in antworten):
                continue
            zahlen = [nutzung.get(str(i), 0) for i in ids.antwort_ids]
            # Der Browser liest den Spitzenreiter an der angezeigten Zahl ab: Sie muss
            # dieselbe Antwort allein vorn zeigen wie die entdoppelte.
            if any(zahl >= zahlen[0] for zahl in zahlen[1:]):
                continue
            for antwort, zahl in zip(antworten, zahlen):
                antwort["usage_count"] = zahl
            zufall.shuffle(antworten)
            proben.append(
                KonterProbe(
                    statement_id=ids.statement_id,
                    text=aussagen[ids.statement_id].text.strip(),
                    antworten=antworten,
                )
            )
        return proben

    async def _vorrat(self) -> List[_ProbeIds]:
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
            await asyncio.to_thread(self._nutzung_entdoppelt, list(kommentare))
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
                beitrag["_id"] = beitrag_id
                geladen.append(beitrag)
            probe = probe_aus_kommentaren(aussage.id, aussage.text, geladen)
            if probe is not None:
                vorrat.append(
                    _ProbeIds(
                        statement_id=probe.statement_id,
                        antwort_ids=tuple(a["_id"] for a in probe.antworten),
                    )
                )
        logger.debug(f"Konter-Probe: {len(vorrat)} passende Aussagen")
        return vorrat
