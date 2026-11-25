"""
Wirkungs-Echo und Danke (#790, #791) gegen ein echtes PostgreSQL: Summen je Beitrag
ohne Kennung und Zeitpunkt, das Danke entdoppelt ueber ``nutzung_heute``.
Wegwerf-Schema aus der Fixture ``datenbank`` von ``test_loeschkommando.py``.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import text

from repositories.usage_tracking_repository import UsageTrackingRepository
from repositories.wirkung_repository import WirkungRepository
from tests.integration.test_loeschkommando import datenbank  # noqa: F401

pytestmark = pytest.mark.integration

BEITRAG = uuid.UUID("11111111-1111-4111-8111-111111111111")
ANDERER = uuid.UUID("22222222-2222-4222-8222-222222222222")
HEUTE = date(2026, 11, 26)


class TestWirkung:
    def test_gepostet_zaehlt_je_meldung(self, datenbank):  # noqa: F811
        repo = WirkungRepository(datenbank)
        repo.gepostet_zaehlen(BEITRAG)
        repo.gepostet_zaehlen(BEITRAG)

        assert repo.je_beitrag([BEITRAG, ANDERER]) == {
            str(BEITRAG): (2, 0),
            str(ANDERER): (0, 0),
        }

    def test_danke_einmal_je_pruefwert(self, datenbank):  # noqa: F811
        repo = WirkungRepository(datenbank)

        assert repo.danke_zaehlen(BEITRAG, "a" * 64, HEUTE) is True
        assert repo.danke_zaehlen(BEITRAG, "a" * 64, HEUTE) is False
        assert repo.danke_zaehlen(BEITRAG, "b" * 64, HEUTE) is True
        repo.gepostet_zaehlen(BEITRAG)

        assert repo.je_beitrag([BEITRAG]) == {str(BEITRAG): (1, 2)}

    def test_pruefwerte_gehen_mit_dem_tageswechsel(self, datenbank):  # noqa: F811
        repo = WirkungRepository(datenbank)
        repo.danke_zaehlen(BEITRAG, "a" * 64, HEUTE)

        UsageTrackingRepository(datenbank).vergangene_tage_verwerfen(date(2026, 11, 27))

        with datenbank.get_session() as c:
            assert c.execute(text("SELECT count(*) FROM nutzung_heute")).scalar() == 0
        assert repo.je_beitrag([BEITRAG]) == {str(BEITRAG): (0, 1)}

    def test_keine_kennung_und_kein_zeitpunkt_am_zaehler(self, datenbank):  # noqa: F811
        with datenbank.get_session() as c:
            spalten = {
                zeile[0]
                for zeile in c.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'wirkung_je_beitrag' "
                        "AND table_schema = current_schema()"
                    )
                )
            }
        assert spalten == {"content_id", "oeffentlich_gepostet", "danke"}

    def test_leere_liste(self, datenbank):  # noqa: F811
        assert WirkungRepository(datenbank).je_beitrag([]) == {}
