"""
Merkliste (#758, GLOSSARY.md "Merkliste"): Beitraege merken und unter "Meine Beitraege"
wiederfinden. Lesen und Merken nur fuer angemeldete Personen mit Art.-9-Einwilligung
(Entfernen auch ohne, wie jedes Zuruecknehmen), nur fuers eigene
Konto; Zaehler fuer andere gibt es nicht. Ohne den Schalter ``merkliste`` antwortet
``GET`` mit 200 und ``aktiv: false`` (die Seite fragt selbst nach, ein 404 je Abruf
fiele im Gateway auf), Merken mit 404, jeweils vor jeder Datenbankabfrage. Die Person kommt aus ``X-User``, nicht aus dem Pfad (#284).

Die Liste nennt IDs, Zeitpunkte und je Eintrag ``sichtbar`` (eine Abfrage an den
Suchindex fuer die ganze Liste, wie der Zustand am Einwurf). Die sichtbaren Beitraege
laedt das Frontend ueber ihre eigene Adresse (GET /api/v1/content/beitrag/{id});
gesperrte und geloeschte fragt es gar nicht erst ab, sonst antwortete jedes Oeffnen des
Reiters mit 404 je Eintrag (fail2ban im Saal-WLAN).

Entfernen geht auch bei ausgeschaltetem Schalter: Zuruecknehmen bleibt immer offen,
sonst laegen Eintraege aus einer Zeit "an" fest, bis die Person widerruft.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from core.config import Settings
from core.fehler import INTERNER_FEHLER
from core.logging import get_logger, log_pseudonym
from domain.models.content_status import zustand_am_einwurf
from dependencies import (
    get_beitrag_laden,
    get_settings,
    require_art9_einwilligung,
    require_user,
)
from repositories.merkliste_repository import (
    MERKLISTE_MAX,
    MerklisteRepository,
    MerklisteVoll,
    get_merkliste_repository,
)
from repositories.implementations.qdrant.moderation_repository import (
    get_moderation_repository,
)
from services.beitrag_laden import BeitragLader, BeitragUnlesbar
from services.schalter_service import schalter_wirksam

logger = get_logger(__name__)

router = APIRouter()

MERKLISTE_VOLL = (
    f"Deine Merkliste ist voll ({MERKLISTE_MAX} Beiträge). Entferne erst einen."
)


class GemerktResponse(BaseModel):
    content_id: uuid.UUID
    gemerkt_am: datetime
    # false: gesperrt oder geloescht, das Frontend fragt ihn nicht ab; None: Suchindex
    # nicht erreichbar, das Frontend versucht es wie vorher
    sichtbar: Optional[bool] = None


class MerklisteResponse(BaseModel):
    # false: Schalter merkliste aus; dann ist die Liste leer und nichts gefragt
    aktiv: bool = True
    eintraege: List[GemerktResponse]


def _merkliste(
    current_user: str = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> MerklisteRepository:
    """
    Ohne Schalter 404: Die Funktion gibt es dann nicht. Vor der Art.-9-Pruefung
    (Reihenfolge der Abhaengigkeiten), damit ein ausgeschalteter Schalter die
    Datenbank nicht fragt.
    """
    if not schalter_wirksam("merkliste", settings):
        raise HTTPException(status_code=404, detail="Not found")
    return get_merkliste_repository()


def merkliste_angeboten(
    current_user: str = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> Optional[MerklisteRepository]:
    """
    Fuer den Abruf: ohne Schalter None statt 404, ohne Einwilligung und Datenbank zu
    fragen; mit Schalter erst die Sperre ohne Einwilligung (``require_art9_einwilligung``,
    403). Synchron wie die Sperre selbst (Threadpool). tests/unit/api/
    test_art9_einwilligung_api.py zaehlt diese Abhaengigkeit als Sperre.
    """
    if not schalter_wirksam("merkliste", settings):
        return None
    require_art9_einwilligung(current_user)
    return get_merkliste_repository()


async def _sichtbarkeit(ids: List[uuid.UUID]) -> Dict[uuid.UUID, bool]:
    """
    Ob die Beitraege zu diesen IDs fuer Leser da sind, mit einer Abfrage an den
    Suchindex. Antwortet der nicht, ein leeres Dict: Die Liste laedt trotzdem.
    """
    if not ids:
        return {}
    try:
        gespeichert = await get_moderation_repository().zustaende_laden(
            [str(i) for i in ids]
        )
    except Exception as e:
        logger.error(
            f"Zustand der gemerkten Beitraege nicht lesbar: {type(e).__name__}",
            exc_info=True,
        )
        return {}
    return {
        i: zustand_am_einwurf(gespeichert.get(str(i)), str(i) in gespeichert)
        == "sichtbar"
        for i in ids
    }


@router.get("", response_model=MerklisteResponse)
async def merkliste_lesen(
    current_user: str = Depends(require_user),
    merkliste: Optional[MerklisteRepository] = Depends(merkliste_angeboten),
) -> MerklisteResponse:
    """Die eigene Merkliste, zuletzt gemerkt zuerst; ohne Schalter ``aktiv: false``."""
    if merkliste is None:
        return MerklisteResponse(aktiv=False, eintraege=[])
    try:
        eintraege = await asyncio.to_thread(merkliste.liste, current_user)
    except Exception as e:
        logger.error(
            f"Merkliste von {log_pseudonym(current_user)} nicht gelesen: {type(e).__name__}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    sichtbar = await _sichtbarkeit([e.content_id for e in eintraege])
    return MerklisteResponse(
        eintraege=[
            GemerktResponse(
                content_id=e.content_id,
                gemerkt_am=e.gemerkt_am,
                sichtbar=sichtbar.get(e.content_id),
            )
            for e in eintraege
        ]
    )


@router.put("/{content_id}", status_code=204)
async def merken(
    content_id: uuid.UUID,
    current_user: str = Depends(require_user),
    merkliste: MerklisteRepository = Depends(_merkliste),
    _einwilligung: None = Depends(require_art9_einwilligung),
    laden: BeitragLader = Depends(get_beitrag_laden),
) -> Response:
    """
    Einen sichtbaren Beitrag merken; schon gemerkt: nach oben holen. 404 fuer
    gesperrte, geloeschte und nie vorhandene Beitraege, 409 bei voller Merkliste.
    """
    try:
        beitrag = await laden(content_id)
    except BeitragUnlesbar:
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    if beitrag is None:
        raise HTTPException(status_code=404, detail="Beitrag nicht gefunden.")
    try:
        await asyncio.to_thread(merkliste.merken, current_user, content_id)
    except MerklisteVoll:
        raise HTTPException(status_code=409, detail=MERKLISTE_VOLL)
    except Exception as e:
        logger.error(
            f"Merken fuer {log_pseudonym(current_user)} gescheitert: {type(e).__name__}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    return Response(status_code=204)


@router.delete("/{content_id}", status_code=204)
async def entfernen(
    content_id: uuid.UUID,
    current_user: str = Depends(require_user),
) -> Response:
    """
    Einen Eintrag entfernen; war er nicht gemerkt, ebenso 204. Ohne Art.-9-Einwilligung
    offen wie jedes Zuruecknehmen (test_art9_einwilligung_api.py), und ohne Schalter
    ebenso: Wer in einer Zeit "an" gemerkt hat, kann das immer selbst zuruecknehmen.
    """
    try:
        merkliste = get_merkliste_repository()
        await asyncio.to_thread(merkliste.entfernen, current_user, content_id)
    except Exception as e:
        logger.error(
            f"Entfernen aus der Merkliste von {log_pseudonym(current_user)} "
            f"gescheitert: {type(e).__name__}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    return Response(status_code=204)
