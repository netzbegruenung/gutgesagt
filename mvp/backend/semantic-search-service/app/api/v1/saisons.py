"""
Saisons mit Gemeinschaftsziel (#782, services/saison_service.py).

- ``router`` unter /api/v1/saisons, ohne Anmeldung: der Balken der laufenden Saison
  (``GET /aktuell``). 404, solange der Schalter ``saison_ziel`` nicht wirkt; ohne
  laufende Saison oder unter der Schwelle ``{"balken": null}``. Nur Summen.
- ``admin_router`` unter /api/v1/moderation/saisons, nur Admins: Saisons mit Stand
  lesen, anlegen, aendern und vor ihrem Beginn loeschen. Das geht auch bei Schalter
  aus, damit eine Saison vor dem Einschalten bereitsteht; wirken tut sie erst mit ihm.
"""

import asyncio
import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from core.fehler import INTERNER_FEHLER
from core.logging import get_logger, log_pseudonym
from dependencies import require_admin
from domain.saisons import (
    ZIEL_MAX,
    SaisonGesperrt,
    SaisonUeberschneidung,
    SaisonUngueltig,
)
from domain.teams import SAISON_MAX
from repositories.saison_repository import SaisonNichtGefunden
from services.saison_service import AdminStand, SaisonService, get_saison_service

logger = get_logger(__name__)

router = APIRouter()
admin_router = APIRouter()


class BalkenResponse(BaseModel):
    name: str
    # Gemeinschaftsziel in Widerspruchs-Wochen
    ziel: int
    # Widerspruchs-Wochen aus abgeschlossenen Wochen der Saison
    erreicht: int


class AktuellResponse(BaseModel):
    # null: keine laufende Saison oder Schwelle noch nicht erreicht
    balken: Optional[BalkenResponse]


class SaisonRequest(BaseModel):
    name: str = Field(..., max_length=200)
    beginn: date
    ende: date
    ziel: int = Field(..., ge=1, le=ZIEL_MAX)


class SaisonResponse(BaseModel):
    id: uuid.UUID
    name: str
    beginn: date
    ende: date
    ziel: int
    # geplant, laufend oder vorbei
    zustand: str
    erreicht: int
    # Nur bei der laufenden Saison: verschiedene Menschen der laufenden Woche bisher
    laufende_woche: Optional[int]


class SaisonListeResponse(BaseModel):
    saisons: List[SaisonResponse]
    schalter_wirksam: bool
    # Ob der Balken fuer alle sichtbar ist (sonst nur hier)
    schwelle_erreicht: bool
    schwelle_menschen: int
    schwelle_wochen: int
    name_max: int = SAISON_MAX


def _service() -> SaisonService:
    return get_saison_service()


def _liste(stand: AdminStand) -> SaisonListeResponse:
    return SaisonListeResponse(
        saisons=[
            SaisonResponse(
                id=s.saison.id,
                name=s.saison.name,
                beginn=s.saison.beginn,
                ende=s.saison.ende,
                ziel=s.saison.ziel,
                zustand=s.zustand.value,
                erreicht=s.erreicht,
                laufende_woche=s.laufende_woche,
            )
            for s in stand.saisons
        ],
        schalter_wirksam=stand.schalter_wirksam,
        schwelle_erreicht=stand.schwelle_erreicht,
        schwelle_menschen=stand.schwelle_menschen,
        schwelle_wochen=stand.schwelle_wochen,
    )


@router.get("/aktuell", response_model=AktuellResponse)
async def aktuell(service: SaisonService = Depends(_service)) -> AktuellResponse:
    if not service.wirksam():
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    try:
        balken = await asyncio.to_thread(service.balken)
    except Exception as e:
        logger.error(f"Saisonbalken nicht gelesen: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    return AktuellResponse(
        balken=BalkenResponse(**vars(balken)) if balken is not None else None
    )


@admin_router.get("", response_model=SaisonListeResponse)
async def saisons(
    admin_user: str = Depends(require_admin),
    service: SaisonService = Depends(_service),
) -> SaisonListeResponse:
    try:
        stand = await asyncio.to_thread(service.admin_stand)
    except Exception as e:
        logger.error(f"Saisons nicht gelesen: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    return _liste(stand)


@admin_router.post("", response_model=SaisonListeResponse, status_code=201)
async def anlegen(
    anfrage: SaisonRequest,
    admin_user: str = Depends(require_admin),
    service: SaisonService = Depends(_service),
) -> SaisonListeResponse:
    try:
        await asyncio.to_thread(
            service.anlegen, anfrage.name, anfrage.beginn, anfrage.ende, anfrage.ziel
        )
        stand = await asyncio.to_thread(service.admin_stand)
    except SaisonNichtGefunden:
        raise HTTPException(status_code=404, detail="Saison nicht gefunden")
    except SaisonUngueltig as e:
        raise HTTPException(status_code=422, detail=e.antworttext)
    except (SaisonUeberschneidung, SaisonGesperrt) as e:
        raise HTTPException(status_code=409, detail=e.antworttext)
    except Exception as e:
        logger.error(f"Saison nicht gespeichert: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    logger.info(f"Saison angelegt von {log_pseudonym(admin_user)}")
    return _liste(stand)


@admin_router.put("/{saison_id}", response_model=SaisonListeResponse)
async def aendern(
    saison_id: uuid.UUID,
    anfrage: SaisonRequest,
    admin_user: str = Depends(require_admin),
    service: SaisonService = Depends(_service),
) -> SaisonListeResponse:
    try:
        await asyncio.to_thread(
            service.aendern,
            saison_id,
            anfrage.name,
            anfrage.beginn,
            anfrage.ende,
            anfrage.ziel,
        )
        stand = await asyncio.to_thread(service.admin_stand)
    except SaisonNichtGefunden:
        raise HTTPException(status_code=404, detail="Saison nicht gefunden")
    except SaisonUngueltig as e:
        raise HTTPException(status_code=422, detail=e.antworttext)
    except (SaisonUeberschneidung, SaisonGesperrt) as e:
        raise HTTPException(status_code=409, detail=e.antworttext)
    except Exception as e:
        logger.error(f"Saison nicht gespeichert: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    logger.info(f"Saison geaendert von {log_pseudonym(admin_user)}")
    return _liste(stand)


@admin_router.delete("/{saison_id}", status_code=204)
async def loeschen(
    saison_id: uuid.UUID,
    admin_user: str = Depends(require_admin),
    service: SaisonService = Depends(_service),
) -> Response:
    try:
        await asyncio.to_thread(service.loeschen, saison_id)
    except SaisonNichtGefunden:
        raise HTTPException(status_code=404, detail="Saison nicht gefunden")
    except SaisonUngueltig as e:
        raise HTTPException(status_code=422, detail=e.antworttext)
    except (SaisonUeberschneidung, SaisonGesperrt) as e:
        raise HTTPException(status_code=409, detail=e.antworttext)
    except Exception as e:
        logger.error(f"Saison nicht gespeichert: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    logger.info(f"Saison geloescht von {log_pseudonym(admin_user)}")
    return Response(status_code=204)
