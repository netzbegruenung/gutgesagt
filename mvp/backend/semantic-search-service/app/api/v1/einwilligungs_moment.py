"""
Einwilligungen im Moment des Gewinns (#788, Schalter ``einwilligung_im_gewinn``):
was die App braucht, um eine Einwilligungsfrage erst dann zu stellen, wenn sie etwas
bringt, und hoechstens eine je Besuch (GLOSSARY.md "Einwilligungs-Budget").

Die Regel selbst steht im Frontend (shared/einwilligungs-budget); der Server liefert
nur Fakten zur angemeldeten Person, die er ohnehin hat, und speichert nichts dazu.
Ohne wirksamen Schalter 404: Dann fragt die App wie bisher.
"""

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.config import Settings
from core.logging import get_logger, log_pseudonym
from dependencies import get_settings, require_user
from repositories.einwilligungs_moment_repository import (
    get_einwilligungs_moment_repository,
)
from services.schalter_service import schalter_wirksam

logger = get_logger(__name__)

router = APIRouter()

SCHALTER = "einwilligung_im_gewinn"


class EinwilligungsMomentResponse(BaseModel):
    abgestimmt: bool
    beantwortet: int
    konto_seit: Optional[datetime] = None


def _angeboten(settings: Settings = Depends(get_settings)) -> None:
    """Ohne wirksamen Schalter 404, vor jeder Datenbankabfrage."""
    if not schalter_wirksam(SCHALTER, settings):
        raise HTTPException(status_code=404, detail="Not found")


@router.get(
    "/users/me/einwilligungs-moment", response_model=EinwilligungsMomentResponse
)
async def einwilligungs_moment(
    current_user: str = Depends(require_user),
    _schalter: None = Depends(_angeboten),
) -> EinwilligungsMomentResponse:
    """
    Ob die Person schon abgestimmt hat, wie viele Einwilligungsfragen sie beantwortet
    hat und seit wann es ihr Konto gibt. Die Person kommt aus ``X-User`` (#284).
    """
    try:
        moment = await asyncio.to_thread(
            get_einwilligungs_moment_repository().lesen, current_user
        )
    except Exception as e:
        logger.error(
            f"Einwilligungs-Moment fuer {log_pseudonym(current_user)} nicht gelesen: "
            f"{type(e).__name__}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Internal server error")
    return EinwilligungsMomentResponse(
        abgestimmt=moment.abgestimmt,
        beantwortet=moment.beantwortet,
        konto_seit=moment.konto_seit,
    )
