"""
Repository fuer Teams: Mitgliedschaften (team_mitgliedschaften), den Zaehler der
Nummern (team_nummern) und die Einwilligung "Team öffentlich am Namen zeigen"
(team_oeffentlich). Was gespeichert wird und warum nicht mehr:
services/team_service.py.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import delete, func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from infrastructure.database.connection import AppDatabase, get_app_database
from infrastructure.database.models import (
    EinladungZeile,
    TeamMitgliedschaftZeile,
    TeamNummerZeile,
    TeamOeffentlichZeile,
)


class NichtEinloesbar(Exception):
    """Die Einladung zaehlt nicht mehr (abgeschaltet, abgelaufen, aufgebraucht, Team geaendert)."""


class _SchonDabei(Exception):
    """Gleichzeitig beigetreten: Die Transaktion wird zurueckgerollt."""


@dataclass(frozen=True)
class Mitgliedschaft:
    id: uuid.UUID
    team_name: str
    team_motiv: Optional[str]
    saison: str
    nummer: int
    eingetreten_am: date

    @classmethod
    def aus_zeile(cls, z) -> "Mitgliedschaft":
        return cls(
            id=z.id,
            team_name=z.team_name,
            team_motiv=z.team_motiv,
            saison=z.saison,
            nummer=z.nummer,
            eingetreten_am=z.eingetreten_am,
        )


@dataclass(frozen=True)
class OeffentlichAntwort:
    zeigen: bool
    einwilligung_kennung: str
    beantwortet_am: datetime


class TeamRepository:
    def __init__(self, db: Optional[AppDatabase] = None):
        # Erst beim ersten Zugriff: Ohne wirksamen Schalter fragt der Dienst die
        # Datenbank nie.
        self._db = db

    @property
    def db(self) -> AppDatabase:
        if self._db is None:
            self._db = get_app_database()
        return self._db

    # --- Lesen ---------------------------------------------------------------

    def mitgliedschaft(
        self, konto: str, team_name: str, saison: str
    ) -> Optional[Mitgliedschaft]:
        with self.db.get_session() as session:
            return self._mitgliedschaft(session, konto, team_name, saison)

    @staticmethod
    def _mitgliedschaft(session, konto, team_name, saison) -> Optional[Mitgliedschaft]:
        zeile = session.execute(
            select(TeamMitgliedschaftZeile).where(
                TeamMitgliedschaftZeile.konto_kennung == konto,
                TeamMitgliedschaftZeile.team_name == team_name,
                TeamMitgliedschaftZeile.saison == saison,
            )
        ).scalar_one_or_none()
        return Mitgliedschaft.aus_zeile(zeile) if zeile is not None else None

    def mitglieder_je_team(
        self, teams: Iterable[Tuple[str, str]]
    ) -> Dict[Tuple[str, str], int]:
        """(Name, Saison) -> Zahl der Mitglieder; nur Zahlen, nie Kennungen."""
        teams = list(set(teams))
        if not teams:
            return {}
        abfrage = (
            select(
                TeamMitgliedschaftZeile.team_name,
                TeamMitgliedschaftZeile.saison,
                func.count(),
            )
            .where(
                tuple_(
                    TeamMitgliedschaftZeile.team_name, TeamMitgliedschaftZeile.saison
                ).in_(teams)
            )
            .group_by(TeamMitgliedschaftZeile.team_name, TeamMitgliedschaftZeile.saison)
        )
        with self.db.get_session() as session:
            gezaehlt = {(n, s): z for n, s, z in session.execute(abfrage).all()}
        return {t: gezaehlt.get(t, 0) for t in teams}

    def letzte_nummer(self, team_name: str, saison: str) -> int:
        with self.db.get_session() as session:
            wert = session.execute(
                select(TeamNummerZeile.letzte_nummer).where(
                    TeamNummerZeile.team_name == team_name,
                    TeamNummerZeile.saison == saison,
                )
            ).scalar_one_or_none()
            return wert or 0

    def meine(self, konto: str) -> List[Mitgliedschaft]:
        """Alle Mitgliedschaften der Person, neueste Saison und neuester Beitritt zuerst."""
        abfrage = (
            select(TeamMitgliedschaftZeile)
            .where(TeamMitgliedschaftZeile.konto_kennung == konto)
            .order_by(
                TeamMitgliedschaftZeile.saison.desc(),
                TeamMitgliedschaftZeile.eingetreten_am.desc(),
                TeamMitgliedschaftZeile.team_name,
            )
        )
        with self.db.get_session() as session:
            return [
                Mitgliedschaft.aus_zeile(z)
                for z in session.execute(abfrage).scalars().all()
            ]

    # --- Beitreten und verlassen ---------------------------------------------

    def beitreten(
        self,
        konto: str,
        team_name: str,
        team_motiv: Optional[str],
        saison: str,
        einwilligung_kennung: str,
        zeitpunkt: datetime,
        heute: date,
        code: Optional[str] = None,
    ) -> Tuple[Mitgliedschaft, bool]:
        """
        Legt die Mitgliedschaft mit der naechsten Nummer an, in einer Transaktion.
        Mit ``code`` zaehlt dieselbe Transaktion die Einloesung (nur, solange die
        Einladung aktiv ist und noch zu diesem Team gehoert; sonst NichtEinloesbar).
        Ist die Person schon im Team, aendert sich nichts und nichts wird gezaehlt:
        ``(vorhandene Mitgliedschaft, False)``. Gleichzeitige Beitritte derselben
        Person laufen auf den eindeutigen Schluessel und zaehlen einmal.
        """
        try:
            with self.db.get_session() as session:
                vorhanden = self._mitgliedschaft(session, konto, team_name, saison)
                if vorhanden is not None:
                    return vorhanden, False
                if code is not None and not self._einloesung_zaehlen(
                    session, code, team_name, saison, heute
                ):
                    raise NichtEinloesbar()
                nummer = self._naechste_nummer(session, team_name, saison)
                eingefuegt = session.execute(
                    pg_insert(TeamMitgliedschaftZeile)
                    .values(
                        id=uuid.uuid4(),
                        konto_kennung=konto,
                        team_name=team_name,
                        team_motiv=team_motiv,
                        saison=saison,
                        nummer=nummer,
                        eingetreten_am=heute,
                        einwilligung_kennung=einwilligung_kennung,
                        einwilligung_zeitpunkt=zeitpunkt,
                    )
                    .on_conflict_do_nothing(
                        constraint="uq_team_mitgliedschaften_konto_team_saison"
                    )
                    .returning(TeamMitgliedschaftZeile.id)
                ).scalar_one_or_none()
                if eingefuegt is None:
                    # Rollt Zaehler und Einloesung dieser Transaktion zurueck.
                    raise _SchonDabei()
                return (
                    Mitgliedschaft(
                        id=eingefuegt,
                        team_name=team_name,
                        team_motiv=team_motiv,
                        saison=saison,
                        nummer=nummer,
                        eingetreten_am=heute,
                    ),
                    True,
                )
        except _SchonDabei:
            vorhanden = self.mitgliedschaft(konto, team_name, saison)
            if vorhanden is None:  # pragma: no cover - gleich wieder verlassen
                raise NichtEinloesbar()
            return vorhanden, False

    @staticmethod
    def _einloesung_zaehlen(session, code, team_name, saison, heute) -> bool:
        ergebnis = session.execute(
            update(EinladungZeile)
            .where(
                EinladungZeile.code == code,
                EinladungZeile.team_name == team_name,
                EinladungZeile.team_saison == saison,
                EinladungZeile.abgeschaltet.is_(False),
                EinladungZeile.gueltig_bis >= heute,
                EinladungZeile.einloesungen < EinladungZeile.erlaubte_einloesungen,
            )
            .values(einloesungen=EinladungZeile.einloesungen + 1)
        )
        return ergebnis.rowcount == 1

    @staticmethod
    def _naechste_nummer(session, team_name: str, saison: str) -> int:
        """Zaehlt den Zaehler des Teams hoch; die Zeile bleibt bis zum Ende gesperrt."""
        einfuegen = pg_insert(TeamNummerZeile).values(
            team_name=team_name, saison=saison, letzte_nummer=1
        )
        return session.execute(
            einfuegen.on_conflict_do_update(
                index_elements=[TeamNummerZeile.team_name, TeamNummerZeile.saison],
                set_={"letzte_nummer": TeamNummerZeile.letzte_nummer + 1},
            ).returning(TeamNummerZeile.letzte_nummer)
        ).scalar_one()

    def verlassen(self, konto: str, mitgliedschaft_id: uuid.UUID) -> bool:
        """Loescht die Mitgliedschaft sofort; nur die eigene. Die Nummer bleibt vergeben."""
        with self.db.get_session() as session:
            ergebnis = session.execute(
                delete(TeamMitgliedschaftZeile).where(
                    TeamMitgliedschaftZeile.id == mitgliedschaft_id,
                    TeamMitgliedschaftZeile.konto_kennung == konto,
                )
            )
            return ergebnis.rowcount == 1

    # --- Oeffentlich am Namen ------------------------------------------------

    def oeffentlich_lesen(self, konto: str) -> Optional[OeffentlichAntwort]:
        with self.db.get_session() as session:
            zeile = session.get(TeamOeffentlichZeile, konto)
            if zeile is None:
                return None
            return OeffentlichAntwort(
                zeigen=zeile.zeigen,
                einwilligung_kennung=zeile.einwilligung_kennung,
                beantwortet_am=zeile.beantwortet_am,
            )

    def oeffentlich_setzen(
        self, konto: str, zeigen: bool, einwilligung_kennung: str, zeitpunkt: datetime
    ) -> None:
        with self.db.get_session() as session:
            einfuegen = pg_insert(TeamOeffentlichZeile).values(
                konto_kennung=konto,
                zeigen=zeigen,
                einwilligung_kennung=einwilligung_kennung,
                beantwortet_am=zeitpunkt,
            )
            session.execute(
                einfuegen.on_conflict_do_update(
                    index_elements=[TeamOeffentlichZeile.konto_kennung],
                    set_={
                        "zeigen": einfuegen.excluded.zeigen,
                        "einwilligung_kennung": einfuegen.excluded.einwilligung_kennung,
                        "beantwortet_am": einfuegen.excluded.beantwortet_am,
                    },
                )
            )

    def oeffentliche_teams(
        self, kennungen: Sequence[str], saison: str
    ) -> Dict[str, List[Tuple[str, Optional[str]]]]:
        """
        Kennung -> [(Teamname, Motiv)] der Saison, nur fuer Personen, die "Team
        öffentlich am Namen zeigen" zugestimmt haben; neuester Beitritt zuerst.
        """
        if not kennungen:
            return {}
        abfrage = (
            select(
                TeamMitgliedschaftZeile.konto_kennung,
                TeamMitgliedschaftZeile.team_name,
                TeamMitgliedschaftZeile.team_motiv,
            )
            .join(
                TeamOeffentlichZeile,
                TeamOeffentlichZeile.konto_kennung
                == TeamMitgliedschaftZeile.konto_kennung,
            )
            .where(
                TeamOeffentlichZeile.zeigen.is_(True),
                TeamMitgliedschaftZeile.saison == saison,
                TeamMitgliedschaftZeile.konto_kennung.in_(set(kennungen)),
            )
            .order_by(
                TeamMitgliedschaftZeile.eingetreten_am.desc(),
                TeamMitgliedschaftZeile.nummer,
                TeamMitgliedschaftZeile.team_name,
            )
        )
        ergebnis: Dict[str, List[Tuple[str, Optional[str]]]] = {}
        with self.db.get_session() as session:
            for kennung, name, motiv in session.execute(abfrage).all():
                ergebnis.setdefault(kennung, []).append((name, motiv))
        return ergebnis


_repository: Optional[TeamRepository] = None


def get_team_repository() -> TeamRepository:
    global _repository
    if _repository is None:
        _repository = TeamRepository()
    return _repository
