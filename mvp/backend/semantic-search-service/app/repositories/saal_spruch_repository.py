"""
Repository fuer die Tabelle ``saal_sprueche``: je Tag hoechstens ein Saal-Spruch
(services/saal_spruch_service.py).
"""

from datetime import date
from typing import Dict, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from infrastructure.database.connection import AppDatabase, get_app_database
from infrastructure.database.models import SaalSpruchZeile


class SaalSpruchRepository:
    def __init__(self, db: Optional[AppDatabase] = None):
        self.db = db if db is not None else get_app_database()

    def fuer_tag(self, tag: date) -> Optional[str]:
        with self.db.get_session() as session:
            return session.execute(
                select(SaalSpruchZeile.text).where(SaalSpruchZeile.datum == tag)
            ).scalar_one_or_none()

    def ab(self, tag: date) -> Dict[date, str]:
        """Alle Sprueche ab diesem Tag (eingeschlossen), nach Datum."""
        with self.db.get_session() as session:
            zeilen = session.execute(
                select(SaalSpruchZeile.datum, SaalSpruchZeile.text)
                .where(SaalSpruchZeile.datum >= tag)
                .order_by(SaalSpruchZeile.datum)
            ).all()
            return {zeile.datum: zeile.text for zeile in zeilen}

    def setzen(self, tag: date, text: str) -> None:
        """Legt den Spruch des Tages an oder ersetzt ihn."""
        with self.db.get_session() as session:
            einfuegen = pg_insert(SaalSpruchZeile).values(
                datum=tag, text=text, geaendert_am=func.now()
            )
            session.execute(
                einfuegen.on_conflict_do_update(
                    index_elements=[SaalSpruchZeile.datum],
                    set_={
                        "text": einfuegen.excluded.text,
                        "geaendert_am": einfuegen.excluded.geaendert_am,
                    },
                )
            )

    def loeschen(self, tag: date) -> None:
        """Entfernt den Spruch des Tages; ohne Spruch passiert nichts."""
        with self.db.get_session() as session:
            session.execute(delete(SaalSpruchZeile).where(SaalSpruchZeile.datum == tag))


_repository: Optional[SaalSpruchRepository] = None


def get_saal_spruch_repository() -> SaalSpruchRepository:
    global _repository
    if _repository is None:
        _repository = SaalSpruchRepository()
    return _repository
