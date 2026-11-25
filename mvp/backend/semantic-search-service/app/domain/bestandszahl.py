"""
Zuwachs zur Bestandszahl auf der Startseite (Entscheidung des Maintainers vom 26.11.2026,
GLOSSARY.md "Bestandszahl"): wie viele Kommentare in den letzten sieben Tagen sichtbar
dazugekommen sind, oder, wenn es weniger als drei sind, an welchem Tag zuletzt einer
dazukam.

Nur Zaehlung und Tag oeffentlicher Inhalte beim Aufruf, nichts wird gespeichert. Der Tag
ist tagesgenau in deutscher Zeit und ohne Uhrzeit: Eine Uhrzeit liesse bei wenigen Aktiven
auf Personen schliessen (juristische Pruefung 26.11.2026). Unter drei neuen nennt die
Antwort deshalb auch keine Zahl, nur den Tag.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Rollierend, nicht die Kalenderwoche
ZUWACHS_TAGE = 7
# Ab so vielen neuen Kommentaren nennt die Startseite die genaue Zahl
ZUWACHS_AB = 3


@dataclass(frozen=True)
class Zuwachs:
    # Genaue Zahl neuer Kommentare in ZUWACHS_TAGE Tagen, nur ab ZUWACHS_AB, sonst None
    neu: Optional[int]
    # Tag (deutsche Zeit) des neuesten Kommentars, nur unter ZUWACHS_AB und wenn es in
    # ZUWACHS_TAGE Tagen einen gab, sonst None
    zuletzt_ergaenzt: Optional[date]


def zeitraum_beginn(jetzt: datetime) -> datetime:
    return jetzt - timedelta(days=ZUWACHS_TAGE)


def tag_in_deutschland(zeitpunkt: datetime) -> date:
    """Kalendertag in deutscher Zeit; ohne Zeitzone gilt UTC."""
    if zeitpunkt.tzinfo is None:
        zeitpunkt = zeitpunkt.replace(tzinfo=timezone.utc)
    try:
        return zeitpunkt.astimezone(ZoneInfo("Europe/Berlin")).date()
    except ZoneInfoNotFoundError:
        return zeitpunkt.astimezone(timezone.utc).date()


def zuwachs(neu: int, zeitpunkte: Iterable[datetime]) -> Zuwachs:
    """
    ``neu``: neue sichtbare Kommentare im Zeitraum; ``zeitpunkte``: deren Anlagezeitpunkte
    (nur gebraucht, wenn es weniger als ZUWACHS_AB sind).
    """
    if neu >= ZUWACHS_AB:
        return Zuwachs(neu=neu, zuletzt_ergaenzt=None)
    zeitpunkte = list(zeitpunkte)
    if neu <= 0 or not zeitpunkte:
        return Zuwachs(neu=None, zuletzt_ergaenzt=None)
    return Zuwachs(neu=None, zuletzt_ergaenzt=tag_in_deutschland(max(zeitpunkte)))
