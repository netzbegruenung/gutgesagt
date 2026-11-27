"""
Neutraler Sammelpfad fuer Meldungen ohne Konto (#799): ``POST /api/v1/ereignis``.

Die Art der Meldung steht nur im Body, nie im Pfad oder in der Query: Zugriffsprotokolle
von Webserver und BFF sehen nur den neutralen Pfad und lassen keinen Rueckschluss zu,
dass jemand "Ja, gepostet" gemeldet hat (Bedingung Jura, 25.11.2026). Der Weg mit Konto
(``/api/v1/usage/users/me/gepostet``) bleibt unveraendert.

Heute gibt es genau eine Art, ``gepostet_ohne_konto``: je Klick +1 auf die Zahl der
Kalenderwoche (services/gepostet_ohne_konto_service.py). Kein Beitrag: Das
Wirkungs-Echo (#790) zaehlt je Beitrag nur mit Konto, entdoppelt ueber die Kennung,
und braucht ihn hier nicht. Unbekannte Felder werden abgewiesen (422), damit kein
Client still etwas mitschickt, das nicht gezaehlt werden darf.
"""

import asyncio
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from core.config import Settings
from core.fehler import INTERNER_FEHLER
from core.logging import get_logger
from dependencies import (
    get_current_user_optional,
    get_ereignis_rate_limiter,
    get_settings,
)
from services.gepostet_ohne_konto_service import (
    GepostetOhneKontoService,
    get_gepostet_ohne_konto_service,
)
from services.schalter_service import notaus_wirksam
from utils.aufrufer import ANONYM
from utils.rate_limiter import RateLimiter

logger = get_logger(__name__)

router = APIRouter()

# Ein Schluessel fuer alle: die Drosselung kennt keine Adresse und keine Person.
DROSSEL_SCHLUESSEL = "ereignis"


class EreignisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    art: Literal["gepostet_ohne_konto"]


class EreignisResponse(BaseModel):
    # False fuer Angemeldete: Sie melden ueber /users/me/gepostet und zaehlen dort als
    # Menschen; hier wuerden sie sonst zusaetzlich als Meldung ohne Konto zaehlen.
    gezaehlt: bool


@router.post("", response_model=EreignisResponse)
async def ereignis(
    body: EreignisRequest,
    aufrufer: Optional[str] = Depends(get_current_user_optional),
    settings: Settings = Depends(get_settings),
    limiter: RateLimiter = Depends(get_ereignis_rate_limiter),
    dienst: GepostetOhneKontoService = Depends(get_gepostet_ohne_konto_service),
) -> EreignisResponse:
    """
    Eine Meldung ohne Konto zaehlen. Mit Not-Aus ``gepostet_ohne_konto``
    (SEMANTIC_SEARCH_GEPOSTET_OHNE_KONTO_AKTIV=false) 404 und nichts gezaehlt; ueber
    der Drosselung 429. Geloggt wird
    nichts zur Person, auch keine Adresse.
    """
    if not notaus_wirksam("gepostet_ohne_konto", settings):
        raise HTTPException(status_code=404, detail="Not found")
    if aufrufer and aufrufer != ANONYM:
        return EreignisResponse(gezaehlt=False)
    if await limiter.is_rate_limited(DROSSEL_SCHLUESSEL):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait.")
    try:
        await asyncio.to_thread(dienst.melden)
    except Exception as e:
        logger.error(f"Meldung ohne Konto nicht gezaehlt: {type(e).__name__}")
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    return EreignisResponse(gezaehlt=True)
