"""
Repository fuer Muster-Hinweise (Tabelle muster_hinweise, #352).

Was ein Muster-Hinweis ist und wie lange er bleibt, steht in
services/muster_hinweise_service.py.
"""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import and_, delete, desc, exists, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert

from infrastructure.database.connection import AppDatabase, get_app_database
from infrastructure.database.models import MusterHinweisZeile, MusterPruefwert

NUTZUNG = "nutzung"
"""Art eines Muster-Hinweises: Die Konten haben sich gegenseitig genutzt (#352)."""

ZUSTIMMUNG = "zustimmung"
"""Art eines Muster-Hinweises: Die Konten haben einander zugestimmt (muster_stimmen)."""

LOESCH_STUECK = 500
"""So viele Hinweise loescht ``loeschen_paare`` je Anweisung."""


@dataclass(frozen=True)
class MusterHinweis:
    konto_a: str
    konto_b: str
    tage: int
    erster_tag: date
    letzter_tag: date
    art: str = NUTZUNG


class MusterHinweisRepository:
    def __init__(self, db: Optional[AppDatabase] = None):
        """``db``: eine AppDatabase; ohne Angabe die globale."""
        self.db = db if db is not None else get_app_database()

    def nutzung_merken(
        self,
        hin: str,
        rueck: Sequence[str],
        nutzende: str,
        autor: str,
        tag: date,
        fenster_ab: date,
        art: str = NUTZUNG,
    ) -> bool:
        """
        Merkt sich den Pruefwert ``hin`` (``nutzende`` hat einen Beitrag von ``autor``
        genutzt, bei ``art=ZUSTIMMUNG`` ihm zugestimmt) mit ``tag``. Steht einer der
        Werte ``rueck`` (die Gegenrichtung, je Schluessel im Speicher einer) mit einem
        Tag ab ``fenster_ab`` da, ist das Paar gegenseitig: Dann zaehlt der Hinweis
        dieser Art zum Paar diesen Tag, hoechstens einmal. Liefert, ob das Paar
        gegenseitig war.
        """
        konto_a, konto_b = sorted([nutzende, autor])
        with self.db.get_session() as session:
            # Je Paar nacheinander: Kaemen A->B und B->A gleichzeitig, saehe sonst
            # keine der beiden Transaktionen den noch nicht festgeschriebenen
            # Pruefwert der anderen, und der Tag ginge verloren.
            session.execute(
                select(
                    func.pg_advisory_xact_lock(
                        func.hashtext(f"{art}|{konto_a}|{konto_b}")
                    )
                )
            )
            neu = insert(MusterPruefwert).values(pruefwert=hin, tag=tag)
            session.execute(
                neu.on_conflict_do_update(
                    index_elements=["pruefwert"],
                    set_={"tag": neu.excluded.tag},
                    where=MusterPruefwert.tag < neu.excluded.tag,
                )
            )
            gegenseitig = session.execute(
                select(
                    exists().where(
                        MusterPruefwert.pruefwert.in_(list(rueck)),
                        MusterPruefwert.tag >= fenster_ab,
                    )
                )
            ).scalar()
            if not gegenseitig:
                return False
            neuer_tag = MusterHinweisZeile.letzter_tag < tag
            session.execute(
                insert(MusterHinweisZeile)
                .values(
                    konto_a=konto_a,
                    konto_b=konto_b,
                    art=art,
                    tage=1,
                    erster_tag=tag,
                    letzter_tag=tag,
                )
                .on_conflict_do_update(
                    index_elements=["konto_a", "konto_b", "art"],
                    set_={"tage": MusterHinweisZeile.tage + 1, "letzter_tag": tag},
                    where=neuer_tag,
                )
            )
            return True

    def hinweise(self, limit: int, art: Optional[str] = None) -> List[MusterHinweis]:
        """
        Die zuletzt aufgefallenen zuerst, bei gleichem Tag die mit mehr Tagen; mit
        ``art`` nur die dieser Art.
        """
        abfrage = select(MusterHinweisZeile)
        if art is not None:
            abfrage = abfrage.where(MusterHinweisZeile.art == art)
        abfrage = abfrage.order_by(
            desc(MusterHinweisZeile.letzter_tag),
            desc(MusterHinweisZeile.tage),
            MusterHinweisZeile.konto_a,
            MusterHinweisZeile.konto_b,
            MusterHinweisZeile.art,
        ).limit(limit)
        with self.db.get_session() as session:
            return [
                MusterHinweis(
                    z.konto_a, z.konto_b, z.tage, z.erster_tag, z.letzter_tag, z.art
                )
                for z in session.execute(abfrage).scalars()
            ]

    def vergessen(self, user_id: str, art: Optional[str] = None) -> int:
        """
        Alle Hinweise loeschen, die ``user_id`` nennen (Widerruf), mit ``art`` nur die
        dieser Art; liefert die Anzahl.
        """
        bedingung = or_(
            MusterHinweisZeile.konto_a == user_id,
            MusterHinweisZeile.konto_b == user_id,
        )
        if art is not None:
            bedingung = and_(bedingung, MusterHinweisZeile.art == art)
        with self.db.get_session() as session:
            return session.execute(delete(MusterHinweisZeile).where(bedingung)).rowcount

    def paare(self) -> List[Tuple[str, str, str]]:
        """Alle Hinweise als (konto_a, konto_b, art), fuer den Abgleich mit der Einwilligung."""
        with self.db.get_session() as session:
            return [
                (z.konto_a, z.konto_b, z.art)
                for z in session.execute(
                    select(
                        MusterHinweisZeile.konto_a,
                        MusterHinweisZeile.konto_b,
                        MusterHinweisZeile.art,
                    )
                )
            ]

    def loeschen_paare(self, paare: Sequence[Tuple[str, str, str]]) -> int:
        """Genau diese Hinweise (konto_a, konto_b, art) loeschen; liefert die Anzahl."""
        liste = list(paare)
        geloescht = 0
        with self.db.get_session() as session:
            for ab in range(0, len(liste), LOESCH_STUECK):
                stueck = liste[ab : ab + LOESCH_STUECK]
                geloescht += session.execute(
                    delete(MusterHinweisZeile).where(
                        tuple_(
                            MusterHinweisZeile.konto_a,
                            MusterHinweisZeile.konto_b,
                            MusterHinweisZeile.art,
                        ).in_(stueck)
                    )
                ).rowcount
        return geloescht

    def paare_verwerfen_vor(self, tag: date) -> int:
        """Paar-Pruefwerte, deren letzter Tag vor ``tag`` liegt, verwerfen."""
        with self.db.get_session() as session:
            return session.execute(
                delete(MusterPruefwert).where(MusterPruefwert.tag < tag)
            ).rowcount

    def loeschen_vor(self, tag: date) -> int:
        """Hinweise, deren letzter Tag vor ``tag`` liegt, loeschen."""
        with self.db.get_session() as session:
            return session.execute(
                delete(MusterHinweisZeile).where(MusterHinweisZeile.letzter_tag < tag)
            ).rowcount


_repository: Optional[MusterHinweisRepository] = None


def get_muster_hinweis_repository() -> MusterHinweisRepository:
    global _repository
    if _repository is None:
        _repository = MusterHinweisRepository()
    return _repository
