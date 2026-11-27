"""
Repository fuer die Tabelle ``spielgefuehl``: die Antwort auf die Frage
"Spielgefuehl" je Kennung (domain/spielgefuehl.py, Schalter spielgefuehl_buehne).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, Optional, Set

from sqlalchemy import func, insert, select

from domain.spielgefuehl import GELTENDE_WORTLAUTE, STIMMEN_WORTLAUT, Stufe
from infrastructure.database.connection import AppDatabase, get_app_database
from infrastructure.database.models import SpielgefuehlZeile
from repositories.rangliste_einwilligung_repository import Teilnahme


@dataclass(frozen=True)
class SpielgefuehlAntwort:
    stufe: Stufe
    mit_anzeigename: bool
    wortlaut: str
    beantwortet_am: datetime
    # Beim ersten Mitspielen gewuerfelt; None davor
    ranglistenname: Optional[str] = None

    @property
    def gilt(self) -> bool:
        """Die Antwort gehoert zu einem Wortlaut, der noch gilt."""
        return self.wortlaut in GELTENDE_WORTLAUTE

    @property
    def wirksame_stufe(self) -> Stufe:
        """Die Stufe, die wirkt: zu einem nicht mehr geltenden Wortlaut nur ``aus``."""
        return self.stufe if self.gilt else Stufe.AUS


def _stufe(wert: str) -> Stufe:
    # Unbekannte Werte (etwa aus einer spaeteren Fassung) gelten als aus.
    try:
        return Stufe(wert)
    except ValueError:
        return Stufe.AUS


class SpielgefuehlRepository:
    def __init__(self, db: Optional[AppDatabase] = None):
        """``db``: eine AppDatabase; ohne Angabe die globale."""
        self.db = db if db is not None else get_app_database()

    def _juengste(self):
        """Je Kennung die juengste Zeile (Unterabfrage mit ``rang`` = 1)."""
        return select(
            SpielgefuehlZeile.user_id,
            SpielgefuehlZeile.stufe,
            SpielgefuehlZeile.mit_anzeigename,
            SpielgefuehlZeile.wortlaut,
            SpielgefuehlZeile.ranglistenname,
            func.row_number()
            .over(
                partition_by=SpielgefuehlZeile.user_id,
                # Bei gleichem Zeitpunkt wie in lesen(): alle Abfragen einig.
                order_by=(
                    SpielgefuehlZeile.beantwortet_am.desc(),
                    SpielgefuehlZeile.id.desc(),
                ),
            )
            .label("rang"),
        ).subquery()

    def lesen(self, user_id: str) -> Optional[SpielgefuehlAntwort]:
        """Die juengste Antwort der Kennung, oder None, wenn sie nie geantwortet hat."""
        with self.db.get_session() as session:
            zeile = session.execute(
                select(
                    SpielgefuehlZeile.stufe,
                    SpielgefuehlZeile.mit_anzeigename,
                    SpielgefuehlZeile.wortlaut,
                    SpielgefuehlZeile.beantwortet_am,
                    SpielgefuehlZeile.ranglistenname,
                )
                .where(SpielgefuehlZeile.user_id == user_id)
                .order_by(
                    SpielgefuehlZeile.beantwortet_am.desc(),
                    SpielgefuehlZeile.id.desc(),
                )
                .limit(1)
            ).first()
            if zeile is None:
                return None
            return SpielgefuehlAntwort(
                stufe=_stufe(zeile.stufe),
                mit_anzeigename=zeile.mit_anzeigename,
                wortlaut=zeile.wortlaut,
                beantwortet_am=zeile.beantwortet_am,
                ranglistenname=zeile.ranglistenname,
            )

    def antworten(
        self,
        user_id: str,
        stufe: Stufe,
        mit_anzeigename: bool,
        wortlaut: str,
        ranglistenname: Optional[str] = None,
    ) -> None:
        """
        Eine neue Zeile; fruehere bleiben als Nachweis stehen. Ist die juengste
        Antwort schon dieselbe, bleibt es bei ihr. Ohne ``ranglistenname`` gilt der
        Name der juengsten Zeile weiter: Die Person behaelt ihn ueber jedes Herabstufen.
        """
        juengste = self.lesen(user_id)
        if ranglistenname is None and juengste is not None:
            ranglistenname = juengste.ranglistenname
        if (
            juengste is not None
            and juengste.stufe is stufe
            and juengste.mit_anzeigename == mit_anzeigename
            and juengste.wortlaut == wortlaut
            and juengste.ranglistenname == ranglistenname
        ):
            return
        with self.db.get_session() as session:
            session.execute(
                insert(SpielgefuehlZeile).values(
                    user_id=user_id,
                    stufe=stufe.value,
                    mit_anzeigename=mit_anzeigename,
                    wortlaut=wortlaut,
                    beantwortet_am=func.now(),
                    ranglistenname=ranglistenname,
                )
            )

    def wirksame_stufen(self, kennungen: Iterable[str]) -> Dict[str, Stufe]:
        """Die wirksame Stufe je Kennung, in einer Abfrage; wer nie geantwortet hat, fehlt."""
        liste = list(set(kennungen))
        if not liste:
            return {}
        juengste = self._juengste()
        abfrage = select(
            juengste.c.user_id, juengste.c.stufe, juengste.c.wortlaut
        ).where(juengste.c.rang == 1, juengste.c.user_id.in_(liste))
        with self.db.get_session() as session:
            return {
                kennung: (
                    _stufe(stufe) if wortlaut in GELTENDE_WORTLAUTE else Stufe.AUS
                )
                for kennung, stufe, wortlaut in session.execute(abfrage)
            }

    def stimmen_eingewilligte(self, kennungen: Iterable[str]) -> Set[str]:
        """
        Die Kennungen, deren juengste Antwort eine Stufe ab ``fuer_mich`` zum Wortlaut
        ``STIMMEN_WORTLAUT`` ist (domain/spielgefuehl.py ``stimmen_eingewilligt``), in
        einer Abfrage.
        """
        liste = list(set(kennungen))
        if not liste:
            return set()
        juengste = self._juengste()
        abfrage = select(juengste.c.user_id).where(
            juengste.c.rang == 1,
            juengste.c.user_id.in_(liste),
            juengste.c.wortlaut == STIMMEN_WORTLAUT,
            juengste.c.stufe.in_([Stufe.FUER_MICH.value, Stufe.RANGLISTE.value]),
        )
        with self.db.get_session() as session:
            return set(session.execute(abfrage).scalars())

    def teilnehmende(self) -> Dict[str, Teilnahme]:
        """
        Alle Kennungen, deren juengste Antwort Stufe rangliste zu einem geltenden
        Wortlaut ist, mit Namenswahl und Ranglistennamen.
        """
        juengste = self._juengste()
        abfrage = select(
            juengste.c.user_id,
            juengste.c.mit_anzeigename,
            juengste.c.ranglistenname,
        ).where(
            juengste.c.rang == 1,
            juengste.c.stufe == Stufe.RANGLISTE.value,
            juengste.c.wortlaut.in_(list(GELTENDE_WORTLAUTE)),
        )
        with self.db.get_session() as session:
            return {
                kennung: Teilnahme(mit, name)
                for kennung, mit, name in session.execute(abfrage)
            }

    def vergebene_namen(self) -> Set[str]:
        """Alle Ranglistennamen, die hier schon jemand hat oder hatte."""
        with self.db.get_session() as session:
            return set(
                session.execute(
                    select(SpielgefuehlZeile.ranglistenname)
                    .where(SpielgefuehlZeile.ranglistenname.is_not(None))
                    .distinct()
                ).scalars()
            )


_repository: Optional[SpielgefuehlRepository] = None


def get_spielgefuehl_repository() -> SpielgefuehlRepository:
    """Die globale Instanz holen oder anlegen."""
    global _repository
    if _repository is None:
        _repository = SpielgefuehlRepository()
    return _repository
