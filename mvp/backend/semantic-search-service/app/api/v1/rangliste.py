"""
Rangliste je Saison (#793, services/rangliste_service.py), unter /api/v1/rangliste,
nur fuer die angemeldete Person selbst (``X-User``). Solange der Schalter ``rangliste``
nicht wirkt (er wirkt nur zusammen mit den Punkten, services/schalter_service.py),
antwortet ``GET`` mit 200 und ``aktiv: false`` (die Seite laedt selbst nach, ein 404 je
Abruf sperrte am Gateway ein Saal-WLAN, docs/ARCHITECTURE.md). ``PUT`` nimmt ein Nein
immer an (Widerruf so einfach wie die Einwilligung, Art. 7 Abs. 3 DSGVO), ein Ja dann
nicht (409).

- ``GET ""``: Antwort der Person, ihr Ranglistenname und, wenn sie selbst
  teilnimmt, die Rangliste der laufenden Saison (Top 10 und eigener Platz, erst ab
  zehn Teilnehmenden) und vergangene Saisons als Summe.
- ``PUT /einwilligung``: Ja oder Nein und die Wahl des Anzeigenamens, jederzeit; ein
  Ja nur mit wirksamem Schalter und nicht im Spielgefuehl-Modell.

Kein teilbarer Link, keine Linkvorschau, kein Export: Es gibt nur diesen Abruf fuer
die angemeldete Person.
"""

import asyncio
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from core.config import Settings
from core.fehler import INTERNER_FEHLER
from core.logging import get_logger, log_pseudonym
from dependencies import get_settings, require_user
from domain.rangliste import (
    AKTUELLER_WORTLAUT,
    MIN_TEILNEHMENDE,
    WORTLAUTE,
    Platz,
    UnbekannterWortlaut,
)
from services import rangliste_service
from services.rangliste_service import RanglisteService, get_rangliste_service
from services.schalter_service import schalter_wirksam
from services.spielgefuehl_service import buehne_aktiv

logger = get_logger(__name__)

router = APIRouter()


class WortlautResponse(BaseModel):
    kennung: str
    text: str


class PlatzResponse(BaseModel):
    platz: int
    name: str
    punkte: int
    ich: bool
    # Nur im Spielgefuehl-Modell: erreichte Meilensteine ohne Wegmarken
    abzeichen: Optional[int] = None


class RanglisteResponse(BaseModel):
    oben: List[PlatzResponse]
    # Der eigene Platz, wenn er nicht unter den ersten zehn steht
    eigener: Optional[PlatzResponse]
    teilnehmende: int


class SaisonResponse(BaseModel):
    name: str
    # Letzter Tag (UTC)
    ende: date


class VergangeneResponse(BaseModel):
    name: str
    punkte: int


class StandResponse(BaseModel):
    # false: Schalter rangliste aus; dann ist nichts gefragt und nichts zu zeigen
    aktiv: bool = True
    gefragt: bool
    teilnehmen: Optional[bool]
    mit_anzeigename: bool
    # Art.-9-Einwilligung und "Punkte und Meilensteine" gelten
    voraussetzungen: bool
    # Erst mit dem ersten Ja vergeben; null davor
    ranglistenname: Optional[str]
    # Der Anzeigename, wie er gespeichert ist; null ohne
    anzeigename: Optional[str]
    saison: Optional[SaisonResponse]
    # Nur fuer Teilnehmende mit laufender Saison
    eigene_punkte: Optional[int]
    # null: nicht teilnehmend, keine laufende Saison oder unter min_teilnehmende
    rangliste: Optional[RanglisteResponse]
    vergangene: List[VergangeneResponse]
    min_teilnehmende: int = MIN_TEILNEHMENDE
    aktueller_wortlaut: WortlautResponse
    # Spielgefuehl-Modell (Schalter spielgefuehl_buehne): Teilnahme und Name waehlt
    # die Person dort (/api/v1/usage/users/me/spielgefuehl), nicht hier
    buehne: bool = False


class EinwilligungRequest(BaseModel):
    teilnehmen: bool
    mit_anzeigename: bool = False
    wortlaut: str


def _frage_angeboten(settings: Settings) -> bool:
    # Im Spielgefuehl-Modell gibt es die eigene Frage zur Rangliste nicht mehr.
    return schalter_wirksam("rangliste", settings) and not buehne_aktiv(settings)


def _dienst_oder_aus(
    settings: Settings = Depends(get_settings),
) -> Optional[RanglisteService]:
    """Fuer den Abruf: ohne Schalter None statt 404."""
    if not schalter_wirksam("rangliste", settings):
        return None
    return get_rangliste_service()


def _wortlaut() -> WortlautResponse:
    return WortlautResponse(
        kennung=AKTUELLER_WORTLAUT, text=WORTLAUTE[AKTUELLER_WORTLAUT]
    )


def _aus() -> StandResponse:
    """Schalter aus: nichts gefragt, nichts zu zeigen, ohne Datenbankabfrage."""
    return StandResponse(
        aktiv=False,
        gefragt=False,
        teilnehmen=None,
        mit_anzeigename=False,
        voraussetzungen=False,
        ranglistenname=None,
        anzeigename=None,
        saison=None,
        eigene_punkte=None,
        rangliste=None,
        vergangene=[],
        aktueller_wortlaut=_wortlaut(),
    )


def _platz(platz: Platz) -> PlatzResponse:
    return PlatzResponse(
        platz=platz.platz,
        name=platz.name,
        punkte=platz.punkte,
        ich=platz.ich,
        abzeichen=platz.abzeichen,
    )


@router.get("", response_model=StandResponse)
async def stand(
    current_user: str = Depends(require_user),
    dienst: Optional[RanglisteService] = Depends(_dienst_oder_aus),
    settings: Settings = Depends(get_settings),
) -> StandResponse:
    if dienst is None:
        return _aus()
    try:
        stand = await dienst.stand(current_user)
    except Exception as e:
        logger.error(
            f"Rangliste fuer {log_pseudonym(current_user)} nicht berechnet: {type(e).__name__}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    antwort = stand.antwort
    return StandResponse(
        gefragt=antwort is not None,
        teilnehmen=antwort.teilnehmen if antwort else None,
        mit_anzeigename=bool(antwort and antwort.mit_anzeigename),
        voraussetzungen=stand.voraussetzungen,
        ranglistenname=stand.ranglistenname,
        anzeigename=stand.anzeigename,
        saison=(
            SaisonResponse(name=stand.saison.name, ende=stand.saison.ende)
            if stand.saison
            else None
        ),
        eigene_punkte=stand.eigene_punkte,
        rangliste=(
            RanglisteResponse(
                oben=[_platz(p) for p in stand.rangliste.oben],
                eigener=(
                    _platz(stand.rangliste.eigener) if stand.rangliste.eigener else None
                ),
                teilnehmende=stand.rangliste.teilnehmende,
            )
            if stand.rangliste
            else None
        ),
        vergangene=[
            VergangeneResponse(name=v.name, punkte=v.punkte) for v in stand.vergangene
        ],
        aktueller_wortlaut=_wortlaut(),
        buehne=buehne_aktiv(settings),
    )


@router.put("/einwilligung", status_code=204)
async def einwilligung(
    request: EinwilligungRequest,
    current_user: str = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    """
    Ja oder Nein zur Rangliste, jederzeit aenderbar; ein Nein wirkt beim naechsten
    Abruf jeder Rangliste. Ein Ja nur zum aktuellen Wortlaut und nur, solange die
    Frage angeboten wird (sonst 409); ein Nein immer, auch bei ausgeschaltetem
    Schalter und im Spielgefuehl-Modell (dort stuft es ``rangliste`` auf ``fuer_mich``).
    """
    if request.teilnehmen and not _frage_angeboten(settings):
        raise HTTPException(status_code=409, detail="Not active")
    try:
        if request.teilnehmen:
            await asyncio.to_thread(
                get_rangliste_service().antworten,
                current_user,
                True,
                request.mit_anzeigename,
                request.wortlaut,
            )
        else:
            await asyncio.to_thread(
                rangliste_service.nein, current_user, request.wortlaut
            )
    except UnbekannterWortlaut:
        raise HTTPException(status_code=422, detail="Unbekannter Wortlaut")
    except Exception as e:
        logger.error(
            f"Einwilligung Rangliste fuer {log_pseudonym(current_user)} nicht gespeichert: {type(e).__name__}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    return Response(status_code=204)
