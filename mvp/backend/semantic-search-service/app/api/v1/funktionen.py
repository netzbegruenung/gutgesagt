"""
Welche Funktionen hinter einem Schalter gerade an sind (#756), ohne Anmeldung und ohne
Personenbezug. Nur fuer Schalter mit ``oeffentlich`` (services/schalter_service.py):
Funktionen, die allein im Browser laufen (Teilen als Bild), haben keinen Endpunkt, der
mit 404 antworten koennte; das Frontend fragt hier und zeigt sie nur, wenn sie an sind.
Die Admin-Seite der Schalter liegt unter /api/v1/moderation/schalter.
"""

from typing import Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.config import Settings
from dependencies import get_settings
from services.schalter_service import oeffentliche_schalter, schalter_wirksam

router = APIRouter()


class FunktionenResponse(BaseModel):
    funktionen: Dict[str, bool]


@router.get("", response_model=FunktionenResponse)
def funktionen(settings: Settings = Depends(get_settings)) -> FunktionenResponse:
    return FunktionenResponse(
        funktionen={
            name: schalter_wirksam(name, settings) for name in oeffentliche_schalter()
        }
    )
