"""
GET /api/v1/funktionen (#756): der wirksame Wert der oeffentlichen Schalter, ohne
Anmeldung. Ohne Admin-Wert aus, mit Admin-Wert und Obergrenze an, ohne Obergrenze aus.

Seit dem Schalter-Umbau (27.11.2026): genau die vier Pakete und die oeffentlichen
Einzelschalter, dazu drei Basisfunktionen mit Not-Aus (Standard an, ohne Admin-Wert).
Die frueheren Teil-Schalter und die uebrigen Basisfunktionen stehen nicht mehr darin.
"""

from datetime import date
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.funktionen import router as funktionen_router
from core.config import Settings
from dependencies import get_settings
from services.schalter_service import SchalterService, schalter_service_setzen

pytestmark = pytest.mark.unit

URL = "/api/v1/funktionen"

PAKETE = ("teams", "spielgefuehl_buehne", "wirkungs_echo", "k_begruessung")
GEMELDET = {
    *PAKETE,
    "team_quests",
    "team_live",
    "muster_stimmen",
    "teams_oeffentlich",
    "merkliste",
    "danke_ohne_konto",
    "k_ankuenfte",
    "gepostet_ohne_konto",
    "null_treffer_anzahl",
    "feedback_gestoert",
    # Hinweis zum Einladungslink waehrend der BDK (services/bdk_hinweis.py)
    "bdk_hinweis",
}
ALLE_OBERGRENZEN = dict(
    teams_aktiv=True,
    spielgefuehl_buehne_aktiv=True,
    wirkungs_echo_aktiv=True,
    k_begruessung_aktiv=True,
    team_quests_aktiv=True,
    team_live_aktiv=True,
    muster_stimmen_aktiv=True,
    teams_oeffentlich_aktiv=True,
    merkliste_aktiv=True,
    danke_ohne_konto_aktiv=True,
    k_ankuenfte_aktiv=True,
)


@pytest.fixture
def werte():
    """Eigener Dienst ohne Eintraege."""
    werte = {}
    schalter_service_setzen(
        SchalterService(
            admin_werte_lesen=lambda: dict(werte),
            admin_wert_setzen=lambda name, an, admin: werte.__setitem__(name, an),
            # Ohne Cache: Die Tests aendern Admin-Werte zwischen zwei Abrufen
            cache_sekunden=0,
        )
    )
    yield werte
    schalter_service_setzen(None)


def _funktionen(**obergrenzen) -> dict:
    app = FastAPI()
    app.include_router(funktionen_router, prefix=URL)
    app.dependency_overrides[get_settings] = lambda: Settings(**obergrenzen)
    antwort = TestClient(app).get(URL)
    assert antwort.status_code == 200
    return antwort.json()["funktionen"]


def test_genau_diese_namen(werte):
    assert set(_funktionen()) == GEMELDET


def test_bdk_hinweis_aus_dem_dienst(werte):
    """Paket und Zeitfenster prueft services/bdk_hinweis.py (test_bdk_hinweis.py)."""
    with patch("api.v1.funktionen.bdk_hinweis_an", return_value=True):
        assert _funktionen(**ALLE_OBERGRENZEN)["bdk_hinweis"] is True
    with patch("api.v1.funktionen.bdk_hinweis_an", return_value=False):
        assert _funktionen(**ALLE_OBERGRENZEN)["bdk_hinweis"] is False


def test_ohne_admin_wert_alle_schalter_aus_not_aus_an(werte):
    funktionen = _funktionen(**ALLE_OBERGRENZEN)

    assert {n for n, an in funktionen.items() if an} == {
        "gepostet_ohne_konto",
        "null_treffer_anzahl",
        "feedback_gestoert",
    }


@pytest.mark.parametrize("paket", PAKETE)
def test_paket_an_nur_mit_admin_wert_und_obergrenze(werte, paket):
    werte[paket] = True

    assert _funktionen(**ALLE_OBERGRENZEN)[paket] is True
    assert _funktionen()[paket] is False


@pytest.mark.parametrize(
    "schalter, paket",
    [
        ("team_quests", "teams"),
        ("team_live", "teams"),
        ("teams_oeffentlich", "teams"),
        ("muster_stimmen", "spielgefuehl_buehne"),
        ("danke_ohne_konto", "wirkungs_echo"),
    ],
)
def test_einzelschalter_mit_paket_an_ohne_paket_aus(werte, schalter, paket):
    werte[schalter] = True
    assert _funktionen(**ALLE_OBERGRENZEN)[schalter] is False

    werte[paket] = True
    assert _funktionen(**ALLE_OBERGRENZEN)[schalter] is True


def test_admin_werte_frueherer_teile_zaehlen_nicht(werte):
    werte.update(
        punkte=True,
        rangliste=True,
        team_fortschritt=True,
        teamlink_vertrauenssatz=True,
        danke_knopf=True,
        saal_spruch=True,
    )

    funktionen = _funktionen(**ALLE_OBERGRENZEN)

    for paket in PAKETE:
        assert funktionen[paket] is False
    assert not {"punkte", "rangliste", "danke_knopf", "saal_spruch"} & set(funktionen)


@pytest.mark.parametrize(
    "name", ["gepostet_ohne_konto", "null_treffer_anzahl", "feedback_gestoert"]
)
def test_not_aus_false_meldet_aus(werte, name):
    assert _funktionen()[name] is True
    assert _funktionen(**{f"{name}_aktiv": False})[name] is False


def test_feedback_gestoert_ab_dem_stichtag_aus(werte):
    with patch("services.feedback_service.heute_utc", return_value=date(2026, 12, 31)):
        assert _funktionen()["feedback_gestoert"] is False
    with patch("services.feedback_service.heute_utc", return_value=date(2026, 12, 30)):
        assert _funktionen()["feedback_gestoert"] is True


def test_herkunft_pruefen_und_aufrufe_nicht_oeffentlich(werte):
    funktionen = _funktionen(aufrufe_zaehlen_aktiv=True)

    assert "herkunft_pruefen" not in funktionen
    assert "aufrufe_zaehlen" not in funktionen
