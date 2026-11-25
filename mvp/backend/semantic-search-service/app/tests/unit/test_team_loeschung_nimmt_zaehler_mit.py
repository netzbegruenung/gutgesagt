"""
Wochenzaehler und Quests "entfallen mit dem Team" (docs/LOESCHKONZEPT.md, #813).

Ein Team ist Teamname plus Saison. Eine Team-Loeschung gibt es noch nicht: Einladungen
lassen sich nur abschalten oder aendern, Mitgliedschaften gehen einzeln ("Team
verlassen", Kontoloeschung), team_nummern bleibt. Damit eine kuenftige Team-Loeschung
die Zeilen in team_wochen und team_quests nicht vergisst, sucht dieser Test jede Stelle
im Code und in den SQL-Skripten, die Einladungen oder den Nummernzaehler eines Teams
loescht, und verlangt dort auch team_wochen und team_quests (ein Aufruf von
TeamFortschrittRepository.team_loeschen oder ein DELETE auf beide Tabellen; ein
blosses Erwaehnen, etwa im Kommentar, reicht nicht).

Grenzen der Suche: Sie liest Python-, SQL- und Shell-Dateien und erkennt die ueblichen
Formen (DELETE, TRUNCATE, DROP TABLE, auch mit Schema oder Anfuehrungszeichen;
delete(...) und .delete() an Modell oder Tabelle; session.delete in Dateien, die die
Modelle nutzen). SQL, dessen Tabellenname erst zur Laufzeit entsteht (f-String aus
einer Liste), sieht sie nicht; wer so etwas baut, prueft es selbst.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

APP = Path(__file__).resolve().parents[2]
MVP = APP.parents[2]
QUELLEN = [APP, MVP / "scripts", MVP / "backend" / "postgres-app"]

# Was ein Team endgueltig verschwinden liesse.
_TABELLE = r"""(\w+\.)?["`]?(einladungen|team_nummern)\b"""
_MODELL = r"(EinladungZeile|TeamNummerZeile)"
TEAM_LOESCHEN = re.compile(
    rf"(DELETE\s+FROM|TRUNCATE(\s+TABLE)?|DROP\s+TABLE(\s+IF\s+EXISTS)?)\s+{_TABELLE}"
    rf"|delete\(\s*{_MODELL}"
    rf"|{_MODELL}\b[^\n]*\.delete\(",
    re.IGNORECASE,
)
SESSION_DELETE = re.compile(r"\.delete\(\s*\w")
MODELL = re.compile(_MODELL)
_ZAEHLER = r"(\w+\.)?[\"`]?{tabelle}\b"
MIT_ZAEHLER = (
    re.compile(
        r"\.team_loeschen\(|DELETE\s+FROM\s+"
        + _ZAEHLER.format(tabelle="team_wochen")
        + r"|delete\(\s*TeamWocheZeile",
        re.IGNORECASE,
    ),
    re.compile(
        r"\.team_loeschen\(|DELETE\s+FROM\s+"
        + _ZAEHLER.format(tabelle="team_quests")
        + r"|delete\(\s*TeamQuestZeile",
        re.IGNORECASE,
    ),
)


def loescht_team(text: str) -> bool:
    return bool(
        TEAM_LOESCHEN.search(text)
        or (MODELL.search(text) and SESSION_DELETE.search(text))
    )


def stellen_ohne_zaehler(texte):
    """Namen der Texte, die ein Team loeschen, ohne Wochenzaehler und Quests mitzunehmen."""
    return [
        name
        for name, text in texte
        if loescht_team(text) and not all(m.search(text) for m in MIT_ZAEHLER)
    ]


def _dateien():
    for wurzel in QUELLEN:
        for pfad in wurzel.rglob("*"):
            if pfad.suffix not in (".py", ".sql", ".sh") or "tests" in pfad.parts:
                continue
            if "venv" in pfad.parts or "node_modules" in pfad.parts:
                continue
            yield str(pfad.relative_to(MVP)), pfad.read_text(encoding="utf-8")


def test_jede_team_loeschung_nimmt_wochenzaehler_und_quests_mit():
    assert stellen_ohne_zaehler(_dateien()) == [], (
        "Ein Team verschwindet hier; team_wochen und team_quests muessen mit "
        "(TeamFortschrittRepository.team_loeschen, docs/LOESCHKONZEPT.md)."
    )


def test_heute_gibt_es_keine_team_loeschung():
    # Kommt eine, faellt dieser Test auch bei richtiger Loeschung auf: dann ARCHITECTURE
    # und Loeschkonzept nachziehen und diesen Test entfernen; der erste bleibt.
    assert [n for n, t in _dateien() if loescht_team(t)] == []


@pytest.mark.parametrize(
    "text, auffaellig",
    [
        ("DELETE FROM einladungen WHERE id = :id", True),
        ("session.execute(delete(TeamNummerZeile).where(...))", True),
        (
            "DELETE FROM team_nummern ...; DELETE FROM team_wochen ...; "
            "DELETE FROM team_quests ...",
            False,
        ),
        ("delete(EinladungZeile); repo.team_loeschen(name, saison)", False),
        ("DELETE FROM team_mitgliedschaften WHERE konto_kennung = :uid", False),
        ('DELETE FROM public."einladungen"', True),
        ("TRUNCATE team_nummern", True),
        ("DROP TABLE IF EXISTS einladungen", True),
        ("session.query(EinladungZeile).filter(x).delete()", True),
        ("EinladungZeile.__table__.delete()", True),
        ("delete(TeamNummerZeile.__table__)", True),
        ("zeile = session.get(EinladungZeile, i)\nsession.delete(zeile)", True),
        ("delete(EinladungZeile)  # team_wochen, TeamQuestZeile erwaehnt", True),
        (
            "delete(EinladungZeile); DELETE FROM team_wochen; DELETE FROM team_quests",
            False,
        ),
    ],
)
def test_die_suche_selbst(text, auffaellig):
    assert bool(stellen_ohne_zaehler([("x", text)])) is auffaellig
