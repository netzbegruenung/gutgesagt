"""
GET /api/v1/search/garten: die Gartenansicht (#783), je Thema die Zahl der Antworten
und der Aussagen ohne Antwort (services/gartenansicht_service.py). Unter /search, damit
sie wie die Suche auch fuer Besucher offen ist (BFF EndpointPolicy). Nur Zahlen, keine
Texte. Ohne den Schalter ``gartenansicht`` 404, ohne eine Abfrage.
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


def _schalter_an(settings: Settings = Depends(get_settings)) -> None:
    """Vor allen anderen Abhaengigkeiten: ohne Schalter keine Abfrage."""
    if not schalter_wirksam(SCHALTER, settings):
        raise HTTPException(status_code=404, detail="Not found")


def get_gartenansicht_service(
    statement_service: StatementService = Depends(get_statement_service),
    unbeantwortete: UnbeantworteteAussagenService = Depends(
        get_unbeantwortete_aussagen_service
    ),
) -> GartenansichtService:
    return GartenansichtService(
        get_aussage_themen_repository(), statement_service, unbeantwortete
    )


@router.get(
    "/garten", response_model=GartenResponse, dependencies=[Depends(_schalter_an)]
)
async def garten(
    service: GartenansichtService = Depends(get_gartenansicht_service),
) -> GartenResponse:
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
