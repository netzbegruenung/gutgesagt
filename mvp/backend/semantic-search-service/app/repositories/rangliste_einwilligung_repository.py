"""
Repository fuer die Tabelle ``rangliste_einwilligung``: die Einwilligung zur
Rangliste je Kennung (#793).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Set

from sqlalchemy import func, insert, select

from infrastructure.database.connection import AppDatabase, get_app_database
from infrastructure.database.models import RanglisteEinwilligungZeile


@dataclass(frozen=True)
class RanglisteAntwort:
    teilnehmen: bool
    mit_anzeigename: bool
    wortlaut: str
    beantwortet_am: datetime
    # Zufaellig beim ersten Ja vergeben; None, solange die Person nie Ja gesagt hat
    ranglistenname: Optional[str] = None


@dataclass(frozen=True)
class Teilnahme:
    mit_anzeigename: bool
    ranglistenname: Optional[str]


class RanglisteEinwilligungRepository:
    def __init__(self, db: Optional[AppDatabase] = None):
        """``db``: eine AppDatabase; ohne Angabe die globale."""
        self.db = db if db is not None else get_app_database()

    def lesen(self, user_id: str) -> Optional[RanglisteAntwort]:
        """Die juengste Antwort der Kennung, oder None, wenn sie nie gefragt wurde."""
        with self.db.get_session() as session:
            zeile = session.execute(
                select(
                    RanglisteEinwilligungZeile.teilnehmen,
                    RanglisteEinwilligungZeile.mit_anzeigename,
                    RanglisteEinwilligungZeile.wortlaut,
                    RanglisteEinwilligungZeile.beantwortet_am,
                    RanglisteEinwilligungZeile.ranglistenname,
                )
                .where(RanglisteEinwilligungZeile.user_id == user_id)
                .order_by(
                    RanglisteEinwilligungZeile.beantwortet_am.desc(),
                    RanglisteEinwilligungZeile.id.desc(),
                )
                .limit(1)
            ).first()
            if zeile is None:
                return None
            return RanglisteAntwort(
                teilnehmen=zeile.teilnehmen,
                mit_anzeigename=zeile.mit_anzeigename,
                wortlaut=zeile.wortlaut,
                beantwortet_am=zeile.beantwortet_am,
                ranglistenname=zeile.ranglistenname,
            )

    def antworten(
        self,
        user_id: str,
        teilnehmen: bool,
        mit_anzeigename: bool,
        wortlaut: str,
        ranglistenname: Optional[str] = None,
    ) -> None:
        """
        Eine neue Zeile; fruehere bleiben als Nachweis stehen. Ist die juengste
        Antwort schon dieselbe, bleibt es bei ihr. Ohne ``ranglistenname`` gilt der
        Name der juengsten Zeile weiter: Die Person behaelt ihn ueber jedes Nein.
        """
        juengste = self.lesen(user_id)
        if ranglistenname is None and juengste is not None:
            ranglistenname = juengste.ranglistenname
        if (
            juengste is not None
            and juengste.teilnehmen == teilnehmen
            and juengste.mit_anzeigename == mit_anzeigename
            and juengste.wortlaut == wortlaut
            and juengste.ranglistenname == ranglistenname
        ):
            return
        with self.db.get_session() as session:
            session.execute(
                insert(RanglisteEinwilligungZeile).values(
                    user_id=user_id,
                    teilnehmen=teilnehmen,
                    mit_anzeigename=mit_anzeigename,
                    wortlaut=wortlaut,
                    beantwortet_am=func.now(),
                    ranglistenname=ranglistenname,
                )
            )

    def vergebene_namen(self) -> Set[str]:
        """Alle Ranglistennamen, die schon jemand hat (zum Wuerfeln ohne Doppelung)."""
        with self.db.get_session() as session:
            return set(
                session.execute(
                    select(RanglisteEinwilligungZeile.ranglistenname)
                    .where(RanglisteEinwilligungZeile.ranglistenname.is_not(None))
                    .distinct()
                ).scalars()
            )

    def teilnehmende(self) -> Dict[str, Teilnahme]:
        """
        Alle Kennungen, deren juengste Antwort "teilnehmen" ist, mit ihrer Wahl des
        Anzeigenamens und ihrem Ranglistennamen.
        """
        juengste = (
            select(
                RanglisteEinwilligungZeile.user_id,
                RanglisteEinwilligungZeile.teilnehmen,
                RanglisteEinwilligungZeile.mit_anzeigename,
                RanglisteEinwilligungZeile.ranglistenname,
                func.row_number()
                .over(
                    partition_by=RanglisteEinwilligungZeile.user_id,
                    # Bei gleichem Zeitpunkt wie in lesen(): beide Abfragen einig.
                    order_by=(
                        RanglisteEinwilligungZeile.beantwortet_am.desc(),
                        RanglisteEinwilligungZeile.id.desc(),
                    ),
                )
                .label("rang"),
            )
        ).subquery()
        abfrage = select(
            juengste.c.user_id, juengste.c.mit_anzeigename, juengste.c.ranglistenname
        ).where(juengste.c.rang == 1, juengste.c.teilnehmen.is_(True))
        with self.db.get_session() as session:
            return {
                kennung: Teilnahme(mit, name)
                for kennung, mit, name in session.execute(abfrage)
            }


_repository: Optional[RanglisteEinwilligungRepository] = None


def get_rangliste_einwilligung_repository() -> RanglisteEinwilligungRepository:
    """Die globale Instanz holen oder anlegen."""
    global _repository
    if _repository is None:
        _repository = RanglisteEinwilligungRepository()
    return _repository
