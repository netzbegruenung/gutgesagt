"""
Repository fuer Seitenaufrufe und Besucher je Tag (#761, services/aufrufe_service.py).

``aufrufe_heute``: je Tagespseudonym des laufenden Tages die Zahl der Aufrufe. Das
Pseudonym lebt nur bis zum Ende seines Tages; ``verdichten_vor`` macht daraus eine
Zeile in ``aufrufe_tage`` (Aufrufe, Besucher) und loescht die Pseudonyme.
"""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from infrastructure.database.connection import AppDatabase, get_app_database
from infrastructure.database.models import AufrufHeuteZeile, AufrufTagZeile

# Hoechstens so viele Aufrufe zaehlt ein Besucher an einem Tag: Wer die Zahl mit
# Anfragen in die Hoehe treiben will, kommt nicht weit.
AUFRUFE_JE_BESUCHER_HOECHSTENS = 500


@dataclass(frozen=True)
class AufrufTag:
    tag: date
    aufrufe: int
    besucher: int


class AufrufeRepository:
    def __init__(self, db: Optional[AppDatabase] = None):
        """``db``: eine AppDatabase; ohne Angabe die globale."""
        self.db = db if db is not None else get_app_database()

    def zaehlen(self, tag: date, pseudonym: str) -> None:
        """Einen Aufruf zaehlen: neue Zeile oder eins mehr, hoechstens bis zur Grenze."""
        with self.db.get_session() as session:
            einfuegen = pg_insert(AufrufHeuteZeile).values(
                tag=tag, pseudonym=pseudonym, aufrufe=1
            )
            session.execute(
                einfuegen.on_conflict_do_update(
                    index_elements=[AufrufHeuteZeile.tag, AufrufHeuteZeile.pseudonym],
                    set_={
                        "aufrufe": func.least(
                            AufrufHeuteZeile.aufrufe + 1, AUFRUFE_JE_BESUCHER_HOECHSTENS
                        )
                    },
                )
            )

    def verdichten_vor(self, heute: date) -> int:
        """
        Alle Tage vor ``heute`` zu Tageszahlen verdichten und ihre Pseudonyme loeschen,
        in einer Transaktion. Ein Nachzuegler fuer einen schon verdichteten Tag kommt
        dazu (Aufrufe und Besucher addiert). Gibt die Zahl geloeschter Zeilen zurueck.
        """
        with self.db.get_session() as session:
            # Loeschen und Zaehlen in einem Schritt: Was zwischen einem SELECT und dem
            # DELETE dazukaeme, ginge sonst verloren.
            geloescht = session.execute(
                delete(AufrufHeuteZeile)
                .where(AufrufHeuteZeile.tag < heute)
                .returning(AufrufHeuteZeile.tag, AufrufHeuteZeile.aufrufe)
            ).all()
            je_tag: dict = {}
            for tag, aufrufe in geloescht:
                summe, besucher = je_tag.get(tag, (0, 0))
                je_tag[tag] = (summe + aufrufe, besucher + 1)
            for tag, (aufrufe, besucher) in je_tag.items():
                einfuegen = pg_insert(AufrufTagZeile).values(
                    tag=tag, aufrufe=int(aufrufe), besucher=int(besucher)
                )
                session.execute(
                    einfuegen.on_conflict_do_update(
                        index_elements=[AufrufTagZeile.tag],
                        set_={
                            "aufrufe": AufrufTagZeile.aufrufe
                            + einfuegen.excluded.aufrufe,
                            "besucher": AufrufTagZeile.besucher
                            + einfuegen.excluded.besucher,
                        },
                    )
                )
            return len(geloescht)

    def heute(self, tag: date) -> AufrufTag:
        """Der laufende Tag bisher, aus den Pseudonymen gezaehlt (ohne sie zu nennen)."""
        with self.db.get_session() as session:
            aufrufe, besucher = session.execute(
                select(
                    func.coalesce(func.sum(AufrufHeuteZeile.aufrufe), 0),
                    func.count(AufrufHeuteZeile.pseudonym),
                ).where(AufrufHeuteZeile.tag == tag)
            ).one()
            return AufrufTag(tag=tag, aufrufe=int(aufrufe), besucher=int(besucher))

    def tage(self, ab: date) -> List[AufrufTag]:
        """Die verdichteten Tage ab ``ab``, neueste zuerst."""
        with self.db.get_session() as session:
            zeilen = session.execute(
                select(AufrufTagZeile)
                .where(AufrufTagZeile.tag >= ab)
                .order_by(AufrufTagZeile.tag.desc())
            ).scalars()
            return [
                AufrufTag(tag=z.tag, aufrufe=z.aufrufe, besucher=z.besucher)
                for z in zeilen
            ]


_repository: Optional[AufrufeRepository] = None


def get_aufrufe_repository() -> AufrufeRepository:
    """Die globale Instanz holen oder anlegen."""
    global _repository
    if _repository is None:
        _repository = AufrufeRepository()
    return _repository
