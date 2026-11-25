"""
Teams ueber Einladungen (GLOSSARY.md "Team").

Ein Admin gibt einer Einladung einen Teamnamen (nur Anlass, Ort oder Saison), ein
Motiv und eine Saison. Wer den Link oeffnet, sieht das Team und die voraussichtliche
Nummer. Gespeichert wird die Mitgliedschaft erst nach dem Knopf "Ja, speichert, dass
ich im Team X bin" (Einwilligung, domain/teams.py), mit Kennung des Wortlauts und
Zeitpunkt; bei Nein bleibt es beim Zaehlen an der Einladung wie bisher:

- ohne Konto (POST /einladungen/einloesen mit Einwilligung): Die Mitgliedschaft
  entsteht, wenn Keycloak das Konto neu angelegt hat. Gibt es zur Adresse schon ein
  Konto, entsteht keine: Sonst koennte jemand fremde Konten in Teams eintragen, und
  die Antwort bliebe trotzdem gleich.
- angemeldet (POST /einladungen/beitreten): Beitritt zaehlt gegen die erlaubten
  Einloesungen; wer schon im Team ist, bekommt seine Nummer, gezaehlt wird nichts.

Datenschutz: An der Mitgliedschaft steht nicht, ueber welche Einladung sie entstand,
nur Teamname, Motiv, Saison, Nummer und Tag. Die eigenen Teams sieht nur die Person
selbst; Admins sehen je Team nur die Zahl der Mitglieder, es gibt keine Liste, keinen
Export und keinen Abruf fremder Mitgliedschaften. "Team verlassen" loescht sofort,
ebenso die Loeschung des Kontos (mvp/scripts/manual/person_loeschen.sql).

Am Namen erscheinen Teams nur, wenn der Schalter ``teams_oeffentlich`` wirkt UND die
Person der eigenen Einwilligung "Team öffentlich am Namen zeigen" zugestimmt hat, und
nur die Teams der aktuellen Saison (services/einstellungen_service.py).

Schalter ``teams`` aus: Teamfelder werden ignoriert, Einladungen wie bisher.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from core.config import Settings
from core.logging import get_logger, log_pseudonym
from domain.teams import (
    EINWILLIGUNG_KENNUNG,
    OEFFENTLICH_KENNUNG,
    OEFFENTLICH_WORTLAUTE,
    wortlaut_pruefen,
)
from repositories.team_repository import (
    Mitgliedschaft,
    NichtEinloesbar,
    OeffentlichAntwort,
    TeamRepository,
)
from services.einstellungen_service import aktuelle_saison
from services.schalter_service import schalter_wirksam
from utils.utc_tag import heute_utc

logger = get_logger(__name__)

__all__ = [
    "Mitgliedschaft",
    "NichtEinloesbar",
    "Team",
    "TeamInfo",
    "TeamService",
    "TeamsAus",
    "OeffentlichAus",
]


class TeamsAus(Exception):
    """Der Schalter teams wirkt nicht."""


class OeffentlichAus(Exception):
    """Der Schalter teams_oeffentlich wirkt nicht."""


@dataclass(frozen=True)
class Team:
    name: str
    motiv: Optional[str]
    saison: str


@dataclass(frozen=True)
class TeamInfo:
    team: Team
    mitglieder: int
    naechste_nummer: int
    # Nummer der aufrufenden Person, wenn sie schon im Team ist
    eigene_nummer: Optional[int]


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


class TeamService:
    def __init__(
        self,
        repository: TeamRepository,
        settings: Optional[Settings] = None,
        saison: Callable[[], str] = aktuelle_saison,
        uhr: Callable[[], datetime] = _jetzt,
    ):
        self._repository = repository
        self._settings = settings
        self._saison = saison
        self._uhr = uhr

    # --- Schalter --------------------------------------------------------------

    def wirksam(self) -> bool:
        return schalter_wirksam("teams", self._settings)

    def oeffentlich_wirksam(self) -> bool:
        return schalter_wirksam("teams_oeffentlich", self._settings)

    def aktuelle_saison(self) -> str:
        return self._saison()

    # --- Einladung -------------------------------------------------------------

    def info(self, team: Team, konto: Optional[str] = None) -> TeamInfo:
        """Was die Begruessung zeigt: Mitglieder, naechste Nummer, eigene Nummer."""
        mitglieder = self._repository.mitglieder_je_team([(team.name, team.saison)])
        eigene = (
            self._repository.mitgliedschaft(konto, team.name, team.saison)
            if konto
            else None
        )
        return TeamInfo(
            team=team,
            mitglieder=mitglieder.get((team.name, team.saison), 0),
            naechste_nummer=self._repository.letzte_nummer(team.name, team.saison) + 1,
            eigene_nummer=eigene.nummer if eigene else None,
        )

    def mitglieder(self, teams: Iterable[Team]) -> Dict[Tuple[str, str], int]:
        """Fuer die Admin-Liste: je Team nur die Zahl."""
        return self._repository.mitglieder_je_team((t.name, t.saison) for t in teams)

    def beitreten(
        self,
        konto: str,
        team: Team,
        code: Optional[str] = None,
        heute: Optional[date] = None,
    ) -> Tuple[Mitgliedschaft, bool]:
        """
        Speichert die Mitgliedschaft mit Einwilligung (Kennung EINWILLIGUNG_KENNUNG,
        Zeitpunkt jetzt). Mit ``code`` zaehlt die Einloesung in derselben Transaktion
        (NichtEinloesbar, wenn die Einladung nicht mehr zaehlt).
        """
        if not self.wirksam():
            raise TeamsAus()
        mitgliedschaft, neu = self._repository.beitreten(
            konto=konto,
            team_name=team.name,
            team_motiv=team.motiv,
            saison=team.saison,
            einwilligung_kennung=EINWILLIGUNG_KENNUNG,
            zeitpunkt=self._uhr(),
            heute=heute or heute_utc(),
            code=code,
        )
        if neu:
            logger.info(f"Team joined by {log_pseudonym(konto)}")
        return mitgliedschaft, neu

    def nach_kontoanlage(
        self, konto: str, team: Team, oeffentlich: bool = False
    ) -> None:
        """
        Beim Einloesen mit Einwilligung, nachdem Keycloak das Konto angelegt hat. Die
        Einloesung ist schon gezaehlt. Scheitert das Speichern, bleibt das Konto; die
        Person kann ueber den Link angemeldet beitreten.
        """
        try:
            self.beitreten(konto, team)
            if oeffentlich and self.oeffentlich_wirksam():
                self.oeffentlich_antworten(konto, True, OEFFENTLICH_KENNUNG)
        except Exception as e:
            logger.error(
                f"Team membership after account creation failed: {type(e).__name__}"
            )

    # --- Meine Teams -----------------------------------------------------------

    def meine(self, konto: str) -> List[Mitgliedschaft]:
        if not self.wirksam():
            raise TeamsAus()
        return self._repository.meine(konto)

    def verlassen(self, konto: str, mitgliedschaft_id: uuid.UUID) -> bool:
        """Loescht sofort. Geht auch bei ausgeschaltetem Schalter (Widerruf)."""
        geloescht = self._repository.verlassen(konto, mitgliedschaft_id)
        if geloescht:
            logger.info(f"Team left by {log_pseudonym(konto)}")
        return geloescht

    # --- Oeffentlich am Namen --------------------------------------------------

    def oeffentlich_stand(self, konto: str) -> Optional[OeffentlichAntwort]:
        return self._repository.oeffentlich_lesen(konto)

    def oeffentlich_antworten(self, konto: str, zeigen: bool, wortlaut: str) -> None:
        """
        Ja nur bei wirksamem Schalter teams_oeffentlich; ein Nein (Widerruf) geht
        immer, damit niemand an einem Schalter haengen bleibt.
        """
        wortlaut_pruefen(wortlaut, OEFFENTLICH_WORTLAUTE)
        if zeigen and not self.oeffentlich_wirksam():
            raise OeffentlichAus()
        self._repository.oeffentlich_setzen(konto, zeigen, wortlaut, self._uhr())

    def pillen(
        self, kennungen: Iterable[Optional[str]]
    ) -> Dict[str, List[Tuple[str, Optional[str]]]]:
        """
        Kennung -> [(Teamname, Motiv)] der aktuellen Saison fuer die Anzeige am Namen;
        leer, solange teams_oeffentlich nicht wirkt. Nur Personen mit Einwilligung.
        """
        if not self.oeffentlich_wirksam():
            return {}
        liste = [k for k in set(kennungen) if k]
        if not liste:
            return {}
        try:
            return self._repository.oeffentliche_teams(liste, self._saison())
        except Exception as e:
            # Lieber keine Pillen als eine fehlgeschlagene Antwort.
            logger.error(f"Public teams not loaded: {type(e).__name__}")
            return {}


_service: Optional[TeamService] = None


def get_team_service() -> TeamService:
    global _service
    if _service is None:
        from repositories.team_repository import get_team_repository

        _service = TeamService(get_team_repository())
    return _service


def team_service_setzen(service: Optional[TeamService]) -> None:
    """Fuer Tests: einen eigenen Dienst einsetzen (None: wieder aus der Datenbank)."""
    global _service
    _service = service
