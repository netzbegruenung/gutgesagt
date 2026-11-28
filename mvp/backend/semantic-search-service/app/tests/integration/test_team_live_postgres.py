"""
Team-Fortschritt quasi-live (Schalter team_live, Jura-Akte 28.11.2026) gegen ein echtes
PostgreSQL: die Migration legt team_stunden an wie das Modell und laeuft wiederholt
durch, der Stundenzaehler traegt keine Kennung, ein Block wird nur einmal vorberechnet,
der Loeschlauf nimmt die Stundenzaehler mit dem Wochenwechsel mit und laesst den
Wochenzaehler stehen, und der Weg vom Beitrag bis zur Anzeige mit dem echten Repository.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import inspect, text

from core.config import Settings
from domain.team_fortschritt import Art
from repositories.team_fortschritt_repository import (
    FREIGEGEBEN,
    OFFEN,
    UEBERTRAGEN,
    TeamFortschrittRepository,
)
from services.loeschfristen_service import LoeschfristenService
from services.team_fortschritt_service import TeamFortschrittService
from services.team_service import Team
from tests.integration import postgres
from tests.integration.test_loeschkommando import datenbank  # noqa: F401
from tests.integration.test_team_fortschritt_postgres import _beitreten, _zeilen

pytestmark = pytest.mark.integration

AN = Settings(teams_aktiv=True, team_live_aktiv=True)
TEAM = Team("BDK 26 Berlin", "vogel", "2026")
SCHLUESSEL = (TEAM.name, TEAM.saison)
UTC = timezone.utc
MIGRATION = postgres.MIGRATIONEN / "2026-11-28-team-stunden.sql"


def utc(tag: int, stunde: int, minute: int = 0) -> datetime:
    return datetime(2026, 12, tag, stunde, minute, tzinfo=UTC)


class Uhr:
    def __init__(self, jetzt):
        self.jetzt = jetzt

    def __call__(self):
        return self.jetzt


def _dienst(db, uhr, settings=AN):
    async def bedarf():
        return ("klima", 20)

    return TeamFortschrittService(
        TeamFortschrittRepository(db),
        settings,
        art9=lambda k: True,
        bedarf=bedarf,
        heute=lambda: uhr().date(),
        saison=lambda: "2026",
        jetzt=uhr,
        # Eingeschaltet nach jeder Einwilligung im Test (die traegt die echte Uhrzeit)
        live_seit=lambda: datetime.now(UTC) + timedelta(days=1),
    )


def _konten(n):
    return [f"konto-{i}" for i in range(n)]


def test_migration_legt_die_tabelle_wie_das_modell_an(wegwerf_schema):
    skript = MIGRATION.read_text(encoding="utf-8")
    for _ in range(2):
        with wegwerf_schema.engine.begin() as c:
            c.exec_driver_sql(skript)

    spalten = {
        s["name"]: s for s in inspect(wegwerf_schema.engine).get_columns("team_stunden")
    }
    # Keine Kennung, kein Beitrag
    assert set(spalten) == {
        "team_name",
        "saison",
        "block_beginn",
        "anzahl",
        "stand",
        "freigabe",
        "mitglieder",
    }
    schluessel = inspect(wegwerf_schema.engine).get_pk_constraint("team_stunden")
    assert schluessel["constrained_columns"] == ["team_name", "saison", "block_beginn"]


def test_stundenzaehler_und_einmal_vorberechnet(datenbank):  # noqa: F811
    repo = TeamFortschrittRepository(datenbank)
    block = utc(4, 12)
    repo.stunde_erhoehen([SCHLUESSEL], block)
    repo.stunde_erhoehen([SCHLUESSEL], block)

    assert repo.stunde_abschliessen(SCHLUESSEL, block, FREIGEGEBEN, 2, 25) is True
    assert repo.stunde_abschliessen(SCHLUESSEL, block, UEBERTRAGEN, None, 30) is False
    # Ohne Ereignisse legt das Vorberechnen den Block mit 0 an
    assert repo.stunde_abschliessen(SCHLUESSEL, utc(4, 13), UEBERTRAGEN, None, 25)

    stunden = repo.stunden([SCHLUESSEL], utc(4, 0))
    assert [(s.anzahl, s.stand, s.freigabe, s.mitglieder) for s in stunden] == [
        (2, FREIGEGEBEN, 2, 25),
        (0, UEBERTRAGEN, None, 25),
    ]
    assert repo.teams_mit_stunden("2026", utc(4, 0)) == [SCHLUESSEL]
    assert repo.teams_mit_stunden("2026", utc(4, 14)) == []


def test_vom_beitrag_bis_zur_anzeige(datenbank):  # noqa: F811
    teams = _beitreten(datenbank, _konten(25), team=TEAM, heute=date(2026, 11, 30))
    assert len(teams.meine("konto-0")) == 1
    uhr = Uhr(utc(4, 6))
    dienst = _dienst(datenbank, uhr)

    uhr.jetzt = utc(4, 12, 10)
    for i, konto in enumerate(_konten(12)):
        dienst.zaehlen(konto, Art.BEITRAG, f"b-{i}")
    uhr.jetzt = utc(4, 13, 16)
    assert dienst.bloecke_veroeffentlichen() == 1

    uhr.jetzt = utc(4, 13, 20)
    live = asyncio.run(dienst.staende("konto-0"))[SCHLUESSEL].live
    assert live.bis == 14
    assert live.tagessumme == "rund 10"
    assert live.mitglieder == 20
    assert live.hinweis_neu is True

    # Keine Kennung und kein Beitrag in der Tabelle
    inhalt = " ".join(str(z) for z in _zeilen(datenbank, "team_stunden"))
    for kennung in ("konto-0", "konto-11", "b-0"):
        assert kennung not in inhalt


def test_unter_zehn_verschiedenen_uebertragen(datenbank):  # noqa: F811
    _beitreten(datenbank, _konten(25), team=TEAM, heute=date(2026, 11, 30))
    uhr = Uhr(utc(4, 6))
    dienst = _dienst(datenbank, uhr)

    uhr.jetzt = utc(4, 12, 10)
    for i in range(30):
        dienst.zaehlen(f"konto-{i % 9}", Art.BEITRAG, f"b-{i}")
    uhr.jetzt = utc(4, 13, 16)
    assert dienst.bloecke_veroeffentlichen() == 0

    [zeile] = [
        z for z in _zeilen(datenbank, "team_stunden") if z["block_beginn"] == utc(4, 12)
    ]
    assert (zeile["anzahl"], zeile["stand"], zeile["freigabe"]) == (
        30,
        UEBERTRAGEN,
        None,
    )


def test_loeschlauf_mit_dem_wochenwechsel(datenbank):  # noqa: F811
    repo = TeamFortschrittRepository(datenbank)
    # Sonntag 6.12. abends und Montag 7.12. frueh (UTC)
    repo.stunde_erhoehen([SCHLUESSEL], utc(6, 22))
    repo.stunde_erhoehen([SCHLUESSEL], utc(7, 0))
    repo.erhoehen([SCHLUESSEL], date(2026, 11, 30), Art.BEITRAG)
    service = LoeschfristenService(
        Mock(**{"bearbeitete_loeschen_vor.return_value": 0}),
        Mock(**{"ohne_beitrag_loeschen_vor.return_value": 0}),
        Mock(
            geloeschte_laden=AsyncMock(return_value=[]), geloescht_am_setzen=AsyncMock()
        ),
        Mock(delete_content=AsyncMock(return_value=True)),
        Mock(**{"aufgehobene_loeschen_vor.return_value": 0}),
        team_stunden=repo,
    )

    asyncio.run(service.fristen_anwenden(date(2026, 12, 7)))

    assert [z["block_beginn"] for z in _zeilen(datenbank, "team_stunden")] == [
        utc(7, 0)
    ]
    # Danach bleibt nur die Wochensumme
    assert len(_zeilen(datenbank, "team_wochen")) == 1


def test_team_loeschen_nimmt_stundenzaehler_mit(datenbank):  # noqa: F811
    repo = TeamFortschrittRepository(datenbank)
    repo.stunde_erhoehen([SCHLUESSEL, (TEAM.name, "2025")], utc(4, 12))

    assert repo.team_loeschen(TEAM.name, TEAM.saison) == 1

    assert [z["saison"] for z in _zeilen(datenbank, "team_stunden")] == ["2025"]


def test_offen_bleibt_offen_bis_zur_vorberechnung(datenbank):  # noqa: F811
    repo = TeamFortschrittRepository(datenbank)
    repo.stunde_erhoehen([SCHLUESSEL], utc(4, 12))

    assert [z["stand"] for z in _zeilen(datenbank, "team_stunden")] == [OFFEN]


def test_schalter_aus_loescht_die_stundenzaehler_sofort(datenbank):  # noqa: F811
    """Jura 28.11.: wirkt team_live nicht mehr, gehen die Zaehler der Woche sofort."""
    repo = TeamFortschrittRepository(datenbank)
    repo.stunde_erhoehen([SCHLUESSEL], utc(4, 11))
    repo.stunde_abschliessen(SCHLUESSEL, utc(4, 11), FREIGEGEBEN, 12, 25)
    repo.stunde_erhoehen([SCHLUESSEL], utc(4, 12))
    repo.erhoehen([SCHLUESSEL], date(2026, 11, 30), Art.BEITRAG)
    uhr = Uhr(utc(4, 12, 30))

    _dienst(
        datenbank, uhr, settings=Settings(teams_aktiv=True)
    ).bloecke_veroeffentlichen()

    assert _zeilen(datenbank, "team_stunden") == []
    # Der Wochenzaehler bleibt
    assert len(_zeilen(datenbank, "team_wochen")) == 1
