"""
Seitenaufrufe und Besucher je Tag, ohne IP und ohne Cookie (#761, GLOSSARY.md "Aufruf").

Heute zaehlen die Kennzahlen nur, wer sucht; wer nur liest, fehlt. Das Frontend meldet
deshalb jeden Seitenwechsel mit einer leeren Anfrage (``POST /api/v1/aufrufe/zaehlen``),
ohne Pfad, ohne Kennung, ohne etwas im Browser abzulegen.

- Besucher ist das vorhandene Tagespseudonym (#446, utils/besucher_pseudonym.py): der
  Anschluss (IPv4-Adresse, bei IPv6 das /64), mit dem Tagesschluessel gehasht, der nur im
  Arbeitsspeicher liegt. Kein neues Merkmal, auch fuer Angemeldete nicht (keine Kennung).
  Vor dem Merkmal steht ``aufruf|``: So ist das Pseudonym ein anderes als an den
  Suchereignissen desselben Tages, beide lassen sich nicht verknuepfen.
- Gespeichert wird je Pseudonym nur die Zahl der Aufrufe des laufenden Tages
  (``aufrufe_heute``). Danach verdichtet der Takt den Tag zu zwei Zahlen (Aufrufe,
  Besucher) in ``aufrufe_tage`` und loescht die Pseudonyme. Das Verdichten laeuft auch
  bei ausgeschaltetem Schalter: Es loescht nur und ruft nichts ab.
- Nur mit dem Schalter ``aufrufe_zaehlen`` (Obergrenze ``SEMANTIC_SEARCH_AUFRUFE_ZAEHLEN_AKTIV``,
  Standard aus, DSFA-Hinweis). Ist er aus, zaehlt nichts und nichts wird gespeichert;
  das Frontend hoert nach der ersten Antwort (404) auf zu melden.
"""

import asyncio
from datetime import date, datetime, timezone
from typing import Callable

from core.logging import get_logger
from repositories.aufrufe_repository import AufrufeRepository
from utils.besucher_pseudonym import besucher_tagespseudonym

logger = get_logger(__name__)

SCHALTER = "aufrufe_zaehlen"
# Vor dem Merkmal: ein eigener Raum fuer die Pseudonyme der Aufrufe
PRAEFIX = "aufruf|"
TAKT_SEKUNDEN = 60 * 60


def heute_utc() -> date:
    return datetime.now(timezone.utc).date()


def aufruf_pseudonym(merkmal: str, tag: date) -> str:
    """Das Tagespseudonym fuer Aufrufe: wie an Suchereignissen, nur mit eigenem Praefix."""
    return besucher_tagespseudonym(f"{PRAEFIX}{merkmal}", tag)


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
