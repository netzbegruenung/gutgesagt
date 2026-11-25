"""
Konter-Probe (#786): Proben aus Spruch und drei echten Antworten, ohne Anmeldung.

Nur lesend. Der Tipp bleibt im Browser: Es gibt keinen Endpunkt, der ihn annimmt,
und nichts wird gespeichert oder gezaehlt. Hinter dem Schalter ``konter_probe``
(services/schalter_service.py); ist er aus, antwortet der Pfad mit 404.

Die Antworten kommen als Karten wie bei "Diese Woche oft genutzt" (api/v1/usage.py,
oft_genutzt), aufbereitet mit ``fuer_aufrufer``: Besucher sehen weder Anzeigenamen
noch Kennungen.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.config import Settings
from dependencies import (
    get_aufrufer,
    get_content_repository,
    get_reference_service,
    get_settings,
    get_statement_service,
)
from dtos.beitrag import BeitragResponse
from dtos.beitragstypen import ANTWORT_JE_TYP
from repositories.varianten_repository import (
    VariantenRepository,
    get_varianten_repository,
)
from services.beitrag_fuer_aufrufer import Aufrufer, fuer_aufrufer
from services.content.reference_service import ReferenceService
from services.guete_service import guete_ergaenzen
from services.konter_probe_service import KonterProbeService
from services.oft_genutzt_service import sichtbaren_beitrag_laden
from services.schalter_service import schalter_wirksam
from services.usage_tracking_service import get_usage_service
from services.varianten import varianten_ergaenzen

logger = logging.getLogger(__name__)

router = APIRouter()


class KonterProbeAussage(BaseModel):
    id: str
    text: str


class KonterProbeEintrag(BaseModel):
    aussage: KonterProbeAussage
    # Karten wie /usage/trending/woche, je mit result_type und usage_count.
    antworten: List[Dict[str, Any]]


class KonterProbenResponse(BaseModel):
    proben: List[KonterProbeEintrag]


def get_konter_probe_service(
    settings: Settings = Depends(get_settings),
    reference_service: ReferenceService = Depends(get_reference_service),
) -> KonterProbeService:
    from repositories.implementations.qdrant.qdrant_repository_factory import (
        QdrantRepositoryFactory,
    )

    return KonterProbeService(
        get_statement_service(),
        # Erst beim Aufruf: Das Repository baut beim ersten Zugriff eine Verbindung auf.
        lambda ids: get_usage_service().repository.get_usage_counts_batch(ids),
        sichtbaren_beitrag_laden(
            settings,
            get_content_repository(settings),
            QdrantRepositoryFactory(),
            reference_service,
        ),
    )


@router.get("", response_model=KonterProbenResponse)
async def konter_proben(
    aufrufer: Aufrufer = Depends(get_aufrufer),
    settings: Settings = Depends(get_settings),
    varianten: VariantenRepository = Depends(get_varianten_repository),
) -> KonterProbenResponse:
    """
    Bis zu zehn Proben in zufaelliger Reihenfolge, die Antworten je Probe gemischt.
    Leer, wenn keine Aussage passt; dann zeigt die App keinen Einstieg.
    """
    if not schalter_wirksam("konter_probe", settings):
        raise HTTPException(status_code=404, detail="Not found")

    try:
        # Im try gebaut: Scheitert ein Repository, antwortet der Endpunkt mit 500 und Log.
        service = get_konter_probe_service(settings, get_reference_service())
        proben = await service.proben()

        ergebnis = []
        for probe in proben:
            antworten = fuer_aufrufer(
                # Vor fuer_aufrufer: Die Guete laesst die Stimme des Autors aus (#427).
                await guete_ergaenzen(
                    [
                        ANTWORT_JE_TYP.get(
                            a["result_type"], BeitragResponse
                        ).model_validate(a)
                        for a in probe.antworten
                    ]
                ),
                aufrufer,
            )
            varianten_ergaenzen(antworten, varianten)
            ergebnis.append(
                KonterProbeEintrag(
                    aussage=KonterProbeAussage(
                        id=str(probe.statement_id), text=probe.text
                    ),
                    antworten=[
                        {
                            **antwort.model_dump(mode="json"),
                            "result_type": a["result_type"],
                            "usage_count": a["usage_count"],
                        }
                        for a, antwort in zip(probe.antworten, antworten)
                    ],
                )
            )
        return KonterProbenResponse(proben=ergebnis)

    except Exception as e:
        logger.error(f"Error getting konter proben: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
