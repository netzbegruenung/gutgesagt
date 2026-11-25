"""
Repository fuer die Tabelle ``saisons`` (#782, domain/saisons.py).

Anlegen und Aendern sperren die Tabelle fuer andere Schreiber, pruefen in derselben
Transaktion, dass sich keine zwei Saisons ueberschneiden, und schreiben erst dann:
So entstehen auch bei gleichzeitigen Admin-Anfragen nie zwei laufende Saisons.
"""

import uuid
from datetime import date
from typing import Callable, List, Optional

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError

from domain.saisons import (
    Saison,
    SaisonEingabe,
    SaisonUeberschneidung,
    SaisonUngueltig,
    ueberschneidung,
)
from infrastructure.database.connection import AppDatabase, get_app_database
from infrastructure.database.models import SaisonZeile

# Lesen bleibt moeglich, ein zweiter Schreiber wartet bis zum Ende der Transaktion.
_SPERREN = text("LOCK TABLE saisons IN SHARE ROW EXCLUSIVE MODE")


class SaisonNichtGefunden(LookupError):
    pass


def _saison(zeile) -> Saison:
    return Saison(
        id=zeile.id,
        name=zeile.name,
        beginn=zeile.beginn,
        ende=zeile.ende,
        ziel=zeile.ziel,
    )


class SaisonRepository:
    def __init__(self, db: Optional[AppDatabase] = None):
        """``db``: eine AppDatabase; ohne Angabe die globale."""
        self.db = db if db is not None else get_app_database()

    @staticmethod
    def _alle(session) -> List[Saison]:
        zeilen = session.execute(
            select(SaisonZeile).order_by(SaisonZeile.beginn.desc())
        ).scalars()
        return [_saison(z) for z in zeilen]

    def alle(self) -> List[Saison]:
        """Alle Saisons, die spaeteste zuerst."""
        with self.db.get_session() as session:
            return self._alle(session)

    def laufende(self, heute: date) -> Optional[Saison]:
        with self.db.get_session() as session:
            zeile = (
                session.execute(
                    select(SaisonZeile).where(
                        SaisonZeile.beginn <= heute, SaisonZeile.ende >= heute
                    )
                )
                .scalars()
                .first()
            )
            return _saison(zeile) if zeile is not None else None

    def anlegen(self, eingabe: SaisonEingabe) -> Saison:
        """Neue Saison; SaisonUeberschneidung oder (Name schon vergeben) SaisonUngueltig."""
        neu_id = uuid.uuid4()
        with self.db.get_session() as session:
            session.execute(_SPERREN)
            self._ohne_ueberschneidung(session, eingabe, ausser=None)
            self._ohne_namensdoppel(session, eingabe.name, ausser=None)
            session.add(
                SaisonZeile(
                    id=neu_id,
                    name=eingabe.name,
                    beginn=eingabe.beginn,
                    ende=eingabe.ende,
                    ziel=eingabe.ziel,
                    angelegt_am=func.now(),
                )
            )
            self._schreiben(session)
        return Saison(neu_id, eingabe.name, eingabe.beginn, eingabe.ende, eingabe.ziel)

    def aendern(
        self,
        saison_id: uuid.UUID,
        eingabe: SaisonEingabe,
        pruefen: Callable[[Saison], None],
    ) -> Saison:
        """
        Saison aendern. ``pruefen`` bekommt den Stand unter der Sperre und wirft, wenn
        die Aenderung in diesem Zustand nicht erlaubt ist (domain/saisons.py).
        """
        with self.db.get_session() as session:
            session.execute(_SPERREN)
            zeile = session.get(SaisonZeile, saison_id)
            if zeile is None:
                raise SaisonNichtGefunden(saison_id)
            pruefen(_saison(zeile))
            self._ohne_ueberschneidung(session, eingabe, ausser=saison_id)
            self._ohne_namensdoppel(session, eingabe.name, ausser=saison_id)
            session.execute(
                update(SaisonZeile)
                .where(SaisonZeile.id == saison_id)
                .values(
                    name=eingabe.name,
                    beginn=eingabe.beginn,
                    ende=eingabe.ende,
                    ziel=eingabe.ziel,
                )
            )
            self._schreiben(session)
        return Saison(
            saison_id, eingabe.name, eingabe.beginn, eingabe.ende, eingabe.ziel
        )

    def loeschen(self, saison_id: uuid.UUID, pruefen: Callable[[Saison], None]) -> None:
        with self.db.get_session() as session:
            session.execute(_SPERREN)
            zeile = session.get(SaisonZeile, saison_id)
            if zeile is None:
                raise SaisonNichtGefunden(saison_id)
            pruefen(_saison(zeile))
            session.execute(delete(SaisonZeile).where(SaisonZeile.id == saison_id))

    def _ohne_ueberschneidung(
        self, session, eingabe: SaisonEingabe, ausser: Optional[uuid.UUID]
    ) -> None:
        andere = ueberschneidung(eingabe, self._alle(session), ausser=ausser)
        if andere is not None:
            raise SaisonUeberschneidung(andere.name)

    @staticmethod
    def _ohne_namensdoppel(session, name: str, ausser: Optional[uuid.UUID]) -> None:
        abfrage = select(SaisonZeile.id).where(SaisonZeile.name == name)
        if ausser is not None:
            abfrage = abfrage.where(SaisonZeile.id != ausser)
        if session.execute(abfrage).first() is not None:
            raise SaisonUngueltig("Diesen Namen hat schon eine andere Saison.")

    @staticmethod
    def _schreiben(session) -> None:
        try:
            session.flush()
        except IntegrityError:
            # Unter der Sperre nur noch ein Rennen mit einer Aenderung von Hand
            raise SaisonUngueltig("Diesen Namen hat schon eine andere Saison.")


_repository: Optional[SaisonRepository] = None


def get_saison_repository() -> SaisonRepository:
    global _repository
    if _repository is None:
        _repository = SaisonRepository()
    return _repository
