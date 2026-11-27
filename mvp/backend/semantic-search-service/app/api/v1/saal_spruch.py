"""
Saal-Spruch (services/saal_spruch_service.py, Schalter ``saal_spruch``).

- ``router`` unter /api/v1/saal-spruch, ohne Anmeldung: ``GET /heute`` liefert den
  heutigen Saal-Spruch, ``{"spruch": null}`` ohne Spruch und ``{"spruch": null, "aktiv":
  false}``, solange der Schalter nicht wirkt. Nie 404: Die Startseite fragt bei jedem
  Aufruf, und ein 404 je Aufruf sperrte am Gateway ein ganzes Saal-WLAN
  (docs/ARCHITECTURE.md). Nur der oeffentliche Text, nichts zur Person.
- ``admin_router`` unter /api/v1/moderation/saal-sprueche, nur Admins: Sprueche ab heute
  lesen, je Tag festlegen und entfernen. Das geht auch bei Schalter aus, damit die
  Sprueche vor dem Einschalten bereitstehen.
"""

import asyncio
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from core.fehler import INTERNER_FEHLER
from core.logging import get_logger, log_pseudonym
from dependencies import require_admin
from infrastructure.database.models import SAAL_SPRUCH_MAX
from services.saal_spruch_service import (
    SaalSpruchService,
    SaalSpruchUngueltig,
    get_saal_spruch_service,
)
from services.schalter_service import schalter_wirksam

logger = get_logger(__name__)

SCHALTER = "saal_spruch"

router = APIRouter()
admin_router = APIRouter()


class HeuteResponse(BaseModel):
    # null: heute kein Spruch (oder Schalter aus)
    spruch: Optional[str]
    # false: Schalter saal_spruch aus (statt 404, die Startseite fragt automatisch)
    aktiv: bool = True


class SpruchRequest(BaseModel):
    # Die genaue Pruefung (Leerraum, Steuerzeichen, Laenge nach dem Bereinigen) macht
    # spruch_bereinigen; hier nur eine grobe Grenze gegen sehr grosse Anfragen.
    text: str = Field(..., max_length=SAAL_SPRUCH_MAX * 4)


class SpruchEintrag(BaseModel):
    datum: date
    text: str


class SpruchListeResponse(BaseModel):
    sprueche: List[SpruchEintrag]
    schalter_wirksam: bool
    # Der heutige Tag in deutscher Zeit (Europe/Berlin), fuer das Formular
    heute: date
    text_max: int = SAAL_SPRUCH_MAX


def _service() -> SaalSpruchService:
    return get_saal_spruch_service()


def _liste(service: SaalSpruchService) -> SpruchListeResponse:
    return SpruchListeResponse(
        sprueche=[
            SpruchEintrag(datum=s.datum, text=s.text) for s in service.kommende()
        ],
        schalter_wirksam=schalter_wirksam(SCHALTER),
        heute=service.heutiger_tag(),
    )


@router.get("/heute", response_model=HeuteResponse)
async def heute(service: SaalSpruchService = Depends(_service)) -> HeuteResponse:
    # schalter_wirksam liest bei abgelaufenem Cache die Schalter aus der Datenbank
    if not await asyncio.to_thread(schalter_wirksam, SCHALTER):
        return HeuteResponse(spruch=None, aktiv=False)
    # heute() faengt Lesefehler selbst ab: dann kein Spruch statt 500
    return HeuteResponse(spruch=await asyncio.to_thread(service.heute))


@admin_router.get("", response_model=SpruchListeResponse)
async def sprueche(
    admin_user: str = Depends(require_admin),
    service: SaalSpruchService = Depends(_service),
) -> SpruchListeResponse:
    try:
        return await asyncio.to_thread(_liste, service)
    except Exception as e:
        logger.error(f"Saal-Sprueche nicht gelesen: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)


@admin_router.put("/{datum}", response_model=SpruchListeResponse)
async def festlegen(
    datum: date,
    anfrage: SpruchRequest,
    admin_user: str = Depends(require_admin),
    service: SaalSpruchService = Depends(_service),
) -> SpruchListeResponse:
    try:
        await asyncio.to_thread(service.setzen, datum, anfrage.text)
        liste = await asyncio.to_thread(_liste, service)
    except SaalSpruchUngueltig as e:
        raise HTTPException(status_code=422, detail=e.antworttext)
    except Exception as e:
        logger.error(
            f"Saal-Spruch nicht gespeichert: {type(e).__name__}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    logger.info(f"Saal-Spruch festgelegt von {log_pseudonym(admin_user)}")
    return liste


@admin_router.delete("/{datum}", status_code=204)
async def entfernen(
    datum: date,
    admin_user: str = Depends(require_admin),
    service: SaalSpruchService = Depends(_service),
) -> Response:
    try:
        await asyncio.to_thread(service.loeschen, datum)
    except Exception as e:
        logger.error(f"Saal-Spruch nicht entfernt: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    logger.info(f"Saal-Spruch entfernt von {log_pseudonym(admin_user)}")
    return Response(status_code=204)
