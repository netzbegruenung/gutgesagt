"""
Ankuenfte je Kampagnenwort und Tag gegen ein echtes PostgreSQL: Upsert je Wort und Tag,
auch gleichzeitig; die Tabelle hat nur Wort, Tag und Zahl; die Frist loescht alte Tage.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from infrastructure.database.models import AnkunftJeTag, Base
from repositories.ankunft_repository import AnkunftRepository
from services.ankunft_service import AnkuenfteAmTag, AnkunftService

pytestmark = pytest.mark.integration

TAG = date(2026, 12, 4)


@pytest.fixture
def db(wegwerf_schema):
    Base.metadata.create_all(wegwerf_schema.engine, tables=[AnkunftJeTag.__table__])
    return wegwerf_schema


def test_je_aufruf_plus_eins_je_wort_und_tag(db):
    dienst = AnkunftService(AnkunftRepository(db))
    for _ in range(3):
        dienst.zaehlen("bdk", heute=TAG)
    dienst.zaehlen("sticker", heute=TAG)
    dienst.zaehlen("bdk", heute=TAG - timedelta(days=1))

    assert dienst.letzte_tage(heute=TAG) == [
        AnkuenfteAmTag(tag=TAG, k="bdk", anzahl=3),
        AnkuenfteAmTag(tag=TAG, k="sticker", anzahl=1),
        AnkuenfteAmTag(tag=TAG - timedelta(days=1), k="bdk", anzahl=1),
    ]


def test_gleichzeitig_geht_nichts_verloren(db):
    repository = AnkunftRepository(db)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: repository.zaehlen("g1", TAG), range(40)))

    assert repository.tage(TAG) == [(TAG, "g1", 40)]


def test_nur_wort_tag_und_zahl(db):
    with db.get_session() as s:
        spalten = {
            zeile[0]
            for zeile in s.execute(
                text(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_name = 'ankuenfte_je_tag'"
                    " AND table_schema = current_schema()"
                )
            )
        }

    assert spalten == {"k", "tag", "anzahl"}


def test_frist_loescht_tage_vor_der_grenze(db):
    repository = AnkunftRepository(db)
    repository.zaehlen("bdk", TAG - timedelta(days=366))
    repository.zaehlen("bdk", TAG - timedelta(days=365))

    grenze = datetime.combine(
        TAG - timedelta(days=365), datetime.min.time(), timezone.utc
    )
    assert repository.loeschen_vor(grenze) == 1
    assert repository.tage(TAG - timedelta(days=400)) == [
        (TAG - timedelta(days=365), "bdk", 1)
    ]
