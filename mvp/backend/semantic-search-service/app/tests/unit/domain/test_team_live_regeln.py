"""
Regeln des Team-Fortschritts quasi-live (Schalter team_live, Jura-Akte 28.11.2026):
k = 10 verschiedene Beitragende je Block, Live erst ab 20 Mitgliedern mit
Einwilligung, Tagessumme und Mitgliederzahl auf 10 abgerundet, Quest-Stufe in
Dritteln, Stundenbloecke in deutscher Zeit. Die Datenschutzerklaerung beschreibt genau
diese Regeln.
"""

from datetime import datetime, timezone

import pytest

from domain.team_fortschritt import (
    LIVE_K,
    LIVE_MINDESTMITGLIEDER,
    abgerundet,
    bis_stunde,
    blockbeginn,
    freigeben,
    live_anzeige,
    live_zeigbar,
    mitglieder_anzeige,
    quest_stufe,
    tagesbeginn,
)

pytestmark = pytest.mark.unit


def test_parameter_der_akte():
    assert LIVE_K == 10
    assert LIVE_MINDESTMITGLIEDER == 20


class TestSchwelle:
    @pytest.mark.parametrize("n, erwartet", [(0, False), (19, False), (20, True)])
    def test_live_erst_ab_zwanzig(self, n, erwartet):
        assert live_zeigbar(n) is erwartet


class TestFreigabe:
    @pytest.mark.parametrize("verschiedene", [0, 1, 9])
    def test_unter_k_nicht(self, verschiedene):
        assert freigeben(verschiedene, beobachtet=True) is False

    @pytest.mark.parametrize("verschiedene", [10, 11, 50])
    def test_ab_k(self, verschiedene):
        assert freigeben(verschiedene, beobachtet=True) is True

    def test_ohne_vollstaendige_menge_nie(self):
        """Nach einem Neustart fehlt die Menge: uebertragen, nicht freigeben."""
        assert freigeben(100, beobachtet=False) is False


class TestRundung:
    @pytest.mark.parametrize("anzahl", [0, 1, 9])
    def test_unter_zehn_keine_zahl(self, anzahl):
        assert abgerundet(anzahl) is None
        assert live_anzeige(anzahl) == "weniger als 10"

    @pytest.mark.parametrize(
        "anzahl, erwartet", [(10, 10), (14, 10), (15, 10), (19, 10), (20, 20), (89, 80)]
    )
    def test_auf_zehn_abgerundet(self, anzahl, erwartet):
        assert abgerundet(anzahl) == erwartet
        assert live_anzeige(anzahl) == f"rund {erwartet}"

    @pytest.mark.parametrize(
        "n, erwartet", [(0, None), (19, None), (20, 20), (29, 20), (30, 30), (47, 40)]
    )
    def test_mitgliederzahl_ab_zwanzig_abgerundet(self, n, erwartet):
        assert mitglieder_anzeige(n) == erwartet


class TestQuestStufe:
    @pytest.mark.parametrize(
        "freigegeben, ziel, stufe",
        [
            (0, 9, 0),
            (2, 9, 0),
            (3, 9, 1),
            (5, 9, 1),
            (6, 9, 2),
            (8, 9, 2),
            (9, 9, 3),
            (20, 9, 3),
            (3, 10, 0),
            (4, 10, 1),
            (7, 10, 2),
        ],
    )
    def test_drittel(self, freigegeben, ziel, stufe):
        assert quest_stufe(freigegeben, ziel) == stufe


class TestZeit:
    def test_block_ist_die_volle_stunde(self):
        z = datetime(2026, 12, 4, 13, 47, 12, tzinfo=timezone.utc)
        assert blockbeginn(z) == datetime(2026, 12, 4, 13, tzinfo=timezone.utc)

    def test_tagesbeginn_deutsche_zeit_winter(self):
        # 00:30 deutsche Zeit am 5.12. ist 23:30 UTC am 4.12.
        z = datetime(2026, 12, 4, 23, 30, tzinfo=timezone.utc)
        assert tagesbeginn(z) == datetime(2026, 12, 4, 23, tzinfo=timezone.utc)

    def test_tagesbeginn_deutsche_zeit_sommer(self):
        z = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
        assert tagesbeginn(z) == datetime(2026, 6, 30, 22, tzinfo=timezone.utc)

    def test_bis_stunde_deutsche_zeit(self):
        # Block 12:00 UTC = 13 bis 14 Uhr deutsche Zeit
        assert bis_stunde(datetime(2026, 12, 4, 12, tzinfo=timezone.utc)) == 14
        # Letzter Block des Tages endet um Mitternacht
        assert bis_stunde(datetime(2026, 12, 4, 22, tzinfo=timezone.utc)) == 24
