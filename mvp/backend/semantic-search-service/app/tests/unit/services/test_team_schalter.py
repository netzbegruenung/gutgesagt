"""
Schalter fuer Team-Fortschritt (#784) und Team-Quests (#792): eigene Obergrenzen, von
Haus aus aus; beide oeffentlich (die Datenschutzerklaerung haengt Saetze daran);
team_fortschritt wirkt nur mit teams, team_quests nur mit
team_fortschritt.
"""

import pytest

from core.config import Settings
from services.schalter_service import SCHALTER, SchalterService, oeffentliche_schalter

pytestmark = pytest.mark.unit

ALLE_AN = {"teams": True, "team_fortschritt": True, "team_quests": True}
OBERGRENZEN_AN = Settings(
    teams_aktiv=True, team_fortschritt_aktiv=True, team_quests_aktiv=True
)


def _dienst(werte):
    return SchalterService(
        admin_werte_lesen=lambda: dict(werte),
        admin_wert_setzen=lambda *a: None,
    )


@pytest.mark.parametrize(
    "name, variable",
    [
        ("team_fortschritt", "SEMANTIC_SEARCH_TEAM_FORTSCHRITT_AKTIV"),
        ("team_quests", "SEMANTIC_SEARCH_TEAM_QUESTS_AKTIV"),
    ],
)
def test_eigene_obergrenze_von_haus_aus_aus(name, variable):
    art = SCHALTER[name]
    assert art.umgebungsvariable == variable
    assert getattr(Settings(), art.feld) is False
    assert art.dsfa_hinweis
    # Nur der wirksame Wert, kein Personenbezug: die Datenschutzerklaerung braucht ihn
    assert name in oeffentliche_schalter()
    assert _dienst(ALLE_AN).wirksam(name, Settings(teams_aktiv=True)) is False


def test_alles_an_wirkt():
    dienst = _dienst(ALLE_AN)
    assert dienst.wirksam("team_fortschritt", OBERGRENZEN_AN)
    assert dienst.wirksam("team_quests", OBERGRENZEN_AN)


def test_ohne_admin_wert_aus():
    dienst = _dienst({"teams": True})
    assert not dienst.wirksam("team_fortschritt", OBERGRENZEN_AN)
    assert not dienst.wirksam("team_quests", OBERGRENZEN_AN)


def test_fortschritt_nur_mit_teams():
    dienst = _dienst({**ALLE_AN, "teams": False})
    assert not dienst.wirksam("team_fortschritt", OBERGRENZEN_AN)
    assert not dienst.wirksam("team_quests", OBERGRENZEN_AN)

    ohne_teams_obergrenze = Settings(
        team_fortschritt_aktiv=True, team_quests_aktiv=True
    )
    assert not _dienst(ALLE_AN).wirksam("team_fortschritt", ohne_teams_obergrenze)


def test_quests_nur_mit_fortschritt():
    dienst = _dienst({**ALLE_AN, "team_fortschritt": False})
    assert dienst.wirksam("teams", OBERGRENZEN_AN)
    assert not dienst.wirksam("team_quests", OBERGRENZEN_AN)

    nur_quests = Settings(teams_aktiv=True, team_quests_aktiv=True)
    assert not _dienst(ALLE_AN).wirksam("team_quests", nur_quests)


def test_stand_listet_beide():
    namen = [s.name for s in _dienst(ALLE_AN).stand(OBERGRENZEN_AN)]
    assert "team_fortschritt" in namen
    assert "team_quests" in namen


def test_einschalt_hinweise_teams():
    # Teams sind rechtlich freigegeben (25.11.), die Anzeige am Namen nicht
    from services.schalter_service import DSFA_HINWEIS

    stand = {s.name: s for s in _dienst({}).stand(OBERGRENZEN_AN)}

    assert stand["teams"].dsfa_hinweis == (
        "Rechtlich freigegeben (25.11.): darf vor dem Beschluss der DSFA eingeschaltet "
        "werden. Die Anzeige am Namen (teams_oeffentlich) bleibt aus."
    )
    # Jura vorlaeufig 26.11.: Team-Summe und Quests duerfen fuer den internen Test an,
    # die Anzeige am Namen nicht
    assert stand["teams_oeffentlich"].dsfa_hinweis.startswith("Aus lassen")
    assert stand["teams_oeffentlich"].wartet_auf_recht is True
    assert stand["team_fortschritt"].dsfa_hinweis.startswith("Jura vorläufig ok 26.11.")
    assert "Go des Vorstands" in stand["team_fortschritt"].dsfa_hinweis
    assert "ab 5 Mitgliedern" in stand["team_fortschritt"].dsfa_hinweis
    # DSE-Absatz zu Team-Quests (Jura-Nachtrag 26.11.): an nur mit team_fortschritt
    assert stand["team_quests"].dsfa_hinweis.startswith("Jura vorläufig ok 26.11.")
    assert "nur mit team_fortschritt" in stand["team_quests"].dsfa_hinweis
    for name in ("team_fortschritt", "team_quests"):
        assert stand[name].wartet_auf_recht is True
    assert DSFA_HINWEIS not in stand["team_fortschritt"].dsfa_hinweis
