"""
GET /api/v1/usage/users/me/naechster-schritt: die Vorschlaege fuer die Karte "Dein
naechster Schritt" (#789, services/naechster_schritt.py). Nur fuer Angemeldete, nur mit
dem Schalter ``naechster_schritt``; ohne ihn 200 mit ``{"vorschlaege": [], "aktiv": false}``
und ohne eine Abfrage (kein 404: die Startseite fragt automatisch, Gateway-fail2ban,
docs/ARCHITECTURE.md).

Der Abruf liest nur: eigene Einwuerfe, Stimmen und Beitraege samt Nutzung, die Zahl
frischer Beitraege anderer und die erste Aussage aus "Hier fehlt eine Antwort". Er
schreibt nichts, auch keinen Besuch. Die Person kommt aus ``X-User`` (#284).
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Awaitable, List, Optional, TypeVar

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.config import Settings
from core.logging import get_logger
from dependencies import (
    get_content_repository,
    get_settings,
    get_unbeantwortete_aussagen_service,
    require_user,
)
from domain.content_registry import BEITRAGSTYPEN_WERTE
from dtos.contribution import ContributionEntry
from repositories.einwurf_repository import EinwurfRepository, get_einwurf_repository
from repositories.punkte_repository import PunkteRepository
from services.naechster_schritt import (
    Brachflaeche,
    EigenerStand,
    meistgenutzter_ohne_kurzfassung,
    vorschlaege,
)
from services.unbeantwortete_aussagen_service import UnbeantworteteAussagenService
from services.usage_tracking_service import get_usage_service

logger = get_logger(__name__)

router = APIRouter()

# So lange wartet jede Quelle hoechstens; danach faellt nur ihre Regel aus.
QUELLE_TIMEOUT_S = 1.5

# "Frisch" wie die Kachel "neue Beitraege" (api/v1/usage.py BESUCH_ZEITRAUM_TAGE) und
# dieselben Typen wie "Frisch aus der Community", wohin der Vorschlag fuehrt.
FRISCH_TAGE = 7
FRISCH_TYPEN = ("commentary", "generic_text")

# So viele eigene Beitraege liest die Karte hoechstens (wie die Nutzungsstatistik).
BEITRAEGE_HOECHSTENS = 10000

T = TypeVar("T")


class BrachflaecheDto(BaseModel):
    statement_id: str
    statement_text: str
    personen_ohne_treffer: int


class KommentarDto(BaseModel):
    content_id: str
    titel: str
    nutzung: int


class VorschlagDto(BaseModel):
    art: str
    anzahl: Optional[int] = None
    brachflaeche: Optional[BrachflaecheDto] = None
    kommentar: Optional[KommentarDto] = None


class NaechsterSchrittResponse(BaseModel):
    # Alle passenden Vorschlaege, der erste gilt; nach dem Wegklicken der naechste.
    vorschlaege: List[VorschlagDto]
    # false: Schalter naechster_schritt aus
    aktiv: bool = True


class Quellen:
    """Liest den eigenen Stand; jede Methode wirft bei einem Fehler."""

    def __init__(
        self,
        einwuerfe: EinwurfRepository,
        settings: Settings,
        unbeantwortete: UnbeantworteteAussagenService,
    ):
        self._einwuerfe = einwuerfe
        self._settings = settings
        self._unbeantwortete = unbeantwortete

    async def einwuerfe(self, person: str) -> int:
        return await asyncio.to_thread(self._einwuerfe.count, submitted_by=person)

    async def stimmen(self, person: str) -> int:
        je_tag = await asyncio.to_thread(
            PunkteRepository().bewertungen_je_tag, person, []
        )
        return sum(je_tag.values())

    async def beitraege(self, person: str) -> List[dict]:
        """Die eigenen sichtbaren Beitraege mit Nutzung (wie "Meine Beitraege")."""
        repository = get_content_repository(self._settings)
        eintraege = await repository.getByAuthor(
            user_id=person,
            limit=BEITRAEGE_HOECHSTENS,
            offset=0,
            content_types=BEITRAGSTYPEN_WERTE,
            eintrag_modell=ContributionEntry,
        )
        return await asyncio.to_thread(
            get_usage_service().enrich_content_with_usage,
            [e.model_dump() for e in eintraege],
        )

    async def frische_antworten(self, person: str) -> int:
        seit = datetime.now(timezone.utc) - timedelta(days=FRISCH_TAGE)
        return await get_content_repository(self._settings).count_neue_von_anderen(
            person, seit, FRISCH_TYPEN
        )

    async def brachflaeche(self) -> Optional[Brachflaeche]:
        erste = await self._unbeantwortete.liste(limit=1, mit_themen=False)
        if not erste:
            return None
        a = erste[0]
        return Brachflaeche(a.statement_id, a.text, a.personen_ohne_treffer)


def get_quellen(
    einwuerfe: EinwurfRepository = Depends(get_einwurf_repository),
    settings: Settings = Depends(get_settings),
    unbeantwortete: UnbeantworteteAussagenService = Depends(
        get_unbeantwortete_aussagen_service
    ),
) -> Quellen:
    return Quellen(einwuerfe, settings, unbeantwortete)


async def _oder_none(aufruf: Awaitable[T], was: str) -> Optional[T]:
    try:
        return await asyncio.wait_for(aufruf, timeout=QUELLE_TIMEOUT_S)
    except Exception as e:
        logger.warning(f"Naechster Schritt: {was} nicht gelesen ({type(e).__name__})")
        return None


def _schalter_an(settings: Settings = Depends(get_settings)) -> bool:
    # Basisfunktion seit dem Schalter-Umbau (27.11.): immer an
    return True


@router.get("/users/me/naechster-schritt", response_model=NaechsterSchrittResponse)
async def naechster_schritt(
    current_user: str = Depends(require_user),
    an: bool = Depends(_schalter_an),
    quellen: Quellen = Depends(get_quellen),
    settings: Settings = Depends(get_settings),
) -> NaechsterSchrittResponse:
    # Quellen sind gebaut, fragen aber erst beim Aufruf ihrer Methoden etwas ab.
    if not an:
        return NaechsterSchrittResponse(vorschlaege=[], aktiv=False)
    einwuerfe, stimmen, beitraege, frisch, brache = await asyncio.gather(
        _oder_none(quellen.einwuerfe(current_user), "Einwuerfe"),
        _oder_none(quellen.stimmen(current_user), "Stimmen"),
        _oder_none(quellen.beitraege(current_user), "Beitraege"),
        _oder_none(quellen.frische_antworten(current_user), "Frische Antworten"),
        _oder_none(quellen.brachflaeche(), "Aussage ohne Antwort"),
    )
    stand = EigenerStand(
        einwuerfe=einwuerfe,
        stimmen=stimmen,
        beitraege=None if beitraege is None else len(beitraege),
        kommentar_ohne_kurzfassung=(
            None if beitraege is None else meistgenutzter_ohne_kurzfassung(beitraege)
        ),
        frische_antworten=frisch,
        brachflaeche=brache,
    )
    return NaechsterSchrittResponse(
        vorschlaege=[
            VorschlagDto(
                art=v.art.value,
                anzahl=v.anzahl,
                brachflaeche=(
                    BrachflaecheDto(
                        statement_id=str(v.brachflaeche.statement_id),
                        statement_text=v.brachflaeche.text,
                        personen_ohne_treffer=v.brachflaeche.personen_ohne_treffer,
                    )
                    if v.brachflaeche
                    else None
                ),
                kommentar=(
                    KommentarDto(
                        content_id=str(v.kommentar.content_id),
                        titel=v.kommentar.titel,
                        nutzung=v.kommentar.nutzung,
                    )
                    if v.kommentar
                    else None
                ),
            )
            for v in vorschlaege(stand, settings.naechster_schritt_stimmen)
        ]
    )
