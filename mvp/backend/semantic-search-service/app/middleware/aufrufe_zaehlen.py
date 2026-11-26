"""
Aufrufe zaehlen aus Abrufen, die die App ohnehin macht (#761, services/aufrufe_service.py).

Nach einer erfolgreichen Antwort (unter 400) auf einen Abruf, der eine Seite anzeigt
(``aufrufe_service.seite_von``), zaehlt diese Middleware einen Aufruf, wenn der Schalter
``aufrufe_zaehlen`` wirkt und die Wiederholsperre den Abruf als neu ansieht. Der Browser
schickt dafuer nichts Zusaetzliches; die Antwort ist dieselbe wie ohne Zaehlen.

Das Zaehlen laeuft nach der Antwort als eigene Aufgabe: Die Seite wartet nie darauf,
und ein Fehler beim Speichern kostet nur diesen Aufruf. Ueber dem Rate-Limit
(utils/rate_limiter.py) wird still nicht gezaehlt, damit niemand mit vielen Abrufen
Schreiblast erzeugt.
"""

import asyncio
from datetime import date
from typing import Callable, Optional, Set

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import Settings, settings as standard_settings
from core.logging import get_logger
from repositories.aufrufe_repository import AufrufeRepository, get_aufrufe_repository
from services import aufrufe_service
from services.schalter_service import schalter_wirksam
from utils.besucher_pseudonym import besucher_merkmal
from utils.client_identity import derive_client_key
from utils.rate_limiter import aufrufe_rate_limiter

logger = get_logger(__name__)

# Laufende Zaehl-Aufgaben, damit sie nicht vorzeitig eingesammelt werden (und Tests sie
# abwarten koennen)
AUSSTEHEND: Set[asyncio.Task] = set()


class AufrufeZaehlenMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        einstellungen: Optional[Callable[[], Settings]] = None,
        repository: Optional[Callable[[], AufrufeRepository]] = None,
        sperre: Optional[aufrufe_service.Wiederholsperre] = None,
        heute: Optional[Callable[[], date]] = None,
    ):
        super().__init__(app)
        self._einstellungen = einstellungen or (lambda: standard_settings)
        self._repository = repository or get_aufrufe_repository
        self._sperre = sperre or aufrufe_service.wiederholsperre
        self._heute = heute or (lambda: aufrufe_service.heute_utc())

    async def dispatch(self, request: Request, call_next):
        antwort = await call_next(request)
        seite = aufrufe_service.seite_von(request.method, request.url.path)
        if seite is None or antwort.status_code >= 400:
            return antwort
        try:
            if not schalter_wirksam(aufrufe_service.SCHALTER, self._einstellungen()):
                return antwort
        except Exception as e:
            logger.warning(f"Aufruf nicht gezaehlt: {type(e).__name__}")
            return antwort
        # Das Merkmal (Anschluss) lebt nur in dieser Anfrage und der Aufgabe danach.
        merkmal = besucher_merkmal(request)
        schluessel = derive_client_key(request)
        aufgabe = asyncio.create_task(self._zaehlen(merkmal, schluessel, seite))
        AUSSTEHEND.add(aufgabe)
        aufgabe.add_done_callback(AUSSTEHEND.discard)
        return antwort

    async def _zaehlen(self, merkmal: str, schluessel: str, seite: str) -> None:
        try:
            tag = self._heute()
            if not self._sperre.neu(merkmal, seite, tag):
                return
            if await aufrufe_rate_limiter.is_rate_limited(schluessel):
                return
            await asyncio.to_thread(
                aufrufe_service.zaehlen, self._repository(), merkmal, tag
            )
        except Exception as e:
            logger.warning(f"Aufruf nicht gezaehlt: {type(e).__name__}")
