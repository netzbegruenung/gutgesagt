"""
Repository fuer Team-Fortschritt und Team-Quests: der Wochenzaehler (team_wochen), die
Quest je Team und Woche (team_quests), der Stundenzaehler fuer den Live-Stand
(team_stunden, Schalter team_live) und, nur lesend, die Mitgliedschaften mit
deckender Einwilligung. Was gezaehlt wird und warum ohne Kennung:
services/team_fortschritt_service.py.

Keine Methode schreibt eine Kennung, und keine gibt fremde Kennungen heraus: Die
Mitgliedschaften werden nur fuer die eigene Kennung gelesen oder je Team gezaehlt.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Collection, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domain.team_fortschritt import Art, Wochenzaehlung
from infrastructure.database.connection import AppDatabase, get_app_database
from infrastructure.database.models import (
    TeamMitgliedschaftZeile,
    TeamQuestZeile,
    TeamStundeZeile,
    TeamWocheZeile,
)

TeamSchluessel = Tuple[str, str]
"""(Teamname, Saison): so ist ein Team bestimmt (GLOSSARY.md "Team")."""

_SPALTE = {
    Art.BEITRAG: "beitraege",
    Art.BEWERTUNG: "bewertungen",
    Art.GEPOSTET: "gepostet",
}


@dataclass(frozen=True)
class EigenesTeam:
    """Ein Team der aufrufenden Person mit deckender Einwilligung."""

    team_name: str
    saison: str
    eingetreten_am: date
    # Zeitpunkt der Einwilligung; fuer den Hinweis an Bestandsmitglieder (team_live)
    einwilligung_zeitpunkt: Optional[datetime] = None

    @property
    def schluessel(self) -> TeamSchluessel:
        return (self.team_name, self.saison)


# Stand eines Stundenblocks (Spalte team_stunden.stand)
OFFEN = "offen"
UEBERTRAGEN = "uebertragen"
FREIGEGEBEN = "freigegeben"


@dataclass(frozen=True)
class Stunde:
    """Ein Stundenzaehler: nur Zahlen, ohne Kennung."""

    team_name: str
    saison: str
    block_beginn: datetime
    anzahl: int
    stand: str
    freigabe: Optional[int]
    mitglieder: Optional[int]

    @property
    def schluessel(self) -> TeamSchluessel:
        return (self.team_name, self.saison)


@dataclass(frozen=True)
class Quest:
    team_name: str
    saison: str
    woche: date
    thema: Optional[str]
    ziel: int


class TeamFortschrittRepository:
    def __init__(self, db: Optional[AppDatabase] = None):
        # Erst beim ersten Zugriff: Ohne wirksamen Schalter fragt der Dienst die
        # Datenbank nie.
        self._db = db

    @property
    def db(self) -> AppDatabase:
        if self._db is None:
            self._db = get_app_database()
        return self._db

    # --- Mitgliedschaften (nur lesen) ------------------------------------------

    def eigene_teams(self, konto: str, kennungen: Collection[str]) -> List[EigenesTeam]:
        """Die Teams der Person, deren Einwilligung eine der ``kennungen`` traegt."""
        abfrage = select(
            TeamMitgliedschaftZeile.team_name,
            TeamMitgliedschaftZeile.saison,
            TeamMitgliedschaftZeile.eingetreten_am,
            TeamMitgliedschaftZeile.einwilligung_zeitpunkt,
        ).where(
            TeamMitgliedschaftZeile.konto_kennung == konto,
            TeamMitgliedschaftZeile.einwilligung_kennung.in_(list(kennungen)),
        )
        with self.db.get_session() as session:
            return [EigenesTeam(*zeile) for zeile in session.execute(abfrage).all()]

    def einwilligende_je_team(
        self, teams: Iterable[TeamSchluessel], kennungen: Collection[str]
    ) -> Dict[TeamSchluessel, int]:
        """(Name, Saison) -> Zahl der Mitglieder mit deckender Einwilligung; nur Zahlen."""
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
                ).in_(teams),
                TeamMitgliedschaftZeile.einwilligung_kennung.in_(list(kennungen)),
            )
            .group_by(TeamMitgliedschaftZeile.team_name, TeamMitgliedschaftZeile.saison)
        )
        with self.db.get_session() as session:
            gezaehlt = {(n, s): z for n, s, z in session.execute(abfrage).all()}
        return {t: gezaehlt.get(t, 0) for t in teams}

    def einwilligende_der_saison(
        self, saison: str, kennungen: Collection[str]
    ) -> Dict[TeamSchluessel, int]:
        """Je Team der Saison die Zahl der Mitglieder mit deckender Einwilligung."""
        abfrage = (
            select(TeamMitgliedschaftZeile.team_name, func.count())
            .where(
                TeamMitgliedschaftZeile.saison == saison,
                TeamMitgliedschaftZeile.einwilligung_kennung.in_(list(kennungen)),
            )
            .group_by(TeamMitgliedschaftZeile.team_name)
        )
        with self.db.get_session() as session:
            return {(n, saison): z for n, z in session.execute(abfrage).all()}

    # --- Wochenzaehler ---------------------------------------------------------

    def erhoehen(self, teams: Iterable[TeamSchluessel], woche: date, art: Art) -> None:
        """Den Zaehler ``art`` je Team fuer ``woche`` um eins erhoehen, in einer Transaktion."""
        spalte = _SPALTE[art]
        with self.db.get_session() as session:
            for team_name, saison in teams:
                anweisung = pg_insert(TeamWocheZeile).values(
                    team_name=team_name, saison=saison, woche=woche, **{spalte: 1}
                )
                session.execute(
                    anweisung.on_conflict_do_update(
                        index_elements=["team_name", "saison", "woche"],
                        set_={spalte: getattr(TeamWocheZeile, spalte) + 1},
                    )
                )

    def wochen(
        self, teams: Iterable[TeamSchluessel], woche: date
    ) -> Dict[TeamSchluessel, Wochenzaehlung]:
        """Die Zaehler der Teams fuer ``woche``; Teams ohne Zeile fehlen."""
        teams = list(set(teams))
        if not teams:
            return {}
        abfrage = select(
            TeamWocheZeile.team_name,
            TeamWocheZeile.saison,
            TeamWocheZeile.beitraege,
            TeamWocheZeile.bewertungen,
            TeamWocheZeile.gepostet,
        ).where(
            tuple_(TeamWocheZeile.team_name, TeamWocheZeile.saison).in_(teams),
            TeamWocheZeile.woche == woche,
        )
        with self.db.get_session() as session:
            return {
                (n, s): Wochenzaehlung(b, w, g)
                for n, s, b, w, g in session.execute(abfrage).all()
            }

    # --- Stundenzaehler (team_live) ---------------------------------------------

    def stunde_erhoehen(
        self, teams: Iterable[TeamSchluessel], block_beginn: datetime
    ) -> None:
        """Den Stundenzaehler je Team fuer den Block um eins erhoehen."""
        with self.db.get_session() as session:
            for team_name, saison in teams:
                anweisung = pg_insert(TeamStundeZeile).values(
                    team_name=team_name,
                    saison=saison,
                    block_beginn=block_beginn,
                    anzahl=1,
                )
                session.execute(
                    anweisung.on_conflict_do_update(
                        index_elements=["team_name", "saison", "block_beginn"],
                        set_={"anzahl": TeamStundeZeile.anzahl + 1},
                    )
                )

    def stunden(self, teams: Iterable[TeamSchluessel], ab: datetime) -> List[Stunde]:
        """Die Stundenzaehler der Teams ab ``ab`` (Blockbeginn), aelteste zuerst."""
        teams = list(set(teams))
        if not teams:
            return []
        abfrage = (
            select(TeamStundeZeile)
            .where(
                tuple_(TeamStundeZeile.team_name, TeamStundeZeile.saison).in_(teams),
                TeamStundeZeile.block_beginn >= ab,
            )
            .order_by(TeamStundeZeile.block_beginn)
        )
        with self.db.get_session() as session:
            return [
                Stunde(
                    z.team_name,
                    z.saison,
                    z.block_beginn,
                    z.anzahl,
                    z.stand,
                    z.freigabe,
                    z.mitglieder,
                )
                for z in session.execute(abfrage).scalars().all()
            ]

    def teams_mit_stunden(self, saison: str, ab: datetime) -> List[TeamSchluessel]:
        """Die Teams der Saison mit einem Stundenzaehler ab ``ab``."""
        abfrage = (
            select(TeamStundeZeile.team_name)
            .where(TeamStundeZeile.saison == saison, TeamStundeZeile.block_beginn >= ab)
            .distinct()
        )
        with self.db.get_session() as session:
            return [(n, saison) for n in session.execute(abfrage).scalars().all()]

    def stunde_abschliessen(
        self,
        team: TeamSchluessel,
        block_beginn: datetime,
        stand: str,
        freigabe: Optional[int],
        mitglieder: int,
    ) -> bool:
        """
        Einen Block einmal vorberechnen: Stand, freigegebene Zahl und Mitgliederzahl
        setzen, nur solange er offen ist (legt ihn ohne Ereignisse mit 0 an). False,
        wenn er schon vorberechnet war.
        """
        anweisung = pg_insert(TeamStundeZeile).values(
            team_name=team[0],
            saison=team[1],
            block_beginn=block_beginn,
            anzahl=0,
            stand=stand,
            freigabe=freigabe,
            mitglieder=mitglieder,
        )
        with self.db.get_session() as session:
            ergebnis = session.execute(
                anweisung.on_conflict_do_update(
                    index_elements=["team_name", "saison", "block_beginn"],
                    set_={
                        "stand": anweisung.excluded.stand,
                        "freigabe": anweisung.excluded.freigabe,
                        "mitglieder": anweisung.excluded.mitglieder,
                    },
                    where=TeamStundeZeile.stand == OFFEN,
                )
            )
            return ergebnis.rowcount > 0

    def erste_stunde(self) -> Optional[datetime]:
        """Der frueheste Blockbeginn aller Stundenzaehler; None ohne Zaehler."""
        with self.db.get_session() as session:
            return session.execute(
                select(func.min(TeamStundeZeile.block_beginn))
            ).scalar()

    def stunden_loeschen_vor(self, grenze: datetime) -> int:
        """Stundenzaehler mit Blockbeginn vor der Grenze loeschen (Wochenwechsel)."""
        with self.db.get_session() as session:
            return session.execute(
                delete(TeamStundeZeile).where(TeamStundeZeile.block_beginn < grenze)
            ).rowcount

    # --- Quests ----------------------------------------------------------------

    def quests(
        self, teams: Iterable[TeamSchluessel], woche: date
    ) -> Dict[TeamSchluessel, Quest]:
        teams = list(set(teams))
        if not teams:
            return {}
        abfrage = select(TeamQuestZeile).where(
            tuple_(TeamQuestZeile.team_name, TeamQuestZeile.saison).in_(teams),
            TeamQuestZeile.woche == woche,
        )
        with self.db.get_session() as session:
            return {
                (z.team_name, z.saison): Quest(
                    z.team_name, z.saison, z.woche, z.thema, z.ziel
                )
                for z in session.execute(abfrage).scalars().all()
            }

    def quest_anlegen(self, quest: Quest) -> Quest:
        """Legt die Quest an; gibt es fuer Team und Woche schon eine, gilt die vorhandene."""
        with self.db.get_session() as session:
            session.execute(
                pg_insert(TeamQuestZeile)
                .values(
                    team_name=quest.team_name,
                    saison=quest.saison,
                    woche=quest.woche,
                    thema=quest.thema,
                    ziel=quest.ziel,
                )
                .on_conflict_do_nothing(index_elements=["team_name", "saison", "woche"])
            )
            zeile = session.execute(
                select(TeamQuestZeile).where(
                    TeamQuestZeile.team_name == quest.team_name,
                    TeamQuestZeile.saison == quest.saison,
                    TeamQuestZeile.woche == quest.woche,
                )
            ).scalar_one()
            return Quest(
                zeile.team_name, zeile.saison, zeile.woche, zeile.thema, zeile.ziel
            )

    def erreichte_quests(
        self, teams: Iterable[TeamSchluessel], vor: date
    ) -> List[Quest]:
        """
        Die Quests der Teams aus Wochen vor ``vor`` (abgeschlossen), deren
        Wochenzaehler das Ziel erreicht hat.
        """
        teams = list(set(teams))
        if not teams:
            return []
        gesamt = (
            TeamWocheZeile.beitraege
            + TeamWocheZeile.bewertungen
            + TeamWocheZeile.gepostet
        )
        abfrage = (
            select(TeamQuestZeile)
            .join(
                TeamWocheZeile,
                (TeamWocheZeile.team_name == TeamQuestZeile.team_name)
                & (TeamWocheZeile.saison == TeamQuestZeile.saison)
                & (TeamWocheZeile.woche == TeamQuestZeile.woche),
            )
            .where(
                tuple_(TeamQuestZeile.team_name, TeamQuestZeile.saison).in_(teams),
                TeamQuestZeile.woche < vor,
                gesamt >= TeamQuestZeile.ziel,
            )
        )
        with self.db.get_session() as session:
            return [
                Quest(z.team_name, z.saison, z.woche, z.thema, z.ziel)
                for z in session.execute(abfrage).scalars().all()
            ]

    # --- Team loeschen ---------------------------------------------------------

    def team_loeschen(self, team_name: str, saison: str, session=None) -> int:
        """
        Wochenzaehler, Stundenzaehler und Quests eines Teams loeschen ("entfallen mit dem Team",
        docs/LOESCHKONZEPT.md). Eine Team-Loeschung gibt es noch nicht; wer sie baut
        (etwa ueber team_nummern oder die Einladungen), uebergibt seine ``session``,
        damit alles in einer Transaktion geht; ohne sie eine eigene.
        tests/unit/test_team_loeschung_nimmt_zaehler_mit.py erinnert daran. Gibt die
        Zahl der geloeschten Zeilen zurueck.
        """
        if session is not None:
            return self._team_loeschen(session, team_name, saison)
        with self.db.get_session() as eigene:
            return self._team_loeschen(eigene, team_name, saison)

    @staticmethod
    def _team_loeschen(session, team_name: str, saison: str) -> int:
        n = 0
        for zeile in (TeamWocheZeile, TeamQuestZeile, TeamStundeZeile):
            n += session.execute(
                delete(zeile).where(
                    zeile.team_name == team_name, zeile.saison == saison
                )
            ).rowcount
        return n


_repository: Optional[TeamFortschrittRepository] = None


def get_team_fortschritt_repository() -> TeamFortschrittRepository:
    global _repository
    if _repository is None:
        _repository = TeamFortschrittRepository()
    return _repository
