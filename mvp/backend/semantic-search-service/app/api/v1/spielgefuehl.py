"""
Spielgefuehl als eine Einstellung in drei Stufen (domain/spielgefuehl.py,
services/spielgefuehl_service.py), unter /api/v1/usage, nur fuer die angemeldete
Person selbst (``X-User``).

Angeboten wird die Frage nur, wenn die Schalter ``spielgefuehl_buehne`` und ``punkte``
wirken; sonst antwortet ``GET`` mit 200 und ``aktiv: false`` ohne Datenbankabfrage
(die Seite fragt automatisch, ein 404 je Abruf sperrte am Gateway ein Saal-WLAN,
docs/ARCHITECTURE.md), ``POST`` mit 404. ``PUT`` nimmt einen Widerruf auch dann an
(``aus`` immer, ``fuer_mich`` aus Stufe ``rangliste``; Art. 7 Abs. 3 DSGVO: so einfach
wie die Einwilligung, jederzeit) und lehnt nur ein Heraufstufen ab (409).

- ``GET /users/me/spielgefuehl``: die gewaehlte Stufe (null: noch keine Antwort im
  neuen Modell, die App fragt), die Namenswahl, der Ranglistenname, der Wortlaut und
  ob der einmalige Hinweis zu den Abzeichen faellig ist.
- ``PUT /users/me/spielgefuehl``: eine Stufe waehlen, jederzeit; Herabstufen wirkt
  sofort und geht auch ohne Schalter. Stufe rangliste nur mit Namenswahl.
- ``POST /users/me/spielgefuehl/ranglistenname``: einen neuen Zufallsnamen wuerfeln
  (nur mit Stufe rangliste, 409 sonst; hoechstens einmal je 10 s, 429 sonst); eine
  neue Nachweiszeile.

Stufe rangliste gibt es nur, solange der Schalter ``rangliste`` wirkt: Sonst fehlt sie
in der Frage, und ``PUT`` nimmt sie nicht an (422). Niemand willigt in eine Rangliste
ein, die es nicht gibt.
"""

import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from core.config import Settings
from core.fehler import INTERNER_FEHLER
from core.logging import get_logger, log_pseudonym
from dependencies import get_settings, require_user
from domain.spielgefuehl import (
    AKTUELLER_WORTLAUT,
    HINWEIS_ABZEICHEN_NUR_RANGLISTE,
    NAMENS_VORBELEGUNG,
    REIHENFOLGE,
    WORTLAUTE,
    NamenswahlFehlt,
    Stufe,
    UnbekannterWortlaut,
)
from services.schalter_service import schalter_wirksam
from services.spielgefuehl_service import (
    NichtInRangliste,
    SpielgefuehlService,
    ZuOftGewuerfelt,
    buehne_aktiv,
    get_spielgefuehl_service,
)

logger = get_logger(__name__)

router = APIRouter()


class StufeResponse(BaseModel):
    stufe: Stufe
    titel: str
    text: str


class NamenswahlResponse(BaseModel):
    frage: str
    anzeigename: str
    zufallsname: str
    tipp: str
    # null: keine Vorbelegung, die Person waehlt aktiv
    vorbelegung_anzeigename: Optional[bool]


class WortlautResponse(BaseModel):
    kennung: str
    ueberschrift: str
    einleitung: str
    # In der Reihenfolge der Knoepfe: Gemeinschaft zuerst
    stufen: List[StufeResponse]
    # Direkt unter den Stufen: Einwilligung in den Schutz gegen Absprachen
    absprachen: str
    namenswahl: NamenswahlResponse
    fuss: str


class SpielgefuehlResponse(BaseModel):
    # false: Schalter aus; dann ist nichts gefragt und alles andere ohne Bedeutung
    aktiv: bool = True
    # null: noch keine Antwort im neuen Modell
    stufe: Optional[Stufe] = None
    # Nur bei Stufe rangliste: Anzeigename (true) oder Zufallsname (false)
    mit_anzeigename: Optional[bool] = None
    ranglistenname: Optional[str] = None
    # Der Anzeigename, wie er gespeichert ist; null ohne
    anzeigename: Optional[str] = None
    # Einmaliger Satz fuer Konten, die bisher Abzeichen am Namen gezeigt haben
    abzeichen_hinweis: Optional[str] = None
    aktueller_wortlaut: WortlautResponse


class SpielgefuehlRequest(BaseModel):
    stufe: Stufe
    # Pflicht bei Stufe rangliste (keine Vorbelegung), sonst ohne Bedeutung
    mit_anzeigename: Optional[bool] = None
    wortlaut: str


class RanglistennameResponse(BaseModel):
    ranglistenname: str


def _angeboten(settings: Settings) -> bool:
    return buehne_aktiv(settings) and schalter_wirksam("punkte", settings)


def _dienst(settings: Settings = Depends(get_settings)) -> SpielgefuehlService:
    if not _angeboten(settings):
        raise HTTPException(status_code=404, detail="Not found")
    return get_spielgefuehl_service()


def _rangliste_angeboten(settings: Settings) -> bool:
    return schalter_wirksam("rangliste", settings)


def _wortlaut(mit_rangliste: bool = True) -> WortlautResponse:
    wortlaut = WORTLAUTE[AKTUELLER_WORTLAUT]
    return WortlautResponse(
        kennung=AKTUELLER_WORTLAUT,
        ueberschrift=wortlaut.ueberschrift,
        einleitung=wortlaut.einleitung,
        stufen=[
            StufeResponse(
                stufe=stufe,
                titel=wortlaut.stufen[stufe].titel,
                text=wortlaut.stufen[stufe].text,
            )
            for stufe in REIHENFOLGE
            if mit_rangliste or stufe is not Stufe.RANGLISTE
        ],
        absprachen=wortlaut.absprachen,
        namenswahl=NamenswahlResponse(
            frage=wortlaut.namenswahl_frage,
            anzeigename=wortlaut.namenswahl_anzeigename,
            zufallsname=wortlaut.namenswahl_zufallsname,
            tipp=wortlaut.namenswahl_tipp,
            vorbelegung_anzeigename=NAMENS_VORBELEGUNG,
        ),
        fuss=wortlaut.fuss,
    )


@router.get("/users/me/spielgefuehl", response_model=SpielgefuehlResponse)
async def spielgefuehl(
    current_user: str = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> SpielgefuehlResponse:
    if not _angeboten(settings):
        return SpielgefuehlResponse(aktiv=False, aktueller_wortlaut=_wortlaut())
    from services.anzeigename_service import get_anzeigename_service

    try:
        stand, namen = await asyncio.gather(
            asyncio.to_thread(get_spielgefuehl_service().stand, current_user),
            asyncio.to_thread(get_anzeigename_service().namen, [current_user]),
        )
    except Exception as e:
        logger.error(
            f"Spielgefuehl fuer {log_pseudonym(current_user)} nicht gelesen: {type(e).__name__}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    return SpielgefuehlResponse(
        stufe=stand.stufe,
        mit_anzeigename=stand.mit_anzeigename,
        ranglistenname=stand.ranglistenname,
        anzeigename=namen.get(current_user),
        abzeichen_hinweis=(
            HINWEIS_ABZEICHEN_NUR_RANGLISTE if stand.abzeichen_hinweis else None
        ),
        aktueller_wortlaut=_wortlaut(_rangliste_angeboten(settings)),
    )


@router.put("/users/me/spielgefuehl", status_code=204)
async def spielgefuehl_waehlen(
    request: SpielgefuehlRequest,
    current_user: str = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    dienst = get_spielgefuehl_service()
    if not _angeboten(settings):
        # Ohne Schalter nur ein Widerruf; "aus" ohne Datenbankabfrage.
        try:
            widerruf = await asyncio.to_thread(
                dienst.herabstufung, current_user, request.stufe
            )
        except Exception as e:
            logger.error(
                f"Spielgefuehl fuer {log_pseudonym(current_user)} nicht gelesen: {type(e).__name__}",
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
        if not widerruf:
            raise HTTPException(status_code=409, detail="Not active")
    elif request.stufe is Stufe.RANGLISTE and not _rangliste_angeboten(settings):
        raise HTTPException(status_code=422, detail="Stufe nicht angeboten")
    try:
        await asyncio.to_thread(
            dienst.antworten,
            current_user,
            request.stufe,
            request.mit_anzeigename,
            request.wortlaut,
        )
    except UnbekannterWortlaut:
        raise HTTPException(status_code=422, detail="Unbekannter Wortlaut")
    except NamenswahlFehlt:
        raise HTTPException(status_code=422, detail="Namenswahl fehlt")
    except Exception as e:
        logger.error(
            f"Spielgefuehl fuer {log_pseudonym(current_user)} nicht gespeichert: {type(e).__name__}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    return Response(status_code=204)


@router.post(
    "/users/me/spielgefuehl/ranglistenname", response_model=RanglistennameResponse
)
async def neu_wuerfeln(
    current_user: str = Depends(require_user),
    dienst: SpielgefuehlService = Depends(_dienst),
) -> RanglistennameResponse:
    try:
        name = await asyncio.to_thread(dienst.neu_wuerfeln, current_user)
    except NichtInRangliste:
        raise HTTPException(status_code=409, detail="Nicht in der Rangliste")
    except ZuOftGewuerfelt:
        raise HTTPException(status_code=429, detail="Zu oft gewuerfelt")
    except Exception as e:
        logger.error(
            f"Ranglistenname fuer {log_pseudonym(current_user)} nicht gewuerfelt: {type(e).__name__}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
    return RanglistennameResponse(ranglistenname=name)
