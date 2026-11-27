"""
Welche Funktionen hinter einem Schalter gerade an sind (#756), ohne Anmeldung und ohne
Personenbezug. Nur fuer Schalter mit ``oeffentlich`` (services/schalter_service.py):
Funktionen, die allein im Browser laufen (Teilen als Bild), haben keinen Endpunkt, der
mit 404 antworten koennte; das Frontend fragt hier und zeigt sie nur, wenn sie an sind.
Die Admin-Seite der Schalter liegt unter /api/v1/moderation/schalter.

``GET /{name}/seit``: seit welchem Tag (deutsche Zeit) ein Schalter wirkt, fuer Saetze
der Datenschutzerklaerung wie "Seit dem ... fliesst auch ein, ..." (muster_stimmen).
Nur fuer Schalter in ``SEIT_OEFFENTLICH``; der Tag ist der, an dem ein Admin ihn
zuletzt eingeschaltet hat (Tabelle ``schalter``, geaendert_am). Wirkt er nicht, 200
mit ``seit: null`` ohne Datenbankabfrage.
"""

import asyncio
from datetime import date, datetime, timezone
from typing import Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.config import Settings
from core.logging import get_logger
from dependencies import get_settings
from services.schalter_service import oeffentliche_schalter, schalter_wirksam

logger = get_logger(__name__)

# Schalter, deren Einschalttag ohne Anmeldung abgefragt werden darf: nur ein Datum, das
# die Datenschutzerklaerung ohnehin nennt.
SEIT_OEFFENTLICH = frozenset({"muster_stimmen"})

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


class SeitResponse(BaseModel):
    # null: Der Schalter wirkt nicht (oder der Tag ist nicht zu lesen)
    seit: Optional[date] = None


def _tag(zeitpunkt: datetime) -> date:
    """Tagesdatum in deutscher Zeit."""
    if zeitpunkt.tzinfo is None:
        zeitpunkt = zeitpunkt.replace(tzinfo=timezone.utc)
    try:
        return zeitpunkt.astimezone(ZoneInfo("Europe/Berlin")).date()
    except ZoneInfoNotFoundError:
        return zeitpunkt.astimezone(timezone.utc).date()


@router.get("/{name}/seit", response_model=SeitResponse)
async def seit(name: str, settings: Settings = Depends(get_settings)) -> SeitResponse:
    if name not in SEIT_OEFFENTLICH:
        raise HTTPException(status_code=404, detail="Not found")
    if not schalter_wirksam(name, settings):
        return SeitResponse()
    from repositories.schalter_repository import get_schalter_repository

    try:
        zeitpunkt = await asyncio.to_thread(
            get_schalter_repository().eingeschaltet_am, name
        )
    except Exception as e:
        # Ohne Tag schreibt die Datenschutzerklaerung "Seit dem Einschalten"
        logger.error(
            f"Einschalttag von {name} nicht gelesen: {type(e).__name__}", exc_info=True
        )
        return SeitResponse()
    return SeitResponse(seit=_tag(zeitpunkt) if zeitpunkt is not None else None)
