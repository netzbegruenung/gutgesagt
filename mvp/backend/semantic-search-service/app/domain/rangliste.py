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
  (``ranglistenname``); den Anzeigenamen nur, wenn sie ihn aktiv waehlt.

Dieses Modul ist rein (keine Datenbank, keine Uhr): Wortlaut, Ranglistenname und wie
aus Punkten Plaetze werden. Wer teilnimmt, entscheidet services/rangliste_service.py.

Der Wortlaut traegt eine Kennung wie die anderen Einwilligungen; wer ihn aendert,
legt eine neue Kennung an und laesst die alte stehen.
"""

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional

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


def ranglistenname(user_id: str) -> str:
    """
    Der zufaellige Ranglistenname einer Kennung, etwa „Flinke Amsel 42“. Abgeleitet
    aus einem Hash der Kennung statt gespeichert: dieselbe Person heisst in jeder
    Saison gleich, und es gibt keine weitere Spalte. Aus dem Namen laesst sich die
    Kennung nicht zurueckgewinnen. Zwei Personen koennen gleich heissen (selten).
    """
    wert = int.from_bytes(
        hashlib.sha256(f"rangliste-name:{user_id}".encode("utf-8")).digest()[:8],
        "big",
    )
    eigenschaft = EIGENSCHAFTEN[wert % len(EIGENSCHAFTEN)]
    wert //= len(EIGENSCHAFTEN)
    tier = TIERE[wert % len(TIERE)]
    wert //= len(TIERE)
    return f"{eigenschaft} {tier} {10 + wert % 90}"


@dataclass(frozen=True)
class Platz:
    platz: int
    name: str
    punkte: int
    # Der eigene Eintrag der fragenden Person
    ich: bool


@dataclass(frozen=True)
class Rangliste:
    # Die ersten PLAETZE Eintraege, bei gleichen Punkten gleicher Platz
    oben: List[Platz]
    # Der eigene Eintrag, wenn er nicht schon oben steht
    eigener: Optional[Platz]
    teilnehmende: int


def rangliste_bilden(
    punkte: Dict[str, int], namen: Dict[str, str], ich: str
) -> Optional[Rangliste]:
    """
    Plaetze aus den Saisonpunkten der Teilnehmenden (Kennung -> Punkte). None unter
    MIN_TEILNEHMENDE. Gleiche Punkte teilen sich den Platz (1, 2, 2, 4); innerhalb
    gleicher Punkte ordnet der Name, damit die Reihenfolge stabil bleibt.
    """
    if len(punkte) < MIN_TEILNEHMENDE:
        return None
    reihe = sorted(punkte, key=lambda k: (-punkte[k], namen.get(k, ""), k))
    plaetze: List[Platz] = []
    vorige: Optional[int] = None
    platz = 0
    for index, kennung in enumerate(reihe):
        if punkte[kennung] != vorige:
            platz = index + 1
            vorige = punkte[kennung]
        plaetze.append(
            Platz(
                platz=platz,
                name=namen.get(kennung) or ranglistenname(kennung),
                punkte=punkte[kennung],
                ich=kennung == ich,
            )
        )
    oben = plaetze[:PLAETZE]
    eigener = next((p for p in plaetze[PLAETZE:] if p.ich), None)
    return Rangliste(oben=oben, eigener=eigener, teilnehmende=len(plaetze))
