"""
Saisons mit Gemeinschaftsziel (#782, GLOSSARY.md "Saison", "Gemeinschaftsziel",
"Widerspruchs-Woche").

Eine Saison hat einen Namen (hoechstens SAISON_MAX Zeichen, etwa „Frühjahr 27“), einen
ersten und letzten Tag und ein Gemeinschaftsziel in Widerspruchs-Wochen. Saisons
ueberschneiden sich nie, deshalb gibt es an jedem Tag hoechstens eine laufende Saison.

Gezaehlt wird nur aus den vorhandenen Wochenzahlen von "Ja, gepostet"
(gepostet_wochen, services/gepostet_service.py): je Kalenderwoche die Zahl der
verschiedenen Personen. Die Saisonzahl ist deren Summe ueber die Wochen der Saison.
Wer drei Wochen dabei ist, zaehlt dreimal; verschiedene Menschen ueber die ganze
Saison lassen sich ohne neue Datenspur nicht zaehlen. Deshalb heisst sie
Widerspruchs-Wochen, nie "Menschen".

Dieses Modul ist rein (keine Datenbank, keine Uhr): Regeln fuer Anlegen und Aendern,
welche Wochen zu einer Saison gehoeren und ob die Schwelle fuer den oeffentlichen
Balken erreicht ist.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Dict, Iterable, List, Optional

from core.fehler import Validierungsfehler
from domain.teams import SAISON_MAX
from utils.utc_tag import wochenbeginn

ZIEL_MAX = 1_000_000

_STEUERZEICHEN = re.compile(r"[\x00-\x1f\x7f]")


class SaisonUngueltig(Validierungsfehler):
    """Name, Tage oder Ziel ungueltig; der Text ist ein Satz fuer den Admin."""


class SaisonUeberschneidung(Validierungsfehler):
    """Die Tage ueberschneiden sich mit einer anderen Saison (``andere``: ihr Name)."""

    def __init__(self, andere: str):
        super().__init__(f"Überschneidet sich mit der Saison „{andere}“.")
        self.andere = andere


class SaisonGesperrt(Validierungsfehler):
    """Die Aenderung ist in diesem Zustand nicht erlaubt; der Text ist ein Satz."""


class SaisonZustand(str, Enum):
    GEPLANT = "geplant"
    LAUFEND = "laufend"
    VORBEI = "vorbei"


@dataclass(frozen=True)
class Saison:
    id: uuid.UUID
    name: str
    # Erster und letzter Tag (UTC), beide eingeschlossen
    beginn: date
    ende: date
    # Gemeinschaftsziel in Widerspruchs-Wochen
    ziel: int

    def zustand(self, heute: date) -> SaisonZustand:
        if heute < self.beginn:
            return SaisonZustand.GEPLANT
        if heute > self.ende:
            return SaisonZustand.VORBEI
        return SaisonZustand.LAUFEND

    def laeuft(self, heute: date) -> bool:
        return self.zustand(heute) is SaisonZustand.LAUFEND

    def wochen(self) -> List[date]:
        """Die Montage aller Kalenderwochen, die in die Saison fallen, auch angebrochene."""
        erste = wochenbeginn(self.beginn)
        anzahl = (wochenbeginn(self.ende) - erste).days // 7 + 1
        return [erste + timedelta(weeks=i) for i in range(anzahl)]


@dataclass(frozen=True)
class SaisonEingabe:
    """Was ein Admin anlegt oder aendert, schon bereinigt (``eingabe_pruefen``)."""

    name: str
    beginn: date
    ende: date
    ziel: int


def name_bereinigen(name: str) -> str:
    """Leerraum zusammenfassen; leer, zu lang oder mit Steuerzeichen: SaisonUngueltig."""
    if _STEUERZEICHEN.search(name.replace(" ", "")):
        raise SaisonUngueltig("Der Name darf keine Steuerzeichen enthalten.")
    name = " ".join(name.split())
    if not name:
        raise SaisonUngueltig("Die Saison braucht einen Namen.")
    if len(name) > SAISON_MAX:
        raise SaisonUngueltig(f"Der Name hat höchstens {SAISON_MAX} Zeichen.")
    return name


def eingabe_pruefen(name: str, beginn: date, ende: date, ziel: int) -> SaisonEingabe:
    name = name_bereinigen(name)
    if ende < beginn:
        raise SaisonUngueltig("Das Ende liegt vor dem Beginn.")
    if not 1 <= ziel <= ZIEL_MAX:
        raise SaisonUngueltig("Das Ziel liegt zwischen 1 und 1.000.000.")
    return SaisonEingabe(name=name, beginn=beginn, ende=ende, ziel=ziel)


def laenge_pruefen(eingabe: SaisonEingabe, hoechstens_tage: Optional[int]) -> None:
    """
    Eine Saison dauert hoechstens ``hoechstens_tage`` Tage (beide Randtage
    eingeschlossen), die Frist der Nutzungsereignisse (``usage_retention_days``). Sonst
    fiele in ihren letzten Tagen die Nutzung vom Anfang aus den Saisonpunkten, und
    nach ihrem Ende erschiene sie nie unter den vergangenen Saisons
    (services/rangliste_service.py). None: keine Frist, keine Grenze.
    """
    if hoechstens_tage is None:
        return
    if (eingabe.ende - eingabe.beginn).days + 1 > hoechstens_tage:
        raise SaisonUngueltig(
            f"Eine Saison dauert höchstens {hoechstens_tage} Tage, so lange liegen "
            "die Nutzungen für die Punkte vor."
        )


def ueberschneidung(
    eingabe: SaisonEingabe,
    andere: Iterable[Saison],
    ausser: Optional[uuid.UUID] = None,
) -> Optional[Saison]:
    """Die erste andere Saison, deren Tage sich mit der Eingabe ueberschneiden."""
    for saison in andere:
        if saison.id == ausser:
            continue
        if eingabe.beginn <= saison.ende and saison.beginn <= eingabe.ende:
            return saison
    return None


def aenderung_pruefen(alt: Saison, neu: SaisonEingabe, heute: date) -> None:
    """
    Was sich je Zustand aendern darf (SaisonGesperrt sonst):

    - geplant: alles, und der Beginn darf nicht in der Vergangenheit liegen;
    - laufend: nur Ziel und Ende, das Ende nicht vor heute. Name und Beginn stehen,
      weil Teamlinks und Mitgliedschaften den Namen als Kopie tragen;
    - vorbei: nichts mehr, die Saison ist Geschichte (Rangliste, Rueckblick).
    """
    zustand = alt.zustand(heute)
    if zustand is SaisonZustand.VORBEI:
        raise SaisonGesperrt("Eine vergangene Saison lässt sich nicht mehr ändern.")
    if zustand is SaisonZustand.LAUFEND:
        if neu.name != alt.name or neu.beginn != alt.beginn:
            raise SaisonGesperrt(
                "Bei einer laufenden Saison lassen sich nur Ziel und Ende ändern."
            )
        if neu.ende < heute:
            raise SaisonGesperrt(
                "Das Ende einer laufenden Saison liegt frühestens heute."
            )
        return
    if neu.beginn < heute:
        raise SaisonGesperrt("Der Beginn liegt frühestens heute.")


def anlegen_pruefen(neu: SaisonEingabe, heute: date) -> None:
    """Neue Saisons beginnen frühestens heute: Vergangene Wochen bekommen keine neue."""
    if neu.beginn < heute:
        raise SaisonGesperrt("Der Beginn liegt frühestens heute.")


def loeschen_pruefen(saison: Saison, heute: date) -> None:
    """Loeschen nur, solange sie noch nicht begonnen hat."""
    if saison.zustand(heute) is not SaisonZustand.GEPLANT:
        raise SaisonGesperrt(
            "Nur eine Saison, die noch nicht begonnen hat, lässt sich löschen."
        )


def wochen_der_saison(saison: Saison, andere: Iterable[Saison] = ()) -> List[date]:
    """
    Die Wochen, die der Saison zaehlen: ihre Kalenderwochen, angebrochene voll. Eine
    Randwoche, deren Montag in einer anderen Saison liegt, gehoert nur dieser anderen
    (die Wochenzahl gibt es nur fuer die ganze Woche): Grenzen zwei Saisons in einer
    Woche aneinander, zaehlt die Woche nur fuer die Saison, in der ihr Montag liegt.
    Nur die erste Woche kann einen Montag vor dem Beginn haben.
    """
    andere = [a for a in andere if a.id != saison.id]
    return [
        w
        for w in saison.wochen()
        if w >= saison.beginn or not any(a.beginn <= w <= a.ende for a in andere)
    ]


def saisonzahl(
    saison: Saison,
    wochenzahlen: Dict[date, int],
    laufende: date,
    andere: Iterable[Saison] = (),
) -> int:
    """
    Widerspruchs-Wochen der Saison: Summe der Wochenzahlen ueber ihre abgeschlossenen
    Wochen (Montag vor ``laufende``; Randwochen nach ``wochen_der_saison``, dafuer
    ``andere``: alle Saisons). Die laufende Woche zaehlt erst nach ihrem Ende, wie die
    Wochenzahl selbst, die erst dann feststeht.
    """
    return sum(
        wochenzahlen.get(w, 0)
        for w in wochen_der_saison(saison, andere)
        if w < laufende
    )


def schwelle_erreicht(
    wochenzahlen: Dict[date, int],
    laufende: date,
    menschen: int,
    wochen_in_folge: int,
) -> bool:
    """
    Ob es irgendwann ``wochen_in_folge`` abgeschlossene Kalenderwochen hintereinander
    gab, in denen je mindestens ``menschen`` verschiedene Personen "Ja, gepostet"
    gemeldet haben. Eine Woche ohne Eintrag zaehlt als 0 und unterbricht die Folge.
    Einmal erreicht, bleibt es erreicht: Die Wochenzahlen vergangener Wochen aendern
    sich nicht mehr.
    """
    if wochen_in_folge <= 0:
        return True
    folge = 0
    vorige: Optional[date] = None
    for woche in sorted(w for w in wochenzahlen if w < laufende):
        if vorige is None or woche - vorige != timedelta(weeks=1):
            folge = 0
        folge = folge + 1 if wochenzahlen[woche] >= menschen else 0
        if folge >= wochen_in_folge:
            return True
        vorige = woche
    return False


def laufende_saison(saisons: Iterable[Saison], heute: date) -> Optional[Saison]:
    """Die Saison, die heute laeuft; wegen der Regel ohne Ueberschneidung hoechstens eine."""
    for saison in saisons:
        if saison.laeuft(heute):
            return saison
    return None


def saison_fuer_teams(saisons: Iterable[Saison], heute: date) -> Optional[Saison]:
    """
    Die Saison, die fuer Teams als aktuell gilt: die laufende; in einer Luecke zwischen
    zwei Saisons die zuletzt beendete, bis die naechste beginnt. Ohne begonnene Saison
    None (dann gilt die Einstellung).
    """
    saisons = list(saisons)
    laufend = laufende_saison(saisons, heute)
    if laufend is not None:
        return laufend
    vorbei = [s for s in saisons if s.ende < heute]
    return max(vorbei, key=lambda s: s.ende) if vorbei else None


def naechste_saison(saisons: Iterable[Saison], heute: date) -> Optional[Saison]:
    """Die geplante Saison, die als naechste beginnt; None, wenn keine geplant ist."""
    geplant = [s for s in saisons if s.beginn > heute]
    return min(geplant, key=lambda s: s.beginn) if geplant else None


def saison_fuer_vorschlag(saisons: Iterable[Saison], heute: date) -> Optional[Saison]:
    """
    Die Saison, die neue Teamlinks als Vorschlag bekommen: die laufende, sonst die
    naechste geplante. Ein Team nach Anlass, das vor dem Saisonbeginn angelegt wird
    (etwa fuer die BDK), traegt so schon den Namen der Saison, in die es faellt, und
    landet mit ihrem Beginn nicht unter "Vergangene Saisons". None ohne beides (dann
    gilt die aktuelle Saison).
    """
    saisons = list(saisons)
    return laufende_saison(saisons, heute) or naechste_saison(saisons, heute)
