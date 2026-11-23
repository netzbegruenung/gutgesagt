"""Unit-Tests fuer das Zaehlen des Tagesdeckels (utils/tagesdeckel.py)."""

from datetime import date, timedelta

import pytest

from core.config import settings
from utils.tagesdeckel import Tagesdeckel, tagesdeckel

pytestmark = pytest.mark.unit


class Uhr:
    def __init__(self) -> None:
        self.tag = date(2026, 12, 4)

    def __call__(self) -> date:
        return self.tag


def test_bis_zum_deckel_frei_danach_nicht():
    deckel = Tagesdeckel(3, Uhr())

    tag = date(2026, 12, 4)

    assert [deckel.reservieren("alice") for _ in range(4)] == [tag, tag, tag, None]


def test_jede_person_hat_einen_eigenen_deckel():
    deckel = Tagesdeckel(1, Uhr())
    deckel.reservieren("alice")

    assert deckel.reservieren("bob") is not None


def test_freigeben_gibt_den_platz_zurueck():
    deckel = Tagesdeckel(2, Uhr())
    deckel.reservieren("alice")
    tag = deckel.reservieren("alice")

    deckel.freigeben("alice", tag)

    assert deckel.reservieren("alice") is not None
    assert deckel.reservieren("alice") is None


def test_freigeben_ohne_reservierung_bleibt_bei_null():
    deckel = Tagesdeckel(1, Uhr())

    deckel.freigeben("alice", date(2026, 12, 4))

    assert "alice" not in deckel._zaehler
    assert deckel.reservieren("alice") is not None


def test_am_naechsten_utc_tag_geht_es_weiter():
    uhr = Uhr()
    deckel = Tagesdeckel(1, uhr)
    deckel.reservieren("alice")
    assert deckel.reservieren("alice") is None

    uhr.tag += timedelta(days=1)

    assert deckel.reservieren("alice") is not None


def test_freigeben_ueber_mitternacht_zaehlt_den_neuen_tag_nicht_herunter():
    uhr = Uhr()
    deckel = Tagesdeckel(5, uhr)
    gestern = deckel.reservieren("alice")
    uhr.tag += timedelta(days=1)
    deckel.reservieren("alice")

    deckel.freigeben("alice", gestern)

    assert deckel._zaehler["alice"] == (uhr.tag, 1)


@pytest.mark.asyncio
async def test_aufraeumen_entfernt_zaehler_von_gestern():
    uhr = Uhr()
    deckel = Tagesdeckel(5, uhr)
    deckel.reservieren("gestern")
    uhr.tag += timedelta(days=1)
    deckel.reservieren("heute")

    await deckel.cleanup()

    assert set(deckel._zaehler) == {"heute"}


def test_der_globale_deckel_nimmt_den_wert_aus_der_konfiguration():
    assert tagesdeckel.je_tag == settings.tagesdeckel_beitraege
