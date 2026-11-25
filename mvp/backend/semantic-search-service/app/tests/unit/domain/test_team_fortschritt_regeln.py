"""
Regeln des Team-Fortschritts (#784) und der Team-Quests (#792): Schwelle von 5
Mitgliedern mit Einwilligung, Rundung (unter 10 "weniger als 10", darueber auf 5) und
das Wochenziel. Die Datenschutzerklaerung beschreibt genau diese Regeln.
"""

import pytest

from domain.team_fortschritt import (
    MINDESTMITGLIEDER,
    SUMME_GEDECKT,
    Wochenzaehlung,
    anzeige,
    gerundet,
    quest_ziel,
    zeigbar,
)
from domain.teams import EINWILLIGUNG_KENNUNG, EINWILLIGUNG_WORTLAUTE

pytestmark = pytest.mark.unit


class TestRundung:
    @pytest.mark.parametrize("anzahl", [0, 1, 5, 9])
    def test_unter_zehn_keine_zahl(self, anzahl):
        assert gerundet(anzahl) is None
        assert anzeige(anzahl) == "weniger als 10"

    @pytest.mark.parametrize(
        "anzahl, erwartet",
        [
            (10, 10),
            (11, 10),
            (12, 10),
            (13, 15),
            (14, 15),
            (15, 15),
            (17, 15),
            (18, 20),
            (42, 40),
            (43, 45),
            (1002, 1000),
        ],
    )
    def test_ab_zehn_auf_fuenf_gerundet(self, anzahl, erwartet):
        assert gerundet(anzahl) == erwartet
        assert anzeige(anzahl) == f"rund {erwartet}"

    def test_nie_die_genaue_zahl_ausser_bei_vielfachen_von_fuenf(self):
        for anzahl in range(10, 200):
            assert gerundet(anzahl) % 5 == 0
            assert abs(gerundet(anzahl) - anzahl) <= 2


class TestSchwelle:
    def test_ab_fuenf(self):
        assert MINDESTMITGLIEDER == 5
        assert not zeigbar(4)
        assert zeigbar(5)
        assert zeigbar(37)

    def test_gedeckt_nur_vom_wortlaut_mit_summe_aller_arten(self):
        # team-2026-11-25 nannte "Ja, gepostet" und Kommentare nicht
        assert SUMME_GEDECKT == {"team-2026-11-26"}
        assert EINWILLIGUNG_KENNUNG in SUMME_GEDECKT
        for kennung in SUMME_GEDECKT:
            text = EINWILLIGUNG_WORTLAUTE[kennung]
            for wort in (
                "Beiträge",
                "Bewertungen",
                "Kommentare",
                "Ja, gepostet",
                "Summe",
            ):
                assert wort in text


class TestQuestZiel:
    @pytest.mark.parametrize(
        "brachflaechen, mitglieder, ziel",
        [
            (10, 30, 10),  # Mitglieder / 3 = 10
            (4, 30, 4),  # weniger Brachflaechen als Mitglieder / 3
            (50, 31, 11),  # aufgerundet
            (50, 5, 3),  # mindestens 3
            (0, 40, 3),  # ohne Bedarf mindestens 3
            (2, 2, 3),
        ],
    )
    def test_ziel(self, brachflaechen, mitglieder, ziel):
        assert quest_ziel(brachflaechen, mitglieder) == ziel


def test_gesamt_summiert_alle_arten():
    assert Wochenzaehlung(beitraege=2, bewertungen=3, gepostet=4).gesamt == 9
