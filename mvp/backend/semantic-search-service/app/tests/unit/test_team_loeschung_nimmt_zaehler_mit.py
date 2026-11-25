"""
Wochenzaehler und Quests "entfallen mit dem Team" (docs/LOESCHKONZEPT.md, #813).

Ein Team ist Teamname plus Saison. Eine Team-Loeschung gibt es noch nicht: Einladungen
lassen sich nur abschalten oder aendern, Mitgliedschaften gehen einzeln ("Team
verlassen", Kontoloeschung), team_nummern bleibt. Damit eine kuenftige Team-Loeschung
die Zeilen in team_wochen und team_quests nicht vergisst, sucht dieser Test jede Stelle
im Code und in den SQL-Skripten, die Einladungen oder den Nummernzaehler eines Teams
loescht, und verlangt dort auch team_wochen und team_quests (etwa ueber
TeamFortschrittRepository.team_loeschen).
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

APP = Path(__file__).resolve().parents[2]
MVP = APP.parents[2]
QUELLEN = [APP, MVP / "scripts", MVP / "backend" / "postgres-app"]

# Was ein Team endgueltig verschwinden liesse.
TEAM_LOESCHEN = re.compile(
    r"DELETE\s+FROM\s+(einladungen|team_nummern)\b"
    r"|delete\(\s*(EinladungZeile|TeamNummerZeile)\s*\)",
    re.IGNORECASE,
)
MIT_ZAEHLER = (
    re.compile(r"team_wochen|TeamWocheZeile|team_loeschen"),
    re.compile(r"team_quests|TeamQuestZeile|team_loeschen"),
)


def stellen_ohne_zaehler(texte):
    """Namen der Texte, die ein Team loeschen, ohne Wochenzaehler und Quests mitzunehmen."""
    return [
        name
        for name, text in texte
        if TEAM_LOESCHEN.search(text) and not all(m.search(text) for m in MIT_ZAEHLER)
    ]


def _dateien():
    for wurzel in QUELLEN:
        for pfad in wurzel.rglob("*"):
            if pfad.suffix not in (".py", ".sql") or "tests" in pfad.parts:
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
    # Kommt eine, faellt dieser Test auf: dann ARCHITECTURE und Loeschkonzept nachziehen.
    assert [n for n, t in _dateien() if TEAM_LOESCHEN.search(t)] == []


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
    ],
)
def test_die_suche_selbst(text, auffaellig):
    assert bool(stellen_ohne_zaehler([("x", text)])) is auffaellig
