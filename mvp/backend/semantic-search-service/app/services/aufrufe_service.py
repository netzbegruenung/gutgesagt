"""
Seitenaufrufe und Besucher je Tag, ohne Cookie und ohne die IP-Adresse zu speichern
(#761, GLOSSARY.md "Aufruf").

Heute zaehlen die Kennzahlen nur, wer sucht; wer nur liest, fehlt. Gezaehlt wird am
Server, aus Abrufen, die die App ohnehin macht (middleware/aufrufe_zaehlen.py): die
neuesten Beitraege der Startseite, eine Suche, die Aussagen eines Themas und ein
Beitrag. Der Browser schickt dafuer keine eigene Anfrage und legt nichts ab: Eine
eigene Zaehl-Anfrage aus dem Browser fiele wohl unter § 25 TDDDG.

- Besucher ist das vorhandene Tagespseudonym (#446, utils/besucher_pseudonym.py): der
  Anschluss (IPv4-Adresse, bei IPv6 das /64), mit dem Tagesschluessel gehasht, der nur im
  Arbeitsspeicher liegt. Kein neues Merkmal, auch fuer Angemeldete nicht (keine Kennung).
  Vor dem Merkmal steht ``aufruf|``: So ist das Pseudonym ein anderes als an den
  Suchereignissen desselben Tages, beide lassen sich nicht verknuepfen.
- Dieselbe Seite desselben Besuchers binnen ``SPERRE_SEKUNDEN`` zaehlt einmal
  (``Wiederholsperre``): Nachladen, Zurueck und mehrere Karten mit demselben Abruf
  blaehen die Zahl nicht auf. Die Sperre haelt nur einen Pruefwert aus Pseudonym und
  Seite im Arbeitsspeicher, bis Mitternacht.
- Gespeichert wird je Pseudonym nur die Zahl der Aufrufe des laufenden Tages
  (``aufrufe_heute``). Danach verdichtet der Takt den Tag zu zwei Zahlen (Aufrufe,
  Besucher) in ``aufrufe_tage`` und loescht die Pseudonyme. Das Verdichten laeuft auch
  bei ausgeschaltetem Schalter: Es loescht nur und ruft nichts ab.
- Nur mit dem Schalter ``aufrufe_zaehlen`` (Obergrenze ``SEMANTIC_SEARCH_AUFRUFE_ZAEHLEN_AKTIV``,
  Standard aus, Einschalt-Hinweis). Ist er aus, zaehlt nichts und nichts wird gespeichert.
"""

import asyncio
import re
import threading
import time
from datetime import date, datetime, timezone
from typing import Callable, Dict, Optional, Tuple

from core.logging import get_logger
from repositories.aufrufe_repository import AufrufeRepository
from utils.besucher_pseudonym import besucher_tagespseudonym

logger = get_logger(__name__)

SCHALTER = "aufrufe_zaehlen"
# Vor dem Merkmal: ein eigener Raum fuer die Pseudonyme der Aufrufe
PRAEFIX = "aufruf|"
# Eigener Raum fuer die Pruefwerte der Wiederholsperre
SPERRE_PRAEFIX = "aufruf-seite|"
TAKT_SEKUNDEN = 60 * 60
# Dieselbe Seite zaehlt binnen dieser Zeit einmal; jeder weitere Abruf verlaengert sie.
SPERRE_SEKUNDEN = 5 * 60
# Hoechstens so viele Pruefwerte haelt die Sperre; darueber zaehlt sie nichts Neues
# (die sichere Richtung), bis abgelaufene weg sind.
SPERRE_HOECHSTENS = 100_000

# Abrufe, die einen Aufruf ausmachen: Methode, Pfad -> Seite. Die Seite traegt bei
# Beitrag und Thema die ID, damit zwei verschiedene Beitraege zwei Aufrufe sind; sie
# geht nur in den Pruefwert der Sperre ein, gespeichert wird sie nicht.
_SEITEN: Tuple[Tuple[str, "re.Pattern[str]", str], ...] = (
    ("GET", re.compile(r"^/api/v1/content/recent$"), "start"),
    ("GET", re.compile(r"^/api/v1/content/beitrag/([^/]+)$"), "beitrag"),
    ("POST", re.compile(r"^/api/v1/search/searchByText$"), "suche"),
    ("GET", re.compile(r"^/api/v1/search/thema/([^/]+)$"), "thema"),
)


def heute_utc() -> date:
    return datetime.now(timezone.utc).date()


def seite_von(methode: str, pfad: str) -> Optional[str]:
    """Die Seite, die dieser Abruf anzeigt, oder None, wenn er kein Aufruf ist."""
    for erwartet, muster, name in _SEITEN:
        if methode != erwartet:
            continue
        treffer = muster.match(pfad)
        if treffer:
            return f"{name}|{treffer.group(1)}" if treffer.groups() else name
    return None


def aufruf_pseudonym(merkmal: str, tag: date) -> str:
    """Das Tagespseudonym fuer Aufrufe: wie an Suchereignissen, nur mit eigenem Praefix."""
    return besucher_tagespseudonym(f"{PRAEFIX}{merkmal}", tag)


class Wiederholsperre:
    """
    Merkt sich je Besucher und Seite, wann sie zuletzt abgerufen wurde, nur im Speicher
    und nur als Pruefwert mit dem Tagesschluessel. Mit dem Tag wechselt alles.
    """

    def __init__(
        self,
        sekunden: float = SPERRE_SEKUNDEN,
        hoechstens: int = SPERRE_HOECHSTENS,
        uhr: Callable[[], float] = time.monotonic,
    ):
        self._sekunden = sekunden
        self._hoechstens = hoechstens
        self._uhr = uhr
        self._tag: Optional[date] = None
        self._zuletzt: Dict[str, float] = {}
        self._lock = threading.Lock()

    def neu(self, merkmal: str, seite: str, tag: date) -> bool:
        """True, wenn dieser Abruf als Aufruf zaehlt; merkt ihn in jedem Fall."""
        pruefwert = besucher_tagespseudonym(f"{SPERRE_PRAEFIX}{merkmal}|{seite}", tag)
        jetzt = self._uhr()
        with self._lock:
            if self._tag != tag:
                self._tag = tag
                self._zuletzt = {}
            vorher = self._zuletzt.get(pruefwert)
            if vorher is None and len(self._zuletzt) >= self._hoechstens:
                self._abgelaufene_entfernen(jetzt)
                if len(self._zuletzt) >= self._hoechstens:
                    return False
            self._zuletzt[pruefwert] = jetzt
            return vorher is None or jetzt - vorher >= self._sekunden

    def _abgelaufene_entfernen(self, jetzt: float) -> None:
        self._zuletzt = {
            k: t for k, t in self._zuletzt.items() if jetzt - t < self._sekunden
        }


wiederholsperre = Wiederholsperre()


def zaehlen(repository: AufrufeRepository, merkmal: str, tag: date) -> None:
    """Einen Aufruf des Besuchers mit diesem Merkmal zaehlen; das Merkmal wird nicht gespeichert."""
    repository.zaehlen(tag, aufruf_pseudonym(merkmal, tag))


async def verdichten_im_takt(
    repository: AufrufeRepository,
    takt_sekunden: float = TAKT_SEKUNDEN,
    heute: Callable[[], date] = heute_utc,
) -> None:
    """
    Hintergrund-Task aus main.py: sofort und dann stuendlich alle vergangenen Tage zu
    Tageszahlen verdichten und ihre Pseudonyme loeschen. Spaetestens eine Stunde nach
    Mitternacht (UTC) ist kein Pseudonym des Vortags mehr da.
    """
    while True:
        try:
            entfernt = await asyncio.to_thread(repository.verdichten_vor, heute())
            if entfernt:
                logger.info(f"Aufrufe: {entfernt} Tagespseudonyme verdichtet")
        except Exception as e:
            logger.error(f"Aufrufe nicht verdichtet: {type(e).__name__}")
        await asyncio.sleep(takt_sekunden)
