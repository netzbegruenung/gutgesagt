"""
Team-Fortschritt (#784) und Team-Quests (#792) gegen ein echtes PostgreSQL.

Mitgliedschaften ueber den echten TeamService, Zaehler und Quests ueber das echte
Repository: Zaehlung und Entdoppelung, die Schwelle von 5 Mitgliedern mit deckender
Einwilligung, Rundung, nur abgeschlossene Wochen, nur Mitglieder sehen, Schalter aus,
die Art.-9-Bedingung fuer "Ja, gepostet", Quests und Quest-Punkte. Dazu: Der Zaehler
traegt keine Kennung, und weder "Team verlassen" noch das Loeschkommando lassen eine
Zuordnung Person -> Zaehler zurueck.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect, text

from core.config import Settings
from domain.team_fortschritt import Art
from repositories.team_fortschritt_repository import Quest, TeamFortschrittRepository
from repositories.team_repository import TeamRepository
from services.team_fortschritt_service import TeamFortschrittService
from services.team_service import Team, TeamService
from tests.integration.test_loeschkommando import _loeschen, datenbank  # noqa: F401

pytestmark = pytest.mark.integration

AN = Settings(teams_aktiv=True, team_quests_aktiv=True)
AUS = Settings(teams_aktiv=True)
HEUTE = date(2026, 11, 25)
LAUFENDE = date(2026, 11, 23)
VORIGE = date(2026, 11, 16)
TEAM = Team("BDK 26 Berlin", "vogel", "2026")
SCHLUESSEL = (TEAM.name, TEAM.saison)


def _beitreten(db, konten, kennung="team-2026-11-26", team=TEAM, heute=VORIGE):
    teams = TeamService(TeamRepository(db), AN, saison=lambda: "2026")
    for konto in konten:
        if kennung == "team-2026-11-26":
            teams.beitreten(konto, team, heute=heute)
        else:
            # Frueherer Wortlaut: nur noch bestehende Nachweise, neu nicht mehr moeglich
            TeamRepository(db).beitreten(
                konto,
                team.name,
                team.motiv,
                team.saison,
                kennung,
                datetime(2026, 11, 20, tzinfo=timezone.utc),
                heute,
            )
    return teams


def _dienst(db, settings=AN, heute=HEUTE, art9=lambda k: True):
    async def bedarf():
        return ("klima", 20)

    return TeamFortschrittService(
        TeamFortschrittRepository(db),
        settings,
        art9=art9,
        bedarf=bedarf,
        heute=lambda: heute,
        saison=lambda: "2026",
    )


def _zeilen(db, tabelle):
    with db.get_session() as c:
        return [dict(z._mapping) for z in c.execute(text(f"SELECT * FROM {tabelle}"))]


def _konten(n):
    return [f"konto-{i}" for i in range(n)]


def test_zaehlung_und_entdoppelung(datenbank):  # noqa: F811
    _beitreten(datenbank, _konten(5))
    dienst = _dienst(datenbank)

    dienst.zaehlen("konto-0", Art.BEITRAG, "b-1")
    dienst.zaehlen("konto-0", Art.BEITRAG, "b-1")
    dienst.zaehlen("konto-1", Art.BEWERTUNG, "b-1")
    dienst.zaehlen("konto-1", Art.BEWERTUNG, "b-1")
    dienst.zaehlen("konto-2", Art.BEWERTUNG, "b-1")
    for _ in range(3):
        dienst.zaehlen("konto-3", Art.GEPOSTET)

    assert _zeilen(datenbank, "team_wochen") == [
        {
            "team_name": TEAM.name,
            "saison": TEAM.saison,
            "woche": LAUFENDE,
            "beitraege": 1,
            "bewertungen": 2,
            "gepostet": 1,
        }
    ]


def test_gepostet_nur_mit_art9_einwilligung(datenbank):  # noqa: F811
    _beitreten(datenbank, _konten(5))
    ohne = _dienst(datenbank, art9=lambda k: k != "konto-0")

    ohne.zaehlen("konto-0", Art.GEPOSTET)
    assert _zeilen(datenbank, "team_wochen") == []

    ohne.zaehlen("konto-1", Art.GEPOSTET)
    assert _zeilen(datenbank, "team_wochen")[0]["gepostet"] == 1


def test_schwelle_fuenf_mit_deckender_einwilligung(datenbank):  # noqa: F811
    _beitreten(datenbank, _konten(4))
    _beitreten(datenbank, ["konto-alt"], kennung="team-2026-11-25")
    dienst = _dienst(datenbank)

    assert dienst.zaehlen("konto-0", Art.BEITRAG, "b-1") == 0
    assert dienst.zaehlen("konto-alt", Art.BEITRAG, "b-2") == 0
    assert _zeilen(datenbank, "team_wochen") == []
    stand = asyncio.run(dienst.staende("konto-0"))[SCHLUESSEL]
    assert stand.wirkung.waechst_noch
    assert stand.quest is None
    # Wer dem frueheren Wortlaut zugestimmt hat, sieht nichts
    assert asyncio.run(dienst.staende("konto-alt")) == {}

    _beitreten(datenbank, ["konto-4"])
    assert dienst.zaehlen("konto-0", Art.BEITRAG, "b-1") == 1


def test_nur_abgeschlossene_woche_gerundet_und_nur_fuer_mitglieder(
    datenbank,  # noqa: F811
):
    _beitreten(datenbank, _konten(6))
    diese_woche = _dienst(datenbank, heute=VORIGE + timedelta(days=2))
    for i in range(6):
        diese_woche.zaehlen(f"konto-{i}", Art.GEPOSTET)
        for b in range(2):
            diese_woche.zaehlen(f"konto-{i}", Art.BEITRAG, f"b-{i}-{b}")

    # In derselben Woche: noch nichts zu sehen (nie live)
    live = asyncio.run(diese_woche.staende("konto-0"))[SCHLUESSEL].wirkung
    assert live.woche == VORIGE - timedelta(days=7)
    assert (live.beitraege, live.gepostet) == ("weniger als 10",) * 2

    danach = _dienst(datenbank)
    wirkung = asyncio.run(danach.staende("konto-0"))[SCHLUESSEL].wirkung
    assert wirkung.woche == VORIGE
    assert wirkung.beitraege == "rund 10"  # 12
    assert wirkung.gepostet == "weniger als 10"  # 6
    assert asyncio.run(danach.staende("fremd")) == {}


def test_schalter_aus_nichts_gezaehlt_nichts_gezeigt(datenbank):  # noqa: F811
    _beitreten(datenbank, _konten(5))
    dienst = _dienst(datenbank, settings=AUS)

    for art in Art:
        assert dienst.zaehlen("konto-0", art, "b-1") == 0

    assert _zeilen(datenbank, "team_wochen") == []
    assert asyncio.run(dienst.staende("konto-0")) == {}
    assert dienst.quest_tage("konto-0", [], datetime.now(timezone.utc)) == {}
    assert _zeilen(datenbank, "team_quests") == []


def test_quest_und_quest_punkte(datenbank):  # noqa: F811
    _beitreten(datenbank, _konten(6))
    # Woche der Quest: das Ziel entsteht beim ersten Abruf
    in_der_woche = _dienst(datenbank, heute=VORIGE + timedelta(days=1))
    quest = asyncio.run(in_der_woche.staende("konto-0"))[SCHLUESSEL].quest
    assert quest.laufende == Quest(TEAM.name, TEAM.saison, VORIGE, "klima", 3)
    asyncio.run(in_der_woche.staende("konto-1"))
    assert len(_zeilen(datenbank, "team_quests")) == 1
    for i in range(3):
        in_der_woche.zaehlen(f"konto-{i}", Art.BEWERTUNG, "b-1")

    danach = _dienst(datenbank)
    stand = asyncio.run(danach.staende("konto-0"))[SCHLUESSEL].quest
    assert stand.vorige_geschafft
    assert stand.vorige_thema == "klima"
    assert stand.laufende.woche == LAUFENDE

    grenze = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)
    mit_beitrag = [datetime(2026, 11, 18, 9, tzinfo=timezone.utc)]
    assert danach.quest_tage("konto-0", mit_beitrag, grenze) == {LAUFENDE: 1}
    assert danach.quest_tage("konto-5", [], grenze) == {}
    assert danach.quest_tage("fremd", mit_beitrag, grenze) == {}


def test_verfehlte_quest_ohne_hinweis_und_ohne_punkte(datenbank):  # noqa: F811
    _beitreten(datenbank, _konten(6))
    in_der_woche = _dienst(datenbank, heute=VORIGE + timedelta(days=1))
    asyncio.run(in_der_woche.staende("konto-0"))
    in_der_woche.zaehlen("konto-0", Art.BEWERTUNG, "b-1")

    danach = _dienst(datenbank)
    stand = asyncio.run(danach.staende("konto-0"))[SCHLUESSEL].quest
    assert not stand.vorige_geschafft
    assert stand.vorige_thema is None
    assert (
        danach.quest_tage(
            "konto-0",
            [datetime(2026, 11, 18, tzinfo=timezone.utc)],
            datetime(2026, 11, 22, tzinfo=timezone.utc),
        )
        == {}
    )


def test_zaehler_ohne_personenbezug(datenbank):  # noqa: F811
    spalten = {
        tabelle: {s["name"] for s in inspect(datenbank.engine).get_columns(tabelle)}
        for tabelle in ("team_wochen", "team_quests")
    }
    assert spalten["team_wochen"] == {
        "team_name",
        "saison",
        "woche",
        "beitraege",
        "bewertungen",
        "gepostet",
    }
    assert spalten["team_quests"] == {"team_name", "saison", "woche", "thema", "ziel"}


def test_verlassen_und_loeschen_lassen_nur_die_summe(datenbank):  # noqa: F811
    teams = _beitreten(datenbank, _konten(5) + ["person-die-loescht"])
    dienst = _dienst(datenbank)
    dienst.zaehlen("person-die-loescht", Art.BEITRAG, "b-1")
    dienst.zaehlen("konto-0", Art.BEITRAG, "b-2")
    vorher = _zeilen(datenbank, "team_wochen")

    [mitgliedschaft] = teams.meine("konto-0")
    teams.verlassen("konto-0", mitgliedschaft.id)
    _loeschen(datenbank, "person-die-loescht")

    assert _zeilen(datenbank, "team_wochen") == vorher
    with datenbank.get_session() as c:
        inhalt = " ".join(
            str(z)
            for tabelle in ("team_wochen", "team_quests")
            for z in c.execute(text(f"SELECT * FROM {tabelle}"))
        )
    for kennung in ("konto-0", "person-die-loescht", "b-1", "b-2"):
        assert kennung not in inhalt


def test_team_loeschen_nimmt_nur_dieses_team_mit(datenbank):  # noqa: F811
    repo = TeamFortschrittRepository(datenbank)
    repo.erhoehen([SCHLUESSEL, (TEAM.name, "2025")], LAUFENDE, Art.BEITRAG)
    repo.quest_anlegen(Quest(TEAM.name, TEAM.saison, LAUFENDE, "klima", 3))

    assert repo.team_loeschen(TEAM.name, TEAM.saison) == 2

    assert _zeilen(datenbank, "team_quests") == []
    assert [z["saison"] for z in _zeilen(datenbank, "team_wochen")] == ["2025"]


def test_team_loeschen_in_der_transaktion_des_aufrufers(datenbank):  # noqa: F811
    repo = TeamFortschrittRepository(datenbank)
    repo.erhoehen([SCHLUESSEL], LAUFENDE, Art.BEITRAG)

    with pytest.raises(RuntimeError):
        with datenbank.get_session() as session:
            assert repo.team_loeschen(TEAM.name, TEAM.saison, session=session) == 1
            raise RuntimeError("Team-Loeschung scheitert danach")

    # Zurueckgerollt mit der Transaktion des Aufrufers
    assert len(_zeilen(datenbank, "team_wochen")) == 1
