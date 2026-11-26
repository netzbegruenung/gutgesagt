"""
Was die angemeldete Person noch widerrufen kann, unabhaengig von den Schaltern
(Art. 7 Abs. 3 DSGVO: Widerruf so einfach wie die Einwilligung, jederzeit). Fuer die
Zeilen "… · Ausschalten" auf der Seite Datenschutz-Einstellungen (frontend
einwilligung/widerrufbar.component.ts), auch wenn die Schalter aus sind und die
Fragen selbst nicht erscheinen.

- ``GET /users/me/widerrufbar``: je gespeicherter Antwort, die kein Nein bzw. ``aus``
  ist, ihr Wortlaut (zum Mitschicken beim Widerruf; ein unbekannter wird durch den
  aktuellen ersetzt); sonst null. Immer 200, auch bei
  ausgeschalteten Schaltern (die Seite fragt beim Oeffnen, ein 404 zaehlte fuer den
  Gateway-fail2ban, docs/ARCHITECTURE.md). Gezeigt wird kein Ja und nichts zum
  Einwilligen; widerrufen wird ueber die bisherigen ``PUT``-Endpunkte, die ein Nein
  immer annehmen.

Gelesen wird die gespeicherte Antwort, nicht ob sie wirkt: Auch ein Ja zu einem
frueheren Wortlaut oder im gerade nicht geltenden Modell laesst sich zuruecknehmen.
"""

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.fehler import INTERNER_FEHLER
from core.logging import get_logger, log_pseudonym
from dependencies import require_user
from domain import abzeichen_sichtbarkeit, punkte_einwilligung, rangliste
from domain.spielgefuehl import AKTUELLER_WORTLAUT, WORTLAUTE, Stufe

logger = get_logger(__name__)

router = APIRouter()


class GespeichertesJa(BaseModel):
    # Der Wortlaut der gespeicherten Antwort; der Widerruf schickt ihn mit.
    wortlaut: str


class GespeicherteStufe(BaseModel):
    stufe: Stufe
    # Der Name der Stufe aus dem Wortlaut, wie die Frage ihn nennt (eine Quelle)
    titel: str
    wortlaut: str


def _bekannt(wortlaut: str, bekannte, aktueller: str) -> str:
    """
    Der Wortlaut zum Mitschicken: der gespeicherte, wenn der Endpunkt ihn kennt, sonst
    der aktuelle. Ein Nein nehmen die Endpunkte zu jedem bekannten Wortlaut an; ein
    unbekannter (etwa nach einem Zurueckrollen) liesse den Widerruf mit 422 scheitern.
    """
    return wortlaut if wortlaut in bekannte else aktueller


def _titel(stufe: Stufe, wortlaut: str) -> str:
    texte = WORTLAUTE.get(wortlaut) or WORTLAUTE[AKTUELLER_WORTLAUT]
    text = texte.stufen.get(stufe) or WORTLAUTE[AKTUELLER_WORTLAUT].stufen[stufe]
    return text.titel


class WiderrufbarResponse(BaseModel):
    # Spielgefuehl: null bei keiner Antwort oder Stufe aus
    spielgefuehl: Optional[GespeicherteStufe] = None
    # Bisheriges Modell: je null bei keiner Antwort oder einem Nein
    punkte: Optional[GespeichertesJa] = None
    rangliste: Optional[GespeichertesJa] = None
    abzeichen: Optional[GespeichertesJa] = None


def _lesen(user_id: str) -> WiderrufbarResponse:
    from repositories.abzeichen_sichtbarkeit_repository import (
        get_abzeichen_sichtbarkeit_repository,
    )
    from repositories.punkte_einwilligung_repository import (
        get_punkte_einwilligung_repository,
    )
    from repositories.rangliste_einwilligung_repository import (
        get_rangliste_einwilligung_repository,
    )
    from repositories.spielgefuehl_repository import get_spielgefuehl_repository

    spielgefuehl = get_spielgefuehl_repository().lesen(user_id)
    punkte = get_punkte_einwilligung_repository().lesen(user_id)
    rangliste_antwort = get_rangliste_einwilligung_repository().lesen(user_id)
    abzeichen = get_abzeichen_sichtbarkeit_repository().lesen(user_id)
    return WiderrufbarResponse(
        spielgefuehl=(
            GespeicherteStufe(
                stufe=spielgefuehl.stufe,
                titel=_titel(spielgefuehl.stufe, spielgefuehl.wortlaut),
                # "aus" geht zu jedem bekannten Wortlaut; ein unbekannter (spaetere
                # Fassung) wird durch den aktuellen ersetzt, damit der Widerruf klappt.
                wortlaut=_bekannt(spielgefuehl.wortlaut, WORTLAUTE, AKTUELLER_WORTLAUT),
            )
            if spielgefuehl is not None and spielgefuehl.stufe is not Stufe.AUS
            else None
        ),
        punkte=(
            GespeichertesJa(
                wortlaut=_bekannt(
                    punkte.wortlaut,
                    punkte_einwilligung.WORTLAUTE,
                    punkte_einwilligung.AKTUELLER_WORTLAUT,
                )
            )
            if punkte is not None and punkte.eingewilligt
            else None
        ),
        rangliste=(
            GespeichertesJa(
                wortlaut=_bekannt(
                    rangliste_antwort.wortlaut,
                    rangliste.WORTLAUTE,
                    rangliste.AKTUELLER_WORTLAUT,
                )
            )
            if rangliste_antwort is not None and rangliste_antwort.teilnehmen
            else None
        ),
        abzeichen=(
            GespeichertesJa(
                wortlaut=_bekannt(
                    abzeichen.wortlaut,
                    abzeichen_sichtbarkeit.WORTLAUTE,
                    abzeichen_sichtbarkeit.AKTUELLER_WORTLAUT,
                )
            )
            if abzeichen is not None and abzeichen.zeigen
            else None
        ),
    )


@router.get("/users/me/widerrufbar", response_model=WiderrufbarResponse)
async def widerrufbar(
    current_user: str = Depends(require_user),
) -> WiderrufbarResponse:
    try:
        return await asyncio.to_thread(_lesen, current_user)
    except Exception as e:
        logger.error(
            f"Widerrufbares fuer {log_pseudonym(current_user)} nicht gelesen: {type(e).__name__}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=INTERNER_FEHLER)
