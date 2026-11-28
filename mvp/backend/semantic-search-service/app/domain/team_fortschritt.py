"""
Team-Fortschritt und Team-Quests (GLOSSARY.md "Team-Fortschritt", "Team-Quest",
"Wochenzaehler"): die Regeln, die bestimmen, was Mitglieder von der Summe ihres Teams
sehen. Hier steht nur die Rechnung; wer zaehlt und wann, entscheidet
services/team_fortschritt_service.py.

Die Regeln stehen so in der Einwilligung ``team-2026-11-26`` und im DSFA-Nachtrag;
wer eine aendert, aendert auch die Texte dort:

- Gezaehlt werden nur Beitraege (jeder Beitragstyp, Kommentare eingeschlossen),
  Bewertungen und Meldungen "Ja, gepostet". Eine Meldung "Ja, gepostet" zaehlt nur mit
  geltender Art.-9-Einwilligung, eine Bewertung nur zu einem fremden Beitrag
  (api/v1/voting.py, ``_fuers_team_zaehlen``; weniger als die Einwilligung erlaubt).
- Sichtbar erst ab ``MINDESTMITGLIEDER`` Mitgliedern mit Team-Einwilligung, die die
  Summe deckt (``SUMME_GEDECKT``), und nur fuer abgeschlossene Wochen.
- Keine genaue Zahl: unter ``RUNDUNG_AB`` steht "weniger als 10", darueber die auf
  ``RUNDUNG_SCHRITT`` gerundete Zahl.

Quasi-live (Schalter ``team_live``, Jura-Akte 28.11.2026 "Team-Fortschritt quasi-live
zur BDK"): Stundenbloecke nach Blockende, die Regeln dazu stehen unten bei
``LIVE_MINDESTMITGLIEDER``; wer sie aendert, aendert auch DSE, VVT T17 und DSFA V29.
"""

import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from enum import StrEnum
from typing import Optional
from zoneinfo import ZoneInfo

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


# --- Quasi-live (team_live, Jura-Akte 28.11.2026) ----------------------------------
#
# - Der laufende Tag zaehlt in Stundenbloecken (deutsche Zeit, volle Stunde). Jeder
#   Block wird VEROEFFENTLICHUNG_NACH nach seinem Ende einmal vorberechnet, nicht je
#   Abruf.
# - Ein Block wird erst freigegeben, wenn mindestens LIVE_K verschiedene Mitglieder in
#   ihm (samt der uebertragenen Bloecke davor) beigetragen haben; sonst geht er in den
#   naechsten Block desselben Tages ueber ("laeuft noch"). Ohne vollstaendige Menge der
#   Pruefwerte (Neustart waehrend des Blocks) wird uebertragen, nie freigegeben.
# - Live nur in Teams ab LIVE_MINDESTMITGLIEDER Mitgliedern mit deckender Einwilligung.
#   Die Tagessumme wird auf LIVE_SCHRITT abgerundet, darunter "weniger als 10"; die
#   Mitgliederzahl ebenso abgerundet. Die Wochenanzeige oben bleibt unveraendert.
# - Die Quest-Stufe (Drittel) kommt nur aus freigegebenen Bloecken.

LIVE_MINDESTMITGLIEDER = 20
LIVE_K = 10
LIVE_SCHRITT = 10
BLOCK = timedelta(hours=1)
VEROEFFENTLICHUNG_NACH = timedelta(minutes=15)
ZEITZONE = ZoneInfo("Europe/Berlin")


def live_zeigbar(einwilligende_mitglieder: int) -> bool:
    """Ob ein Team gross genug fuer den Live-Stand ist (ab 20 mit Einwilligung)."""
    return einwilligende_mitglieder >= LIVE_MINDESTMITGLIEDER


def abgerundet(anzahl: int) -> Optional[int]:
    """Auf LIVE_SCHRITT abgerundet; None unter RUNDUNG_AB ("weniger als 10")."""
    if anzahl < RUNDUNG_AB:
        return None
    return anzahl // LIVE_SCHRITT * LIVE_SCHRITT


def live_anzeige(anzahl: int) -> str:
    """Die abgerundete Tagessumme als Text: "weniger als 10" oder "rund 80"."""
    wert = abgerundet(anzahl)
    return WENIGER_ALS if wert is None else f"rund {wert}"


def mitglieder_anzeige(einwilligende_mitglieder: int) -> Optional[int]:
    """Die Mitgliederzahl fuer den Live-Stand: erst ab 20, auf 10 abgerundet."""
    if not live_zeigbar(einwilligende_mitglieder):
        return None
    return abgerundet(einwilligende_mitglieder)


def freigeben(verschiedene: int, beobachtet: bool) -> bool:
    """
    Ob ein Block (mit den uebertragenen davor) freigegeben wird: nur ab LIVE_K
    verschiedenen Beitragenden und nur, wenn der Block vollstaendig beobachtet wurde
    (kein Neustart seit Blockbeginn).
    """
    return beobachtet and verschiedene >= LIVE_K


def quest_stufe(freigegeben_in_der_woche: int, ziel: int) -> int:
    """Die Quest-Stufe: 0 (unter einem Drittel), 1 (ein Drittel), 2 (zwei Drittel), 3 (geschafft)."""
    if ziel <= 0 or freigegeben_in_der_woche >= ziel:
        return 3
    if 3 * freigegeben_in_der_woche >= 2 * ziel:
        return 2
    if 3 * freigegeben_in_der_woche >= ziel:
        return 1
    return 0


def blockbeginn(zeitpunkt: datetime) -> datetime:
    """
    Beginn (UTC) des Stundenblocks, in den der Zeitpunkt faellt. Deutsche Zeit weicht
    um ganze Stunden von UTC ab, die volle Stunde ist also in beiden dieselbe.
    """
    utc = zeitpunkt.astimezone(timezone.utc)
    return utc.replace(minute=0, second=0, microsecond=0)


def tagesbeginn(zeitpunkt: datetime) -> datetime:
    """Mitternacht (deutsche Zeit) des Tages, in den der Zeitpunkt faellt, in UTC."""
    tag = zeitpunkt.astimezone(ZEITZONE).date()
    return datetime.combine(tag, time.min, tzinfo=ZEITZONE).astimezone(timezone.utc)


def wochenbeginn_live(zeitpunkt: datetime) -> datetime:
    """
    Montag 0 Uhr (deutsche Zeit) der Woche, in die der Zeitpunkt faellt, in UTC: die
    Wochengrenze der Stundenzaehler (Loeschung, Quest-Stufe), passend zum Tag in
    deutscher Zeit.
    """
    tag = zeitpunkt.astimezone(ZEITZONE).date()
    montag = tag - timedelta(days=tag.weekday())
    return datetime.combine(montag, time.min, tzinfo=ZEITZONE).astimezone(timezone.utc)


def bis_stunde(block: datetime) -> int:
    """Die volle Stunde (deutsche Zeit), mit der der Block endet; Mitternacht als 24."""
    stunde = (block + BLOCK).astimezone(ZEITZONE).hour
    return stunde or 24
