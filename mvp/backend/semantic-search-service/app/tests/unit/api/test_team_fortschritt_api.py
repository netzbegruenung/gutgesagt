"""
Team-Fortschritt (#784) und Team-Quests (#792) in GET /api/v1/teams/meine: je eigenem
Team die Wirkung der letzten abgeschlossenen Woche (nur gerundete Texte) und die Quest.
Schalter aus: Felder null. Die Antwort traegt nie eine genaue Zahl des Zaehlers.
"""

import asyncio
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.v1.teams as teams_module
from api.v1.teams import router as teams_router
from core.config import Settings
from repositories.team_fortschritt_repository import Quest
from repositories.team_repository import Mitgliedschaft
from services.punkte_service import PunkteService
from services.team_fortschritt_service import (
    TeamFortschrittService,
    TeamQuestStand,
    TeamStand,
    TeamWirkung,
)
from services.team_service import TeamService
from tests.unit.services.test_team_fortschritt_service import (
    HEUTE,
    LAUFENDE,
    TEAM,
    VORIGE,
    Speicher,
    _team,
)

pytestmark = [pytest.mark.unit, pytest.mark.api]

AN = Settings(teams_aktiv=True, team_fortschritt_aktiv=True, team_quests_aktiv=True)
NUR_TEAMS = Settings(teams_aktiv=True)
PERSON = f"{TEAM[0]}-0"


def _mitgliedschaft(name=TEAM[0], saison=TEAM[1]):
    return Mitgliedschaft(
        id=uuid.uuid4(),
        team_name=name,
        team_motiv="vogel",
        saison=saison,
        nummer=3,
        eingetreten_am=date(2026, 11, 1),
    )


def _client(speicher, settings=AN, meine=None):
    team_repo = Mock()
    team_repo.meine.return_value = meine or [_mitgliedschaft()]
    team_repo.oeffentlich_lesen.return_value = None
    teams = TeamService(team_repo, settings, saison=lambda: "2026")

    async def bedarf():
        return ("energie-heizen", 40)

    fortschritt = TeamFortschrittService(
        speicher, settings, art9=lambda k: True, bedarf=bedarf, heute=lambda: HEUTE
    )
    app = FastAPI()
    app.include_router(teams_router, prefix="/api/v1/teams")
    app.dependency_overrides[teams_module._service] = lambda: teams
    app.dependency_overrides[teams_module._fortschritt] = lambda: fortschritt
    return TestClient(app)


def _team_json(client):
    antwort = client.get("/api/v1/teams/meine", headers={"X-User": PERSON})
    assert antwort.status_code == 200
    return antwort.json()["teams"][0]


def test_wirkung_der_abgeschlossenen_woche_gerundet():
    speicher = Speicher(_team(7))
    speicher.zaehler[(TEAM, VORIGE)] = {
        "beitraege": 27,
        "bewertungen": 4,
        "gepostet": 41,
    }
    speicher.zaehler[(TEAM, LAUFENDE)] = {"beitraege": 99}

    team = _team_json(_client(speicher))

    assert team["wirkung"] == {
        "woche": VORIGE.isoformat(),
        "waechst_noch": False,
        "gesamt": "rund 70",
        "beitraege": "rund 25",
        "bewertungen": "weniger als 10",
        "gepostet": "rund 40",
    }
    # Keine genaue Zahl und nichts aus der laufenden Woche in der Antwort
    text = str(team["wirkung"]) + str(team["quest"])
    for genau in ("27", "41", "72", "99"):
        assert genau not in text


def test_quest_mit_ziel_ohne_stand():
    speicher = Speicher(_team(7))

    quest = _team_json(_client(speicher))["quest"]

    assert quest == {
        "woche": LAUFENDE.isoformat(),
        "ziel": 3,
        "thema": "energie-heizen",
        "thema_name": "Energie und Heizen",
        "thema_motiv": "themen/energie-heizen.svg",
        "vorige_geschafft": False,
        "vorige_thema_name": None,
    }


def test_vorige_quest_geschafft():
    speicher = Speicher(_team(7))
    speicher.quest_zeilen[(TEAM, VORIGE)] = Quest(*TEAM, VORIGE, "klima", 3)
    speicher.zaehler[(TEAM, VORIGE)] = {"gepostet": 3}

    quest = _team_json(_client(speicher))["quest"]

    assert quest["vorige_geschafft"] is True
    assert quest["vorige_thema_name"] == "Klima"


def test_unter_fuenf_waechst_noch():
    team = _team_json(_client(Speicher(_team(4))))

    assert team["wirkung"]["waechst_noch"] is True
    assert team["wirkung"]["gesamt"] is None
    assert team["quest"] is None


def test_schalter_aus_felder_null():
    team = _team_json(_client(Speicher(_team(7)), settings=NUR_TEAMS))

    assert team["wirkung"] is None
    assert team["quest"] is None


def test_fehler_im_fortschritt_laesst_die_teams_stehen():
    speicher = Mock()
    speicher.eigene_teams.side_effect = RuntimeError("weg")

    team = _team_json(_client(speicher))

    assert team["team_name"] == TEAM[0]
    assert team["wirkung"] is None


def test_team_ohne_deckende_einwilligung_ohne_wirkung():
    # Mitgliedschaft in einem Team, fuer das der Dienst nichts liefert
    speicher = Speicher(_team(7))
    andere = _mitgliedschaft("Anderes Team")

    antwort = _client(speicher, meine=[_mitgliedschaft(), andere]).get(
        "/api/v1/teams/meine", headers={"X-User": PERSON}
    )

    teams = {t["team_name"]: t for t in antwort.json()["teams"]}
    assert teams["Anderes Team"]["wirkung"] is None
    assert teams[TEAM[0]]["wirkung"] is not None


class TestQuestPunkte:
    """Quest-Punkte fliessen in die Stufe Quests des Punktestands (ADR 0004)."""

    def _punkte(self, quest_tage, eingewilligt=True):
        beitrag = Mock(
            id="b-1", created=datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
        )
        nutzung = Mock()
        nutzung.get_nutzung_entdoppelt_batch.return_value = {}
        stimmen = Mock()
        stimmen.zustimmungen.return_value = 0
        stimmen.einwuerfe_ausformuliert_je_tag.return_value = {}
        stimmen.bewertungen_je_tag.return_value = {}
        dienst = PunkteService(
            AsyncMock(return_value=[beitrag]),
            nutzung,
            stimmen,
            Settings(punkte_quest=4, punkte_deckel_quests_je_tag=8, punkte_beitrag=0),
            jetzt=lambda: datetime(2026, 11, 25, 12, tzinfo=timezone.utc),
            eingewilligt=lambda k: eingewilligt,
            quest_tage=quest_tage,
        )
        return asyncio.run(dienst.punkte("konto"))

    def test_erreichte_quest_bringt_quest_punkte(self):
        gefragt = []

        def quest_tage(konto, beitraege, grenze):
            gefragt.append((konto, beitraege, grenze))
            return {LAUFENDE: 1}

        stand = self._punkte(quest_tage)

        assert stand.quests == 4
        konto, beitraege, grenze = gefragt[0]
        assert konto == "konto"
        assert beitraege == [datetime(2026, 11, 17, 12, tzinfo=timezone.utc)]
        assert grenze == datetime(2026, 11, 22, 12, tzinfo=timezone.utc)

    def test_ohne_punkte_einwilligung_keine(self):
        quest_tage = Mock(return_value={LAUFENDE: 1})

        stand = self._punkte(quest_tage, eingewilligt=False)

        assert not stand.sammelt
        quest_tage.assert_not_called()

    def test_mit_echtem_dienst(self):
        speicher = Speicher(_team(5))
        speicher.mitglieder[0].konto = "konto"
        speicher.quest_zeilen[(TEAM, VORIGE)] = Quest(*TEAM, VORIGE, "klima", 3)
        speicher.zaehler[(TEAM, VORIGE)] = {"beitraege": 3}
        fortschritt = TeamFortschrittService(speicher, AN, heute=lambda: HEUTE)

        assert self._punkte(fortschritt.quest_tage).quests == 4


def test_staende_als_datenklassen():
    # Die Antwort baut aus den Feldern der Datenklasse; neue Felder brauchen das Modell.
    stand = TeamStand(
        TeamWirkung(
            VORIGE, False, "rund 10", "rund 10", "weniger als 10", "weniger als 10"
        ),
        TeamQuestStand(Quest(*TEAM, LAUFENDE, None, 3), False),
    )
    assert teams_module.TeamWirkungResponse(**vars(stand.wirkung)).gesamt == "rund 10"
    assert teams_module._quest_response(stand).thema is None
