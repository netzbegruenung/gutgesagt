"""
Team-Fortschritt quasi-live (Schalter team_live, Jura-Akte 28.11.2026) im Dienst, mit
einem Repository im Speicher: Stundenzaehler nur ab 20 Mitgliedern, Freigabe eines
Blocks erst ab 10 verschiedenen Beitragenden, Uebertrag in den naechsten Block (nur am
selben Tag), nach einem Neustart uebertragen statt freigeben, einmal vorberechnet,
Tagessumme auf 10 abgerundet, Mitgliederzahl, Quest-Stufe nur aus freigegebenen
Bloecken, Hinweis an Bestandsmitglieder und die Kopplung an die Schalter.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.v1.teams as teams_module
from core.config import Settings
from domain.team_fortschritt import Art, Wochenzaehlung
from repositories.team_fortschritt_repository import (
    FREIGEGEBEN,
    OFFEN,
    UEBERTRAGEN,
    EigenesTeam,
    Quest,
    Stunde,
)
from repositories.team_repository import Mitgliedschaft
from services.schalter_service import get_schalter_service
from services.team_fortschritt_service import (
    StundenPruefwerte,
    TeamFortschrittService,
    _sekunden_bis_zum_takt,
)
from services.team_service import TeamService

pytestmark = pytest.mark.unit

AN = Settings(teams_aktiv=True, team_quests_aktiv=True, team_live_aktiv=True)
LIVE_AUS = Settings(teams_aktiv=True, team_quests_aktiv=True)
TEAMS_AUS = Settings(team_quests_aktiv=True, team_live_aktiv=True)

TEAM = ("BDK 26 Hannover", "2026")
GEDECKT = "team-2026-11-26"
UTC = timezone.utc
# Freitag der BDK; 13:00 UTC ist 14 Uhr deutsche Zeit
TAG = date(2026, 12, 4)


def utc(stunde: int, minute: int = 0, tag: date = TAG) -> datetime:
    return datetime(tag.year, tag.month, tag.day, stunde, minute, tzinfo=UTC)


class Uhr:
    def __init__(self, jetzt: datetime):
        self.jetzt = jetzt

    def __call__(self) -> datetime:
        return self.jetzt


@dataclass
class Mitglied:
    konto: str
    team: Tuple[str, str] = TEAM
    eingewilligt: datetime = field(
        default_factory=lambda: utc(8, tag=date(2026, 11, 30))
    )


class Speicher:
    """TeamFortschrittRepository im Speicher, mit denselben Methoden."""

    def __init__(self, mitglieder: List[Mitglied]):
        self.mitglieder = mitglieder
        self.zaehler: Dict[tuple, Dict[str, int]] = {}
        self.quest_zeilen: Dict[tuple, Quest] = {}
        self.stunden_zeilen: Dict[tuple, Dict] = {}

    def eigene_teams(self, konto, kennungen):
        return [
            EigenesTeam(m.team[0], m.team[1], m.eingewilligt.date(), m.eingewilligt)
            for m in self.mitglieder
            if m.konto == konto
        ]

    def einwilligende_je_team(self, teams, kennungen):
        return {t: sum(1 for m in self.mitglieder if m.team == t) for t in teams}

    def einwilligende_der_saison(self, saison, kennungen):
        ergebnis: Dict[tuple, int] = {}
        for m in self.mitglieder:
            if m.team[1] == saison:
                ergebnis[m.team] = ergebnis.get(m.team, 0) + 1
        return ergebnis

    def erhoehen(self, teams, woche, art):
        spalte = {
            Art.BEITRAG: "beitraege",
            Art.BEWERTUNG: "bewertungen",
            Art.GEPOSTET: "gepostet",
        }[art]
        for t in teams:
            zeile = self.zaehler.setdefault((t, woche), {})
            zeile[spalte] = zeile.get(spalte, 0) + 1

    def wochen(self, teams, woche):
        return {
            t: Wochenzaehlung(**self.zaehler[(t, woche)])
            for t in teams
            if (t, woche) in self.zaehler
        }

    def quests(self, teams, woche):
        return {
            t: self.quest_zeilen[(t, woche)]
            for t in teams
            if (t, woche) in self.quest_zeilen
        }

    def quest_anlegen(self, quest):
        schluessel = ((quest.team_name, quest.saison), quest.woche)
        return self.quest_zeilen.setdefault(schluessel, quest)

    # Stundenzaehler

    def stunde_erhoehen(self, teams, block):
        for t in teams:
            zeile = self.stunden_zeilen.setdefault(
                (t, block),
                {"anzahl": 0, "stand": OFFEN, "freigabe": None, "mitglieder": None},
            )
            zeile["anzahl"] += 1

    def stunden(self, teams, ab):
        teams = set(teams)
        return sorted(
            (
                Stunde(
                    t[0],
                    t[1],
                    b,
                    z["anzahl"],
                    z["stand"],
                    z["freigabe"],
                    z["mitglieder"],
                )
                for (t, b), z in self.stunden_zeilen.items()
                if t in teams and b >= ab
            ),
            key=lambda s: s.block_beginn,
        )

    def teams_mit_stunden(self, saison, ab):
        return list({t for (t, b) in self.stunden_zeilen if t[1] == saison and b >= ab})

    def stunde_abschliessen(self, team, block, stand, freigabe, mitglieder):
        zeile = self.stunden_zeilen.setdefault(
            (team, block),
            {"anzahl": 0, "stand": OFFEN, "freigabe": None, "mitglieder": None},
        )
        if zeile["stand"] != OFFEN:
            return False
        zeile.update(stand=stand, freigabe=freigabe, mitglieder=mitglieder)
        return True

    def stunden_loeschen_vor(self, grenze):
        self.loeschungen = getattr(self, "loeschungen", 0) + 1
        alt = [k for k in self.stunden_zeilen if k[1] < grenze]
        for k in alt:
            del self.stunden_zeilen[k]
        return len(alt)

    def zeile(self, block, team=TEAM):
        return self.stunden_zeilen.get((team, block))


def _mitglieder(n: int, team=TEAM) -> List[Mitglied]:
    return [Mitglied(f"{team[0]}-{i}", team) for i in range(n)]


def _dienst(
    speicher,
    uhr,
    settings=AN,
    stunden: Optional[StundenPruefwerte] = None,
    live_seit=lambda: utc(7),
    bedarf=("energie-heizen", 100),
):
    async def bedarf_lesen():
        return bedarf

    return TeamFortschrittService(
        speicher,
        settings,
        art9=lambda k: True,
        bedarf=bedarf_lesen,
        heute=lambda: uhr().date(),
        saison=lambda: "2026",
        jetzt=uhr,
        stunden=stunden,
        live_seit=live_seit,
    )


_ZAEHLER = iter(range(10**9))


def _beitragen(dienst, uhr, konten: List[str], zeitpunkt: datetime, je: int = 1):
    """Jede Person speichert ``je`` Beitraege zum Zeitpunkt."""
    uhr.jetzt = zeitpunkt
    for konto in konten:
        for _ in range(je):
            dienst.zaehlen(konto, Art.BEITRAG, f"beitrag-{next(_ZAEHLER)}")


def _live(dienst, uhr, konto, jetzt):
    uhr.jetzt = jetzt
    stand = asyncio.run(dienst.staende(konto)).get(TEAM)
    return stand.live if stand else None


@pytest.fixture
def team():
    return Speicher(_mitglieder(30))


@pytest.fixture
def uhr():
    # Prozessstart vor dem ersten Block des Tages
    return Uhr(utc(6))


def konten(n, ab=0):
    return [f"{TEAM[0]}-{i}" for i in range(ab, ab + n)]


class TestZaehlen:
    def test_stundenzaehler_ohne_kennung_nur_zahl(self, team, uhr):
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(3), utc(12, 10), je=2)

        assert team.zeile(utc(12)) == {
            "anzahl": 6,
            "stand": OFFEN,
            "freigabe": None,
            "mitglieder": None,
        }

    def test_unter_zwanzig_kein_stundenzaehler(self, uhr):
        speicher = Speicher(_mitglieder(19))
        dienst = _dienst(speicher, uhr)
        _beitragen(dienst, uhr, konten(19), utc(12, 10))

        assert speicher.stunden_zeilen == {}
        # Der Wochenzaehler zaehlt wie bisher
        assert sum(z["beitraege"] for z in speicher.zaehler.values()) == 19

    def test_ab_zwanzig_stundenzaehler(self, uhr):
        speicher = Speicher(_mitglieder(20))
        dienst = _dienst(speicher, uhr)
        _beitragen(dienst, uhr, konten(1), utc(12, 10))

        assert speicher.zeile(utc(12))["anzahl"] == 1

    def test_doppeltes_ereignis_zaehlt_auch_stuendlich_nicht(self, team, uhr):
        dienst = _dienst(team, uhr)
        uhr.jetzt = utc(12, 10)
        dienst.zaehlen(konten(1)[0], Art.BEITRAG, "derselbe")
        dienst.zaehlen(konten(1)[0], Art.BEITRAG, "derselbe")

        assert team.zeile(utc(12))["anzahl"] == 1

    @pytest.mark.parametrize("settings", [LIVE_AUS, TEAMS_AUS])
    def test_schalter_aus_kein_stundenzaehler(self, team, uhr, settings):
        dienst = _dienst(team, uhr, settings=settings)
        _beitragen(dienst, uhr, konten(12), utc(12, 10))

        assert team.stunden_zeilen == {}


class TestFreigabe:
    def test_ab_zehn_verschiedenen_freigegeben(self, team, uhr):
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(10), utc(12, 10), je=2)
        uhr.jetzt = utc(13, 16)

        assert dienst.bloecke_veroeffentlichen() == 1
        assert team.zeile(utc(12)) == {
            "anzahl": 20,
            "stand": FREIGEGEBEN,
            "freigabe": 20,
            "mitglieder": 30,
        }
        live = _live(dienst, uhr, konten(1)[0], utc(13, 20))
        assert live.bis == 14
        assert live.tagessumme == "rund 20"
        assert live.laeuft_noch is False
        assert live.mitglieder == 30

    def test_unter_zehn_verschiedenen_uebertragen_laeuft_noch(self, team, uhr):
        """Neun Personen mit vielen Beitraegen reichen nicht: es zaehlen Personen."""
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(9), utc(12, 10), je=5)
        uhr.jetzt = utc(13, 16)

        assert dienst.bloecke_veroeffentlichen() == 0
        assert team.zeile(utc(12))["stand"] == UEBERTRAGEN
        assert team.zeile(utc(12))["freigabe"] is None
        live = _live(dienst, uhr, konten(1)[0], utc(13, 20))
        assert live.laeuft_noch is True
        assert live.tagessumme is None
        assert live.bis is None

    def test_vor_ablauf_der_viertelstunde_nichts(self, team, uhr):
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(10), utc(12, 10))
        uhr.jetzt = utc(13, 14)

        dienst.bloecke_veroeffentlichen()

        assert team.zeile(utc(12))["stand"] == OFFEN

    def test_uebertrag_in_den_naechsten_block(self, team, uhr):
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(6), utc(11, 10), je=2)
        uhr.jetzt = utc(12, 16)
        dienst.bloecke_veroeffentlichen()
        assert team.zeile(utc(11))["stand"] == UEBERTRAGEN

        # Vier neue und zwei bekannte: zusammen 10 verschiedene
        _beitragen(dienst, uhr, konten(4, ab=6) + konten(2), utc(12, 30))
        uhr.jetzt = utc(13, 16)
        assert dienst.bloecke_veroeffentlichen() == 1

        assert team.zeile(utc(12))["freigabe"] == 12 + 6
        live = _live(dienst, uhr, konten(1)[0], utc(13, 20))
        assert live.bis == 14
        assert live.tagessumme == "rund 10"

    def test_bekannte_zaehlen_im_uebertrag_nur_einmal(self, team, uhr):
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(6), utc(11, 10))
        uhr.jetzt = utc(12, 16)
        dienst.bloecke_veroeffentlichen()
        # Dieselben sechs wieder plus drei neue: 9 verschiedene
        _beitragen(dienst, uhr, konten(6) + konten(3, ab=6), utc(12, 30))
        uhr.jetzt = utc(13, 16)

        assert dienst.bloecke_veroeffentlichen() == 0
        assert team.zeile(utc(12))["stand"] == UEBERTRAGEN

    def test_uebertragener_block_fehlt_in_der_tagessumme(self, team, uhr):
        """
        Jura-Pruefpunkt 1 (Differenz): Die Tagessumme reicht nur bis zur letzten
        freigegebenen Blockgrenze; ein uebertragener Block laesst sich nicht als
        Tagessumme minus Bloecke herausrechnen.
        """
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(10), utc(11, 10))
        # Neun Personen mit je zwei Beitraegen: 18 Ereignisse, uebertragen
        _beitragen(dienst, uhr, konten(9, ab=10), utc(12, 10), je=2)
        uhr.jetzt = utc(13, 16)
        dienst.bloecke_veroeffentlichen()

        werte = dienst.live_werte([TEAM])[TEAM]
        assert werte.tagessumme == "rund 10"
        assert werte.bis == 13
        assert werte.woche_freigegeben == 10
        assert werte.laeuft_noch is True

        # Erst mit dem naechsten freigegebenen Block kommt er dazu: 10 + 18 + 1
        _beitragen(dienst, uhr, konten(1, ab=19), utc(13, 20))
        uhr.jetzt = utc(14, 16)
        dienst.bloecke_veroeffentlichen()
        werte = dienst.live_werte([TEAM])[TEAM]
        assert werte.tagessumme == "rund 20"
        assert werte.woche_freigegeben == 29
        assert werte.bis == 15

    def test_keine_logs_je_block(self, team, uhr, caplog):
        """Jura-Pruefpunkt 5: kein Log mit Einzelereignissen oder Zahlen je Block."""
        dienst = _dienst(team, uhr)
        with caplog.at_level("DEBUG"):
            _beitragen(dienst, uhr, konten(12), utc(12, 10))
            uhr.jetzt = utc(13, 16)
            dienst.bloecke_veroeffentlichen()

        assert [
            r for r in caplog.records if r.name.endswith("team_fortschritt_service")
        ] == []

    def test_tagessumme_aus_mehreren_freigaben(self, team, uhr):
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(10), utc(10, 10), je=3)
        _beitragen(dienst, uhr, konten(10, ab=10), utc(11, 10), je=2)
        uhr.jetzt = utc(12, 16)

        assert dienst.bloecke_veroeffentlichen() == 2
        live = _live(dienst, uhr, konten(1)[0], utc(12, 20))
        assert live.tagessumme == "rund 50"
        assert live.bis == 13

    def test_abgerundet_auf_zehn(self, team, uhr):
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(10), utc(12, 10))
        _beitragen(dienst, uhr, konten(9), utc(12, 20))
        uhr.jetzt = utc(13, 16)
        dienst.bloecke_veroeffentlichen()

        assert team.zeile(utc(12))["freigabe"] == 19
        assert _live(dienst, uhr, konten(1)[0], utc(13, 20)).tagessumme == "rund 10"

    def test_einmal_vorberechnet(self, team, uhr):
        """Spaetere Laeufe und Abrufe aendern einen vorberechneten Block nicht."""
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(10), utc(12, 10))
        uhr.jetzt = utc(13, 16)
        dienst.bloecke_veroeffentlichen()
        vorher = dict(team.zeile(utc(12)))

        # Auch ein zweiter Prozess rechnet ihn nicht noch einmal
        zweiter = _dienst(team, uhr)
        zweiter.bloecke_veroeffentlichen()
        dienst.bloecke_veroeffentlichen()

        assert team.zeile(utc(12)) == vorher

    def test_laeuft_noch_nach_freigabe_wenn_letzte_stunde_uebertragen(self, team, uhr):
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(10), utc(11, 10))
        _beitragen(dienst, uhr, konten(3), utc(12, 10))
        uhr.jetzt = utc(13, 16)
        dienst.bloecke_veroeffentlichen()

        live = _live(dienst, uhr, konten(1)[0], utc(13, 20))
        assert live.bis == 13
        assert live.tagessumme == "rund 10"
        assert live.laeuft_noch is True

    def test_uebertrag_nur_am_selben_tag(self, team, uhr):
        """Was gestern nicht freigegeben wurde, kommt heute nicht dazu."""
        gestern = TAG - timedelta(days=1)
        uhr.jetzt = utc(6, tag=gestern)
        dienst = _dienst(team, uhr)
        # 22:00 UTC = 23 Uhr deutsche Zeit am Vortag
        _beitragen(dienst, uhr, konten(5), utc(22, 10, tag=gestern), je=4)
        uhr.jetzt = utc(23, 16, tag=gestern)
        dienst.bloecke_veroeffentlichen()
        assert team.zeile(utc(22, tag=gestern))["stand"] == UEBERTRAGEN

        # 23:00 UTC = 0 Uhr deutsche Zeit am Freitag; fuenf andere
        _beitragen(dienst, uhr, konten(5, ab=5), utc(23, 20, tag=gestern))
        _beitragen(dienst, uhr, konten(5, ab=10), utc(23, 30, tag=gestern))
        uhr.jetzt = utc(0, 16)
        assert dienst.bloecke_veroeffentlichen() == 1

        assert team.zeile(utc(23, tag=gestern))["freigabe"] == 10
        live = _live(dienst, uhr, konten(1)[0], utc(0, 20))
        assert live.bis == 1
        assert live.tagessumme == "rund 10"


class TestMitternacht:
    def test_kein_flackern_bis_der_letzte_block_vorberechnet_ist(self, team, uhr):
        """0:00 bis 0:15: noch der Stand von 22 bis 23 Uhr, der Tag beginnt neu."""
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(10), utc(21, 10))  # 22 bis 23 Uhr deutsche Zeit
        uhr.jetzt = utc(22, 16)
        dienst.bloecke_veroeffentlichen()

        live = _live(dienst, uhr, konten(1)[0], utc(23, 5))  # 0:05 am Samstag
        assert live is not None
        assert live.tagessumme is None
        assert live.laeuft_noch is True
        assert live.mitglieder == 30


class TestNeustart:
    def test_nach_neustart_uebertragen_statt_freigegeben(self, team, uhr):
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(15), utc(12, 10))

        # Neustart um 12:40: die Pruefwerte sind weg
        uhr.jetzt = utc(12, 40)
        neu = _dienst(team, uhr)
        uhr.jetzt = utc(13, 16)
        assert neu.bloecke_veroeffentlichen() == 0

        assert team.zeile(utc(12))["stand"] == UEBERTRAGEN

    def test_naechster_voller_block_gibt_samt_uebertrag_frei(self, team, uhr):
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(15), utc(12, 10))
        uhr.jetzt = utc(12, 40)
        neu = _dienst(team, uhr)
        uhr.jetzt = utc(13, 16)
        neu.bloecke_veroeffentlichen()

        _beitragen(neu, uhr, konten(10, ab=15), utc(13, 20))
        uhr.jetzt = utc(14, 16)
        assert neu.bloecke_veroeffentlichen() == 1

        assert team.zeile(utc(13))["freigabe"] == 25

    def test_neustart_holt_verpasste_bloecke_nach(self, team, uhr):
        """Lief der Dienst zur Veroeffentlichung nicht, rechnet der Start nach."""
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(10), utc(10, 10))
        uhr.jetzt = utc(13, 5)
        neu = _dienst(team, uhr)
        uhr.jetzt = utc(13, 16)

        assert neu.bloecke_veroeffentlichen() == 0
        assert team.zeile(utc(10))["stand"] == UEBERTRAGEN
        assert team.zeile(utc(11))["stand"] == UEBERTRAGEN
        assert team.zeile(utc(12))["stand"] == UEBERTRAGEN

    def test_schalter_aus_verwirft_pruefwerte(self, team, uhr, schalter_admin_alle_an):
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(15), utc(12, 10))
        schalter_admin_alle_an["team_live"] = False
        get_schalter_service().admin_werte(frisch=True)
        uhr.jetzt = utc(12, 30)
        assert dienst.bloecke_veroeffentlichen() == 0
        schalter_admin_alle_an["team_live"] = True
        get_schalter_service().admin_werte(frisch=True)

        uhr.jetzt = utc(13, 16)
        dienst.bloecke_veroeffentlichen()

        assert team.zeile(utc(12))["stand"] == UEBERTRAGEN


class TestSchwelle:
    def test_unter_zwanzig_kein_live(self, uhr):
        speicher = Speicher(_mitglieder(19))
        dienst = _dienst(speicher, uhr)
        _beitragen(dienst, uhr, konten(19), utc(12, 10))
        uhr.jetzt = utc(13, 16)

        assert dienst.bloecke_veroeffentlichen() == 0
        assert _live(dienst, uhr, konten(1)[0], utc(13, 20)) is None
        # Die Woche wie bisher
        assert (
            asyncio.run(dienst.staende(konten(1)[0]))[TEAM].wirkung.waechst_noch
            is False
        )

    def test_unter_zwanzig_gefallen_kein_live_mehr(self, team, uhr):
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(10), utc(11, 10))
        uhr.jetzt = utc(12, 16)
        dienst.bloecke_veroeffentlichen()
        # Elf verlassen das Team
        team.mitglieder = team.mitglieder[:19]
        uhr.jetzt = utc(13, 16)
        dienst.bloecke_veroeffentlichen()

        assert team.zeile(utc(12))["mitglieder"] == 19
        assert _live(dienst, uhr, konten(1)[0], utc(13, 20)) is None

    def test_mitgliederzahl_stuendlich_ohne_beitraege(self, team, uhr):
        dienst = _dienst(team, uhr)
        uhr.jetzt = utc(13, 16)
        dienst.bloecke_veroeffentlichen()

        live = _live(dienst, uhr, konten(1)[0], utc(13, 20))
        assert live.mitglieder == 30
        assert live.laeuft_noch is True
        assert live.tagessumme is None
        # Neue Mitglieder erscheinen erst mit dem naechsten Block
        team.mitglieder += [Mitglied(f"neu-{i}") for i in range(10)]
        assert _live(dienst, uhr, konten(1)[0], utc(13, 50)).mitglieder == 30
        uhr.jetzt = utc(14, 16)
        dienst.bloecke_veroeffentlichen()
        assert _live(dienst, uhr, konten(1)[0], utc(14, 20)).mitglieder == 40


class TestQuestStufe:
    def test_nur_aus_freigegebenen_bloecken(self, uhr):
        # 90 Mitglieder: Ziel min(100, 30) = 30
        speicher = Speicher(_mitglieder(90))
        dienst = _dienst(speicher, uhr)
        konto = konten(1)[0]
        assert _live(dienst, uhr, konto, utc(10, 30)) is None  # legt die Quest an

        _beitragen(dienst, uhr, konten(10), utc(11, 10))
        uhr.jetzt = utc(12, 16)
        dienst.bloecke_veroeffentlichen()
        assert _live(dienst, uhr, konto, utc(12, 20)).quest_stufe == 1

        # Viele Beitraege, aber unter 10 Personen: die Stufe bleibt
        _beitragen(dienst, uhr, konten(5), utc(12, 30), je=4)
        assert _live(dienst, uhr, konto, utc(12, 50)).quest_stufe == 1
        uhr.jetzt = utc(13, 16)
        dienst.bloecke_veroeffentlichen()
        assert _live(dienst, uhr, konto, utc(13, 20)).quest_stufe == 1

        # Mit fuenf weiteren wird der Block samt Uebertrag frei: 10 + 20 + 5 = 35
        _beitragen(dienst, uhr, konten(5, ab=20), utc(13, 30))
        assert _live(dienst, uhr, konto, utc(13, 50)).quest_stufe == 1
        uhr.jetzt = utc(14, 16)
        dienst.bloecke_veroeffentlichen()
        assert _live(dienst, uhr, konto, utc(14, 20)).quest_stufe == 3

    def test_ohne_quests_keine_stufe(self, team, uhr):
        dienst = _dienst(
            team, uhr, settings=Settings(teams_aktiv=True, team_live_aktiv=True)
        )
        _beitragen(dienst, uhr, konten(10), utc(12, 10))
        uhr.jetzt = utc(13, 16)
        dienst.bloecke_veroeffentlichen()

        assert _live(dienst, uhr, konten(1)[0], utc(13, 20)).quest_stufe is None


class TestHinweis:
    def test_vor_dem_einschalten_eingewilligt(self, team, uhr):
        dienst = _dienst(team, uhr, live_seit=lambda: utc(7))
        uhr.jetzt = utc(13, 16)
        dienst.bloecke_veroeffentlichen()

        assert _live(dienst, uhr, konten(1)[0], utc(13, 20)).hinweis_neu is True

    def test_nach_dem_einschalten_eingewilligt(self, team, uhr):
        team.mitglieder.append(Mitglied("neu", eingewilligt=utc(9)))
        dienst = _dienst(team, uhr, live_seit=lambda: utc(7))
        uhr.jetzt = utc(13, 16)
        dienst.bloecke_veroeffentlichen()

        assert _live(dienst, uhr, "neu", utc(13, 20)).hinweis_neu is False

    def test_einschaltzeit_nicht_lesbar(self, team, uhr):
        def kaputt():
            raise RuntimeError("db weg")

        dienst = _dienst(team, uhr, live_seit=kaputt)
        uhr.jetzt = utc(13, 16)
        dienst.bloecke_veroeffentlichen()

        live = _live(dienst, uhr, konten(1)[0], utc(13, 20))
        assert live.hinweis_neu is False
        assert live.mitglieder == 30


class TestSchalter:
    def test_aus_loescht_die_stundenzaehler_sofort(
        self, team, uhr, schalter_admin_alle_an
    ):
        """Jura 28.11.: wirkt team_live nicht mehr, gehen die Stundenzaehler sofort."""
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(10), utc(11, 10))
        uhr.jetzt = utc(12, 16)
        dienst.bloecke_veroeffentlichen()
        _beitragen(dienst, uhr, konten(3), utc(12, 20))
        assert team.stunden_zeilen

        schalter_admin_alle_an["team_live"] = False
        get_schalter_service().admin_werte(frisch=True)
        uhr.jetzt = utc(12, 30)
        dienst.bloecke_veroeffentlichen()

        # Auch der laufende Block
        assert team.stunden_zeilen == {}
        assert dienst.live_werte([TEAM]) == {}
        # In jedem Lauf, solange er nicht wirkt: Waehrend des Schalter-Caches kann
        # noch ein Ereignis einen Zaehler anlegen
        team.stunde_erhoehen([TEAM], utc(12))
        dienst.bloecke_veroeffentlichen()
        assert team.stunden_zeilen == {}
        assert team.loeschungen == 2

    def test_nach_wiedereinschalten_und_ausschalten_wieder_geloescht(
        self, team, uhr, schalter_admin_alle_an
    ):
        dienst = _dienst(team, uhr)
        schalter_admin_alle_an["team_live"] = False
        get_schalter_service().admin_werte(frisch=True)
        dienst.bloecke_veroeffentlichen()
        schalter_admin_alle_an["team_live"] = True
        get_schalter_service().admin_werte(frisch=True)
        _beitragen(dienst, uhr, konten(3), utc(12, 20))
        uhr.jetzt = utc(13, 16)
        dienst.bloecke_veroeffentlichen()
        schalter_admin_alle_an["team_live"] = False
        get_schalter_service().admin_werte(frisch=True)

        dienst.bloecke_veroeffentlichen()

        assert team.stunden_zeilen == {}

    def test_nach_dem_enddatum_geloescht(self, team, uhr):
        """Nach team_live_bis wirkt der Schalter nicht mehr: dieselbe Loeschung."""
        from services.schalter_service import SchalterService, schalter_service_setzen

        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(3), utc(12, 20))
        schalter_service_setzen(
            SchalterService(
                admin_werte_lesen=lambda: {"teams": True, "team_live": True},
                admin_wert_setzen=lambda *a: None,
                enddatum=lambda name: date(2026, 12, 3),
                heute=lambda: TAG,
            )
        )
        uhr.jetzt = utc(13, 16)
        dienst.bloecke_veroeffentlichen()

        assert team.stunden_zeilen == {}

    @pytest.mark.parametrize("settings", [LIVE_AUS, TEAMS_AUS])
    def test_aus_kein_live_und_keine_vorberechnung(self, team, uhr, settings):
        an = _dienst(team, uhr)
        _beitragen(an, uhr, konten(10), utc(12, 10))
        uhr.jetzt = utc(13, 16)
        an.bloecke_veroeffentlichen()

        aus = _dienst(team, uhr, settings=settings)
        assert aus.bloecke_veroeffentlichen() == 0
        assert _live(aus, uhr, konten(1)[0], utc(13, 20)) is None

    def test_admin_wert_aus(self, team, uhr, schalter_admin_alle_an):
        schalter_admin_alle_an["team_live"] = False
        dienst = _dienst(team, uhr)
        _beitragen(dienst, uhr, konten(10), utc(12, 10))
        uhr.jetzt = utc(13, 16)

        assert dienst.bloecke_veroeffentlichen() == 0
        assert team.stunden_zeilen == {}
        assert _live(dienst, uhr, konten(1)[0], utc(13, 20)) is None


class TestPruefwerte:
    def test_nur_hmac_keine_kennung(self):
        uhr = Uhr(utc(6))
        werte = StundenPruefwerte(uhr)
        werte.merken(TEAM, utc(12), "konto-geheim")

        gespeichert = [w for menge in werte._werte.values() for w in menge]
        assert len(gespeichert) == 1
        assert "konto-geheim" not in gespeichert[0]

    def test_beobachtet_erst_ab_prozessstart(self):
        werte = StundenPruefwerte(Uhr(utc(12, 30)))

        assert werte.beobachtet(utc(12)) is False
        assert werte.beobachtet(utc(13)) is True

    def test_aufraeumen_verwirft_vortage(self):
        werte = StundenPruefwerte(Uhr(utc(6)))
        werte.merken(TEAM, utc(12, tag=TAG - timedelta(days=1)), "a")
        werte.merken(TEAM, utc(12), "a")

        werte.aufraeumen(utc(0))

        assert list(werte._werte) == [(TEAM, utc(12))]


@pytest.mark.parametrize(
    "jetzt, sekunden",
    [
        (utc(13, 0), 15 * 60 + 5),
        (utc(13, 15) + timedelta(seconds=5), 3600),
        (utc(13, 20), 55 * 60 + 5),
    ],
)
def test_takt_15_minuten_nach_der_vollen_stunde(jetzt, sekunden):
    assert _sekunden_bis_zum_takt(jetzt) == sekunden


class TestApi:
    """GET /api/v1/teams/meine traegt ``live`` nur mit wirksamem team_live."""

    def _client(self, speicher, uhr, settings=AN):
        team_repo = Mock()
        team_repo.meine.return_value = [
            Mitgliedschaft(
                id=uuid.uuid4(),
                team_name=TEAM[0],
                team_motiv="vogel",
                saison=TEAM[1],
                nummer=3,
                eingetreten_am=date(2026, 11, 30),
            )
        ]
        team_repo.oeffentlich_lesen.return_value = None
        teams = TeamService(team_repo, settings, saison=lambda: "2026")
        dienst = _dienst(speicher, uhr, settings=settings)
        app = FastAPI()
        app.include_router(teams_module.router, prefix="/api/v1/teams")
        app.dependency_overrides[teams_module._service] = lambda: teams
        app.dependency_overrides[teams_module._fortschritt] = lambda: dienst
        return TestClient(app), dienst

    def test_live_in_der_antwort_ohne_genaue_zahl(self, team, uhr):
        client, dienst = self._client(team, uhr)
        _beitragen(dienst, uhr, konten(10), utc(12, 10), je=2)
        _beitragen(dienst, uhr, konten(7), utc(12, 20))
        uhr.jetzt = utc(13, 16)
        dienst.bloecke_veroeffentlichen()
        uhr.jetzt = utc(13, 20)

        antwort = client.get("/api/v1/teams/meine", headers={"X-User": konten(1)[0]})

        assert antwort.status_code == 200
        live = antwort.json()["teams"][0]["live"]
        assert live == {
            "laeuft_noch": False,
            "mitglieder": 30,
            "bis": 14,
            "tagessumme": "rund 20",
            # Ziel min(100, 30 / 3) = 10, freigegeben 27
            "quest_stufe": 3,
            "hinweis_neu": True,
        }
        assert "27" not in str(live)

    def test_ohne_team_live_null(self, team, uhr):
        client, _ = self._client(team, uhr, settings=LIVE_AUS)
        uhr.jetzt = utc(13, 20)

        antwort = client.get("/api/v1/teams/meine", headers={"X-User": konten(1)[0]})

        assert antwort.json()["teams"][0]["live"] is None
