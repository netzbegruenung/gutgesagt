"""
Repository fuer Team-Fortschritt und Team-Quests: der Wochenzaehler (team_wochen), die
Quest je Team und Woche (team_quests) und, nur lesend, die Mitgliedschaften mit
deckender Einwilligung. Was gezaehlt wird und warum ohne Kennung:
services/team_fortschritt_service.py.

Keine Methode schreibt eine Kennung, und keine gibt fremde Kennungen heraus: Die
Mitgliedschaften werden nur fuer die eigene Kennung gelesen oder je Team gezaehlt.
"""

from dataclasses import dataclass
from datetime import date
from typing import Collection, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domain.team_fortschritt import Art, Wochenzaehlung
from infrastructure.database.connection import AppDatabase, get_app_database
from infrastructure.database.models import (
    TeamMitgliedschaftZeile,
    TeamQuestZeile,
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

    def team_loeschen(self, team_name: str, saison: str) -> int:
        """
        Wochenzaehler und Quests eines Teams loeschen ("entfallen mit dem Team",
        docs/LOESCHKONZEPT.md). Eine Team-Loeschung gibt es noch nicht; wer sie baut
        (etwa ueber team_nummern oder die Einladungen), ruft dies in derselben
        Transaktion auf. tests/unit/test_team_loeschung_nimmt_zaehler_mit.py erinnert
        daran. Gibt die Zahl der geloeschten Zeilen zurueck.
        """
        with self.db.get_session() as session:
            n = 0
            for zeile in (TeamWocheZeile, TeamQuestZeile):
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
