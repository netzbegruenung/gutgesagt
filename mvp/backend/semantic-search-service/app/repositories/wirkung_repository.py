"""
Repository fuer ``wirkung_je_beitrag``: je Beitrag die Summen "oeffentlich gepostet"
(Wirkungs-Echo, #790) und "Danke" (#791). Wie die Werte entstehen und was nicht
gespeichert wird: services/wirkung_service.py.
"""

import uuid
from datetime import date
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from infrastructure.database.connection import AppDatabase, get_app_database
from infrastructure.database.models import NutzungHeute, WirkungJeBeitrag


class WirkungRepository:
    def __init__(self, db: Optional[AppDatabase] = None):
        """``db``: eine AppDatabase; ohne Angabe die globale."""
        self.db = db if db is not None else get_app_database()

    @staticmethod
    def _hochzaehlen(session, content_id: uuid.UUID, spalte: str) -> None:
        session.execute(
            insert(WirkungJeBeitrag)
            .values(content_id=content_id, **{spalte: 1})
            .on_conflict_do_update(
                index_elements=["content_id"],
                set_={spalte: getattr(WirkungJeBeitrag, spalte) + 1},
            )
        )

    def gepostet_zaehlen(self, content_id: uuid.UUID) -> None:
        """Die Summe "oeffentlich gepostet" dieses Beitrags um eins erhoehen."""
        with self.db.get_session() as session:
            self._hochzaehlen(session, content_id, "oeffentlich_gepostet")

    def danke_zaehlen(self, content_id: uuid.UUID, pruefwert: str, tag: date) -> bool:
        """
        Ein Danke zaehlen, wenn ``pruefwert`` heute neu ist (Tages-Pruefwert wie bei
        der Nutzung, ``nutzung_heute``). In einer Transaktion: Der Pruefwert gilt nur
        zusammen mit dem gezaehlten Danke. True, wenn gezaehlt.
        """
        with self.db.get_session() as session:
            neu = (
                session.execute(
                    insert(NutzungHeute)
                    .values(pruefwert=pruefwert, tag=tag)
                    .on_conflict_do_nothing(index_elements=["pruefwert"])
                ).rowcount
                == 1
            )
            if neu:
                self._hochzaehlen(session, content_id, "danke")
            return neu

    def je_beitrag(self, content_ids: List[uuid.UUID]) -> Dict[str, Tuple[int, int]]:
        """Je Beitrag (ID als String) ``(oeffentlich_gepostet, danke)``, ohne Zeile 0."""
        ergebnis = {str(c): (0, 0) for c in content_ids}
        if not content_ids:
            return ergebnis
        with self.db.get_session() as session:
            for zeile in session.execute(
                select(
                    WirkungJeBeitrag.content_id,
                    WirkungJeBeitrag.oeffentlich_gepostet,
                    WirkungJeBeitrag.danke,
                ).where(WirkungJeBeitrag.content_id.in_(content_ids))
            ):
                ergebnis[str(zeile.content_id)] = (
                    zeile.oeffentlich_gepostet,
                    zeile.danke,
                )
        return ergebnis


_repository: Optional[WirkungRepository] = None


def get_wirkung_repository() -> WirkungRepository:
    global _repository
    if _repository is None:
        _repository = WirkungRepository()
    return _repository
