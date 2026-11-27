"""
Repository fuer die Ankuenfte je Kampagnenwort und Tag (``ankuenfte_je_tag``): je Wort
und UTC-Tag nur eine Zahl. Jeder Aufruf von ``zaehlen`` erhoeht sie um eins; mehr wird
nicht gespeichert (services/ankunft_service.py).
"""

from datetime import date, datetime
from typing import List, Optional, Tuple

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from infrastructure.database.connection import AppDatabase, get_app_database
from infrastructure.database.models import AnkunftJeTag


class AnkunftRepository:
    def __init__(self, db: Optional[AppDatabase] = None):
        """``db``: eine AppDatabase; ohne Angabe die globale."""
        self.db = db if db is not None else get_app_database()

    def zaehlen(self, k: str, tag: date) -> None:
        """Die Zahl fuer Wort und Tag um eins erhoehen; eine Anweisung, sicher bei Gleichzeitigkeit."""
        anweisung = insert(AnkunftJeTag).values(k=k, tag=tag, anzahl=1)
        with self.db.get_session() as session:
            session.execute(
                anweisung.on_conflict_do_update(
                    index_elements=["k", "tag"],
                    set_={"anzahl": AnkunftJeTag.anzahl + 1},
                )
            )

    def tage(self, von: date) -> List[Tuple[date, str, int]]:
        """(Tag, Wort, Zahl) ab ``von``, neueste Tage zuerst, je Tag nach Wort."""
        with self.db.get_session() as session:
            return [
                (zeile.tag, zeile.k, zeile.anzahl)
                for zeile in session.execute(
                    select(AnkunftJeTag.tag, AnkunftJeTag.k, AnkunftJeTag.anzahl)
                    .where(AnkunftJeTag.tag >= von)
                    .order_by(AnkunftJeTag.tag.desc(), AnkunftJeTag.k)
                )
            ]

    def loeschen_vor(self, grenze: datetime) -> int:
        """Zeilen von Tagen vor ``grenze`` loeschen (Loeschfrist); Zahl der Zeilen."""
        with self.db.get_session() as session:
            ergebnis = session.execute(
                delete(AnkunftJeTag).where(AnkunftJeTag.tag < grenze.date())
            )
            return ergebnis.rowcount or 0


_repository: Optional[AnkunftRepository] = None


def get_ankunft_repository() -> AnkunftRepository:
    global _repository
    if _repository is None:
        _repository = AnkunftRepository()
    return _repository
