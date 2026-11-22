"""
Repository fuer die Tabelle ``herkunft_pruefung``: das Ergebnis von "Herkunft pruefen"
je Herkunft mit Link (#759, services/herkunft_pruefen.py).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from infrastructure.database.connection import AppDatabase, get_app_database
from infrastructure.database.models import HerkunftPruefungZeile


@dataclass(frozen=True)
class HerkunftPruefung:
    herkunft_id: uuid.UUID
    adresse: str
    ergebnis: str
    http_status: Optional[int]
    ziel: Optional[str]
    geprueft_am: datetime
    auffaellig_seit: Optional[datetime]


@dataclass(frozen=True)
class HerkunftPruefungStand:
    geprueft: int
    letzter_lauf: Optional[datetime]
    auffaellig: List[HerkunftPruefung]


class HerkunftPruefungRepository:
    def __init__(self, db: Optional[AppDatabase] = None):
        """``db``: eine AppDatabase; ohne Angabe die globale."""
        self.db = db if db is not None else get_app_database()

    def speichern(
        self,
        herkunft_id: uuid.UUID,
        adresse: str,
        ergebnis: str,
        http_status: Optional[int],
        ziel: Optional[str],
        geprueft_am: datetime,
        auffaellig: bool,
    ) -> None:
        """
        Ergebnis einer Herkunft festhalten. ``auffaellig_seit`` bleibt beim ersten
        auffaelligen Lauf stehen und faellt weg, sobald der Link wieder geht oder die
        Adresse sich geaendert hat.
        """
        with self.db.get_session() as session:
            einfuegen = pg_insert(HerkunftPruefungZeile).values(
                herkunft_id=herkunft_id,
                adresse=adresse,
                ergebnis=ergebnis,
                http_status=http_status,
                ziel=ziel,
                geprueft_am=geprueft_am,
                auffaellig_seit=geprueft_am if auffaellig else None,
            )
            alt = HerkunftPruefungZeile.__table__.c
            # Nur bei gleicher Adresse zaehlt der alte Zeitpunkt weiter
            seit = _seit_bei_gleicher_adresse(alt, einfuegen) if auffaellig else None
            session.execute(
                einfuegen.on_conflict_do_update(
                    index_elements=[HerkunftPruefungZeile.herkunft_id],
                    set_={
                        "adresse": einfuegen.excluded.adresse,
                        "ergebnis": einfuegen.excluded.ergebnis,
                        "http_status": einfuegen.excluded.http_status,
                        "ziel": einfuegen.excluded.ziel,
                        "geprueft_am": einfuegen.excluded.geprueft_am,
                        "auffaellig_seit": seit,
                    },
                )
            )

    def uebrige_loeschen(self, behalten: Iterable[uuid.UUID]) -> int:
        """Zeilen zu Herkuenften loeschen, die es nicht mehr gibt (nicht in ``behalten``)."""
        ids = list(behalten)
        with self.db.get_session() as session:
            abfrage = delete(HerkunftPruefungZeile)
            if ids:
                abfrage = abfrage.where(HerkunftPruefungZeile.herkunft_id.notin_(ids))
            return session.execute(abfrage).rowcount

    def stand(self, ok: str, hoechstens: int) -> HerkunftPruefungStand:
        """Wie viele geprueft sind, wann zuletzt, und die auffaelligen (laengste zuerst)."""
        with self.db.get_session() as session:
            geprueft, letzter = session.execute(
                select(
                    func.count(HerkunftPruefungZeile.herkunft_id),
                    func.max(HerkunftPruefungZeile.geprueft_am),
                )
            ).one()
            zeilen = (
                session.execute(
                    select(HerkunftPruefungZeile)
                    .where(HerkunftPruefungZeile.ergebnis != ok)
                    .order_by(
                        HerkunftPruefungZeile.auffaellig_seit.asc().nulls_last(),
                        HerkunftPruefungZeile.adresse,
                    )
                    .limit(hoechstens)
                )
                .scalars()
                .all()
            )
            return HerkunftPruefungStand(
                geprueft=geprueft or 0,
                letzter_lauf=letzter,
                auffaellig=[
                    HerkunftPruefung(
                        herkunft_id=z.herkunft_id,
                        adresse=z.adresse,
                        ergebnis=z.ergebnis,
                        http_status=z.http_status,
                        ziel=z.ziel,
                        geprueft_am=z.geprueft_am,
                        auffaellig_seit=z.auffaellig_seit,
                    )
                    for z in zeilen
                ],
            )

    def letzter_lauf(self) -> Optional[datetime]:
        with self.db.get_session() as session:
            return session.execute(
                select(func.max(HerkunftPruefungZeile.geprueft_am))
            ).scalar()


def _seit_bei_gleicher_adresse(alt, einfuegen):
    """auffaellig_seit beim Update: der alte Zeitpunkt, wenn es ihn gibt und die Adresse
    gleich blieb, sonst der dieses Laufs."""
    return case(
        (
            (alt.auffaellig_seit.isnot(None))
            & (alt.adresse == einfuegen.excluded.adresse),
            alt.auffaellig_seit,
        ),
        else_=einfuegen.excluded.geprueft_am,
    )


_repository: Optional[HerkunftPruefungRepository] = None


def get_herkunft_pruefung_repository() -> HerkunftPruefungRepository:
    """Die globale Instanz holen oder anlegen."""
    global _repository
    if _repository is None:
        _repository = HerkunftPruefungRepository()
    return _repository
