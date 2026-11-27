"""
GET /api/v1/search/garten: die Gartenansicht (#783), je Thema die Zahl der Antworten
und der Aussagen ohne Antwort (services/gartenansicht_service.py). Unter /search, damit
sie wie die Suche auch fuer Besucher offen ist (BFF EndpointPolicy). Nur Zahlen, keine
Texte. Ohne den Schalter ``gartenansicht`` 200 mit ``{"beete": [], "aktiv": false}``,
ohne eine Abfrage; kein 404, weil die Seite selbst nachlaedt (Gateway-fail2ban,
docs/ARCHITECTURE.md).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.config import Settings
from core.fehler import INTERNER_FEHLER
from core.logging import get_logger
from dependencies import (
    get_settings,
    get_statement_service,
    get_unbeantwortete_aussagen_service,
)
from domain.themen import NACH_SCHLUESSEL
from repositories.aussage_themen_repository import get_aussage_themen_repository
from services.content.statement_service import StatementService
from services.gartenansicht_service import SCHALTER, GartenansichtService
from services.schalter_service import schalter_wirksam
from services.unbeantwortete_aussagen_service import UnbeantworteteAussagenService

logger = get_logger(__name__)

router = APIRouter()


class BeetDto(BaseModel):
    schluessel: str
    name: str
    motiv: Optional[str] = None
    antworten: int
    ohne_antwort: int


class GartenResponse(BaseModel):
    beete: List[BeetDto]
    # false: Schalter gartenansicht aus
    aktiv: bool = True


def get_gartenansicht_service(
    statement_service: StatementService = Depends(get_statement_service),
    unbeantwortete: UnbeantworteteAussagenService = Depends(
        get_unbeantwortete_aussagen_service
    ),
) -> GartenansichtService:
    return GartenansichtService(
        get_aussage_themen_repository(), statement_service, unbeantwortete
    )


def _schalter_an(settings: Settings = Depends(get_settings)) -> bool:
    # Basisfunktion seit dem Schalter-Umbau (27.11.): immer an
    return True


@router.get("/garten", response_model=GartenResponse)
async def garten(
    an: bool = Depends(_schalter_an),
    service: GartenansichtService = Depends(get_gartenansicht_service),
) -> GartenResponse:
    # Der Dienst ist gebaut, fragt aber erst mit beete() etwas ab.
    if not an:
        return GartenResponse(beete=[], aktiv=False)
    try:
        beete = await service.beete()
    except Exception as e:
        logger.error(f"Error in /garten: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    return GartenResponse(
        beete=[
            BeetDto(
                schluessel=b.schluessel,
                name=NACH_SCHLUESSEL[b.schluessel].name,
                motiv=NACH_SCHLUESSEL[b.schluessel].motiv,
                antworten=b.antworten,
                ohne_antwort=b.ohne_antwort,
            )
            for b in beete
        ]
    )
