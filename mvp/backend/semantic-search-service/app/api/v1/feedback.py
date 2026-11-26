"""
Feedback an das Team (#343). Senden darf jede Person, auch ohne Anmeldung; lesen,
als erledigt markieren und einzeln loeschen (#425) duerfen nur Admins. Was
gespeichert wird: services/feedback_service.py. Die Kategorie "gestoert" (Knopf
"Was hat dich gestört?") nimmt der Dienst nur an, solange der Schalter
feedback_gestoert wirkt, und nie mit Kontakt (domain/feedback_gestoert.py).
"""

import uuid
from datetime import date
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator, model_validator

from core.config import Settings
from core.logging import get_logger
from dependencies import get_feedback_service, get_settings, require_admin
from domain.feedback_gestoert import KATEGORIE_GESTOERT
from services.feedback_service import (
    AUFBEWAHRUNG_TAGE,
    KONTAKT_MAX,
    LIMIT_STANDARD,
    TEXT_MAX,
    FeedbackEintrag,
    FeedbackService,
)
from services.schalter_service import schalter_wirksam
from utils.client_identity import derive_client_key
from utils.rate_limiter import feedback_rate_limiter

logger = get_logger(__name__)

router = APIRouter()


class FeedbackSendenRequest(BaseModel):
    text: str = Field(..., max_length=TEXT_MAX)
    kontakt: Optional[str] = Field(None, max_length=KONTAKT_MAX)
    # Nur "gestoert" (Knopf "Was hat dich gestört?"); ohne: der Knopf "Feedback"
    kategorie: Optional[Literal["gestoert"]] = None

    @field_validator("text")
    @classmethod
    def _text_nicht_leer(cls, wert: str) -> str:
        wert = wert.strip()
        if not wert:
            raise ValueError("Feedback darf nicht leer sein")
        return wert

    @field_validator("kontakt")
    @classmethod
    def _leerer_kontakt_ist_keiner(cls, wert: Optional[str]) -> Optional[str]:
        if wert is None:
            return None
        return wert.strip() or None

    @model_validator(mode="after")
    def _gestoert_ohne_kontakt(self) -> "FeedbackSendenRequest":
        # Freitext ohne Kennung (Jura 26.11., Punkt g): das Formular fragt keinen
        # Kontakt; kommt doch einer, wird nichts gespeichert.
        if self.kategorie == KATEGORIE_GESTOERT and self.kontakt is not None:
            raise ValueError("Kategorie gestoert nimmt keinen Kontakt an")
        return self


class FeedbackSendenResponse(BaseModel):
    success: bool


class FeedbackEintragResponse(BaseModel):
    id: uuid.UUID
    text: str
    kontakt: Optional[str]
    eingegangen_am: date
    erledigt: bool
    kategorie: Optional[str] = None

    @classmethod
    def aus(cls, e: FeedbackEintrag) -> "FeedbackEintragResponse":
        return cls(
            id=e.id,
            text=e.text,
            kontakt=e.kontakt,
            eingegangen_am=e.eingegangen_am,
            erledigt=e.erledigt,
            kategorie=e.kategorie,
        )


class FeedbackErledigtRequest(BaseModel):
    erledigt: bool


class FeedbackListeResponse(BaseModel):
    aufbewahrung_tage: int
    eintraege: List[FeedbackEintragResponse]


@router.post("/senden", status_code=201, response_model=FeedbackSendenResponse)
async def feedback_senden(
    request: FeedbackSendenRequest,
    http_request: Request,
    service: FeedbackService = Depends(get_feedback_service),
    settings: Settings = Depends(get_settings),
):
    """
    Feedback speichern. Ohne Anmeldung erreichbar (BFF/Proxy/EndpointPolicy.cs);
    das Rate-Limit haengt deshalb an der Adresse, wie bei Meldungen. Der Schluessel
    ist ein prozesslokaler Hash und wird weder gespeichert noch geloggt. X-User
    wird bewusst nicht gelesen: Feedback traegt keine Kennung.

    Die Kategorie "gestoert" bei ausgeschaltetem Schalter (oder nach der Startphase)
    antwortet 409, nicht 404: Senden ist eine Handlung, und das Formular sagt dann,
    dass der Knopf gerade aus ist.
    """
    if request.kategorie == KATEGORIE_GESTOERT and not schalter_wirksam(
        "feedback_gestoert", settings
    ):
        raise HTTPException(status_code=409, detail="Feedback category is off")
    if await feedback_rate_limiter.is_rate_limited(derive_client_key(http_request)):
        raise HTTPException(
            status_code=429, detail="Too much feedback. Please wait a moment."
        )
    try:
        if request.kategorie is None:
            service.senden(request.text, request.kontakt)
        else:
            service.senden(request.text, None, kategorie=request.kategorie)
    except Exception as e:
        logger.error(f"Error storing feedback: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to store feedback")
    return FeedbackSendenResponse(success=True)


@router.get("", response_model=FeedbackListeResponse)
async def feedback_liste(
    limit: int = Query(LIMIT_STANDARD, ge=1, le=500),
    erledigt: Optional[bool] = Query(None),
    admin_user: str = Depends(require_admin),
    service: FeedbackService = Depends(get_feedback_service),
):
    """
    Das neueste Feedback zuerst, mit Kontakt, falls angegeben. erledigt=false
    liefert nur das offene, erledigt=true nur das erledigte, ohne alles.
    """
    try:
        eintraege = service.neueste(limit, erledigt)
    except Exception as e:
        logger.error(f"Error fetching feedback: {type(e).__name__}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch feedback")
    return FeedbackListeResponse(
        aufbewahrung_tage=AUFBEWAHRUNG_TAGE,
        eintraege=[FeedbackEintragResponse.aus(e) for e in eintraege],
    )


@router.patch("/{feedback_id}", response_model=FeedbackEintragResponse)
async def feedback_erledigt_setzen(
    feedback_id: uuid.UUID,
    request: FeedbackErledigtRequest,
    admin_user: str = Depends(require_admin),
    service: FeedbackService = Depends(get_feedback_service),
):
    """Als erledigt markieren oder das zuruecknehmen; die Frist bleibt."""
    eintrag = service.erledigt_setzen(feedback_id, request.erledigt)
    if eintrag is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return FeedbackEintragResponse.aus(eintrag)


@router.delete("/{feedback_id}", status_code=204)
async def feedback_loeschen(
    feedback_id: uuid.UUID,
    admin_user: str = Depends(require_admin),
    service: FeedbackService = Depends(get_feedback_service),
):
    """Ein Feedback samt Kontakt sofort loeschen, vor der Frist."""
    if not service.loeschen(feedback_id):
        raise HTTPException(status_code=404, detail="Feedback not found")
    return Response(status_code=204)
