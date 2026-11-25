"""
Team-Fortschritt und Team-Quests (GLOSSARY.md "Team-Fortschritt", "Team-Quest",
"Wochenzaehler"): die Regeln, die bestimmen, was Mitglieder von der Summe ihres Teams
sehen. Hier steht nur die Rechnung; wer zaehlt und wann, entscheidet
services/team_fortschritt_service.py.

Die Regeln stehen so in der Einwilligung ``team-2026-11-26`` und im DSFA-Nachtrag;
wer eine aendert, aendert auch die Texte dort:

- Gezaehlt werden nur Beitraege (jeder Beitragstyp, Kommentare eingeschlossen),
  Bewertungen und Meldungen "Ja, gepostet". Eine Meldung "Ja, gepostet" zaehlt nur mit
  geltender Art.-9-Einwilligung.
- Sichtbar erst ab ``MINDESTMITGLIEDER`` Mitgliedern mit Team-Einwilligung, die die
  Summe deckt (``SUMME_GEDECKT``), und nur fuer abgeschlossene Wochen.
- Keine genaue Zahl: unter ``RUNDUNG_AB`` steht "weniger als 10", darueber die auf
  ``RUNDUNG_SCHRITT`` gerundete Zahl.
"""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Optional

# Kennungen der Team-Einwilligung, die die Summe des Teams decken. team-2026-11-25
# nannte nur Beitraege und Bewertungen; wer ihr zugestimmt hat, zaehlt nicht mit und
# zaehlt nicht zur Schwelle.
SUMME_GEDECKT = frozenset({"team-2026-11-26"})

# Erst ab so vielen Mitgliedern mit deckender Einwilligung wird gezaehlt und gezeigt.
MINDESTMITGLIEDER = 5

# Unter dieser Zahl steht keine Zahl, sondern "weniger als 10".
RUNDUNG_AB = 10
RUNDUNG_SCHRITT = 5
WENIGER_ALS = "weniger als 10"

# Team-Quest (#792): Ziel aus Bedarf, mindestens so viel.
QUEST_MINDESTZIEL = 3
# Je so viele Mitglieder mit Einwilligung ein Schritt zum Ziel (aufgerundet).
QUEST_MITGLIEDER_JE_SCHRITT = 3


class Art(StrEnum):
    """Was in den Wochenzaehler eingeht (die Spalten von team_wochen)."""

    BEITRAG = "beitrag"
    BEWERTUNG = "bewertung"
    GEPOSTET = "gepostet"


def gerundet(anzahl: int) -> Optional[int]:
    """
    Die Zahl, die Mitglieder sehen duerfen: None unter RUNDUNG_AB ("weniger als 10"),
    sonst auf RUNDUNG_SCHRITT gerundet (halbe Schritte aufwaerts: 12 -> 10, 13 -> 15).
    """
    if anzahl < RUNDUNG_AB:
        return None
    return (anzahl + RUNDUNG_SCHRITT // 2) // RUNDUNG_SCHRITT * RUNDUNG_SCHRITT


def anzeige(anzahl: int) -> str:
    """Die gerundete Zahl als Text: "weniger als 10" oder "rund 45"."""
    wert = gerundet(anzahl)
    return WENIGER_ALS if wert is None else f"rund {wert}"


def zeigbar(einwilligende_mitglieder: int) -> bool:
    """Ob ein Team gross genug ist, dass seine Summe gezaehlt und gezeigt wird."""
    return einwilligende_mitglieder >= MINDESTMITGLIEDER


def quest_ziel(brachflaechen: int, einwilligende_mitglieder: int) -> int:
    """
    Das Wochenziel eines Teams: min(Brachflaechen im Thema, Mitglieder / 3
    aufgerundet), mindestens QUEST_MINDESTZIEL.
    """
    je_mitglieder = math.ceil(einwilligende_mitglieder / QUEST_MITGLIEDER_JE_SCHRITT)
    return max(QUEST_MINDESTZIEL, min(brachflaechen, je_mitglieder))


@dataclass(frozen=True)
class Wochenzaehlung:
    """Ein Wochenzaehler: nur Zahlen, ohne Kennung und ohne Beitrag."""

    beitraege: int = 0
    bewertungen: int = 0
    gepostet: int = 0

    @property
    def gesamt(self) -> int:
        return self.beitraege + self.bewertungen + self.gepostet
