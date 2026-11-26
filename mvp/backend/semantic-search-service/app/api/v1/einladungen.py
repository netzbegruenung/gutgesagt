"""
Einladungen (#429). Verwalten duerfen nur Admins; pruefen und einloesen darf jede
Person ohne Anmeldung, die den Link hat (BFF/Proxy/EndpointPolicy.cs). Was gespeichert
wird und was nicht: services/einladung_service.py.

Teams (services/team_service.py): Teamfelder an der Einladung, das Team in /pruefen,
die Mitgliedschaft beim Einloesen nur mit Einwilligung und /beitreten fuer
Angemeldete. Ohne wirksamen Schalter teams werden Teamfelder ignoriert und /pruefen
liefert kein Team.
"""

import asyncio
import re
import uuid
from datetime import date, timedelta
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import (
    BaseModel,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from core.logging import get_logger
from dependencies import get_einladung_service, require_admin, require_user
from domain.teams import (
    EINWILLIGUNG_GELTEND,
    EINWILLIGUNG_KENNUNG,
    EINWILLIGUNG_WORTLAUTE,
    KNOPF_JA,
    KNOPF_NEIN,
    MOTIVE,
    OEFFENTLICH_KENNUNG,
    OEFFENTLICH_WORTLAUTE,
    SAISON_MAX,
    SAISON_VERBOTEN,
    TEAM_ART_ANLASS,
    TEAM_ART_GRUPPE,
    TEAM_NAME_MAX,
    TEAMNAME_HINWEIS,
)
from services.anzeigename_service import angemeldet
from services.einladung_service import (
    EINLOESUNGEN_MAX,
    GUELTIG_TAGE_MAX,
    NOTIZ_MAX,
    UNVERAENDERT,
    Einladung,
    EinladungOhneTeam,
    EinladungService,
    EinladungUngueltig,
    EinladungZustand,
    KontoAnlegenFehlgeschlagen,
    EinloesenNichtEingerichtet,
)
from services.team_service import Team, TeamsAus
from utils.client_identity import derive_client_key
from utils.rate_limiter import (
    einladung_pruefen_rate_limiter,
    einladung_rate_limiter,
    team_beitreten_rate_limiter,
)
from utils.utc_tag import heute_utc

logger = get_logger(__name__)

router = APIRouter()

# Nur grob: ein @, davor und dahinter kein Leerraum, dahinter ein Punkt. Ob es die
# Adresse gibt, zeigt erst die Mail von Keycloak.
MAIL_MUSTER = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAIL_MAX = 254
CODE_MAX = 64
# Vor- und Nachname gehen an Keycloak (firstName, lastName). Erlaubt ist, was das
# Benutzerprofil von Keycloak erlaubt (Validator person-name-prohibited-characters,
# 26.8.2); sonst lehnte Keycloak das Konto ab, und die Seite meldete einen
# Serverfehler statt eines falschen Namens. Dazu "@": Daraus bildete die BFF keinen
# Anzeigenamen (DisplayNamePolicy). Laenger als 100 Zeichen heisst niemand.
NAME_MAX = 100
# Kennung eines Einwilligungswortlauts (domain/teams.py), etwa "team-2026-11-26"
KENNUNG_MAX = 64
NAME_VERBOTEN = re.compile(r'[<>&"\v$%!#?§;*~/\\|^=\[\]{}()@\x00-\x1f\x7f]')
# Der Teamname steht an Namen und in Pillen: keine Steuerzeichen, kein Markup, keine
# Schraegstriche. Die Saison folgt der Regel der Saisons (SAISON_VERBOTEN in
# domain/teams.py), damit jede angelegte Saison auch am Teamlink geht.
TEAM_VERBOTEN = re.compile(r'[<>&"\\/\x00-\x1f\x7f]')


def _team_text(
    wert: Optional[str], feld: str, verboten: re.Pattern = TEAM_VERBOTEN
) -> Optional[str]:
    if wert is None:
        return None
    if verboten.search(wert):
        raise ValueError(f"{feld} enthaelt ein Zeichen, das nicht geht")
    wert = " ".join(wert.split())
    if not wert:
        raise ValueError(f"{feld} darf nicht leer sein")
    return wert


class TeamFelder(BaseModel):
    """
    Team an der Einladung: Name, Motiv, Saison und Teamart. ``team_art`` ist "anlass"
    (Team nach Anlass, Ort oder Saison; Standard) oder "gruppe" (Team nach Gruppe).
    Bei "gruppe" ist ``team_zustimmung_am`` Pflicht: der Tag, an dem die schriftliche
    Zustimmung der Gruppenleitung vorlag, nicht in der Zukunft. Gespeichert nur als
    Nachweis fuer Admins, ohne Namen; bei "anlass" gibt es kein Datum.
    """

    team_name: Optional[str] = Field(None, max_length=TEAM_NAME_MAX)
    team_motiv: Optional[str] = None
    team_saison: Optional[str] = Field(None, max_length=SAISON_MAX)
    team_art: Optional[Literal["anlass", "gruppe"]] = None
    team_zustimmung_am: Optional[date] = None

    @field_validator("team_name")
    @classmethod
    def _team_name(cls, wert: Optional[str]) -> Optional[str]:
        return _team_text(wert, "Der Teamname")

    @field_validator("team_saison")
    @classmethod
    def _team_saison(cls, wert: Optional[str]) -> Optional[str]:
        return _team_text(wert, "Die Saison", SAISON_VERBOTEN)

    @field_validator("team_motiv")
    @classmethod
    def _team_motiv(cls, wert: Optional[str]) -> Optional[str]:
        if wert is not None and wert not in MOTIVE:
            raise ValueError("Unbekanntes Motiv")
        return wert

    @model_validator(mode="after")
    def _motiv_zum_namen(self):
        if self.team_name is None:
            if any(
                v is not None
                for v in (
                    self.team_motiv,
                    self.team_saison,
                    self.team_art,
                    self.team_zustimmung_am,
                )
            ):
                raise ValueError("Motiv, Saison und Teamart nur mit Teamname")
            return self
        if self.team_motiv is None:
            raise ValueError("Ein Team braucht ein Motiv")
        if self.team_art is None:
            self.team_art = TEAM_ART_ANLASS
        if self.team_art == TEAM_ART_GRUPPE:
            if self.team_zustimmung_am is None:
                raise ValueError(
                    "Ein Team nach Gruppe braucht das Datum der schriftlichen "
                    "Zustimmung der Gruppenleitung"
                )
            if self.team_zustimmung_am > heute_utc():
                raise ValueError("Das Datum der Zustimmung liegt in der Zukunft")
        elif self.team_zustimmung_am is not None:
            raise ValueError("Ein Datum der Zustimmung nur bei einem Team nach Gruppe")
        return self

    def team(self, saison_vorschlag: str) -> Optional[Team]:
        """Ohne Saison gilt der Vorschlag (laufende oder naechste geplante Saison)."""
        if self.team_name is None:
            return None
        return Team(
            self.team_name,
            self.team_motiv,
            self.team_saison or saison_vorschlag,
            art=self.team_art or TEAM_ART_ANLASS,
            zustimmung_am=self.team_zustimmung_am,
        )


class EinladungAnlegenRequest(TeamFelder):
    notiz: str = Field(..., max_length=NOTIZ_MAX)
    erlaubte_einloesungen: int = Field(..., ge=1, le=EINLOESUNGEN_MAX)
    gueltig_bis: date

    @field_validator("notiz")
    @classmethod
    def _notiz_nicht_leer(cls, wert: str) -> str:
        wert = wert.strip()
        if not wert:
            raise ValueError("Die Notiz darf nicht leer sein")
        return wert

    @field_validator("gueltig_bis")
    @classmethod
    def _gueltig_bis_im_rahmen(cls, wert: date) -> date:
        heute = heute_utc()
        if wert < heute:
            raise ValueError("Der letzte Tag liegt in der Vergangenheit")
        if wert > heute + timedelta(days=GUELTIG_TAGE_MAX):
            raise ValueError(f"Hoechstens {GUELTIG_TAGE_MAX} Tage gueltig")
        return wert


class EinladungAendernRequest(TeamFelder):
    """
    Alle Felder optional. Teamfelder wirken nur, wenn ``team_name`` im Request steht:
    ein Name setzt das Team, ``null`` nimmt es weg. Ohne ``team_name`` bleibt das Team.
    """

    abgeschaltet: Optional[bool] = None

    @model_validator(mode="after")
    def _etwas_aendern(self):
        if self.abgeschaltet is None and "team_name" not in self.model_fields_set:
            raise ValueError("Nichts zu aendern")
        return self


class TeamAdminResponse(BaseModel):
    name: str
    motiv: Optional[str]
    saison: str
    # "anlass" oder "gruppe"; bei "gruppe" der Tag der schriftlichen Zustimmung der
    # Gruppenleitung, nur fuer Admins
    art: str = TEAM_ART_ANLASS
    zustimmung_am: Optional[date] = None
    # Nur die Zahl, nie wer (keine Liste, kein Export)
    mitglieder: int


class EinladungResponse(BaseModel):
    id: uuid.UUID
    code: str
    notiz: str
    erlaubte_einloesungen: int
    einloesungen: int
    gueltig_bis: date
    abgeschaltet: bool
    angelegt_am: date
    zustand: EinladungZustand
    # Nur bei wirksamem Schalter teams und mit Team an der Einladung
    team: Optional[TeamAdminResponse] = None

    @classmethod
    def aus(
        cls, e: Einladung, team: Optional[Team] = None, mitglieder: int = 0
    ) -> "EinladungResponse":
        return cls(
            id=e.id,
            code=e.code,
            notiz=e.notiz,
            erlaubte_einloesungen=e.erlaubte_einloesungen,
            einloesungen=e.einloesungen,
            gueltig_bis=e.gueltig_bis,
            abgeschaltet=e.abgeschaltet,
            angelegt_am=e.angelegt_am,
            zustand=e.zustand(),
            team=(
                TeamAdminResponse(
                    name=team.name,
                    motiv=team.motiv,
                    saison=team.saison,
                    art=team.art,
                    zustimmung_am=team.zustimmung_am,
                    mitglieder=mitglieder,
                )
                if team
                else None
            ),
        )


class MotivResponse(BaseModel):
    schluessel: str
    name: str


class EinladungListeResponse(BaseModel):
    # Ob Einloesen ueberhaupt geht; sonst sagt das Dashboard, dass Links ins Leere fuehren.
    einloesen_eingerichtet: bool
    einladungen: List[EinladungResponse]
    # Teams: ob der Schalter wirkt (sonst kein Teamblock im Formular), Vorschlag fuer
    # die Saison, die Motive mit Namen und der Hinweis zum Teamnamen.
    teams_aktiv: bool = False
    aktuelle_saison: Optional[str] = None
    # Vorschlag fuer neue Teamlinks: laufende oder naechste geplante Saison, sonst die
    # aktuelle Saison
    saison_vorschlag: Optional[str] = None
    motive: List[MotivResponse] = []
    teamname_hinweis: Optional[str] = None


class CodeRequest(BaseModel):
    code: str = Field(..., max_length=CODE_MAX)


class TeamPruefenResponse(BaseModel):
    name: str
    motiv: Optional[str]
    saison: str
    # "anlass" oder "gruppe": bei "gruppe" zeigt die Begruessung den Satz, dass das
    # Team mit Zustimmung der Gruppe nach ihr benannt ist. Das Datum der Zustimmung
    # geht hier nie mit.
    art: str = TEAM_ART_ANLASS
    mitglieder: int
    # Die Nummer, die als naechste vergeben wird; fest erst beim Speichern.
    naechste_nummer: int
    # Nummer der angemeldeten Person, wenn sie schon im Team ist ("schon dabei")
    eigene_nummer: Optional[int] = None
    # Einwilligung zur Mitgliedschaft: Kennung, Wortlaut mit Teamnamen, Knoepfe
    einwilligung_kennung: str
    einwilligung_text: str
    knopf_ja: str
    knopf_nein: str
    # Zweite Frage "Team öffentlich am Namen zeigen": nur bei wirksamem Schalter
    # teams_oeffentlich, sonst null (dann nicht fragen)
    oeffentlich_kennung: Optional[str] = None
    oeffentlich_text: Optional[str] = None


class PruefenResponse(BaseModel):
    einloesbar: bool
    team: Optional[TeamPruefenResponse] = None


class EinloesenRequest(CodeRequest):
    email: str = Field(..., max_length=MAIL_MAX)

    @field_validator("email")
    @classmethod
    def _email_grob_pruefen(cls, wert: str) -> str:
        # Klein, wie Keycloak Benutzernamen ablegt.
        wert = wert.strip().lower()
        if not MAIL_MUSTER.match(wert):
            raise ValueError("Keine gueltige Mail-Adresse")
        return wert

    # Optional, damit eine noch zwischengespeicherte alte Seite (PWA) weiter einloesen
    # kann; Keycloak fragt dann beim ersten Anmelden nach dem Namen.
    vorname: Optional[str] = Field(None, max_length=NAME_MAX)
    nachname: Optional[str] = Field(None, max_length=NAME_MAX)

    # Knopf "Ja, speichert, dass ich im Team X bin": nur dann entsteht eine
    # Mitgliedschaft, und nur, wenn das Konto neu angelegt wird.
    team_einwilligung: bool = False
    # Zweite Frage "Team öffentlich am Namen zeigen"; wirkt nur mit team_einwilligung
    # und wirksamem Schalter teams_oeffentlich.
    team_oeffentlich: bool = False
    # Kennungen der Wortlaute, die die Seite gezeigt hat (aus /pruefen). Gespeichert
    # wird die gezeigte Kennung, nicht die aktuelle: Hat sich der Wortlaut inzwischen
    # geaendert, bleibt nachweisbar, welchem Text die Person zugestimmt hat. Pflicht,
    # sobald die jeweilige Einwilligung gegeben wird; unbekannt: 422.
    team_einwilligung_kennung: Optional[str] = Field(
        None, max_length=KENNUNG_MAX, validate_default=True
    )
    team_oeffentlich_kennung: Optional[str] = Field(
        None, max_length=KENNUNG_MAX, validate_default=True
    )

    @field_validator("team_einwilligung_kennung")
    @classmethod
    def _einwilligung_kennung(
        cls, wert: Optional[str], info: ValidationInfo
    ) -> Optional[str]:
        if info.data.get("team_einwilligung") and wert not in EINWILLIGUNG_GELTEND:
            raise ValueError("Unbekannter Wortlaut")
        return wert

    @field_validator("team_oeffentlich_kennung")
    @classmethod
    def _oeffentlich_kennung(
        cls, wert: Optional[str], info: ValidationInfo
    ) -> Optional[str]:
        if (
            info.data.get("team_einwilligung")
            and info.data.get("team_oeffentlich")
            and wert not in OEFFENTLICH_WORTLAUTE
        ):
            raise ValueError("Unbekannter Wortlaut")
        return wert

    @field_validator("vorname", "nachname")
    @classmethod
    def _name_pruefen(cls, wert: Optional[str]) -> Optional[str]:
        if wert is None:
            return None
        wert = " ".join(wert.split())
        if not wert:
            raise ValueError("Der Name darf nicht leer sein")
        if NAME_VERBOTEN.search(wert):
            raise ValueError("Der Name enthaelt ein Zeichen, das nicht geht")
        return wert

    @model_validator(mode="after")
    def _beide_namen_oder_keiner(self) -> "EinloesenRequest":
        if (self.vorname is None) != (self.nachname is None):
            raise ValueError("Vor- und Nachname nur zusammen")
        return self


class EinloesenResponse(BaseModel):
    success: bool


class BeitretenRequest(CodeRequest):
    # Muss true sein: der Knopf "Ja, speichert, dass ich im Team X bin"
    einwilligung: bool
    # Kennung des gezeigten Wortlauts (aus /pruefen); unbekannt oder frueher: 422
    einwilligung_kennung: str = Field(..., max_length=KENNUNG_MAX)
    # Zweite Frage "Team öffentlich am Namen zeigen" (nur bei wirksamem Schalter)
    oeffentlich: bool = False
    # Kennung ihres gezeigten Wortlauts; Pflicht mit oeffentlich true
    oeffentlich_kennung: Optional[str] = Field(
        None, max_length=KENNUNG_MAX, validate_default=True
    )

    @field_validator("einwilligung_kennung")
    @classmethod
    def _einwilligung_kennung(cls, wert: str) -> str:
        if wert not in EINWILLIGUNG_GELTEND:
            raise ValueError("Unbekannter Wortlaut")
        return wert

    @field_validator("oeffentlich_kennung")
    @classmethod
    def _oeffentlich_kennung(
        cls, wert: Optional[str], info: ValidationInfo
    ) -> Optional[str]:
        if info.data.get("oeffentlich") and wert not in OEFFENTLICH_WORTLAUTE:
            raise ValueError("Unbekannter Wortlaut")
        return wert


class TeamKurzResponse(BaseModel):
    name: str
    motiv: Optional[str]
    saison: str


class BeitretenResponse(BaseModel):
    team: TeamKurzResponse
    nummer: int
    # False: schon dabei, nichts gezaehlt
    neu: bool


def _mit_team(e: Einladung, mitglieder: dict) -> EinladungResponse:
    team = e.team
    return EinladungResponse.aus(
        e, team, mitglieder.get((team.name, team.saison), 0) if team else 0
    )


def _antwort(service: EinladungService, e: Einladung) -> EinladungResponse:
    if not service.teams_wirksam or e.team is None:
        return EinladungResponse.aus(e)
    return _mit_team(e, service.teams.mitglieder([e.team]))


@router.get("", response_model=EinladungListeResponse)
async def einladungen_liste(
    admin_user: str = Depends(require_admin),
    service: EinladungService = Depends(get_einladung_service),
):
    """Alle Einladungen, die neuesten zuerst, mit Zaehler, Zustand und Team (nur Zahl)."""
    einladungen = service.alle()
    if not service.teams_wirksam:
        return EinladungListeResponse(
            einloesen_eingerichtet=service.einloesen_eingerichtet,
            einladungen=[EinladungResponse.aus(e) for e in einladungen],
        )
    teams = service.teams
    mitglieder = teams.mitglieder(e.team for e in einladungen if e.team)
    return EinladungListeResponse(
        einloesen_eingerichtet=service.einloesen_eingerichtet,
        einladungen=[_mit_team(e, mitglieder) for e in einladungen],
        teams_aktiv=True,
        aktuelle_saison=teams.aktuelle_saison(),
        saison_vorschlag=teams.saison_vorschlag(),
        motive=[MotivResponse(schluessel=k, name=v) for k, v in MOTIVE.items()],
        teamname_hinweis=TEAMNAME_HINWEIS,
    )


@router.post("", status_code=201, response_model=EinladungResponse)
async def einladung_anlegen(
    request: EinladungAnlegenRequest,
    admin_user: str = Depends(require_admin),
    service: EinladungService = Depends(get_einladung_service),
):
    team = None
    if service.teams_wirksam:
        team = request.team(service.teams.saison_vorschlag())
    einladung = service.anlegen(
        request.notiz, request.erlaubte_einloesungen, request.gueltig_bis, team=team
    )
    return _antwort(service, einladung)


@router.patch("/{einladung_id}", response_model=EinladungResponse)
async def einladung_schalten(
    einladung_id: uuid.UUID,
    request: EinladungAendernRequest,
    admin_user: str = Depends(require_admin),
    service: EinladungService = Depends(get_einladung_service),
):
    """Abschalten oder wieder einschalten und/oder das Team setzen; der Zaehler bleibt."""
    team = UNVERAENDERT
    if "team_name" in request.model_fields_set and service.teams_wirksam:
        team = request.team(service.teams.saison_vorschlag())
    einladung = service.aendern(
        einladung_id, abgeschaltet=request.abgeschaltet, team=team
    )
    if einladung is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return _antwort(service, einladung)


@router.post("/pruefen", response_model=PruefenResponse)
async def einladung_pruefen(
    request: CodeRequest,
    http_request: Request,
    service: EinladungService = Depends(get_einladung_service),
    x_user: Optional[str] = Header(None, alias="X-User"),
):
    """
    Ob sich mit dem Code ein Konto anlegen laesst. Warum nicht (abgelaufen,
    aufgebraucht, unbekannt), erfaehrt niemand: Das hilft nur beim Durchprobieren.
    Bei wirksamem Schalter teams und einem Team an einer einloesbaren Einladung dazu
    das Team mit Mitgliederzahl, naechster Nummer und den Einwilligungstexten.
    """
    if await einladung_pruefen_rate_limiter.is_rate_limited(
        derive_client_key(http_request)
    ):
        raise HTTPException(status_code=429, detail="Too many requests.")
    einloesbar = service.ist_einloesbar(request.code)
    if not service.teams_wirksam:
        return PruefenResponse(einloesbar=einloesbar)
    konto = x_user if angemeldet(x_user) else None
    if not einloesbar and konto is None:
        return PruefenResponse(einloesbar=False)
    # Nicht mehr einloesbar: das Team nur fuer ein Mitglied ("schon dabei"), sonst nichts.
    info = service.team_info(request.code, konto)
    if info is None:
        return PruefenResponse(einloesbar=einloesbar)
    oeffentlich = service.teams.oeffentlich_wirksam()
    team = info.team
    return PruefenResponse(
        einloesbar=einloesbar,
        team=TeamPruefenResponse(
            name=team.name,
            motiv=team.motiv,
            saison=team.saison,
            art=team.art,
            mitglieder=info.mitglieder,
            naechste_nummer=info.naechste_nummer,
            eigene_nummer=info.eigene_nummer,
            einwilligung_kennung=EINWILLIGUNG_KENNUNG,
            einwilligung_text=EINWILLIGUNG_WORTLAUTE[EINWILLIGUNG_KENNUNG].format(
                team=team.name
            ),
            knopf_ja=KNOPF_JA.format(team=team.name),
            knopf_nein=KNOPF_NEIN,
            oeffentlich_kennung=OEFFENTLICH_KENNUNG if oeffentlich else None,
            oeffentlich_text=(
                OEFFENTLICH_WORTLAUTE[OEFFENTLICH_KENNUNG] if oeffentlich else None
            ),
        ),
    )


@router.post("/einloesen", status_code=202, response_model=EinloesenResponse)
async def einladung_einloesen(
    request: EinloesenRequest,
    http_request: Request,
    service: EinladungService = Depends(get_einladung_service),
):
    """
    Legt das Konto mit Vor- und Nachname an; Keycloak schickt die Mail "Passwort
    festlegen". Gibt es zur
    Adresse schon ein Konto, ist die Antwort dieselbe: Ob eine Adresse ein Konto hat,
    soll hier niemand herausfinden. X-User wird nicht gelesen. Mit
    ``team_einwilligung`` entsteht die Mitgliedschaft im Team der Einladung, wenn
    das Konto neu angelegt wird; die Antwort sagt darueber nichts.
    """
    if await einladung_rate_limiter.is_rate_limited(derive_client_key(http_request)):
        raise HTTPException(status_code=429, detail="Too many requests.")
    try:
        # Im Thread: Keycloak antwortet ueber das Netz, bis zu zehn Sekunden je Schritt.
        await asyncio.to_thread(
            service.einloesen,
            request.code,
            request.email,
            vorname=request.vorname,
            nachname=request.nachname,
            team_einwilligung=request.team_einwilligung,
            team_oeffentlich=request.team_oeffentlich and request.team_einwilligung,
            team_einwilligung_kennung=request.team_einwilligung_kennung,
            team_oeffentlich_kennung=request.team_oeffentlich_kennung,
        )
    except EinladungUngueltig:
        raise HTTPException(status_code=410, detail="Invitation not valid")
    except EinloesenNichtEingerichtet:
        raise HTTPException(status_code=503, detail="Registration not configured")
    except KontoAnlegenFehlgeschlagen:
        raise HTTPException(status_code=502, detail="Account could not be created")
    return EinloesenResponse(success=True)


@router.post("/beitreten", response_model=BeitretenResponse)
async def einladung_beitreten(
    request: BeitretenRequest,
    user_id: str = Depends(require_user),
    service: EinladungService = Depends(get_einladung_service),
):
    """
    Angemeldet dem Team einer Einladung beitreten, nach dem Knopf "Ja, speichert,
    dass ich im Team X bin" (``einwilligung`` muss true sein). Neu: zaehlt gegen die
    erlaubten Einloesungen. Schon dabei: ``neu`` false mit der vorhandenen Nummer,
    nichts wird gezaehlt. Ein neues Konto entsteht hier nie. Das Rate-Limit zaehlt je
    Person, nicht je Anschluss (Saal-WLAN).
    """
    if await team_beitreten_rate_limiter.is_rate_limited(f"user:{user_id}"):
        raise HTTPException(status_code=429, detail="Too many requests.")
    if not request.einwilligung:
        raise HTTPException(status_code=422, detail="Consent required")
    try:
        _, mitgliedschaft, neu = await asyncio.to_thread(
            service.beitreten,
            request.code,
            user_id,
            einwilligung_kennung=request.einwilligung_kennung,
        )
    except TeamsAus:
        raise HTTPException(status_code=404, detail="Not found")
    except EinladungUngueltig:
        raise HTTPException(status_code=410, detail="Invitation not valid")
    except EinladungOhneTeam:
        raise HTTPException(status_code=409, detail="Invitation has no team")
    if request.oeffentlich and service.teams.oeffentlich_wirksam():
        await asyncio.to_thread(
            service.teams.oeffentlich_antworten,
            user_id,
            True,
            request.oeffentlich_kennung,
        )
    return BeitretenResponse(
        team=TeamKurzResponse(
            name=mitgliedschaft.team_name,
            motiv=mitgliedschaft.team_motiv,
            saison=mitgliedschaft.saison,
        ),
        nummer=mitgliedschaft.nummer,
        neu=neu,
    )
