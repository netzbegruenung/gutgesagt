"""
Ankuenfte je Kampagnenwort und Tag (services/ankunft_service.py).

- ``POST /api/v1/ankunft`` (ohne Anmeldung): die App meldet einmal je geoeffneter Seite,
  dass sie mit ``?k=<wort>`` geoeffnet wurde. Das Wort steht nur im Body, nie im Pfad
  oder in der Query, und der Frontend-nginx schreibt fuer diesen Pfad keine
  Zugriffszeile (nginx.protokoll.conf, wie bei /api/v1/ereignis aus #799). Wer fragt,
  liest der Endpunkt nicht: weder Kennung noch Adresse gehen an den Dienst. Die App
  fragt ihn beim Laden ohne Zutun der Person, deshalb antwortet er nie 401 oder 404
  (CODING_STANDARDS.md "Endpoints"): Schalter aus oder Wort nicht auf der Positivliste
  ist ``{"gezaehlt": false}`` mit 200. Unbekannte Felder werden abgewiesen (422).
- ``GET /api/v1/ankuenfte`` (nur Admins): die Zahlen der letzten Tage fuer die
  Uebersicht; Schalter aus ist ``{"aktiv": false, "tage": []}``.

Schalter ``k_ankuenfte``.
"""

import asyncio
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from core.config import Settings
from core.fehler import INTERNER_FEHLER
from core.logging import get_logger
from dependencies import get_ankunft_rate_limiter, get_settings, require_admin
from services.ankunft_service import (
    AnkunftService,
    get_ankunft_service,
    kampagnenwort_pruefen,
)
from services.schalter_service import schalter_wirksam
from utils.rate_limiter import RateLimiter

logger = get_logger(__name__)

router = APIRouter()
admin_router = APIRouter()

# Ein Schluessel fuer alle: die Drosselung kennt keine Adresse und keine Person.
DROSSEL_SCHLUESSEL = "ankunft"


class AnkunftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    k: str = Field(min_length=1, max_length=40)


class AnkunftResponse(BaseModel):
    gezaehlt: bool


@router.post("", response_model=AnkunftResponse)
async def ankunft(
    body: AnkunftRequest,
    settings: Settings = Depends(get_settings),
    limiter: RateLimiter = Depends(get_ankunft_rate_limiter),
    dienst: AnkunftService = Depends(get_ankunft_service),
) -> AnkunftResponse:
    """
    Eine Ankunft zaehlen. Ohne Schalter ``k_ankuenfte`` oder mit einem Wort ausserhalb
    der Positivliste 200 und nichts gezaehlt; ueber der Drosselung 429. Geloggt wird
    nichts zur Person und nicht das Wort.
    """
    if not schalter_wirksam("k_ankuenfte", settings):
        return AnkunftResponse(gezaehlt=False)
    k = kampagnenwort_pruefen(body.k, settings.kampagnenwoerter())
    if k is None:
        return AnkunftResponse(gezaehlt=False)
    if await limiter.is_rate_limited(DROSSEL_SCHLUESSEL):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait.")
    try:
        await asyncio.to_thread(dienst.zaehlen, k)
    except Exception as e:
        logger.error(f"Ankunft nicht gezaehlt: {type(e).__name__}")
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    return AnkunftResponse(gezaehlt=True)


class AnkunftZeile(BaseModel):
    tag: date = Field(description="UTC-Tag")
    k: str
    anzahl: int


class AnkuenfteResponse(BaseModel):
    aktiv: bool
    tage: List[AnkunftZeile]


@admin_router.get("", response_model=AnkuenfteResponse)
async def ankuenfte(
    admin_user: str = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    dienst: AnkunftService = Depends(get_ankunft_service),
) -> AnkuenfteResponse:
    """Ankuenfte je Kampagnenwort und Tag der letzten 30 Tage, neueste zuerst."""
    if not schalter_wirksam("k_ankuenfte", settings):
        return AnkuenfteResponse(aktiv=False, tage=[])
    try:
        zeilen = await asyncio.to_thread(dienst.letzte_tage)
    except Exception as e:
        logger.error(f"Ankuenfte nicht gelesen: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    return AnkuenfteResponse(
        aktiv=True,
        tage=[AnkunftZeile(tag=z.tag, k=z.k, anzahl=z.anzahl) for z in zeilen],
    )
