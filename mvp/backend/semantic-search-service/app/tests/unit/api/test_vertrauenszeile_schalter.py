"""
Schalter "vertrauenszeile" (Zeile ueber den Anmeldewegen, vorlaeufige juristische
Einschaetzung 26.11.2026): steht in GET /api/v1/funktionen ohne Anmeldung, ohne
Admin-Wert aus, mit Admin-Wert und Obergrenze an. Die Obergrenze ist von Haus aus aus
(Grundsatz 26.11.: Neues hinter einem Schalter, Standard aus), die Admin-Seite nennt
die Bedingung der Einschaetzung.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.funktionen import router as funktionen_router
from core.config import Settings
from dependencies import get_settings
from services.schalter_service import (
    GRUNDFUNKTIONEN,
    SCHALTER,
    ObergrenzeAus,
    SchalterService,
    oeffentliche_schalter,
    schalter_service_setzen,
)

pytestmark = pytest.mark.unit

URL = "/api/v1/funktionen"
NAME = "vertrauenszeile"
HINWEIS = (
    "Satz stimmt nur, solange Rangliste/Team-Fortschritt aus oder freiwillig sind; "
    "mit Vorstands-Go ergänzen."
)


@pytest.fixture
def werte():
    """Eigener Dienst ohne Eintraege: Admin-Werte gelten als aus."""
    werte = {}
    schalter_service_setzen(
        SchalterService(
            admin_werte_lesen=lambda: dict(werte),
            admin_wert_setzen=lambda name, an, admin: werte.__setitem__(name, an),
        )
    )
    yield werte
    schalter_service_setzen(None)


def _client(**obergrenzen) -> TestClient:
    app = FastAPI()
    app.include_router(funktionen_router, prefix=URL)
    app.dependency_overrides[get_settings] = lambda: Settings(**obergrenzen)
    return TestClient(app)


def test_registriert_mit_umgebungsvariable_gruppe_und_hinweis():
    art = SCHALTER[NAME]

    assert art.feld == "vertrauenszeile_aktiv"
    assert art.umgebungsvariable == "SEMANTIC_SEARCH_VERTRAUENSZEILE_AKTIV"
    assert art.gruppe == GRUNDFUNKTIONEN
    assert art.einschalt_hinweis == HINWEIS
    assert art.rechtlich_freigegeben is False
    assert NAME in oeffentliche_schalter()


def test_obergrenze_von_haus_aus_aus():
    """Der Standard im Code, unabhaengig von der Umgebung der Entwicklerin."""
    assert Settings.model_fields["vertrauenszeile_aktiv"].default is False


def test_admin_seite_zeigt_wartet_auf_recht():
    dienst = SchalterService(admin_werte_lesen=lambda: {}, admin_wert_setzen=None)
    stand = {s.name: s for s in dienst.stand(Settings(vertrauenszeile_aktiv=False))}[
        NAME
    ]

    assert (stand.obergrenze, stand.admin_wert, stand.wirksam) == (False, False, False)
    assert stand.dsfa_hinweis == HINWEIS
    assert stand.wartet_auf_recht is True


def test_einschalten_ueber_die_obergrenze_geht_nicht(werte):
    dienst = SchalterService(
        admin_werte_lesen=lambda: dict(werte),
        admin_wert_setzen=lambda name, an, admin: werte.__setitem__(name, an),
    )

    with pytest.raises(ObergrenzeAus):
        dienst.setzen(NAME, True, "admin-1", Settings(vertrauenszeile_aktiv=False))


def test_ohne_anmeldung_lesbar_obergrenze_aus_schlaegt_admin_wert(werte):
    werte[NAME] = True

    antwort = _client(vertrauenszeile_aktiv=False).get(URL)

    assert antwort.status_code == 200
    assert antwort.json()["funktionen"][NAME] is False


def test_ohne_admin_wert_aus(werte):
    antwort = _client(vertrauenszeile_aktiv=True).get(URL)

    assert antwort.status_code == 200
    assert antwort.json()["funktionen"][NAME] is False


def test_an_mit_obergrenze_und_admin_wert(werte):
    werte[NAME] = True

    antwort = _client(vertrauenszeile_aktiv=True).get(URL)

    assert antwort.json()["funktionen"][NAME] is True
