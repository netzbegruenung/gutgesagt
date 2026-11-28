"""
Hinweis zum Einladungslink waehrend der BDK (services/bdk_hinweis.py, Rundgang 28.11.2026):
nur mit dem Paket k_begruessung und nur von bdk_hinweis_von bis bdk_hinweis_bis
(deutsche Zeit, je einschliesslich).
"""

from datetime import date

import pytest

from core.config import Settings
from services.bdk_hinweis import bdk_hinweis_an
from services.einstellungen_service import (
    BDK_HINWEIS_BIS,
    BDK_HINWEIS_VON,
    EinstellungenService,
    UngueltigerWert,
    einstellungen_service_setzen,
    wert_bereinigen,
)
from services.schalter_service import SchalterService, schalter_service_setzen

pytestmark = pytest.mark.unit

AN = Settings(k_begruessung_aktiv=True)


@pytest.fixture
def paket():
    werte = {"k_begruessung": True}
    schalter_service_setzen(
        SchalterService(
            admin_werte_lesen=lambda: dict(werte),
            admin_wert_setzen=lambda *a: None,
            cache_sekunden=0,
        )
    )
    yield werte
    schalter_service_setzen(None)


@pytest.fixture
def einstellungen():
    gespeichert = {}
    einstellungen_service_setzen(
        EinstellungenService(
            lesen=lambda: dict(gespeichert), setzen=lambda *a: None, cache_sekunden=0
        )
    )
    yield gespeichert
    einstellungen_service_setzen(None)


def _tag(t):
    return lambda: t


@pytest.mark.parametrize(
    "heute, erwartet",
    [
        (date(2026, 12, 3), False),  # vorher
        (date(2026, 12, 4), True),  # erster Tag
        (date(2026, 12, 5), True),
        (date(2026, 12, 6), True),  # letzter Tag, einschliesslich
        (date(2026, 12, 7), False),  # danach
    ],
)
def test_standardfenster_bdk(paket, einstellungen, heute, erwartet):
    assert bdk_hinweis_an(AN, heute=_tag(heute)) is erwartet


def test_paket_aus_kein_hinweis_auch_im_fenster(paket, einstellungen):
    paket["k_begruessung"] = False
    assert bdk_hinweis_an(AN, heute=_tag(date(2026, 12, 5))) is False


def test_ohne_obergrenze_kein_hinweis(paket, einstellungen):
    assert bdk_hinweis_an(Settings(), heute=_tag(date(2026, 12, 5))) is False


def test_fenster_aus_den_einstellungen(paket, einstellungen):
    einstellungen.update({BDK_HINWEIS_VON: "2027-01-10", BDK_HINWEIS_BIS: "2027-01-11"})
    assert bdk_hinweis_an(AN, heute=_tag(date(2026, 12, 5))) is False
    assert bdk_hinweis_an(AN, heute=_tag(date(2027, 1, 11))) is True


def test_unlesbarer_wert_kein_hinweis(paket, einstellungen):
    einstellungen[BDK_HINWEIS_BIS] = "kaputt"
    assert bdk_hinweis_an(AN, heute=_tag(date(2026, 12, 5))) is False


@pytest.mark.parametrize("name", [BDK_HINWEIS_VON, BDK_HINWEIS_BIS])
def test_nur_tage_als_wert(name):
    assert wert_bereinigen(name, "2026-12-04") == "2026-12-04"
    with pytest.raises(UngueltigerWert):
        wert_bereinigen(name, "4.12.2026")
