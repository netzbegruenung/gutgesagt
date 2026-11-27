"""
Herkunft pruefen (#759), nur fuer Admins: die auffaelligen Links und ein Lauf auf
Knopfdruck. Logik: services/herkunft_pruefen.py, Abruf: utils/sicherer_abruf.py.

Ohne wirksamen Schalter ``herkunft_pruefen`` sagt die Liste ``aktiv: false`` und
nichts sonst (die Uebersicht zeigt dann keine Karte), und ein Lauf laesst sich nicht
anstossen (404).
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from core.config import Settings
from core.fehler import INTERNER_FEHLER
from core.logging import get_logger, log_pseudonym
from dependencies import get_settings, require_admin
from services.herkunft_pruefen import (
    SCHALTER,
    HerkunftPruefenService,
    get_herkunft_pruefen_service,
)
from services.schalter_service import notaus_wirksam

logger = get_logger(__name__)

router = APIRouter()


class AuffaelligeHerkunft(BaseModel):
    herkunft_id: uuid.UUID
    adresse: str
    ergebnis: str
    http_status: Optional[int]
    ziel: Optional[str]
    geprueft_am: datetime
    auffaellig_seit: Optional[datetime]


class HerkunftPruefenResponse(BaseModel):
    aktiv: bool
    laeuft: bool = False
    geprueft: int = 0
    letzter_lauf: Optional[datetime] = None
    # Alle auffaelligen; die Liste zeigt hoechstens AUFFAELLIGE_HOECHSTENS davon
    auffaellig_gesamt: int = 0
    auffaellig: List[AuffaelligeHerkunft] = []


def _dienst() -> Optional[HerkunftPruefenService]:
    return get_herkunft_pruefen_service()


@router.get("", response_model=HerkunftPruefenResponse)
async def herkunft_pruefen_stand(
    admin_user: str = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    dienst: Optional[HerkunftPruefenService] = Depends(_dienst),
) -> HerkunftPruefenResponse:
    if not notaus_wirksam(SCHALTER, settings) or dienst is None:
        return HerkunftPruefenResponse(aktiv=False)
    try:
        stand = await dienst.stand()
    except Exception as e:
        logger.error(f"Herkunft pruefen: Stand nicht gelesen: {type(e).__name__}")
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    return HerkunftPruefenResponse(
        aktiv=True,
        laeuft=dienst.laeuft,
        geprueft=stand.geprueft,
        letzter_lauf=stand.letzter_lauf,
        auffaellig_gesamt=stand.auffaellig_gesamt,
        auffaellig=[AuffaelligeHerkunft(**vars(z)) for z in stand.auffaellig],
    )


@router.post("/lauf", status_code=202)
async def herkunft_pruefen_anstossen(
    admin_user: str = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    dienst: Optional[HerkunftPruefenService] = Depends(_dienst),
) -> Response:
    """Einen Lauf sofort starten; 409, wenn schon einer laeuft."""
    if not notaus_wirksam(SCHALTER, settings) or dienst is None:
        raise HTTPException(status_code=404, detail="Not found")
    if not dienst.anstossen():
        raise HTTPException(status_code=409, detail="Die Prüfung läuft schon.")
    logger.info(f"Herkunft pruefen: Lauf angestossen von {log_pseudonym(admin_user)}")
    return Response(status_code=202)
