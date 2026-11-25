"""
Meine Teams (services/team_service.py): die eigenen Mitgliedschaften lesen, ein Team
verlassen und die Einwilligung "Team öffentlich am Namen zeigen" geben oder
zuruecknehmen. Nur fuer die angemeldete Person selbst; fremde Mitgliedschaften gibt
es ueber keine Schnittstelle, auch nicht fuer Admins.
"""

import asyncio
import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from core.logging import get_logger
from dependencies import require_user
from domain.themen import NACH_SCHLUESSEL as THEMEN_NACH_SCHLUESSEL
from domain.teams import (
    MOTIVE,
    OEFFENTLICH_KENNUNG,
    OEFFENTLICH_WORTLAUTE,
    UnbekannterWortlaut,
)
from services.team_fortschritt_service import (
    TeamFortschrittService,
    TeamStand,
    get_team_fortschritt_service,
)
from services.team_service import (
    OeffentlichAus,
    TeamService,
    get_team_service,
)

logger = get_logger(__name__)

router = APIRouter()


class TeamWirkungResponse(BaseModel):
    """
    Team-Fortschritt (#784) der letzten abgeschlossenen Woche, nie der laufenden. Nur
    gerundete Texte ("weniger als 10", "rund 45"), nie die genaue Zahl; unter 5
    Mitgliedern mit Einwilligung nur ``waechst_noch``.
    """

    # Montag der abgeschlossenen Woche
    woche: date
    waechst_noch: bool
    gesamt: Optional[str] = None
    beitraege: Optional[str] = None
    bewertungen: Optional[str] = None
    gepostet: Optional[str] = None


class TeamQuestResponse(BaseModel):
    """
    Team-Quest (#792): das Ziel der laufenden Woche ohne Stand (nie live) und ob das
    Ziel der Vorwoche geschafft ist. Ein verfehltes Ziel kommt nicht vor.
    """

    # Laufende Woche; null, wenn es (noch) keine Quest gibt
    woche: Optional[date] = None
    ziel: Optional[int] = None
    thema: Optional[str] = None
    thema_name: Optional[str] = None
    thema_motiv: Optional[str] = None
    vorige_geschafft: bool = False
    vorige_thema_name: Optional[str] = None


class MeinTeamResponse(BaseModel):
    # Zum Verlassen: DELETE /api/v1/teams/meine/{id}
    id: uuid.UUID
    team_name: str
    motiv: Optional[str]
    # Name des Motivs fuer Alt-Text und Beschriftung
    motiv_name: Optional[str]
    saison: str
    nummer: int
    eingetreten_am: date
    # Ob das Team zur aktuellen Saison gehoert (sonst ein Abzeichen vergangener Saisons)
    aktuelle_saison: bool
    # Nur mit Schalter team_fortschritt und deckender Einwilligung, sonst null
    wirkung: Optional[TeamWirkungResponse] = None
    # Nur mit Schalter team_quests und ab der Schwelle, sonst null
    quest: Optional[TeamQuestResponse] = None


class MeineTeamsResponse(BaseModel):
    # Schalter teams: false heisst, es gehen keine neuen Beitritte, die vorhandenen
    # Mitgliedschaften lassen sich aber weiter ansehen und verlassen.
    teams_aktiv: bool = True
    aktuelle_saison: str
    # Schalter teams_oeffentlich: nur wenn true den Umschalter zeigen
    oeffentlich_verfuegbar: bool
    # Juengste Antwort auf "Team öffentlich am Namen zeigen"; null: nie gefragt
    oeffentlich_zeigen: Optional[bool]
    oeffentlich_kennung: Optional[str]
    oeffentlich_text: Optional[str]
    teams: List[MeinTeamResponse]


class OeffentlichRequest(BaseModel):
    zeigen: bool
    # Kennung des Wortlauts, der gezeigt wurde
    wortlaut: str = Field(..., max_length=64)


def _service() -> TeamService:
    return get_team_service()


def _fortschritt() -> TeamFortschrittService:
    return get_team_fortschritt_service()


def _thema_name(schluessel: Optional[str]) -> Optional[str]:
    thema = THEMEN_NACH_SCHLUESSEL.get(schluessel or "")
    return thema.name if thema else None


def _quest_response(stand: Optional[TeamStand]) -> Optional[TeamQuestResponse]:
    if stand is None or stand.quest is None:
        return None
    laufende = stand.quest.laufende
    thema = THEMEN_NACH_SCHLUESSEL.get(laufende.thema or "") if laufende else None
    return TeamQuestResponse(
        woche=laufende.woche if laufende else None,
        ziel=laufende.ziel if laufende else None,
        thema=thema.schluessel if thema else None,
        thema_name=thema.name if thema else None,
        thema_motiv=thema.motiv if thema else None,
        vorige_geschafft=stand.quest.vorige_geschafft,
        vorige_thema_name=_thema_name(stand.quest.vorige_thema),
    )


async def _staende(fortschritt: TeamFortschrittService, user_id: str):
    """Fortschritt und Quests; scheitert das, fehlen sie, die Teams bleiben."""
    try:
        return await fortschritt.staende(user_id)
    except Exception as e:
        logger.error(f"Team progress not loaded: {type(e).__name__}")
        return {}


@router.get("/meine", response_model=MeineTeamsResponse)
async def meine_teams(
    user_id: str = Depends(require_user),
    service: TeamService = Depends(_service),
    fortschritt: TeamFortschrittService = Depends(_fortschritt),
):
    """
    Die eigenen Teams aller Saisons, neueste zuerst. Bei ausgeschaltetem Schalter teams
    nur, wenn es eigene gibt (zum Ansehen und Verlassen, ohne Umschalter), sonst 404.
    Je Team mit Schalter team_fortschritt die Wirkung der letzten abgeschlossenen
    Woche und mit team_quests die Quest; nur fuer die eigenen Teams.
    """
    teams = await asyncio.to_thread(service.meine, user_id)
    aktiv = service.wirksam()
    if not aktiv and not teams:
        raise HTTPException(status_code=404, detail="Not found")
    saison = service.aktuelle_saison()
    verfuegbar = aktiv and service.oeffentlich_wirksam()
    antwort = (
        await asyncio.to_thread(service.oeffentlich_stand, user_id)
        if verfuegbar
        else None
    )
    staende = await _staende(fortschritt, user_id) if teams else {}
    return MeineTeamsResponse(
        teams_aktiv=aktiv,
        aktuelle_saison=saison,
        oeffentlich_verfuegbar=verfuegbar,
        oeffentlich_zeigen=antwort.zeigen if antwort else None,
        oeffentlich_kennung=OEFFENTLICH_KENNUNG if verfuegbar else None,
        oeffentlich_text=(
            OEFFENTLICH_WORTLAUTE[OEFFENTLICH_KENNUNG] if verfuegbar else None
        ),
        teams=[
            MeinTeamResponse(
                id=t.id,
                team_name=t.team_name,
                motiv=t.team_motiv,
                motiv_name=MOTIVE.get(t.team_motiv) if t.team_motiv else None,
                saison=t.saison,
                nummer=t.nummer,
                eingetreten_am=t.eingetreten_am,
                aktuelle_saison=t.saison == saison,
                wirkung=(
                    TeamWirkungResponse(
                        **vars(staende[(t.team_name, t.saison)].wirkung)
                    )
                    if (t.team_name, t.saison) in staende
                    else None
                ),
                quest=_quest_response(staende.get((t.team_name, t.saison))),
            )
            for t in teams
        ],
    )


@router.delete("/meine/{mitgliedschaft_id}", status_code=204)
async def team_verlassen(
    mitgliedschaft_id: uuid.UUID,
    user_id: str = Depends(require_user),
    service: TeamService = Depends(_service),
):
    """
    "Team verlassen": loescht die eigene Mitgliedschaft sofort (Widerruf der
    Einwilligung). Geht auch bei ausgeschaltetem Schalter. 404: keine eigene.
    """
    if not await asyncio.to_thread(service.verlassen, user_id, mitgliedschaft_id):
        raise HTTPException(status_code=404, detail="Not found")
    return Response(status_code=204)


@router.put("/oeffentlich", status_code=204)
async def team_oeffentlich(
    anfrage: OeffentlichRequest,
    user_id: str = Depends(require_user),
    service: TeamService = Depends(_service),
):
    """
    Einwilligung "Team öffentlich am Namen zeigen" geben (zeigen true) oder
    zuruecknehmen (false). Ja nur bei wirksamem Schalter teams_oeffentlich (sonst
    409), Zuruecknehmen geht immer. Unbekannter Wortlaut: 422.
    """
    try:
        await asyncio.to_thread(
            service.oeffentlich_antworten, user_id, anfrage.zeigen, anfrage.wortlaut
        )
    except UnbekannterWortlaut:
        raise HTTPException(status_code=422, detail="Unknown wording")
    except OeffentlichAus:
        raise HTTPException(status_code=409, detail="Not active")
    return Response(status_code=204)
