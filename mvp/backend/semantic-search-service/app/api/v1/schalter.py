"""
Schalter mit Obergrenze und Admin-Wert (#708, GLOSSARY.md "Schalter"), nur fuer
Admins: Stand aller Schalter lesen und den Admin-Wert setzen. Logik:
services/schalter_service.py.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.config import Settings
from core.fehler import INTERNER_FEHLER
from core.logging import get_logger, log_pseudonym
from dependencies import get_settings, require_admin
from services.einstellungen_service import (
    AKTUELLE_SAISON,
    EinstellungenService,
    UnbekannteEinstellung,
    UngueltigerWert,
    get_einstellungen_service,
)
from services.saison_service import get_saison_service
from services.schalter_service import (
    ObergrenzeAus,
    SchalterService,
    UnbekannterSchalter,
    get_schalter_service,
)

logger = get_logger(__name__)

router = APIRouter()

OBERGRENZE_AUS = (
    "Der Server erlaubt diesen Schalter nicht (Umgebungsvariable aus). "
    "Einschalten geht erst, wenn die Obergrenze an ist."
)


class SchalterResponse(BaseModel):
    name: str
    erklaerung: str
    umgebungsvariable: str
    obergrenze: bool
    admin_wert: bool
    wirksam: bool
    dsfa_hinweis: Optional[str]


class EinstellungResponse(BaseModel):
    name: str
    erklaerung: str
    wert: str
    standard: str
    max_laenge: int
    # Warum der Wert gerade nicht gilt, etwa weil eine Saison laeuft (#782)
    hinweis: Optional[str] = None


class SchalterListeResponse(BaseModel):
    schalter: List[SchalterResponse]
    # Admin-Einstellungen mit Textwert, etwa aktuelle_saison (Teams)
    einstellungen: List[EinstellungResponse] = []


class EinstellungSetzenRequest(BaseModel):
    wert: str


class SchalterSetzenRequest(BaseModel):
    an: bool


def _service() -> SchalterService:
    return get_schalter_service()


def _einstellungen() -> EinstellungenService:
    return get_einstellungen_service()


def _hinweis(name: str) -> Optional[str]:
    """Die laufende Saison ersetzt die Einstellung aktuelle_saison (#782)."""
    if name != AKTUELLE_SAISON:
        return None
    laufende = get_saison_service().saison_fuer_teams()
    if laufende is None:
        return None
    return (
        f"Gilt gerade nicht: Die laufende Saison „{laufende}“ ist die aktuelle "
        "Saison der Teams (Abschnitt Saisons)."
    )


def _liste(
    dienst: SchalterService,
    settings: Settings,
    einstellungen: Optional[EinstellungenService] = None,
) -> SchalterListeResponse:
    # Frisch, am Cache vorbei: Mit mehreren Replikas zeigte die Seite sonst bis zu
    # CACHE_SEKUNDEN einen alten Stand, und der Umschalter spraenge zurueck.
    einstellungen = einstellungen or get_einstellungen_service()
    return SchalterListeResponse(
        schalter=[
            SchalterResponse(**vars(s)) for s in dienst.stand(settings, frisch=True)
        ],
        einstellungen=[
            EinstellungResponse(**vars(e), hinweis=_hinweis(e.name))
            for e in einstellungen.stand(frisch=True)
        ],
    )


@router.get("", response_model=SchalterListeResponse)
def schalter_liste(
    admin_user: str = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    dienst: SchalterService = Depends(_service),
    einstellungen: EinstellungenService = Depends(_einstellungen),
) -> SchalterListeResponse:
    return _liste(dienst, settings, einstellungen)


@router.put("/einstellungen/{name}", response_model=SchalterListeResponse)
def einstellung_setzen(
    name: str,
    anfrage: EinstellungSetzenRequest,
    admin_user: str = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    dienst: SchalterService = Depends(_service),
    einstellungen: EinstellungenService = Depends(_einstellungen),
) -> SchalterListeResponse:
    """Textwert einer Einstellung setzen (etwa aktuelle_saison); 404 unbekannt, 422 ungueltig."""
    try:
        einstellungen.setzen(name, anfrage.wert, admin_user)
    except UnbekannteEinstellung:
        raise HTTPException(status_code=404, detail="Einstellung nicht gefunden")
    except UngueltigerWert:
        raise HTTPException(status_code=422, detail="Ungueltiger Wert")
    except Exception as e:
        logger.error(
            f"Einstellung {name} nicht gesetzt: {type(e).__name__}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    logger.info(f"Einstellung {name} gesetzt von {log_pseudonym(admin_user)}")
    return _liste(dienst, settings, einstellungen)


@router.put("/{name}", response_model=SchalterListeResponse)
def schalter_setzen(
    name: str,
    anfrage: SchalterSetzenRequest,
    admin_user: str = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    dienst: SchalterService = Depends(_service),
) -> SchalterListeResponse:
    """Admin-Wert setzen; Einschalten ueber die Obergrenze hinaus: 409."""
    try:
        dienst.setzen(name, anfrage.an, admin_user, settings)
    except UnbekannterSchalter:
        raise HTTPException(status_code=404, detail="Schalter nicht gefunden")
    except ObergrenzeAus:
        raise HTTPException(status_code=409, detail=OBERGRENZE_AUS)
    except Exception as e:
        logger.error(
            f"Schalter {name} nicht gesetzt: {type(e).__name__}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    logger.info(
        f"Schalter {name} auf {'an' if anfrage.an else 'aus'} "
        f"von {log_pseudonym(admin_user)}"
    )
    return _liste(dienst, settings)
