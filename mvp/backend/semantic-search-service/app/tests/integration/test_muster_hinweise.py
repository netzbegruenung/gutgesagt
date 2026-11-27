"""
Muster-Hinweise fuer Admins (#352) gegen ein echtes PostgreSQL: zwei Konten, die
innerhalb von sieben Tagen jeweils einen Beitrag des anderen nutzen. Wegwerf-Schema aus der
Fixture ``datenbank`` von ``test_loeschkommando.py``.
"""

import threading
from datetime import date, datetime, time, timedelta, timezone

import pytest

from repositories.muster_hinweis_repository import (
    NUTZUNG,
    ZUSTIMMUNG,
    MusterHinweisRepository,
)
from services.muster_hinweise_service import (
    MUSTER_FENSTER_TAGE,
    MUSTER_FRIST_TAGE,
    MusterHinweiseService,
)
from tests.integration.test_loeschkommando import datenbank  # noqa: F401

pytestmark = pytest.mark.integration

MONTAG = date(2026, 10, 26)


def _um(tag: date) -> datetime:
    return datetime.combine(tag, time(12), timezone.utc)


@pytest.fixture
def dienst(datenbank):  # noqa: F811
    return MusterHinweiseService(MusterHinweisRepository(datenbank))


class TestMusterHinweise:
    def test_nutzung_melden_gegenseitig_am_selben_tag_wird_hinweis(self, dienst):
        dienst.nutzung_melden("kim-1", "bo-2", _um(MONTAG))
        assert dienst.hinweise() == []

        dienst.nutzung_melden("bo-2", "kim-1", _um(MONTAG))

        [hinweis] = dienst.hinweise()
        assert (hinweis.konto_a, hinweis.konto_b) == ("bo-2", "kim-1")
        assert (hinweis.tage, hinweis.erster_tag, hinweis.letzter_tag) == (
            1,
            MONTAG,
            MONTAG,
        )

    def test_nutzung_melden_einseitig_kein_hinweis(self, dienst):
        for _ in range(3):
            dienst.nutzung_melden("kim-1", "bo-2", _um(MONTAG))

        assert dienst.hinweise() == []

    def test_nutzung_melden_gegenseitig_innerhalb_des_fensters_wird_hinweis(
        self, dienst
    ):
        spaeter = MONTAG + timedelta(MUSTER_FENSTER_TAGE - 1)
        dienst.nutzung_melden("kim-1", "bo-2", _um(MONTAG))
        dienst.nutzung_melden("bo-2", "kim-1", _um(spaeter))

        [hinweis] = dienst.hinweise()
        assert (hinweis.tage, hinweis.erster_tag, hinweis.letzter_tag) == (
            1,
            spaeter,
            spaeter,
        )

    def test_nutzung_melden_nach_dem_fenster_kein_hinweis(self, dienst):
        dienst.nutzung_melden("kim-1", "bo-2", _um(MONTAG))
        dienst.nutzung_melden(
            "bo-2", "kim-1", _um(MONTAG + timedelta(MUSTER_FENSTER_TAGE))
        )

        assert dienst.hinweise() == []

    def test_fristen_anwenden_verwirft_paar_pruefwerte_nach_dem_fenster(self, dienst):
        """Nach dem Lauf ist die alte Richtung weg, auch wenn noch jemand fragt."""
        dienst.nutzung_melden("kim-1", "bo-2", _um(MONTAG))

        dienst.fristen_anwenden(MONTAG + timedelta(MUSTER_FENSTER_TAGE))
        # Ein Nachzuegler mit altem Zeitstempel, noch im Fenster des ersten Tages.
        dienst.nutzung_melden("bo-2", "kim-1", _um(MONTAG + timedelta(1)))

        assert dienst.hinweise() == []

    def test_nutzung_melden_zaehlt_tage_nicht_nutzungen(self, dienst):
        for tag in [MONTAG, MONTAG + timedelta(2)]:
            for _ in range(2):
                dienst.nutzung_melden("kim-1", "bo-2", _um(tag))
                dienst.nutzung_melden("bo-2", "kim-1", _um(tag))

        [hinweis] = dienst.hinweise()
        assert (hinweis.tage, hinweis.erster_tag, hinweis.letzter_tag) == (
            2,
            MONTAG,
            MONTAG + timedelta(2),
        )

    def test_nutzung_melden_gleichzeitig_verliert_keinen_tag(self, dienst):
        """A nutzt B und B nutzt A im selben Augenblick: Der Tag zaehlt trotzdem."""
        for runde in range(10):
            a, b = f"a-{runde}", f"b-{runde}"
            start = threading.Barrier(2)

            def melden(von, an):
                start.wait()
                dienst.nutzung_melden(von, an, _um(MONTAG))

            faeden = [
                threading.Thread(target=melden, args=paar) for paar in [(a, b), (b, a)]
            ]
            for faden in faeden:
                faden.start()
            for faden in faeden:
                faden.join()

        assert len(dienst.hinweise()) == 10

    def test_nutzung_melden_eigene_und_anonyme_zaehlen_nicht(self, dienst):
        dienst.nutzung_melden("kim-1", "kim-1", _um(MONTAG))
        dienst.nutzung_melden(None, "kim-1", _um(MONTAG))
        dienst.nutzung_melden("anonymous", "kim-1", _um(MONTAG))
        dienst.nutzung_melden("kim-1", None, _um(MONTAG))

        assert dienst.hinweise() == []

    def test_fristen_anwenden_loescht_alte_hinweise(self, dienst):
        alt = MONTAG - timedelta(MUSTER_FRIST_TAGE + 1)
        for tag in [alt, MONTAG]:
            dienst.nutzung_melden(f"a-{tag}", f"b-{tag}", _um(tag))
            dienst.nutzung_melden(f"b-{tag}", f"a-{tag}", _um(tag))

        dienst.fristen_anwenden(MONTAG + timedelta(1))

        assert [h.letzter_tag for h in dienst.hinweise()] == [MONTAG]

    def test_vergessen_loescht_alle_hinweise_mit_der_person(self, dienst):
        """Widerruf: Hinweise mit der Person gehen, die anderer Paare bleiben."""
        for a, b in [("kim-1", "bo-2"), ("ali-3", "kim-1"), ("ali-3", "bo-2")]:
            dienst.nutzung_melden(a, b, _um(MONTAG))
            dienst.nutzung_melden(b, a, _um(MONTAG))
        assert len(dienst.hinweise()) == 3

        dienst.vergessen("kim-1")

        assert [(h.konto_a, h.konto_b) for h in dienst.hinweise()] == [
            ("ali-3", "bo-2")
        ]


def _gegenseitig(dienst, melden):
    melden("kim-1", "bo-2", _um(MONTAG))
    melden("bo-2", "kim-1", _um(MONTAG))


class TestZustimmungen:
    """
    Gegenseitige Zustimmungen (Schalter muster_stimmen): dieselbe Schwelle und Frist
    wie bei der Nutzung, ein eigener Hinweis je Art.
    """

    def test_gegenseitig_im_fenster_wird_eigener_hinweis(self, dienst):
        spaeter = MONTAG + timedelta(MUSTER_FENSTER_TAGE - 1)
        dienst.zustimmung_melden("kim-1", "bo-2", _um(MONTAG))
        assert dienst.hinweise() == []

        dienst.zustimmung_melden("bo-2", "kim-1", _um(spaeter))

        [hinweis] = dienst.hinweise()
        assert (hinweis.konto_a, hinweis.konto_b, hinweis.art) == (
            "bo-2",
            "kim-1",
            ZUSTIMMUNG,
        )
        assert (hinweis.tage, hinweis.erster_tag, hinweis.letzter_tag) == (
            1,
            spaeter,
            spaeter,
        )

    def test_nach_dem_fenster_kein_hinweis(self, dienst):
        dienst.zustimmung_melden("kim-1", "bo-2", _um(MONTAG))
        dienst.zustimmung_melden(
            "bo-2", "kim-1", _um(MONTAG + timedelta(MUSTER_FENSTER_TAGE))
        )

        assert dienst.hinweise() == []

    def test_einseitig_kein_hinweis(self, dienst):
        for tag in range(3):
            dienst.zustimmung_melden("kim-1", "bo-2", _um(MONTAG + timedelta(tag)))

        assert dienst.hinweise() == []

    def test_nutzung_und_zustimmung_mischen_sich_nicht(self, dienst):
        """A nutzt B, B stimmt A zu: keine der beiden Arten ist gegenseitig."""
        dienst.nutzung_melden("kim-1", "bo-2", _um(MONTAG))
        dienst.zustimmung_melden("bo-2", "kim-1", _um(MONTAG))

        assert dienst.hinweise() == []

    def test_beide_arten_stehen_nebeneinander(self, dienst):
        _gegenseitig(dienst, dienst.nutzung_melden)
        _gegenseitig(dienst, dienst.zustimmung_melden)

        assert sorted(h.art for h in dienst.hinweise()) == [NUTZUNG, ZUSTIMMUNG]

    def test_frist_gilt_auch_fuer_zustimmungen(self, dienst):
        _gegenseitig(dienst, dienst.zustimmung_melden)

        dienst.fristen_anwenden(MONTAG + timedelta(MUSTER_FRIST_TAGE + 1))

        assert dienst.hinweise() == []

    def test_widerruf_loescht_beide_arten(self, dienst):
        _gegenseitig(dienst, dienst.nutzung_melden)
        _gegenseitig(dienst, dienst.zustimmung_melden)

        dienst.vergessen("kim-1")

        assert dienst.hinweise() == []

    def test_widerruf_nur_des_zwecks_zustimmungen(self, dienst):
        _gegenseitig(dienst, dienst.nutzung_melden)
        _gegenseitig(dienst, dienst.zustimmung_melden)

        dienst.vergessen("kim-1", art=ZUSTIMMUNG)

        assert [h.art for h in dienst.hinweise()] == [NUTZUNG]
