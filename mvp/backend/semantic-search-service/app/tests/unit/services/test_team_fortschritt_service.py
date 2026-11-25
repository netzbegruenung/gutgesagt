"""
Team-Fortschritt (#784) und Team-Quests (#792) im Dienst, mit einem Repository im
Speicher: wer zaehlt (Einwilligung, Art.-9-Bedingung fuer "Ja, gepostet", keine
Startkonten, Schwelle), Entdoppelung ueber den Wochen-Pruefwert, was Mitglieder sehen
(nur die abgeschlossene Woche, gerundet, erst ab 5), das Wochenziel und die
Quest-Punkte. Schalter aus: nichts gezaehlt, nichts gezeigt, keine Datenbank.
"""

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Tuple
from unittest.mock import MagicMock

import pytest

from core.config import Settings
from domain.team_fortschritt import Art, Wochenzaehlung
from repositories.team_fortschritt_repository import EigenesTeam, Quest
from services.team_fortschritt_service import (
    TeamFortschrittService,
    WochenPruefwerte,
    bedarf_aus,
)

pytestmark = pytest.mark.unit

AN = Settings(teams_aktiv=True, team_fortschritt_aktiv=True, team_quests_aktiv=True)
OHNE_QUESTS = Settings(teams_aktiv=True, team_fortschritt_aktiv=True)
FORTSCHRITT_AUS = Settings(teams_aktiv=True, team_quests_aktiv=True)
TEAMS_AUS = Settings(team_fortschritt_aktiv=True, team_quests_aktiv=True)
MIT_STARTKONTO = Settings(
    teams_aktiv=True, team_fortschritt_aktiv=True, startkonten="start-1"
)

# Mittwoch; laufende Woche ab Montag 23.11., abgeschlossene ab 16.11.
HEUTE = date(2026, 11, 25)
LAUFENDE = date(2026, 11, 23)
VORIGE = date(2026, 11, 16)
TEAM = ("BDK 26 Berlin", "2026")
KLEIN = ("Bayreuth", "2026")
GEDECKT = "team-2026-11-26"
FRUEHER = "team-2026-11-25"


@dataclass
class Mitglied:
    konto: str
    team: Tuple[str, str]
    kennung: str = GEDECKT
    eingetreten_am: date = date(2026, 11, 1)


class Speicher:
    """TeamFortschrittRepository im Speicher, mit denselben Methoden."""

    def __init__(self, mitglieder: List[Mitglied]):
        self.mitglieder = mitglieder
        self.zaehler: Dict[tuple, Dict[str, int]] = {}
        self.quest_zeilen: Dict[tuple, Quest] = {}
        self.aufrufe = 0

    def eigene_teams(self, konto, kennungen):
        self.aufrufe += 1
        return [
            EigenesTeam(m.team[0], m.team[1], m.eingetreten_am)
            for m in self.mitglieder
            if m.konto == konto and m.kennung in kennungen
        ]

    def einwilligende_je_team(self, teams, kennungen):
        teams = list(teams)
        return {
            t: sum(1 for m in self.mitglieder if m.team == t and m.kennung in kennungen)
            for t in teams
        }

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

    def erreichte_quests(self, teams, vor):
        teams = list(teams)
        return [
            q
            for (t, woche), q in self.quest_zeilen.items()
            if t in teams
            and woche < vor
            and self.wochen([t], woche).get(t, Wochenzaehlung()).gesamt >= q.ziel
        ]

    def zahl(self, team, woche, spalte):
        return self.zaehler.get((team, woche), {}).get(spalte, 0)


def _team(n: int, team=TEAM, kennung=GEDECKT) -> List[Mitglied]:
    return [Mitglied(f"{team[0]}-{i}", team, kennung) for i in range(n)]


def _dienst(speicher, settings=AN, art9=lambda k: True, heute=HEUTE, bedarf=None):
    async def kein_bedarf():
        return ("energie-heizen", 10)

    return TeamFortschrittService(
        speicher,
        settings,
        art9=art9,
        bedarf=bedarf or kein_bedarf,
        heute=lambda: heute,
        saison=lambda: "2026",
    )


def _staende(dienst, konto):
    return asyncio.run(dienst.staende(konto))


class TestZaehlen:
    def test_beitrag_zaehlt_einmal_je_team(self):
        speicher = Speicher(_team(5))
        dienst = _dienst(speicher)

        assert dienst.zaehlen(f"{TEAM[0]}-0", Art.BEITRAG, "b-1") == 1
        assert dienst.zaehlen(f"{TEAM[0]}-0", Art.BEITRAG, "b-1") == 0
        assert dienst.zaehlen(f"{TEAM[0]}-0", Art.BEITRAG, "b-2") == 1

        assert speicher.zahl(TEAM, LAUFENDE, "beitraege") == 2

    def test_stimme_je_person_und_beitrag_einmal_je_woche(self):
        speicher = Speicher(_team(5))
        dienst = _dienst(speicher)

        # Umgedreht (like, dann dislike) zaehlt nicht doppelt
        dienst.zaehlen(f"{TEAM[0]}-0", Art.BEWERTUNG, "b-1")
        dienst.zaehlen(f"{TEAM[0]}-0", Art.BEWERTUNG, "b-1")
        dienst.zaehlen(f"{TEAM[0]}-1", Art.BEWERTUNG, "b-1")

        assert speicher.zahl(TEAM, LAUFENDE, "bewertungen") == 2

    def test_gepostet_je_person_einmal_je_woche(self):
        speicher = Speicher(_team(5))
        dienst = _dienst(speicher)

        for _ in range(3):
            dienst.zaehlen(f"{TEAM[0]}-0", Art.GEPOSTET)
        dienst.zaehlen(f"{TEAM[0]}-1", Art.GEPOSTET)

        assert speicher.zahl(TEAM, LAUFENDE, "gepostet") == 2

    def test_neue_woche_zaehlt_neu(self):
        speicher = Speicher(_team(5))
        pruefwerte = WochenPruefwerte()
        tage = iter([HEUTE, HEUTE + timedelta(days=7)])
        dienst = TeamFortschrittService(
            speicher,
            AN,
            art9=lambda k: True,
            heute=lambda: next(tage),
            pruefwerte=pruefwerte,
            saison=lambda: "2026",
        )

        dienst.zaehlen(f"{TEAM[0]}-0", Art.GEPOSTET)
        dienst.zaehlen(f"{TEAM[0]}-0", Art.GEPOSTET)

        assert speicher.zahl(TEAM, LAUFENDE, "gepostet") == 1
        assert speicher.zahl(TEAM, LAUFENDE + timedelta(days=7), "gepostet") == 1

    def test_gepostet_ohne_art9_einwilligung_zaehlt_nicht(self):
        speicher = Speicher(_team(5))
        gefragt = []
        dienst = _dienst(speicher, art9=lambda k: gefragt.append(k) or False)

        assert dienst.zaehlen(f"{TEAM[0]}-0", Art.GEPOSTET) == 0

        assert gefragt == [f"{TEAM[0]}-0"]
        assert speicher.zaehler == {}
        # Beitraege und Stimmen pruefen ihre Endpunkte; hier fragt der Dienst nicht.
        assert dienst.zaehlen(f"{TEAM[0]}-0", Art.BEITRAG, "b-1") == 1
        assert gefragt == [f"{TEAM[0]}-0"]

    def test_gepostet_mit_art9_einwilligung_zaehlt(self):
        speicher = Speicher(_team(5))
        dienst = _dienst(speicher, art9=lambda k: True)

        assert dienst.zaehlen(f"{TEAM[0]}-0", Art.GEPOSTET) == 1

    def test_startkonto_zaehlt_nicht(self):
        speicher = Speicher(_team(4) + [Mitglied("start-1", TEAM)])
        dienst = _dienst(speicher, settings=MIT_STARTKONTO)

        assert dienst.zaehlen("start-1", Art.BEITRAG, "b-1") == 0
        assert speicher.aufrufe == 0

    def test_unter_fuenf_wird_nicht_gezaehlt(self):
        speicher = Speicher(_team(4))
        dienst = _dienst(speicher)

        assert dienst.zaehlen(f"{TEAM[0]}-0", Art.BEITRAG, "b-1") == 0
        assert speicher.zaehler == {}

    def test_nur_einwilligung_mit_summe_zaehlt_mit_und_zur_schwelle(self):
        # Fuenf Mitglieder, aber eines mit dem frueheren Wortlaut ohne "Ja, gepostet"
        speicher = Speicher(_team(4) + [Mitglied("alt", TEAM, FRUEHER)])
        dienst = _dienst(speicher)

        assert dienst.zaehlen(f"{TEAM[0]}-0", Art.BEITRAG, "b-1") == 0
        speicher.mitglieder.append(Mitglied("neu", TEAM))
        assert dienst.zaehlen(f"{TEAM[0]}-0", Art.BEITRAG, "b-1") == 1
        assert dienst.zaehlen("alt", Art.BEITRAG, "b-9") == 0

    def test_mehrere_teams_nur_die_grossen(self):
        speicher = Speicher(
            _team(5) + _team(2, KLEIN) + [Mitglied(f"{TEAM[0]}-0", KLEIN)]
        )
        dienst = _dienst(speicher)

        assert dienst.zaehlen(f"{TEAM[0]}-0", Art.BEITRAG, "b-1") == 1
        assert speicher.zahl(KLEIN, LAUFENDE, "beitraege") == 0

    def test_ohne_team_nichts(self):
        speicher = Speicher(_team(5))
        assert _dienst(speicher).zaehlen("fremd", Art.BEITRAG, "b-1") == 0
        assert _dienst(speicher).zaehlen(None, Art.BEITRAG, "b-1") == 0

    @pytest.mark.parametrize("settings", [FORTSCHRITT_AUS, TEAMS_AUS, Settings()])
    def test_schalter_aus_zaehlt_nichts_und_fragt_keine_datenbank(self, settings):
        repository = MagicMock()
        dienst = _dienst(repository, settings=settings)

        for art in Art:
            assert dienst.zaehlen("konto", art, "b-1") == 0

        repository.assert_not_called()
        assert repository.method_calls == []

    def test_am_zaehler_keine_kennung_und_kein_beitrag(self):
        repository = MagicMock()
        repository.eigene_teams.return_value = [EigenesTeam(*TEAM, date(2026, 11, 1))]
        repository.einwilligende_je_team.return_value = {TEAM: 5}
        dienst = _dienst(repository)

        dienst.zaehlen("konto-geheim", Art.BEITRAG, "beitrag-geheim")

        repository.erhoehen.assert_called_once_with([TEAM], LAUFENDE, Art.BEITRAG)
        assert "konto-geheim" not in repr(repository.erhoehen.call_args)
        assert "beitrag-geheim" not in repr(repository.erhoehen.call_args)


class TestSaison:
    def test_vergangene_saison_zaehlt_nicht_und_zeigt_nichts(self):
        alt = ("BDK 26 Berlin", "2025")
        speicher = Speicher(_team(5, alt))
        dienst = _dienst(speicher)

        assert dienst.zaehlen(f"{alt[0]}-0", Art.BEITRAG, "b-1") == 0
        assert _staende(dienst, f"{alt[0]}-0") == {}
        assert speicher.zaehler == {}

    def test_quest_punkte_frueherer_saison_bleiben(self):
        alt = ("BDK 26 Berlin", "2025")
        speicher = Speicher(_team(5, alt))
        speicher.quest_zeilen[(alt, VORIGE)] = Quest(*alt, VORIGE, "klima", 3)
        speicher.zaehler[(alt, VORIGE)] = {"beitraege": 3}
        tage = _dienst(speicher).quest_tage(
            f"{alt[0]}-0",
            [datetime(2026, 11, 17, tzinfo=timezone.utc)],
            datetime(2026, 11, 22, tzinfo=timezone.utc),
        )
        assert tage == {LAUFENDE: 1}


class TestWochenPruefwerte:
    def test_kein_klartext_im_speicher(self):
        werte = WochenPruefwerte()
        werte.erstmals("beitrag|konto-geheim|b-1|Team|2026", LAUFENDE)

        assert all("konto-geheim" not in w for w in werte._werte)
        assert all(len(w) == 64 for w in werte._werte)

    def test_vorwoche_zaehlt_nach_dem_wechsel_nicht_mehr(self):
        werte = WochenPruefwerte()
        assert werte.erstmals("x", LAUFENDE)
        # Eine Anfrage, die noch zur Vorwoche gehoert: Die Vorwoche ist abgeschlossen.
        assert not werte.erstmals("y", VORIGE)

    def test_wochenwechsel_verwirft_die_alten_werte(self):
        werte = WochenPruefwerte()
        werte.erstmals("x", VORIGE)
        werte.erstmals("y", VORIGE)
        assert werte.erstmals("x", LAUFENDE)
        assert len(werte._werte) == 1


class TestZeigen:
    def test_nur_die_abgeschlossene_woche_gerundet(self):
        speicher = Speicher(_team(6))
        speicher.zaehler[(TEAM, VORIGE)] = {
            "beitraege": 13,
            "bewertungen": 9,
            "gepostet": 41,
        }
        # Die laufende Woche zeigt nie etwas
        speicher.zaehler[(TEAM, LAUFENDE)] = {"beitraege": 500}

        stand = _staende(_dienst(speicher, settings=OHNE_QUESTS), f"{TEAM[0]}-0")[TEAM]

        assert stand.wirkung.woche == VORIGE
        assert not stand.wirkung.waechst_noch
        assert stand.wirkung.beitraege == "rund 15"
        assert stand.wirkung.bewertungen == "weniger als 10"
        assert stand.wirkung.gepostet == "rund 40"
        # Keine Gesamtsumme: aus zwei gerundeten Zahlen liesse sich zurueckrechnen
        assert not hasattr(stand.wirkung, "gesamt")
        assert stand.quest is None

    def test_live_gezaehltes_erscheint_erst_nach_wochenende(self):
        speicher = Speicher(_team(5))
        dienst = _dienst(speicher, settings=OHNE_QUESTS)
        for i in range(5):
            dienst.zaehlen(f"{TEAM[0]}-{i}", Art.GEPOSTET)
            for b in range(3):
                dienst.zaehlen(f"{TEAM[0]}-{i}", Art.BEITRAG, f"b-{i}-{b}")

        heute = _staende(dienst, f"{TEAM[0]}-0")[TEAM].wirkung
        naechste_woche = _staende(
            _dienst(speicher, settings=OHNE_QUESTS, heute=HEUTE + timedelta(days=7)),
            f"{TEAM[0]}-0",
        )[TEAM].wirkung

        assert (heute.beitraege, heute.gepostet) == ("weniger als 10",) * 2
        assert naechste_woche.beitraege == "rund 15"
        assert naechste_woche.gepostet == "weniger als 10"

    def test_ohne_zeile_weniger_als_zehn(self):
        stand = _staende(
            _dienst(Speicher(_team(5)), settings=OHNE_QUESTS), f"{TEAM[0]}-0"
        )
        wirkung = stand[TEAM].wirkung
        assert (wirkung.beitraege, wirkung.bewertungen, wirkung.gepostet) == (
            "weniger als 10",
        ) * 3

    def test_unter_fuenf_waechst_noch_ohne_zahlen(self):
        speicher = Speicher(_team(4))
        speicher.zaehler[(TEAM, VORIGE)] = {"beitraege": 30}

        wirkung = _staende(_dienst(speicher), f"{TEAM[0]}-0")[TEAM].wirkung

        assert wirkung.waechst_noch
        assert (
            wirkung.beitraege,
            wirkung.bewertungen,
            wirkung.gepostet,
        ) == (None,) * 3

    def test_nur_eigene_teams(self):
        speicher = Speicher(_team(5) + _team(5, KLEIN))

        staende = _staende(_dienst(speicher), f"{TEAM[0]}-0")

        assert list(staende) == [TEAM]
        assert _staende(_dienst(speicher), "fremd") == {}

    def test_mitglied_ohne_deckende_einwilligung_sieht_nichts(self):
        speicher = Speicher(_team(5) + [Mitglied("alt", TEAM, FRUEHER)])
        assert _staende(_dienst(speicher), "alt") == {}

    @pytest.mark.parametrize("settings", [FORTSCHRITT_AUS, TEAMS_AUS, Settings()])
    def test_schalter_aus_zeigt_nichts(self, settings):
        repository = MagicMock()
        assert _staende(_dienst(repository, settings=settings), "konto") == {}
        assert repository.method_calls == []


class TestQuests:
    def test_ziel_aus_bedarf_beim_ersten_abruf(self):
        speicher = Speicher(_team(31))
        aufrufe = []

        async def bedarf():
            aufrufe.append(1)
            return ("energie-heizen", 50)

        dienst = _dienst(speicher, bedarf=bedarf)
        quest = _staende(dienst, f"{TEAM[0]}-0")[TEAM].quest
        _staende(dienst, f"{TEAM[0]}-1")

        assert quest.laufende == Quest(*TEAM, LAUFENDE, "energie-heizen", 11)
        assert not quest.vorige_geschafft
        assert quest.vorige_thema is None
        assert len(aufrufe) == 1

    def test_mindestziel_drei_auch_ohne_bedarf(self):
        async def ohne():
            return (None, 0)

        quest = _staende(_dienst(Speicher(_team(5)), bedarf=ohne), f"{TEAM[0]}-0")[
            TEAM
        ].quest
        assert quest.laufende.ziel == 3
        assert quest.laufende.thema is None

    def test_bedarf_scheitert_keine_quest_naechster_abruf_versucht_es_wieder(self):
        speicher = Speicher(_team(5))
        antworten = iter([RuntimeError("weg"), ("klima", 20)])

        async def bedarf():
            antwort = next(antworten)
            if isinstance(antwort, Exception):
                raise antwort
            return antwort

        dienst = _dienst(speicher, bedarf=bedarf)
        erste = _staende(dienst, f"{TEAM[0]}-0")[TEAM].quest
        zweite = _staende(dienst, f"{TEAM[0]}-0")[TEAM].quest

        assert erste.laufende is None
        assert zweite.laufende == Quest(*TEAM, LAUFENDE, "klima", 3)

    def test_geschafft_erst_nach_wochenende(self):
        speicher = Speicher(_team(5))
        speicher.quest_zeilen[(TEAM, VORIGE)] = Quest(*TEAM, VORIGE, "klima", 3)
        speicher.zaehler[(TEAM, VORIGE)] = {
            "beitraege": 1,
            "bewertungen": 1,
            "gepostet": 1,
        }

        quest = _staende(_dienst(speicher), f"{TEAM[0]}-0")[TEAM].quest

        assert quest.vorige_geschafft
        assert quest.vorige_thema == "klima"

    def test_verfehlt_wird_nicht_erwaehnt(self):
        speicher = Speicher(_team(5))
        speicher.quest_zeilen[(TEAM, VORIGE)] = Quest(*TEAM, VORIGE, "klima", 3)
        speicher.zaehler[(TEAM, VORIGE)] = {"beitraege": 2}

        quest = _staende(_dienst(speicher), f"{TEAM[0]}-0")[TEAM].quest

        assert not quest.vorige_geschafft
        assert quest.vorige_thema is None

    def test_unter_fuenf_keine_quest(self):
        speicher = Speicher(_team(4))
        assert _staende(_dienst(speicher), f"{TEAM[0]}-0")[TEAM].quest is None
        assert speicher.quest_zeilen == {}

    def test_ohne_schalter_keine_quest(self):
        speicher = Speicher(_team(5))
        assert (
            _staende(_dienst(speicher, settings=OHNE_QUESTS), f"{TEAM[0]}-0")[
                TEAM
            ].quest
            is None
        )
        assert speicher.quest_zeilen == {}


def _utc(tag: date, stunde=12) -> datetime:
    return datetime(tag.year, tag.month, tag.day, stunde, tzinfo=timezone.utc)


class TestQuestPunkte:
    GRENZE = _utc(HEUTE) - timedelta(days=3)

    def _erreicht(self, speicher, woche=VORIGE):
        speicher.quest_zeilen[(TEAM, woche)] = Quest(*TEAM, woche, "klima", 3)
        speicher.zaehler[(TEAM, woche)] = {"beitraege": 3}

    def test_mit_beitrag_in_der_woche(self):
        speicher = Speicher(_team(5))
        self._erreicht(speicher)

        tage = _dienst(speicher).quest_tage(
            f"{TEAM[0]}-0", [_utc(date(2026, 11, 17))], self.GRENZE
        )

        assert tage == {LAUFENDE: 1}

    def test_beitrag_juenger_als_drei_tage_noch_nicht(self):
        speicher = Speicher(_team(5))
        self._erreicht(speicher)
        # Sonntag der Quest-Woche, heute Mittwoch: noch keine drei Tage
        tage = _dienst(speicher).quest_tage(
            f"{TEAM[0]}-0", [_utc(date(2026, 11, 22), 23)], self.GRENZE
        )
        assert tage == {}

    def test_ohne_beitrag_in_der_woche_keine(self):
        speicher = Speicher(_team(5))
        self._erreicht(speicher)
        tage = _dienst(speicher).quest_tage(
            f"{TEAM[0]}-0", [_utc(date(2026, 11, 10))], self.GRENZE
        )
        assert tage == {}

    def test_verfehlt_keine(self):
        speicher = Speicher(_team(5))
        speicher.quest_zeilen[(TEAM, VORIGE)] = Quest(*TEAM, VORIGE, "klima", 3)
        speicher.zaehler[(TEAM, VORIGE)] = {"beitraege": 2}
        tage = _dienst(speicher).quest_tage(
            f"{TEAM[0]}-0", [_utc(date(2026, 11, 17))], self.GRENZE
        )
        assert tage == {}

    def test_laufende_woche_zaehlt_nicht(self):
        speicher = Speicher(_team(5))
        self._erreicht(speicher, LAUFENDE)
        tage = _dienst(speicher).quest_tage(
            f"{TEAM[0]}-0", [_utc(date(2026, 11, 17)), _utc(LAUFENDE)], _utc(HEUTE)
        )
        assert tage == {}

    def test_beitrag_vor_dem_beitritt_zaehlt_nicht(self):
        speicher = Speicher(_team(5))
        speicher.mitglieder[0].eingetreten_am = date(2026, 11, 19)
        self._erreicht(speicher)
        konto = speicher.mitglieder[0].konto
        dienst = _dienst(speicher)

        assert dienst.quest_tage(konto, [_utc(date(2026, 11, 17))], self.GRENZE) == {}
        assert dienst.quest_tage(konto, [_utc(date(2026, 11, 20))], self.GRENZE) == {
            LAUFENDE: 1
        }

    def test_ohne_deckende_einwilligung_keine(self):
        speicher = Speicher(_team(5) + [Mitglied("alt", TEAM, FRUEHER)])
        self._erreicht(speicher)
        assert (
            _dienst(speicher).quest_tage("alt", [_utc(date(2026, 11, 17))], self.GRENZE)
            == {}
        )

    def test_ohne_schalter_keine(self):
        repository = MagicMock()
        assert (
            _dienst(repository, settings=OHNE_QUESTS).quest_tage(
                "konto", [_utc(date(2026, 11, 17))], self.GRENZE
            )
            == {}
        )
        assert repository.method_calls == []


class TestBedarf:
    def test_thema_mit_den_meisten_aussagen(self):
        assert bedarf_aus(
            [
                ["klima"],
                ["energie-heizen", "klima"],
                ["energie-heizen"],
                ["energie-heizen"],
            ]
        ) == ("energie-heizen", 3)

    def test_gleichstand_nach_der_festen_liste(self):
        # klima steht in themen.json vor energie-heizen
        assert bedarf_aus([["energie-heizen"], ["klima"]]) == ("klima", 1)

    def test_ohne_themen(self):
        assert bedarf_aus([[], ["unbekannt"]]) == (None, 0)
