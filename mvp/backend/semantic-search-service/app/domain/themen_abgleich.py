"""
Kurze Sucheingaben einem Thema zuordnen ("Alles zum Thema", #754).

Ein einzelnes Wort wie "Heizung" liegt in der semantischen Suche oft unter der Schwelle
und findet nichts. Passt eine Eingabe aus einem bis drei Woertern zu einem Stichwort oder
zum Namen eines Themas (domain/themen.json), zeigt die Ergebnisseite oben die Aussagen
dieses Themas. Die Treffer der Suche bleiben davon unberuehrt.

Abgeglichen wird ohne Modell, nur normalisiert:
- Kleinschreibung; ae/oe/ue/ss statt Umlaut und Eszett, damit "Waermepumpe" und
  "Wärmepumpe" gleich sind; Bindestriche fallen weg ("E-Auto" = "EAuto"), andere
  Satzzeichen trennen Woerter.
- Einfache Wortformen: Endungen wie -en, -er, -e, -n, -s fallen weg, solange vier
  Buchstaben bleiben ("Heizungen" = "Heizung", "Flüchtling" = "Flüchtlinge").
- Ein Stichwort trifft, wenn seine Woerter zusammenhaengend in der Eingabe stehen
  ("neue Heizung"). Ein Wort der Eingabe, das mit einem Stichwort ab sechs Buchstaben
  beginnt, trifft schwaecher ("Heizungskosten" ueber "Heizung"): Kuerzere Stichwoerter
  wie "Auto" oder "trans" stuenden sonst am Anfang fremder Woerter ("Autor", "Transport").

Der Name eines Themas zaehlt wie ein Stichwort, ebenso jeder Teil vor und nach "und"
("Ernährung" aus "Landwirtschaft und Ernährung").

Die Eingabe wird nur im Speicher verglichen, nicht gespeichert und nicht geloggt.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from domain.themen import THEMEN, Thema

HOECHSTENS_WOERTER = 3
"""Laengere Eingaben sind Saetze; fuer sie ist die semantische Suche da."""

HOECHSTENS_THEMEN = 2
"""Mehrere Treffer: hoechstens zwei Themen, sonst wird der Kasten zur Themenliste."""

PRAEFIX_AB = 6
"""Ab so vielen Buchstaben trifft ein Stichwort auch am Anfang eines laengeren Worts."""

_ENDUNGEN = ("innen", "en", "er", "es", "e", "n", "s")
_STAMM_MINDESTENS = 4
_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})

# Treffergueten: genau (alle Woerter des Stichworts) vor Wortanfang.
_GENAU = 2
_ANFANG = 1


def _woerter(text: str) -> List[str]:
    """Kleingeschrieben, ohne Umlaute und Bindestriche, an Satzzeichen getrennt."""
    flach = text.casefold().translate(_UMLAUTE).replace("-", "").replace("‑", "")
    return [w for w in re.split(r"[^0-9a-z]+", flach) if w]


def _stamm(wort: str) -> str:
    """Einfache Wortform: Endungen abschneiden, solange vier Buchstaben bleiben."""
    geaendert = True
    while geaendert:
        geaendert = False
        for endung in _ENDUNGEN:
            if wort.endswith(endung) and len(wort) - len(endung) >= _STAMM_MINDESTENS:
                wort = wort[: -len(endung)]
                geaendert = True
                break
    return wort


@dataclass(frozen=True)
class _Begriff:
    staemme: Tuple[str, ...]
    # Normalisiert, ungestemmt: fuer den Abgleich am Wortanfang (nur einteilige).
    flach: str


def begriffe(thema: Thema) -> List[str]:
    """Stichwoerter, Name und Namensteile eines Themas, wie der Abgleich sie kennt."""
    teile = [t.strip() for t in re.split(r"\bund\b", thema.name) if t.strip()]
    return list(dict.fromkeys([*thema.stichwoerter, thema.name, *teile]))


def normalisiert(begriff: str) -> Tuple[str, ...]:
    """Die Wortstaemme eines Begriffs; gleich heisst: trifft dieselben Eingaben."""
    return tuple(_stamm(w) for w in _woerter(begriff))


def _verzeichnis(themen: Sequence[Thema]) -> List[Tuple[Thema, List[_Begriff]]]:
    ergebnis = []
    for thema in themen:
        liste = []
        for begriff in begriffe(thema):
            woerter = _woerter(begriff)
            if woerter:
                liste.append(
                    _Begriff(
                        tuple(_stamm(w) for w in woerter),
                        woerter[0] if len(woerter) == 1 else "",
                    )
                )
        ergebnis.append((thema, liste))
    return ergebnis


_VERZEICHNIS = _verzeichnis(THEMEN)


def _enthaelt(folge: Tuple[str, ...], teil: Tuple[str, ...]) -> bool:
    n = len(teil)
    return any(folge[i : i + n] == teil for i in range(len(folge) - n + 1))


def passende_themen(
    eingabe: str, verzeichnis: Optional[List[Tuple[Thema, List[_Begriff]]]] = None
) -> List[Thema]:
    """
    Die Themen, zu denen eine kurze Eingabe passt, bestes zuerst, hoechstens
    HOECHSTENS_THEMEN. Leer bei mehr als HOECHSTENS_WOERTER Woertern (gezaehlt an
    Leerraum) oder ohne Treffer.

    Reihenfolge: genaue Treffer vor Treffern am Wortanfang, dann mehr getroffene
    Woerter, dann die Reihenfolge der Themenliste.
    """
    if verzeichnis is None:
        verzeichnis = _VERZEICHNIS
    if len(eingabe.split()) > HOECHSTENS_WOERTER:
        return []
    woerter = _woerter(eingabe)
    if not woerter:
        return []
    staemme = tuple(_stamm(w) for w in woerter)

    bewertung: Dict[int, Tuple[int, int]] = {}
    for platz, (thema, liste) in enumerate(verzeichnis):
        beste = (0, 0)
        for begriff in liste:
            if _enthaelt(staemme, begriff.staemme):
                guete = (_GENAU, len(begriff.staemme))
            elif len(begriff.flach) >= PRAEFIX_AB and any(
                w.startswith(begriff.flach) for w in woerter
            ):
                guete = (_ANFANG, 1)
            else:
                continue
            beste = max(beste, guete)
        if beste > (0, 0):
            bewertung[platz] = beste

    reihenfolge = sorted(
        bewertung, key=lambda p: (-bewertung[p][0], -bewertung[p][1], p)
    )
    return [verzeichnis[p][0] for p in reihenfolge[:HOECHSTENS_THEMEN]]
