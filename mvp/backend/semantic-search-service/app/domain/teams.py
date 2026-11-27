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

import re
from dataclasses import dataclass
from typing import Collection, Dict, Optional

TEAM_NAME_MAX = 40
SAISON_MAX = 20

# Zeichen, die ein Saisonname nicht enthalten darf, gleich ob er als Saison angelegt
# (domain/saisons.py) oder an einem Teamlink eingegeben wird (api/v1/einladungen.py):
# Teams zaehlen nur zusammen, wenn ihr Saisonname gleich ist. Kein Markup, kein
# Rueckstrich, keine Steuerzeichen. Der Schraegstrich ist erlaubt („Winter 26/27“): Der
# Saisonname steht in keiner Adresse und keinem Pfad, Saisons gehen ueber ihre ID.
SAISON_VERBOTEN = re.compile(r'[<>&"\\\x00-\x1f\x7f]')

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

# Teamart an der Einladung (GLOSSARY.md "Team"). Ein Team nach Gruppe traegt den
# Namen einer Gruppe, die oeffentlich unter diesem Namen auftritt und vorher
# schriftlich und widerruflich zugestimmt hat; das Datum dieser Zustimmung steht an
# der Einladung, nur als Nachweis fuer Admins. Die Gruppe bekommt nie Namen, Listen
# oder eigene Zahlen und steuert nichts (GLOSSARY.md "Team", Bedingungen).
# Beschriftungen im Admin-Formular: TEAM_ARTEN in frontend shared/teams/teams.ts.
TEAM_ART_ANLASS = "anlass"
TEAM_ART_GRUPPE = "gruppe"

# Hinweis fuer das Admin-Formular (Teamname).
TEAMNAME_HINWEIS = (
    "Anlass, Ort, Saison oder öffentliche Gruppe mit schriftlicher Zustimmung; "
    "keine Namen zu Religion, Gesundheit, sexueller Orientierung, Herkunft oder "
    "Gewerkschaft."
)

# --- Einwilligung zur Mitgliedschaft -------------------------------------------

EINWILLIGUNG_KENNUNG = "team-2026-11-26"

# {team} steht fuer den Namen des Teams. Fruehere Wortlaute bleiben stehen, damit
# vorhandene Nachweise (Kennung an der Mitgliedschaft) lesbar bleiben; fuer neue
# Einwilligungen gilt nur, was in EINWILLIGUNG_GELTEND steht.
EINWILLIGUNG_WORTLAUTE: Dict[str, str] = {
    "team-2026-11-25": (
        "Ich willige ausdrücklich ein, dass Gut gesagt an meinem Konto speichert, "
        "dass ich im Team {team} bin, mit meiner Nummer und dem Tag des Beitritts, "
        "und dass die Zahl meiner Beiträge und Bewertungen in eine Summe meines "
        "Teams eingeht (Art. 9 Abs. 2 lit. a DSGVO). Meine Teams sehe nur ich, die "
        "Summe nur Mitglieder des Teams, nie mit einzelnen Namen. Ich kann die "
        "Einwilligung jederzeit unter „Meine Teams“ mit „Team verlassen“ widerrufen; "
        "dann wird der Eintrag sofort gelöscht."
    ),
    "team-2026-11-26": (
        "Ich willige ausdrücklich ein, dass Gut gesagt an meinem Konto speichert, "
        "dass ich im Team {team} bin, mit meiner Nummer und dem Tag des Beitritts, "
        "und dass die Zahl meiner Beiträge, Bewertungen und Kommentare und meiner "
        "Meldungen „Ja, gepostet“ in eine Summe meines Teams eingeht (Art. 9 Abs. 2 "
        "lit. a DSGVO). Meine Teams sehe nur ich, die Summe nur Mitglieder des "
        "Teams, nie mit einzelnen Namen. Ich kann die Einwilligung jederzeit unter "
        "„Meine Teams“ mit „Team verlassen“ widerrufen; dann wird der Eintrag "
        "sofort gelöscht."
    ),
}

# Kennungen, die neue Einwilligungen tragen duerfen. Eine fruehere Kennung wird bei
# neuen Anfragen abgelehnt wie eine unbekannte; bestehende Mitgliedschaften mit ihr
# bleiben unangetastet.
EINWILLIGUNG_GELTEND = frozenset({EINWILLIGUNG_KENNUNG})

# Die Knoepfe tragen die Erklaerung, gleichwertig nebeneinander.
KNOPF_JA = "Ja, speichert, dass ich im Team {team} bin"
KNOPF_NEIN = "Nein, ohne Team weiter"

# --- Einwilligung "Team öffentlich am Namen zeigen" ------------------------------

# Wortlaut noch nicht juristisch geprueft: Er wird erst gezeigt, wenn der Schalter
# teams_oeffentlich wirkt, und der bleibt aus, bis Datenschutzbeauftragte und Jura ihn
# freigegeben haben (dabei auch den Satz der Datenschutzerklaerung zur Speicherung
# dieser Antwort mit Kennung und Zeitpunkt vorlegen).
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


def wortlaut_pruefen(kennung: str, wortlaute: Collection[str]) -> str:
    """Kennung zurueck, wenn sie in ``wortlaute`` steht, sonst UnbekannterWortlaut."""
    if kennung not in wortlaute:
        raise UnbekannterWortlaut(kennung)
    return kennung
