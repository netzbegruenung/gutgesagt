"""
Einladungen (#429): Ein Admin legt im Admin-Dashboard eine Einladung an (Notiz, Zahl
erlaubter Einloesungen, letzter gueltiger Tag), und wer den Link hat, legt damit selbst ein
Konto im Realm von Gut gesagt an. Gruppenlink und persoenlicher Link sind derselbe
Mechanismus, nur mit anderen Zahlen.

Ablauf beim Einloesen: die Einloesung zaehlen (atomar in der Datenbank, nur solange
die Einladung aktiv ist), dann das Konto mit Vor- und Nachname ueber die
Keycloak-Admin-Schnittstelle anlegen; Keycloak schickt die Mail "Passwort festlegen",
deren Link auch die Adresse bestaetigt. Scheitert Keycloak, wird die
Einloesung zurueckgenommen. Gibt es zur Adresse schon ein Konto, bleibt sie gezaehlt:
Der Zaehler zaehlt Einloesungen, nicht angelegte Konten. Wuerde sie zurueckgenommen,
verriete /pruefen danach, dass die Adresse ein Konto hat (etwa bei einem persoenlichen
Link mit einer fremden Adresse). Auch eine Adresse mit Tippfehler zaehlt; das Konto
entsteht dann fuer sie, und die Mail geht dorthin.

Datenschutz: Am Konto steht nicht, ueber welche Einladung es entstand, und an der
Einladung keine Mail-Adresse, nur der Zaehler. Sonst liesse sich aus einer Einladung
etwa fuer eine bestimmte Gruppe die Zugehoerigkeit einer Person ableiten (Art. 9
DSGVO). Keycloak bekommt deshalb nie den Code, die Datenbank weder Mail-Adresse noch
Namen, und keine Logzeile nennt eines davon.

Teams (services/team_service.py): Eine Einladung kann zu einem Team gehoeren. Die
Mitgliedschaft entsteht nur mit ausdruecklicher Einwilligung und traegt nicht, ueber
welche Einladung sie entstand. Ohne wirksamen Schalter ``teams`` werden Teamfelder
ignoriert.
"""

import enum
import secrets
import uuid
from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Tuple

from core.logging import get_logger
from domain.teams import TEAM_ART_ANLASS, TEAM_ART_GRUPPE
from domain.interfaces.konten_im_realm import IKontenImRealm, KontoErgebnis
from repositories.einladung_repository import EinladungRepository
from services.team_service import (
    Mitgliedschaft,
    NichtEinloesbar,
    Team,
    TeamInfo,
    TeamService,
    TeamsAus,
)
from utils.utc_tag import heute_utc

logger = get_logger(__name__)

NOTIZ_MAX = 200
EINLOESUNGEN_MAX = 1000
# Laenger als ein Jahr gilt keine Einladung; wer mehr braucht, legt eine neue an.
GUELTIG_TAGE_MAX = 366
# 16 Bytes Zufall, URL-sicher kodiert: 22 Zeichen, nicht zu erraten.
CODE_BYTES = 16


class EinladungUngueltig(Exception):
    """Den Code gibt es nicht, oder die Einladung ist abgeschaltet, abgelaufen oder aufgebraucht."""


class EinloesenNichtEingerichtet(Exception):
    """Kein Zugang zur Keycloak-Admin-Schnittstelle konfiguriert."""


class KontoAnlegenFehlgeschlagen(Exception):
    """Keycloak hat das Konto nicht angelegt oder die Mail nicht verschickt."""


class EinladungOhneTeam(Exception):
    """Die Einladung gehoert zu keinem Team (oder der Schalter teams wirkt nicht)."""


# Fuer aendern(): Team nicht anfassen.
UNVERAENDERT = object()


class EinladungZustand(str, enum.Enum):
    AKTIV = "aktiv"
    ABGESCHALTET = "abgeschaltet"
    ABGELAUFEN = "abgelaufen"
    AUFGEBRAUCHT = "aufgebraucht"


@dataclass(frozen=True)
class Einladung:
    id: uuid.UUID
    code: str
    notiz: str
    erlaubte_einloesungen: int
    einloesungen: int
    gueltig_bis: date
    abgeschaltet: bool
    angelegt_am: date
    team_name: Optional[str] = None
    team_motiv: Optional[str] = None
    team_saison: Optional[str] = None
    # "anlass" oder "gruppe" (domain/teams.py TEAM_ARTEN); leer bei Einladungen
    # von vor dieser Spalte, dann gilt "anlass".
    team_art: Optional[str] = None
    # Tag der schriftlichen Zustimmung der Gruppenleitung, nur bei "gruppe"
    team_zustimmung_am: Optional[date] = None

    @classmethod
    def aus_zeile(cls, z) -> "Einladung":
        return cls(
            id=z.id,
            code=z.code,
            notiz=z.notiz,
            erlaubte_einloesungen=z.erlaubte_einloesungen,
            einloesungen=z.einloesungen,
            gueltig_bis=z.gueltig_bis,
            abgeschaltet=z.abgeschaltet,
            angelegt_am=z.angelegt_am,
            team_name=getattr(z, "team_name", None),
            team_motiv=getattr(z, "team_motiv", None),
            team_saison=getattr(z, "team_saison", None),
            team_art=getattr(z, "team_art", None),
            team_zustimmung_am=getattr(z, "team_zustimmung_am", None),
        )

    @property
    def team(self) -> Optional[Team]:
        """Das Team, wie es an der Einladung steht (ohne Blick auf den Schalter)."""
        if not self.team_name or not self.team_saison:
            return None
        return Team(
            self.team_name,
            self.team_motiv,
            self.team_saison,
            art=self.team_art or TEAM_ART_ANLASS,
            zustimmung_am=self.team_zustimmung_am,
        )

    def zustand(self, heute: Optional[date] = None) -> EinladungZustand:
        """Nur eine aktive Einladung laesst sich einloesen."""
        if self.abgeschaltet:
            return EinladungZustand.ABGESCHALTET
        if self.gueltig_bis < (heute or heute_utc()):
            return EinladungZustand.ABGELAUFEN
        if self.einloesungen >= self.erlaubte_einloesungen:
            return EinladungZustand.AUFGEBRAUCHT
        return EinladungZustand.AKTIV


class EinladungService:
    def __init__(
        self,
        repository: EinladungRepository,
        konten: Optional[IKontenImRealm],
        teams: Optional[TeamService] = None,
    ):
        self._repository = repository
        self._konten = konten
        self._teams = teams

    @property
    def einloesen_eingerichtet(self) -> bool:
        return self._konten is not None

    @property
    def teams_wirksam(self) -> bool:
        return self._teams is not None and self._teams.wirksam()

    @property
    def teams(self) -> Optional[TeamService]:
        return self._teams

    def team(self, einladung: Einladung) -> Optional[Team]:
        """Das Team der Einladung, nur bei wirksamem Schalter teams."""
        return einladung.team if self.teams_wirksam else None

    def anlegen(
        self,
        notiz: str,
        erlaubte_einloesungen: int,
        gueltig_bis: date,
        heute: Optional[date] = None,
        team: Optional[Team] = None,
    ) -> Einladung:
        """Ohne wirksamen Schalter teams wird ``team`` ignoriert."""
        team = team if self.teams_wirksam else None
        zeile = self._repository.anlegen(
            code=secrets.token_urlsafe(CODE_BYTES),
            notiz=notiz,
            erlaubte_einloesungen=erlaubte_einloesungen,
            gueltig_bis=gueltig_bis,
            angelegt_am=heute or heute_utc(),
            **_team_spalten(team),
        )
        return Einladung.aus_zeile(zeile)

    def alle(self) -> List[Einladung]:
        return [Einladung.aus_zeile(z) for z in self._repository.alle()]

    def schalten(
        self, einladung_id: uuid.UUID, abgeschaltet: bool
    ) -> Optional[Einladung]:
        """Ab- oder wieder einschalten; der Zaehler bleibt."""
        return self.aendern(einladung_id, abgeschaltet=abgeschaltet)

    def aendern(
        self,
        einladung_id: uuid.UUID,
        abgeschaltet: Optional[bool] = None,
        team=UNVERAENDERT,
    ) -> Optional[Einladung]:
        """
        Ab- oder einschalten und/oder das Team setzen (``None`` nimmt es weg). Der
        Zaehler bleibt; vorhandene Mitgliedschaften behalten ihre Kopie des Teams.
        Ohne wirksamen Schalter teams bleibt das Team unveraendert.
        """
        werte: dict = {}
        if abgeschaltet is not None:
            werte["abgeschaltet"] = abgeschaltet
        if team is not UNVERAENDERT and self.teams_wirksam:
            werte.update(_team_spalten(team))
        zeile = self._repository.aendern(einladung_id, **werte)
        return Einladung.aus_zeile(zeile) if zeile is not None else None

    def nach_code(self, code: str) -> Optional[Einladung]:
        zeile = self._repository.nach_code(code)
        return Einladung.aus_zeile(zeile) if zeile is not None else None

    def ist_einloesbar(self, code: str, heute: Optional[date] = None) -> bool:
        einladung = self.nach_code(code)
        return (
            einladung is not None and einladung.zustand(heute) is EinladungZustand.AKTIV
        )

    def team_info(
        self, code: str, konto: Optional[str] = None, heute: Optional[date] = None
    ) -> Optional[TeamInfo]:
        """
        Fuer /pruefen: das Team einer einloesbaren Einladung mit Mitgliederzahl und
        naechster Nummer; None ohne Team oder ohne Schalter. Ist die Einladung nicht
        mehr einloesbar, nur fuer ein Mitglied des Teams (``konto``), damit es "schon
        dabei" sieht; allen anderen verraet sie dann nichts.
        """
        einladung = self.nach_code(code)
        if einladung is None or self.team(einladung) is None:
            return None
        info = self._teams.info(einladung.team, konto)
        if einladung.zustand(heute) is EinladungZustand.AKTIV:
            return info
        return info if konto and info.eigene_nummer is not None else None

    def einloesen(
        self,
        code: str,
        email: str,
        heute: Optional[date] = None,
        vorname: Optional[str] = None,
        nachname: Optional[str] = None,
        team_einwilligung: bool = False,
        team_oeffentlich: bool = False,
        team_einwilligung_kennung: Optional[str] = None,
        team_oeffentlich_kennung: Optional[str] = None,
    ) -> None:
        """
        Legt ueber die Einladung ein Konto an. Gibt es zur Adresse schon eines, endet
        der Aufruf genauso und zaehlt genauso: Ob eine Adresse ein Konto hat, erfaehrt
        hier niemand.

        Mit ``team_einwilligung`` (Knopf "Ja, speichert ...") und einem Team an der
        Einladung entsteht die Mitgliedschaft, sobald Keycloak das Konto neu angelegt
        hat; ``team_oeffentlich`` gibt dazu die Einwilligung "Team öffentlich am Namen
        zeigen", wenn deren Schalter wirkt. Gespeichert werden die Kennungen der
        gezeigten Wortlaute. Ohne Einwilligung: keine Mitgliedschaft.
        """
        if self._konten is None:
            raise EinloesenNichtEingerichtet()
        team = None
        if team_einwilligung:
            einladung = self.nach_code(code)
            team = self.team(einladung) if einladung is not None else None
        if not self._repository.einloesung_zaehlen(code, heute or heute_utc()):
            raise EinladungUngueltig()
        weitere = {}
        if team is not None:
            teams = self._teams

            def bei_angelegt(konto_id: str) -> None:
                teams.nach_kontoanlage(
                    konto_id,
                    team,
                    einwilligung_kennung=team_einwilligung_kennung,
                    oeffentlich=team_oeffentlich,
                    oeffentlich_kennung=team_oeffentlich_kennung,
                )

            weitere["bei_angelegt"] = bei_angelegt
        try:
            ergebnis = self._konten.konto_anlegen(email, vorname, nachname, **weitere)
        except Exception as e:
            self._repository.einloesung_zuruecknehmen(code)
            # Ohne Adresse und Code, nur die Art des Fehlers.
            logger.error(f"Creating account via invitation failed: {type(e).__name__}")
            raise KontoAnlegenFehlgeschlagen() from e
        if ergebnis is KontoErgebnis.VORHANDEN:
            logger.info("Invitation redeemed for an existing account")
        else:
            logger.info("Account created via invitation")

    def beitreten(
        self,
        code: str,
        konto: str,
        heute: Optional[date] = None,
        einwilligung_kennung: Optional[str] = None,
    ) -> Tuple[Team, Mitgliedschaft, bool]:
        """
        Angemeldet einem Team beitreten (nach dem Knopf "Ja, speichert ..."). Neu:
        zaehlt gegen die erlaubten Einloesungen. Schon dabei: nichts wird gezaehlt,
        ``neu`` ist False, die Nummer die vorhandene.
        """
        if not self.teams_wirksam:
            raise TeamsAus()
        einladung = self.nach_code(code)
        if einladung is None:
            raise EinladungUngueltig()
        team = einladung.team
        if team is None:
            raise EinladungOhneTeam()
        try:
            mitgliedschaft, neu = self._teams.beitreten(
                konto,
                team,
                code=code,
                heute=heute,
                einwilligung_kennung=einwilligung_kennung,
            )
        except NichtEinloesbar:
            raise EinladungUngueltig()
        return team, mitgliedschaft, neu


def _team_spalten(team: Optional[Team]) -> dict:
    return {
        "team_name": team.name if team else None,
        "team_motiv": team.motiv if team else None,
        "team_saison": team.saison if team else None,
        "team_art": team.art if team else None,
        "team_zustimmung_am": (
            team.zustimmung_am if team and team.art == TEAM_ART_GRUPPE else None
        ),
    }
