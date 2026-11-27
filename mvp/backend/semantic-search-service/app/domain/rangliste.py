"""
Rangliste je Saison mit eigener Einwilligung (#793, ADR 0004 "Ranglisten nur mit
Zustimmung", GLOSSARY.md "Rangliste").

Zuschnitt laut #793:
- Sehen koennen die Rangliste nur Angemeldete, die selbst eingewilligt haben und
  selbst darin stehen; sie ist nicht oeffentlich.
- Bezugsgroesse sind die Punkte nach ADR 0004 innerhalb der laufenden Saison.
- Gezeigt werden die ersten zehn Plaetze und der eigene Platz, und erst ab zehn
  Teilnehmenden (``MIN_TEILNEHMENDE``).
- Jede Person erscheint mit einem zufaelligen Ranglistennamen ohne Freitext
  (``neuer_ranglistenname``); den Anzeigenamen nur, wenn sie ihn aktiv waehlt.

Dieses Modul ist rein (keine Datenbank, keine Uhr): Wortlaut, Ranglistenname und wie
aus Punkten Plaetze werden. Wer teilnimmt, entscheidet services/rangliste_service.py.

Der Wortlaut traegt eine Kennung wie die anderen Einwilligungen; wer ihn aendert,
legt eine neue Kennung an und laesst die alte stehen.
"""

import random
import secrets
from dataclasses import dataclass
from typing import Collection, Dict, List, Optional

AKTUELLER_WORTLAUT = "rangliste-2026-11-25"

# Wortgleich aus #793; geht vor dem Einschalten zur juristischen Freigabe.
WORTLAUTE: Dict[str, str] = {
    "rangliste-2026-11-25": (
        "Ich willige ausdrücklich ein, dass ich in der Rangliste der laufenden Saison "
        "erscheine, mit meinem Ranglistennamen, meinem Platz und meinen Punkten "
        "(Art. 9 Abs. 2 lit. a DSGVO). Der Ranglistenname wird zufällig vergeben, außer "
        "ich wähle selbst meinen Anzeigenamen. Sehen können die Rangliste nur "
        "Angemeldete, die selbst mitmachen, und erst ab zehn Teilnehmenden. Daraus "
        "lässt sich schließen, dass und wie stark ich mich bei Gut gesagt engagiere. "
        "Angemeldet sind nicht nur Mitglieder, und Screenshots kann Gut gesagt nicht "
        "verhindern. Ich kann die Einwilligung jederzeit unter „Meine Beiträge“ "
        "widerrufen; dann verschwinde ich sofort aus der Rangliste."
    ),
}

# Erst ab so vielen Teilnehmenden zeigt die Rangliste Plaetze (#793).
MIN_TEILNEHMENDE = 10
# So viele Plaetze stehen oben; der eigene kommt dazu, wenn er darunter liegt.
PLAETZE = 10

# Ranglistennamen: Eigenschaft und Tier, beide weiblich, damit die Endung immer passt,
# dazu eine Zahl. Feste Listen ohne Freitext: Niemand kann darueber etwas mitteilen.
EIGENSCHAFTEN = (
    "Flinke",
    "Kluge",
    "Mutige",
    "Ruhige",
    "Heitere",
    "Wache",
    "Kühne",
    "Stille",
    "Frische",
    "Treue",
    "Freundliche",
    "Muntere",
    "Findige",
    "Gelassene",
    "Wendige",
    "Fröhliche",
)
TIERE = (
    "Amsel",
    "Eule",
    "Lerche",
    "Meise",
    "Biene",
    "Hummel",
    "Libelle",
    "Möwe",
    "Schwalbe",
    "Elster",
    "Drossel",
    "Robbe",
    "Katze",
    "Ente",
    "Gämse",
    "Krähe",
)


class UnbekannterWortlaut(ValueError):
    """Die Kennung gehoert zu keinem bekannten Wortlaut."""


# So oft wird gewuerfelt, bevor ein schon vergebener Name doch genommen wird; die
# Liste macht gleiche Namen dann unterscheidbar (``rangliste_bilden``).
NAMEN_VERSUCHE = 50
# Ersatz, falls eine Kennung ohne gespeicherten Namen in die Liste kaeme
OHNE_NAMEN = "Ohne Namen"

_zufall = secrets.SystemRandom()


def neuer_ranglistenname(
    vergeben: Collection[str], zufall: random.Random = _zufall
) -> str:
    """
    Ein zufaelliger Ranglistenname wie „Flinke Amsel 42“, moeglichst keiner aus
    ``vergeben``. Echt zufaellig und beim ersten Ja gespeichert
    (rangliste_einwilligung.ranglistenname), nicht aus der Kennung abgeleitet: Wer
    eine Kennung kennt, etwa aus der Moderation oder aus Logs, kann den Namen nicht
    ausrechnen (Review zu #793). Die Person behaelt ihn, auch ueber Saisons hinweg.
    """
    name = ""
    for _ in range(NAMEN_VERSUCHE):
        name = (
            f"{zufall.choice(EIGENSCHAFTEN)} {zufall.choice(TIERE)} "
            f"{zufall.randint(10, 99)}"
        )
        if name not in vergeben:
            break
    return name


@dataclass(frozen=True)
class Platz:
    platz: int
    name: str
    punkte: int
    # Der eigene Eintrag der fragenden Person
    ich: bool
    # Erreichte Meilensteine ohne Wegmarken; nur im Spielgefuehl-Modell
    # (domain/spielgefuehl.py), dort erscheinen Abzeichen nur in der Rangliste
    abzeichen: Optional[int] = None


@dataclass(frozen=True)
class Rangliste:
    # Die ersten PLAETZE Eintraege, bei gleichen Punkten gleicher Platz
    oben: List[Platz]
    # Der eigene Eintrag, wenn er nicht schon oben steht
    eigener: Optional[Platz]
    teilnehmende: int


def rangliste_bilden(
    punkte: Dict[str, int],
    namen: Dict[str, str],
    ich: str,
    abzeichen: Optional[Dict[str, int]] = None,
) -> Optional[Rangliste]:
    """
    Plaetze aus den Saisonpunkten der Teilnehmenden (Kennung -> Punkte) und ihren
    Namen in der Liste (Kennung -> Ranglistenname oder gewaehlter Anzeigename). None
    unter MIN_TEILNEHMENDE. Gleiche Punkte teilen sich den Platz (1, 2, 2, 4);
    innerhalb gleicher Punkte ordnet der Name, damit die Reihenfolge stabil bleibt.
    Steht ein Name mehrmals in der Liste, bekommt jeder weitere eine Nummer
    („Flinke Amsel 42 (2)“), damit sich niemand mit einem anderen verwechselt.
    ``abzeichen`` (Kennung -> Zahl) steht, wo vorhanden, am Platz.
    """
    if len(punkte) < MIN_TEILNEHMENDE:
        return None
    reihe = sorted(punkte, key=lambda k: (-punkte[k], namen.get(k, ""), k))
    plaetze: List[Platz] = []
    vorige: Optional[int] = None
    platz = 0
    gezeigt: Dict[str, int] = {}
    for index, kennung in enumerate(reihe):
        if punkte[kennung] != vorige:
            platz = index + 1
            vorige = punkte[kennung]
        name = namen.get(kennung) or OHNE_NAMEN
        gezeigt[name] = gezeigt.get(name, 0) + 1
        if gezeigt[name] > 1:
            name = f"{name} ({gezeigt[name]})"
        plaetze.append(
            Platz(
                platz=platz,
                name=name,
                punkte=punkte[kennung],
                ich=kennung == ich,
                abzeichen=(abzeichen or {}).get(kennung),
            )
        )
    oben = plaetze[:PLAETZE]
    eigener = next((p for p in plaetze[PLAETZE:] if p.ich), None)
    return Rangliste(oben=oben, eigener=eigener, teilnehmende=len(plaetze))
