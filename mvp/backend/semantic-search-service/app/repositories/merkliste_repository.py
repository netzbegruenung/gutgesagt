"""
Repository fuer die Tabelle ``merkliste``: gemerkte Beitraege je Kennung (#758,
GLOSSARY.md "Merkliste").
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from infrastructure.database.connection import AppDatabase, get_app_database
from infrastructure.database.models import MerklisteZeile

# So viele Eintraege haelt eine Merkliste hoechstens; darueber lehnt Merken ab.
MERKLISTE_MAX = 500


class MerklisteVoll(RuntimeError):
    """Die Merkliste hat schon MERKLISTE_MAX Eintraege."""


@dataclass(frozen=True)
class Gemerkt:
    content_id: uuid.UUID
    gemerkt_am: datetime


class MerklisteRepository:
    def __init__(self, db: Optional[AppDatabase] = None):
        """``db``: eine AppDatabase; ohne Angabe die globale."""
        self.db = db if db is not None else get_app_database()

    def liste(self, user_id: str) -> List[Gemerkt]:
        """Die Merkliste der Kennung, zuletzt gemerkt zuerst."""
        with self.db.get_session() as session:
            zeilen = session.execute(
                select(MerklisteZeile.content_id, MerklisteZeile.gemerkt_am)
                .where(MerklisteZeile.user_id == user_id)
                .order_by(MerklisteZeile.gemerkt_am.desc(), MerklisteZeile.content_id)
                .limit(MERKLISTE_MAX)
            ).all()
            return [Gemerkt(z.content_id, z.gemerkt_am) for z in zeilen]

    def merken(self, user_id: str, content_id: uuid.UUID) -> None:
        """
        Merken oder, wenn schon gemerkt, nach oben holen (``gemerkt_am`` neu).

        Zaehlen und Einfuegen laufen je Kennung hintereinander (Transaktionssperre auf
        den Hash der Kennung): Parallele Tipps fuehren so nicht ueber MERKLISTE_MAX.

        Raises:
        - MerklisteVoll, wenn ein neuer Eintrag ueber MERKLISTE_MAX ginge.
        """
        with self.db.get_session() as session:
            session.execute(
                select(
                    func.pg_advisory_xact_lock(func.hashtext("merkliste:" + user_id))
                )
            )
            schon = session.execute(
                select(MerklisteZeile.content_id).where(
                    MerklisteZeile.user_id == user_id,
                    MerklisteZeile.content_id == content_id,
                )
            ).first()
            if schon is None:
                anzahl = session.execute(
                    select(func.count())
                    .select_from(MerklisteZeile)
                    .where(MerklisteZeile.user_id == user_id)
                ).scalar_one()
                if anzahl >= MERKLISTE_MAX:
                    raise MerklisteVoll(user_id)
            einfuegen = pg_insert(MerklisteZeile).values(
                user_id=user_id, content_id=content_id, gemerkt_am=func.now()
            )
            session.execute(
                einfuegen.on_conflict_do_update(
                    index_elements=[MerklisteZeile.user_id, MerklisteZeile.content_id],
                    set_={"gemerkt_am": einfuegen.excluded.gemerkt_am},
                )
            )

    def entfernen(self, user_id: str, content_id: uuid.UUID) -> bool:
        """Einen Eintrag entfernen; False, wenn er nicht gemerkt war."""
        with self.db.get_session() as session:
            ergebnis = session.execute(
                delete(MerklisteZeile).where(
                    MerklisteZeile.user_id == user_id,
                    MerklisteZeile.content_id == content_id,
                )
            )
            return ergebnis.rowcount > 0

    def loeschen_fuer_person(self, user_id: str, session=None) -> int:
        """
        Die ganze Merkliste einer Person (Widerruf der Art.-9-Einwilligung). Mit
        ``session`` in deren Transaktion, sonst in einer eigenen.
        """
        abfrage = delete(MerklisteZeile).where(MerklisteZeile.user_id == user_id)
        if session is not None:
            return session.execute(abfrage).rowcount
        with self.db.get_session() as eigene:
            return eigene.execute(abfrage).rowcount

    def loeschen_fuer_beitrag(self, content_id: uuid.UUID) -> int:
        """Alle Eintraege zu einem Beitrag, der endgueltig entfernt wird."""
        with self.db.get_session() as session:
            return session.execute(
                delete(MerklisteZeile).where(MerklisteZeile.content_id == content_id)
            ).rowcount


_repository: Optional[MerklisteRepository] = None


def get_merkliste_repository() -> MerklisteRepository:
    global _repository
    if _repository is None:
        _repository = MerklisteRepository()
    return _repository
