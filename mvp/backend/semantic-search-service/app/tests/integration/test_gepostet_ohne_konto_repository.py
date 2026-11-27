"""
Meldungen ohne Konto (#799) gegen ein echtes PostgreSQL: je Klick +1 auf die Zahl der
Woche, getrennt von "Ja, gepostet" mit Konto; die Tabelle hat keine Spalte fuer einen
Pruefwert, eine Adresse oder einen Beitrag; das Saison-Ziel zaehlt sie nicht.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
from sqlalchemy import text

from core.config import Settings
from infrastructure.database.models import (
    Base,
    EinladungZeile,
    GepostetOhneKontoWoche,
    GepostetPruefwert,
    GepostetWoche,
    SaisonZeile,
)
from repositories.gepostet_ohne_konto_repository import GepostetOhneKontoRepository
from repositories.gepostet_repository import GepostetRepository
from repositories.saison_repository import SaisonRepository
from services.gepostet_ohne_konto_service import GepostetOhneKontoService
from services.saison_service import SaisonService

pytestmark = pytest.mark.integration

MO = date(2026, 11, 30)
# einladungen: Saison anlegen gibt Teamlinks mit ihrem Namen die ID (#858,
# repositories/saison_repository.py)
TABELLEN = [
    EinladungZeile.__table__,
    GepostetOhneKontoWoche.__table__,
    GepostetPruefwert.__table__,
    GepostetWoche.__table__,
    SaisonZeile.__table__,
]


@pytest.fixture
def db(wegwerf_schema):
    Base.metadata.create_all(wegwerf_schema.engine, tables=TABELLEN)
    return wegwerf_schema


def _anzahl(db, tabelle: str) -> int:
    with db.get_session() as s:
        return s.execute(text(f"SELECT count(*) FROM {tabelle}")).scalar()


def test_je_klick_plus_eins_je_woche(db):
    dienst = GepostetOhneKontoService(GepostetOhneKontoRepository(db))
    for _ in range(3):
        dienst.melden(heute=MO + timedelta(days=2))
    dienst.melden(heute=MO + timedelta(days=7))

    assert dienst.wochenzahlen(MO, MO + timedelta(weeks=1)) == {
        MO: 3,
        MO + timedelta(weeks=1): 1,
    }


def test_gleichzeitige_klicks_gehen_nicht_verloren(db):
    repo = GepostetOhneKontoRepository(db)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: repo.zaehlen(MO), range(40)))

    assert repo.wochen(MO, MO) == {MO: 40}


def test_getrennt_von_gepostet_mit_konto(db):
    GepostetOhneKontoRepository(db).zaehlen(MO)
    GepostetOhneKontoRepository(db).zaehlen(MO)
    GepostetRepository(db).melden("a" * 64, MO)

    assert GepostetRepository(db).wochen(MO, MO) == {MO: 1}
    assert _anzahl(db, "gepostet_pruefwerte") == 1
    assert GepostetOhneKontoRepository(db).wochen(MO, MO) == {MO: 2}


def test_kein_pruefwert_gespeichert(db):
    """Nur Woche und Zahl: keine Spalte, in der eine Adresse oder ein Pruefwert stehen koennte."""
    GepostetOhneKontoRepository(db).zaehlen(MO)
    with db.get_session() as s:
        spalten = {
            zeile[0]: zeile[1]
            for zeile in s.execute(
                text(
                    "SELECT column_name, data_type FROM information_schema.columns"
                    " WHERE table_name = 'gepostet_ohne_konto_wochen'"
                    " AND table_schema = current_schema()"
                )
            )
        }
        zeilen = s.execute(
            text("SELECT woche, meldungen FROM gepostet_ohne_konto_wochen")
        ).all()

    assert spalten == {"woche": "date", "meldungen": "integer"}
    assert [tuple(z) for z in zeilen] == [(MO, 1)]
    # Auch nicht nebenbei bei "Ja, gepostet" mit Konto
    assert _anzahl(db, "gepostet_pruefwerte") == 0


def test_saison_ziel_zaehlt_sie_nicht(db):
    ohne_konto = GepostetOhneKontoRepository(db)
    gepostet = GepostetRepository(db)
    service = SaisonService(
        SaisonRepository(db),
        gepostet.wochen,
        einstellungen=Settings(
            saison_ziel_schwelle_menschen=1, saison_ziel_schwelle_wochen=1
        ),
        ohne_konto_wochenzahlen=ohne_konto.wochen,
        wirksam=lambda _s: True,
    )
    service.anlegen("Winter 26", MO, MO + timedelta(weeks=8), 10, heute=MO)
    for _ in range(50):
        ohne_konto.zaehlen(MO)
    heute = MO + timedelta(weeks=1)

    [stand] = service.admin_stand(heute=heute).saisons

    assert stand.erreicht == 0
    assert stand.meldungen_ohne_konto == 50
    assert service.admin_stand(heute=heute).schwelle_erreicht is False
    assert service.balken(heute=heute) is None
