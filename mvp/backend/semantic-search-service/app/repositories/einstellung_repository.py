"""
Repository fuer die Tabelle ``einstellungen``: Admin-Einstellungen mit Textwert
(services/einstellungen_service.py).
"""

from typing import Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from infrastructure.database.connection import AppDatabase, get_app_database
from infrastructure.database.models import EinstellungZeile


class EinstellungRepository:
    def __init__(self, db: Optional[AppDatabase] = None):
        self.db = db if db is not None else get_app_database()

    def alle(self) -> Dict[str, str]:
        """Alle gespeicherten Werte; eine Einstellung ohne Zeile fehlt (gilt Standard)."""
        with self.db.get_session() as session:
            zeilen = session.execute(
                select(EinstellungZeile.name, EinstellungZeile.wert)
            ).all()
            return {zeile.name: zeile.wert for zeile in zeilen}

    def setzen(self, name: str, wert: str, admin: str) -> None:
        with self.db.get_session() as session:
            einfuegen = pg_insert(EinstellungZeile).values(
                name=name, wert=wert, geaendert_am=func.now(), geaendert_von=admin
            )
            session.execute(
                einfuegen.on_conflict_do_update(
                    index_elements=[EinstellungZeile.name],
                    set_={
                        "wert": einfuegen.excluded.wert,
                        "geaendert_am": einfuegen.excluded.geaendert_am,
                        "geaendert_von": einfuegen.excluded.geaendert_von,
                    },
                )
            )


_repository: Optional[EinstellungRepository] = None


def get_einstellung_repository() -> EinstellungRepository:
    global _repository
    if _repository is None:
        _repository = EinstellungRepository()
    return _repository
