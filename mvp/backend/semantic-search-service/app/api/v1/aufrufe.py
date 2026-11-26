"""
Seitenaufrufe und Besucher je Tag (#761). Logik: services/aufrufe_service.py.

- Gezaehlt wird ohne eigene Route: middleware/aufrufe_zaehlen.py zaehlt aus Abrufen,
  die die App ohnehin macht ohne eigene Anfrage aus dem Browser (§ 25 TDDDG).
- ``GET ""``: nur fuer Admins, die Tageszahlen fuer Admin -> Kennzahlen; ohne Schalter
  ``aktiv: false`` und nichts sonst.
"""

import asyncio
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.config import Settings
from core.fehler import INTERNER_FEHLER
from core.logging import get_logger
from dependencies import get_settings, require_admin
from repositories.aufrufe_repository import AufrufeRepository, get_aufrufe_repository
from services import aufrufe_service
from services.schalter_service import schalter_wirksam

logger = get_logger(__name__)

router = APIRouter()

TAGE_STANDARD = 28


class AufrufTagResponse(BaseModel):
    tag: date
    aufrufe: int
    besucher: int


class AufrufeResponse(BaseModel):
    aktiv: bool
    # Der laufende Tag bisher (UTC)
    heute: Optional[AufrufTagResponse] = None
    # Die abgeschlossenen Tage, neueste zuerst; ein Tag ohne Aufruf fehlt
    tage: List[AufrufTagResponse] = []


def _repository() -> AufrufeRepository:
    return get_aufrufe_repository()


@router.get("", response_model=AufrufeResponse)
async def aufrufe(
    tage: int = Query(TAGE_STANDARD, ge=1, le=366),
    admin_user: str = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    repository: AufrufeRepository = Depends(_repository),
) -> AufrufeResponse:
    if not schalter_wirksam(aufrufe_service.SCHALTER, settings):
        return AufrufeResponse(aktiv=False)
    heute = aufrufe_service.heute_utc()
    try:
        stand_heute, vergangen = await asyncio.gather(
            asyncio.to_thread(repository.heute, heute),
            asyncio.to_thread(repository.tage, heute - timedelta(days=tage)),
        )
    except Exception as e:
        logger.error(f"Aufrufe nicht gelesen: {type(e).__name__}")
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    return AufrufeResponse(
        aktiv=True,
        heute=AufrufTagResponse(**vars(stand_heute)),
        tage=[AufrufTagResponse(**vars(t)) for t in vergangen],
    )
