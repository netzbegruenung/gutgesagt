"""
Wirkungs-Echo und Danke (#790, #791): nur Summen je Beitrag, entdoppelt je Person,
Beitrag und Tag; das Echo nur im Arbeitsspeicher, das Danke ueber den Tages-Pruefwert.
"""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest

from services.wirkung_service import EchoMerker, WirkungService

pytestmark = pytest.mark.unit

BEITRAG = uuid.UUID("11111111-1111-4111-8111-111111111111")
ANDERER = uuid.UUID("22222222-2222-4222-8222-222222222222")
MITTAG = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
FOLGETAG = datetime(2026, 11, 27, 9, 0, tzinfo=timezone.utc)


class TestEchoMerker:
    def test_einmal_je_person_beitrag_und_tag(self):
        merker = EchoMerker()
        tag = date(2026, 11, 26)

        assert merker.erstmals("kim", BEITRAG, tag) is True
        assert merker.erstmals("kim", BEITRAG, tag) is False
        assert merker.erstmals("kim", ANDERER, tag) is True
        assert merker.erstmals("bo", BEITRAG, tag) is True

    def test_neuer_tag_zaehlt_wieder(self):
        merker = EchoMerker()

        assert merker.erstmals("kim", BEITRAG, date(2026, 11, 26)) is True
        assert merker.erstmals("kim", BEITRAG, date(2026, 11, 27)) is True

    def test_haelt_keine_kennung(self):
        merker = EchoMerker()
        merker.erstmals("kim-geheim", BEITRAG, date(2026, 11, 26))

        assert not any("kim-geheim" in wert for wert in merker._gesehen)
        assert not any(str(BEITRAG) in wert for wert in merker._gesehen)

    def test_obergrenze_beginnt_neu(self):
        merker = EchoMerker(hoechstens=1)
        tag = date(2026, 11, 26)
        merker.erstmals("kim", BEITRAG, tag)
        merker.erstmals("bo", BEITRAG, tag)

        assert len(merker._gesehen) == 1


class TestGepostet:
    def test_zaehlt_nur_das_erste_mal_am_tag(self):
        repo = Mock()
        dienst = WirkungService(repo)

        assert dienst.gepostet_melden("kim", BEITRAG, MITTAG) is True
        assert dienst.gepostet_melden("kim", BEITRAG, MITTAG) is False
        assert dienst.gepostet_melden("kim", BEITRAG, FOLGETAG) is True

        assert repo.gepostet_zaehlen.call_count == 2
        repo.gepostet_zaehlen.assert_called_with(BEITRAG)


class TestDanke:
    def test_gleicher_pruefwert_fuer_person_beitrag_und_tag(self):
        repo = Mock()
        repo.danke_zaehlen.return_value = True
        dienst = WirkungService(repo)

        dienst.danke_sagen("kim", None, BEITRAG, MITTAG)
        dienst.danke_sagen("kim", None, BEITRAG, MITTAG)
        dienst.danke_sagen("kim", None, ANDERER, MITTAG)
        dienst.danke_sagen(None, "anschluss-1", BEITRAG, MITTAG)

        werte = [c.args[1] for c in repo.danke_zaehlen.call_args_list]
        assert werte[0] == werte[1]
        assert len({werte[0], werte[2], werte[3]}) == 3
        assert all("kim" not in w for w in werte)
        assert repo.danke_zaehlen.call_args_list[0].args[2] == date(2026, 11, 26)

    def test_niemand_erkennbar_zaehlt_nicht(self):
        repo = Mock()

        assert WirkungService(repo).danke_sagen(None, None, BEITRAG, MITTAG) is False
        repo.danke_zaehlen.assert_not_called()

    def test_anderer_pruefwert_als_die_nutzung(self):
        """Eine Kopie verbraucht kein Danke und umgekehrt."""
        from services.entdoppelung import danke_pruefwert, pruefwert

        assert pruefwert("kim", None, BEITRAG, MITTAG) != danke_pruefwert(
            "kim", None, BEITRAG, MITTAG
        )


class TestNachtragen:
    def test_nur_mit_schalter(self):
        repo = Mock()
        repo.je_beitrag.return_value = {str(BEITRAG): (3, 5)}
        dienst = WirkungService(repo)

        beide = dienst.nachtragen([{"id": str(BEITRAG)}], True, True)
        nur_danke = dienst.nachtragen([{"id": str(BEITRAG)}], False, True)
        keins = dienst.nachtragen([{"id": str(BEITRAG)}], False, False)

        assert beide == [{"id": str(BEITRAG), "oeffentlich_gepostet": 3, "danke": 5}]
        assert nur_danke == [{"id": str(BEITRAG), "danke": 5}]
        assert keins == [{"id": str(BEITRAG)}]
        assert repo.je_beitrag.call_count == 2

    def test_summe(self):
        repo = Mock()
        repo.je_beitrag.return_value = {str(BEITRAG): (3, 5), str(ANDERER): (2, 0)}

        assert WirkungService(repo).gepostet_summe([BEITRAG, ANDERER]) == 5
