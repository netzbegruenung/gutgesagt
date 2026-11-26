"""Zuwachs zur Bestandszahl (domain/bestandszahl.py): ehrlich, nie "0 neu", ohne Uhrzeit."""

from datetime import date, datetime, timedelta, timezone

import pytest

from domain.bestandszahl import (
    ZUWACHS_AB,
    ZUWACHS_TAGE,
    Zuwachs,
    tag_in_deutschland,
    zeitraum_beginn,
    zuwachs,
)

pytestmark = pytest.mark.unit

UTC = timezone.utc


def test_ab_drei_die_genaue_zahl_ohne_tag():
    assert ZUWACHS_AB == 3
    assert zuwachs(3, []) == Zuwachs(neu=3, zuletzt_ergaenzt=None)
    assert zuwachs(12, [datetime(2026, 11, 25, tzinfo=UTC)]).neu == 12


def test_unter_drei_nur_der_tag_des_neuesten():
    z = zuwachs(
        2,
        [datetime(2026, 11, 20, 9, tzinfo=UTC), datetime(2026, 11, 24, 9, tzinfo=UTC)],
    )
    assert z == Zuwachs(neu=None, zuletzt_ergaenzt=date(2026, 11, 24))


def test_nichts_neu_weder_zahl_noch_tag():
    assert zuwachs(0, []) == Zuwachs(neu=None, zuletzt_ergaenzt=None)
    # Zaehlung und Zeitpunkte passen nicht zusammen: lieber nichts als etwas Falsches
    assert zuwachs(1, []) == Zuwachs(neu=None, zuletzt_ergaenzt=None)


def test_tag_in_deutscher_zeit():
    # Winterzeit: 23:30 UTC ist in Deutschland schon der naechste Tag
    assert tag_in_deutschland(datetime(2026, 11, 24, 23, 30, tzinfo=UTC)) == date(
        2026, 11, 25
    )
    # Ohne Zeitzone gilt UTC
    assert tag_in_deutschland(datetime(2026, 11, 24, 12, 0)) == date(2026, 11, 24)


def test_rollierende_sieben_tage():
    jetzt = datetime(2026, 11, 26, 0, 45, tzinfo=UTC)
    assert ZUWACHS_TAGE == 7
    assert zeitraum_beginn(jetzt) == jetzt - timedelta(days=7)
