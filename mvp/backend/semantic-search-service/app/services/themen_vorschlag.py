"""
Themenvorschlaege (#401): zu einem Text bis zu drei Themen aus der festen Liste, die
eine Person mit einem Tipp uebernehmen kann. Nur Vorschlaege: Gespeichert wird nichts,
die Zuordnung bleibt von Hand (Zuordnungsart.VON_HAND), damit sie als Testset taugt.

Je Thema ein Prototyp: der Mittelwert der Vektoren seiner von Hand zugeordneten Aussagen
(Testset, AussageThemenService.testset) und des Vektors aus Name und Stichwoertern des
Themas, alle um ihre gemeinsame Mitte verschoben. Ein Thema ohne Zuordnung hat nur den
Namensvektor. Vorgeschlagen werden die
Themen, deren Prototyp dem Text am naechsten ist, ab einer Schwelle und nicht weiter
als einen Abstand hinter dem naechsten. Optional urteilt das NLI-Modell der NLI-Stufe
(#387) als zweite Meinung ueber die naechsten Kandidaten ("In diesem Satz geht es um
<Thema>."); es streicht Kandidaten, ergaenzt aber keine.

Eingebettet wird mit dem Modell der Suche und dem Praefix der Aussagen ("query: "),
gerechnet auf der CPU im selben Dienst, ohne neues Modell (ADR 0005). Schwellen und
Messung: tests/regression/THEMEN.md.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import (
    Awaitable,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
)

import numpy as np

from domain.themen import THEMEN, Thema

# Standard-Logger wie nli_modell: auch Messskripte ohne initialize_logging laden das Modul.
logger = logging.getLogger(__name__)

# Vorlage fuer die zweite Meinung (Zero-Shot-NLI, Model Card des NLI-Modells).
NLI_VORLAGE = "In diesem Satz geht es um {}."
# So viele naechste Themen prueft das NLI-Modell; je Kandidat ein Paar, etwa 20 ms.
NLI_KANDIDATEN = 5


@dataclass(frozen=True)
class Schwellen:
    """Wann ein Thema vorgeschlagen wird; gemessen in tests/regression/THEMEN.md."""

    # Mindestaehnlichkeit Text zu Prototyp (Kosinus der normierten Vektoren).
    aehnlichkeit_ab: float
    # Hoechstens so weit hinter dem naechsten Thema.
    abstand_hoechstens: float
    # Folgerung des NLI-Modells mindestens (nur mit zweiter Meinung).
    folgerung_ab: float = 0.0


def namenstext(thema: Thema) -> str:
    """Name und Stichwoerter eines Themas als ein Text fuer den Namensvektor.

    Die Stichwoerter kommen mit #754 an Thema; bis dahin nur der Name."""
    stichwoerter = getattr(thema, "stichwoerter", ()) or ()
    if not stichwoerter:
        return thema.name
    return f"{thema.name}: {', '.join(stichwoerter)}"


def _normiert(vektor: np.ndarray) -> np.ndarray:
    laenge = float(np.linalg.norm(vektor))
    return vektor if laenge == 0.0 else vektor / laenge


# Der Namensvektor eines Themas zaehlt so viel wie so viele Beispiele (THEMEN.md).
NAMENSGEWICHT = 5.0


@dataclass(frozen=True)
class Prototypen:
    """
    Je Thema ein Prototyp, dazu die Mitte: der Mittelwert aller Vektoren, aus denen die
    Prototypen gebaut sind. Die Mitte wird vor dem Vergleich abgezogen. Die Vektoren des
    Einbettungsmodells liegen alle in einem engen Kegel (Kosinus 0,8 bis 0,9 auch fuer
    fremde Themen); ohne die Mitte unterscheiden sich die Themen kaum (THEMEN.md).
    """

    mitte: np.ndarray
    vektoren: Dict[str, np.ndarray]


def prototypen_bauen(
    namensvektoren: Mapping[str, Sequence[float]],
    beispiele: Sequence[Tuple[Sequence[float], Sequence[str]]],
    namensgewicht: float = NAMENSGEWICHT,
) -> Prototypen:
    """
    Je Thema der normierte Mittelwert aus Namensvektor (mit namensgewicht) und den
    Vektoren seiner Beispiele (Vektor einer Aussage, ihre Themen), alle um die Mitte
    verschoben. Die Mitte ist der Mittelwert aus Namensvektoren und Beispielen; ohne
    Beispiele also die der Namen. Themen, die nicht in namensvektoren stehen, fallen weg.
    """
    namen = {s: np.asarray(v, dtype=np.float32) for s, v in namensvektoren.items()}
    alle = list(namen.values()) + [
        np.asarray(v, dtype=np.float32) for v, _ in beispiele
    ]
    mitte = np.mean(alle, axis=0)
    summen = {s: namensgewicht * _normiert(v - mitte) for s, v in namen.items()}
    for vektor, themen in beispiele:
        v = _normiert(np.asarray(vektor, dtype=np.float32) - mitte)
        for schluessel in themen:
            if schluessel in summen:
                summen[schluessel] = summen[schluessel] + v
    return Prototypen(mitte, {s: _normiert(summe) for s, summe in summen.items()})


def rangliste(
    vektor: Sequence[float], prototypen: Prototypen
) -> List[Tuple[str, float]]:
    """Alle Themen mit ihrer Aehnlichkeit zum Text (um die Mitte verschoben), das
    naechste zuerst."""
    v = _normiert(np.asarray(vektor, dtype=np.float32) - prototypen.mitte)
    werte = [(s, float(np.dot(v, p))) for s, p in prototypen.vektoren.items()]
    return sorted(werte, key=lambda w: w[1], reverse=True)


def auswaehlen(
    rang: Sequence[Tuple[str, float]],
    schwellen: Schwellen,
    hoechstens: int,
    folgerungen: Optional[Mapping[str, float]] = None,
) -> List[str]:
    """
    Die vorgeschlagenen Themen aus der Rangliste: ab aehnlichkeit_ab, nicht weiter als
    abstand_hoechstens hinter dem ersten, hoechstens so viele. Mit folgerungen (zweite
    Meinung) nur die, deren Folgerung mindestens folgerung_ab ist; ein Thema ohne Urteil
    faellt dann weg.
    """
    if not rang or hoechstens <= 0:
        return []
    beste = rang[0][1]
    ergebnis: List[str] = []
    for schluessel, wert in rang:
        if (
            wert < schwellen.aehnlichkeit_ab
            or beste - wert > schwellen.abstand_hoechstens
        ):
            break
        if folgerungen is not None and (
            folgerungen.get(schluessel, -1.0) < schwellen.folgerung_ab
        ):
            continue
        ergebnis.append(schluessel)
        if len(ergebnis) >= hoechstens:
            break
    return ergebnis


def nli_paare(text: str, kandidaten: Sequence[str]) -> List[Tuple[str, str]]:
    """Je Kandidat (Schluessel) das Paar (Text, Hypothese) fuer die zweite Meinung."""
    namen = {t.schluessel: t.name for t in THEMEN}
    return [(text, NLI_VORLAGE.format(namen[s])) for s in kandidaten if s in namen]


class Einbetter(Protocol):
    def encode_query(self, query: str) -> List[float]: ...


class Folgerer(Protocol):
    """Das NLI-Modell (NliModell.folgerungen); Tests geben eine Attrappe."""

    async def folgerungen(
        self,
        paare: Sequence[Tuple[str, str]],
        warte_hoechstens: Optional[float] = None,
    ) -> Optional[List[float]]: ...


# Die Beispiele: je von Hand zugeordneter Aussage (Text, Themen).
BeispieleLaden = Callable[[], Awaitable[List[Tuple[str, List[str]]]]]


class ThemenVorschlagService:
    """
    Haelt die Prototypen im Speicher und baut sie hoechstens alle `neu_nach` Sekunden
    neu, damit neue Zuordnungen von Hand ankommen. Vektoren schon eingebetteter Texte
    bleiben im Speicher; neu eingebettet werden nur neue Texte.
    """

    def __init__(
        self,
        einbetter: Einbetter,
        beispiele_laden: BeispieleLaden,
        schwellen: Schwellen,
        folgerer: Optional[Folgerer] = None,
        neu_nach: float = 600.0,
        nli_wartet_hoechstens: float = 1.0,
        uhr: Callable[[], float] = time.monotonic,
    ):
        self._einbetter = einbetter
        self._beispiele_laden = beispiele_laden
        self._schwellen = schwellen
        self._folgerer = folgerer
        self._neu_nach = neu_nach
        self._nli_wartet_hoechstens = nli_wartet_hoechstens
        self._uhr = uhr
        self._prototypen: Optional[Prototypen] = None
        self._gebaut_um = 0.0
        self._vektoren: Dict[str, np.ndarray] = {}
        self._sperre = asyncio.Lock()

    def _einbetten(self, text: str) -> np.ndarray:
        # Als float32-Array: 3 KB je Text statt rund 25 KB als Liste von floats.
        if text not in self._vektoren:
            self._vektoren[text] = np.asarray(
                self._einbetter.encode_query(text), dtype=np.float32
            )
        return self._vektoren[text]

    def _bauen_sync(self, beispiele: List[Tuple[str, List[str]]]) -> Prototypen:
        namen = {t.schluessel: self._einbetten(namenstext(t)) for t in THEMEN}
        bekannt = {namenstext(t) for t in THEMEN} | {text for text, _ in beispiele}
        # Texte, die nicht mehr im Testset stehen (geloescht, umgeordnet), vergessen.
        self._vektoren = {t: v for t, v in self._vektoren.items() if t in bekannt}
        return prototypen_bauen(
            namen, [(self._einbetten(text), themen) for text, themen in beispiele]
        )

    async def _prototypen_holen(self) -> Prototypen:
        async with self._sperre:
            veraltet = self._uhr() - self._gebaut_um >= self._neu_nach
            if self._prototypen is None or veraltet:
                try:
                    beispiele = await self._beispiele_laden()
                except Exception as e:
                    if self._prototypen is None:
                        raise
                    # Mit den alten Prototypen weiter, beim naechsten Mal neu versuchen.
                    logger.warning(
                        f"Themen-Prototypen nicht neu gebaut: {type(e).__name__}"
                    )
                    self._gebaut_um = self._uhr()
                    return self._prototypen
                self._prototypen = await asyncio.to_thread(self._bauen_sync, beispiele)
                self._gebaut_um = self._uhr()
                logger.info(
                    f"Themen-Prototypen gebaut aus {len(beispiele)} Zuordnungen von Hand"
                )
            return self._prototypen

    async def vorschlagen(self, text: str, hoechstens: int) -> List[str]:
        """Die vorgeschlagenen Themen zu einem Text, das naechste zuerst; [] bei leerem Text."""
        text = text.strip()
        if not text or hoechstens <= 0:
            return []
        prototypen = await self._prototypen_holen()
        vektor = await asyncio.to_thread(self._einbetter.encode_query, text)
        rang = rangliste(vektor, prototypen)
        folgerungen = await self._zweite_meinung(text, rang)
        return auswaehlen(rang, self._schwellen, hoechstens, folgerungen)

    async def _zweite_meinung(
        self, text: str, rang: Sequence[Tuple[str, float]]
    ) -> Optional[Dict[str, float]]:
        """Folgerung je Kandidat; None ohne NLI oder wenn das Modell nicht rechtzeitig frei
        ist: Dann gilt der Prototyp allein."""
        if self._folgerer is None:
            return None
        kandidaten = [s for s, _ in rang[:NLI_KANDIDATEN]]
        werte = await self._folgerer.folgerungen(
            nli_paare(text, kandidaten), warte_hoechstens=self._nli_wartet_hoechstens
        )
        if werte is None:
            return None
        return dict(zip(kandidaten, werte))
