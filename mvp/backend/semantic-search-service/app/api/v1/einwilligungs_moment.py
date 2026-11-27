"""
Einwilligungen im Moment des Gewinns (#788, Schalter ``einwilligung_im_gewinn``):
was die App braucht, um eine Einwilligungsfrage erst dann zu stellen, wenn sie etwas
bringt, und hoechstens eine je Besuch (GLOSSARY.md "Einwilligungs-Budget").

Die Regel selbst steht im Frontend (shared/einwilligungs-budget); der Server liefert
nur Fakten zur angemeldeten Person, die er ohnehin hat, und speichert nichts dazu.
Ohne wirksamen Schalter 200 mit ``aktiv: false`` und ohne Datenbankabfrage: Dann fragt
die App wie bisher. Kein 404, weil die Seite automatisch fragt und das Gateway eine IP
nach 50 Antworten 404 sperrt (docs/ARCHITECTURE.md); ``aktiv: false`` ist dasselbe
sichere "Schalter aus" wie zuvor das 404 (#812).
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
from services.spielgefuehl_service import buehne_aktiv

logger = get_logger(__name__)

router = APIRouter()

SCHALTER = "einwilligung_im_gewinn"


class EinwilligungsMomentResponse(BaseModel):
    # false: Schalter aus, die anderen Felder sind dann ohne Bedeutung
    aktiv: bool = True
    abgestimmt: bool = False
    beantwortet: int = 0
    konto_seit: Optional[datetime] = None


def _angeboten(settings: Settings = Depends(get_settings)) -> bool:
    """
    Basisfunktion seit dem Schalter-Umbau (27.11.): immer angeboten. Die Grenzen
    (hoechstens eine neue Frage je Besuch, vier im ersten Monat) setzt das Frontend
    (shared/einwilligungs-budget), unabhaengig von einem Schalter.
    """
    return True


@router.get(
    "/users/me/einwilligungs-moment", response_model=EinwilligungsMomentResponse
)
async def einwilligungs_moment(
    current_user: str = Depends(require_user),
    angeboten: bool = Depends(_angeboten),
    settings: Settings = Depends(get_settings),
) -> EinwilligungsMomentResponse:
    """
    Ob die Person schon abgestimmt hat, wie viele Einwilligungsfragen sie beantwortet
    hat und seit wann es ihr Konto gibt. Die Person kommt aus ``X-User`` (#284).
    """
    if not angeboten:
        return EinwilligungsMomentResponse(aktiv=False)
    try:
        moment = await asyncio.to_thread(
            get_einwilligungs_moment_repository().lesen,
            current_user,
            buehne_aktiv(settings),
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
