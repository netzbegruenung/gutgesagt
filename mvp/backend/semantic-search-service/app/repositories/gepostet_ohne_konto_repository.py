"""
Repository fuer die Meldungen ohne Konto (#799): je Kalenderwoche nur eine Zahl
(``gepostet_ohne_konto_wochen``). Jeder Aufruf von ``zaehlen`` erhoeht sie um eins;
mehr wird nicht gespeichert, auch kein Pruefwert. Getrennt von
repositories/gepostet_repository.py, das verschiedene Menschen mit Konto zaehlt.
"""

from datetime import date
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from infrastructure.database.connection import AppDatabase, get_app_database
from infrastructure.database.models import GepostetOhneKontoWoche


class GepostetOhneKontoRepository:
    def __init__(self, db: Optional[AppDatabase] = None):
        """``db``: eine AppDatabase; ohne Angabe die globale."""
        self.db = db if db is not None else get_app_database()

    def zaehlen(self, woche: date) -> None:
        """Die Zahl der Woche um eins erhoehen; eine Anweisung, sicher bei Gleichzeitigkeit."""
        anweisung = insert(GepostetOhneKontoWoche).values(woche=woche, meldungen=1)
        with self.db.get_session() as session:
            session.execute(
                anweisung.on_conflict_do_update(
                    index_elements=["woche"],
                    set_={"meldungen": GepostetOhneKontoWoche.meldungen + 1},
                )
            )

    def wochen(self, von: date, bis: date) -> Dict[date, int]:
        """Die Zahl je Woche von ``von`` bis ``bis`` (beide Montage), nur Wochen mit Meldungen."""
        with self.db.get_session() as session:
            return {
                zeile.woche: zeile.meldungen
                for zeile in session.execute(
                    select(
                        GepostetOhneKontoWoche.woche, GepostetOhneKontoWoche.meldungen
                    ).where(
                        GepostetOhneKontoWoche.woche >= von,
                        GepostetOhneKontoWoche.woche <= bis,
                    )
                )
            }


_repository: Optional[GepostetOhneKontoRepository] = None


def get_gepostet_ohne_konto_repository() -> GepostetOhneKontoRepository:
    global _repository
    if _repository is None:
        _repository = GepostetOhneKontoRepository()
    return _repository
