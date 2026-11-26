"""
Seitenaufrufe je Tag (#761) gegen ein echtes PostgreSQL: zaehlen, Grenze je Besucher,
verdichten am Tagesende (Pseudonyme weg, zwei Zahlen bleiben). Wegwerf-Schema aus der
Fixture ``datenbank`` von ``test_loeschkommando.py``.
"""

from datetime import date

import pytest
from sqlalchemy import text

from repositories import aufrufe_repository as modul
from repositories.aufrufe_repository import AufrufeRepository, AufrufTag
from tests.integration.test_loeschkommando import datenbank  # noqa: F401

pytestmark = pytest.mark.integration

GESTERN = date(2026, 11, 21)
HEUTE = date(2026, 11, 22)
P1 = "a" * 64
P2 = "b" * 64


def _zeilen(datenbank, tabelle):  # noqa: F811
    with datenbank.get_session() as s:
        return s.execute(text(f"SELECT count(*) FROM {tabelle}")).scalar()


class TestAufrufeRepository:
    def test_zaehlen_und_heute(self, datenbank):  # noqa: F811
        repo = AufrufeRepository(datenbank)
        repo.zaehlen(HEUTE, P1)
        repo.zaehlen(HEUTE, P1)
        repo.zaehlen(HEUTE, P2)

        assert repo.heute(HEUTE) == AufrufTag(HEUTE, aufrufe=3, besucher=2)
        assert repo.heute(GESTERN) == AufrufTag(GESTERN, aufrufe=0, besucher=0)

    def test_grenze_je_besucher(self, datenbank, monkeypatch):  # noqa: F811
        monkeypatch.setattr(modul, "AUFRUFE_JE_BESUCHER_HOECHSTENS", 2)
        repo = AufrufeRepository(datenbank)
        for _ in range(5):
            repo.zaehlen(HEUTE, P1)

        assert repo.heute(HEUTE).aufrufe == 2

    def test_verdichten_loescht_pseudonyme_und_behaelt_zahlen(
        self, datenbank  # noqa: F811
    ):
        repo = AufrufeRepository(datenbank)
        repo.zaehlen(GESTERN, P1)
        repo.zaehlen(GESTERN, P1)
        repo.zaehlen(GESTERN, P2)
        repo.zaehlen(HEUTE, P1)

        assert repo.verdichten_vor(HEUTE) == 2

        assert repo.tage(GESTERN) == [AufrufTag(GESTERN, aufrufe=3, besucher=2)]
        # Nur der laufende Tag hat noch ein Pseudonym
        with datenbank.get_session() as s:
            tage = s.execute(text("SELECT DISTINCT tag FROM aufrufe_heute")).scalars()
            assert list(tage) == [HEUTE]
        assert repo.verdichten_vor(HEUTE) == 0

    def test_nachzuegler_wird_addiert(self, datenbank):  # noqa: F811
        repo = AufrufeRepository(datenbank)
        repo.zaehlen(GESTERN, P1)
        repo.verdichten_vor(HEUTE)
        repo.zaehlen(GESTERN, P2)
        repo.verdichten_vor(HEUTE)

        assert repo.tage(GESTERN) == [AufrufTag(GESTERN, aufrufe=2, besucher=2)]
        assert _zeilen(datenbank, "aufrufe_heute") == 0
