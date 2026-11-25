"""
Teams ueber Einladungen (GLOSSARY.md "Team"): Grenzen, Motive und die Wortlaute der
beiden Einwilligungen.

Die Zugehoerigkeit zu einem Team kann zusammen mit dem Teamnamen auf politische
Haltung und Ort schliessen lassen (Art. 9 DSGVO). Gespeichert wird sie deshalb nur
mit einer eigenen, ausdruecklichen Einwilligung (Art. 6 Abs. 1 lit. a, Art. 9 Abs. 2
lit. a DSGVO), getrennt von der Art.-9-Einwilligung zur Mitwirkung und von "Punkte
und Meilensteine". Am Namen erscheinen Teams nur mit einer zweiten, eigenen
Einwilligung und nur, solange der Schalter ``teams_oeffentlich`` an ist.

Jeder Wortlaut traegt eine Kennung; wer ihn aendert, legt eine neue Kennung an und
laesst die alte stehen (wie domain/art9_einwilligung.py).
"""

from dataclasses import dataclass
from typing import Dict, Optional

TEAM_NAME_MAX = 40
SAISON_MAX = 20

# Motive wie bei den Meilensteinen (Fluent Emoji, Frontend public/meilensteine/<schluessel>.svg),
# immer mit Namen daneben. Schluessel -> Name.
MOTIVE: Dict[str, str] = {
    "vogel": "Vogel",
    "sprechblase": "Sprechblase",
    "handschlag": "Handschlag",
    "laufschuh": "Laufschuh",
    "waage": "Waage",
    "lautsprecher": "Lautsprecher",
}

# Hinweis fuer das Admin-Formular (Teamname).
TEAMNAME_HINWEIS = (
    "Nur nach Anlass, Ort oder Saison benennen, etwa „BDK 26 Berlin“ oder "
    "„Bayreuth“. Nie nach Personen und nie nach weiteren sensiblen Merkmalen "
    "(Gesundheit, Religion, Orientierung)."
)

# --- Einwilligung zur Mitgliedschaft -------------------------------------------

EINWILLIGUNG_KENNUNG = "team-2026-11-24"

# {team} steht fuer den Namen des Teams.
EINWILLIGUNG_WORTLAUTE: Dict[str, str] = {
    "team-2026-11-24": (
        "Ich willige ausdrücklich ein, dass Gut gesagt an meinem Konto speichert, "
        "dass ich im Team {team} bin, mit meiner Nummer und dem Tag des Beitritts "
        "(Art. 9 Abs. 2 lit. a DSGVO). Das sehe nur ich. Ich kann die Einwilligung "
        "jederzeit unter „Meine Teams“ mit „Team verlassen“ widerrufen; dann wird "
        "der Eintrag sofort gelöscht."
    ),
}

# Die Knoepfe tragen die Erklaerung, gleichwertig nebeneinander.
KNOPF_JA = "Ja, speichert, dass ich im Team {team} bin"
KNOPF_NEIN = "Nein, ohne Team weiter"

# --- Einwilligung "Team öffentlich am Namen zeigen" ------------------------------

OEFFENTLICH_KENNUNG = "team-oeffentlich-2026-11-25"

OEFFENTLICH_WORTLAUTE: Dict[str, str] = {
    "team-oeffentlich-2026-11-25": (
        "Ich willige ausdrücklich ein, dass andere Angemeldete an meinem Namen sehen, "
        "in welchen Teams der aktuellen Saison ich bin (Art. 9 Abs. 2 lit. a DSGVO). "
        "Besucher ohne Anmeldung sehen es nie. Ich kann das jederzeit unter "
        "„Meine Teams“ zurücknehmen; dann verschwinden die Teams sofort von meinem "
        "Namen."
    ),
}


@dataclass(frozen=True)
class TeamPille:
    """Ein Team am Anzeigenamen (nur aktuelle Saison, nur mit Einwilligung)."""

    name: str
    motiv: Optional[str]
    # Name des Motivs fuer Alt-Text und Beschriftung
    motiv_name: Optional[str]

    @classmethod
    def aus(cls, name: str, motiv: Optional[str]) -> "TeamPille":
        return cls(name=name, motiv=motiv, motiv_name=MOTIVE.get(motiv or ""))


class UnbekannterWortlaut(ValueError):
    """Die Kennung gehoert zu keinem bekannten Wortlaut."""


def wortlaut_pruefen(kennung: str, wortlaute: Dict[str, str]) -> str:
    if kennung not in wortlaute:
        raise UnbekannterWortlaut(kennung)
    return kennung
