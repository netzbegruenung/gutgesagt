"""
Die Themen: eine feste, kurze Liste, mit der Aussagen geordnet werden (Glossar
"Thema"). Freie Schlagworte gibt es nicht.

Die Liste steht in themen.json neben dieser Datei und wird per PR gepflegt. Der
Schluessel ist das, was an einer Aussage gespeichert wird; der Name ist nur die
Anzeige und darf sich aendern. Ein Schluessel, der wegfaellt, laesst seine
Zuordnungen in der Datenbank stehen; sie werden dann nicht mehr angezeigt
(AussageThemenService).

Das Motiv ist der Pfad eines SVG unter public/ im Frontend, etwa "themen/klima.svg":
ein Fluent-Emoji im Stil der Meilensteine, bei Europa eine eigene Zeichnung
(public/themen/HINWEIS-EUROPA.txt). Es ist rein dekorativ, der Name steht immer
daneben. Dass jedes Thema eins hat und die Datei existiert, pruefen
tests/unit/domain/test_themen.py und scripts/tests/test_themen_motive.py.

Die Stichwoerter sind gaengige Begriffe aus der Kommentarspalten-Debatte zum Thema. Sie
haengen nicht an Aussagen, sondern ordnen nur kurze Sucheingaben einem Thema zu
("Alles zum Thema", domain/themen_abgleich.py, #754). Ein Begriff steht bei genau
einem Thema; das prueft test_themen.py.
"""

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Dict, Iterable, List, Tuple

from pydantic import AfterValidator

from core.fehler import Validierungsfehler

# Glossar: "eine Aussage hat hoechstens drei".
HOECHSTENS_JE_AUSSAGE = 3
# Beim Einwerfen nur ein erster Fingerzeig (Glossar "Thema"): hoechstens zwei.
HOECHSTENS_JE_EINWURF = 2

_DATEI = Path(__file__).with_name("themen.json")


@dataclass(frozen=True)
class Thema:
    schluessel: str
    name: str
    motiv: str
    stichwoerter: Tuple[str, ...] = ()


class Zuordnungsart(StrEnum):
    """
    Wie ein Thema an eine Aussage kam. Nur die Zuordnungen von Hand taugen als
    Testset; eine spaetere Automatik (#401) bekommt einen eigenen Wert.
    """

    VON_HAND = "von_hand"


class ThemaUngueltig(Validierungsfehler):
    """Ein Schluessel steht nicht in der Liste, doppelt, oder es sind zu viele."""


def _laden() -> Tuple[Thema, ...]:
    with _DATEI.open(encoding="utf-8") as datei:
        return tuple(
            Thema(
                e["schluessel"],
                e["name"],
                e["motiv"],
                tuple(e.get("stichwoerter", ())),
            )
            for e in json.load(datei)
        )


THEMEN: Tuple[Thema, ...] = _laden()
NACH_SCHLUESSEL: Dict[str, Thema] = {t.schluessel: t for t in THEMEN}


def themen_pruefen(schluessel: Iterable[str]) -> List[str]:
    """
    Die Themen einer Zuordnung, ohne Doppelte und in der gegebenen Reihenfolge.
    Leer ist erlaubt (die Zuordnung ist optional).

    Raises:
        ThemaUngueltig: ein Schluessel steht nicht in der Liste, oder es sind
            mehr als HOECHSTENS_JE_AUSSAGE.
    """
    ergebnis: List[str] = []
    for eintrag in schluessel:
        if eintrag not in NACH_SCHLUESSEL:
            raise ThemaUngueltig(f"Unbekanntes Thema: {eintrag!r}")
        if eintrag not in ergebnis:
            ergebnis.append(eintrag)
    if len(ergebnis) > HOECHSTENS_JE_AUSSAGE:
        raise ThemaUngueltig(
            f"Hoechstens {HOECHSTENS_JE_AUSSAGE} Themen je Aussage, nicht {len(ergebnis)}"
        )
    return ergebnis


# Die Themen einer Aussage in einer Anfrage, geprueft, bevor etwas gespeichert wird:
# Sonst stuende der Beitrag oder die Aussage schon, ohne Themen.
ThemenDerAussage = Annotated[List[str], AfterValidator(themen_pruefen)]


def einwurf_themen_pruefen(schluessel: Iterable[str]) -> List[str]:
    """
    Die Themen eines Einwurfs, in der gegebenen Reihenfolge. Leer ist erlaubt: Einwerfen
    bleibt ohne Thema so schnell wie vorher.

    Strenger als bei der Aussage: Ein doppelter Schluessel wird abgewiesen statt
    zusammengefasst, denn das Formular schickt nie einen; kommt einer, ist der Aufrufer
    kaputt, und das soll er erfahren.

    Raises:
        ThemaUngueltig: ein Schluessel steht nicht in der Liste, steht doppelt da, oder
            es sind mehr als HOECHSTENS_JE_EINWURF.
    """
    ergebnis: List[str] = []
    for eintrag in schluessel:
        if eintrag not in NACH_SCHLUESSEL:
            raise ThemaUngueltig(f"Unbekanntes Thema: {eintrag!r}")
        if eintrag in ergebnis:
            raise ThemaUngueltig(f"Thema doppelt: {eintrag!r}")
        ergebnis.append(eintrag)
    if len(ergebnis) > HOECHSTENS_JE_EINWURF:
        raise ThemaUngueltig(
            f"Hoechstens {HOECHSTENS_JE_EINWURF} Themen je Einwurf, nicht {len(ergebnis)}"
        )
    return ergebnis


ThemenDesEinwurfs = Annotated[List[str], AfterValidator(einwurf_themen_pruefen)]
