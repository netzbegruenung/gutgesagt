"""
Meldungen ohne Konto (#799) am neutralen Sammelpfad ``POST /api/v1/ereignis``: nur mit
Schalter (der nur mit "Ja, gepostet" wirkt), je Klick +1, Angemeldete zaehlen hier
nicht, Drosselung im Sekundenfenster ohne Adresse, die Art steht nur im Body.
"""

import asyncio
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1 import ereignis as ereignis_modul
from api.v1.ereignis import router as ereignis_router
from core.config import Settings
from dependencies import get_ereignis_rate_limiter, get_settings
from services.gepostet_ohne_konto_service import get_gepostet_ohne_konto_service
from utils.rate_limiter import RateLimiter

pytestmark = pytest.mark.unit

PFAD = "/api/v1/ereignis"
ART = {"art": "gepostet_ohne_konto"}
BESUCHER = {"X-User": "anonymous"}


def _client(dienst, limiter=None, **schalter):
    app = FastAPI()
    app.include_router(ereignis_router, prefix=PFAD)
    werte = dict(gepostet_aktiv=True, gepostet_ohne_konto_aktiv=True)
    werte.update(schalter)
    app.dependency_overrides[get_settings] = lambda: Settings(**werte)
    app.dependency_overrides[get_gepostet_ohne_konto_service] = lambda: dienst
    drossel = limiter or RateLimiter(max_requests=100, window_seconds=1)
    app.dependency_overrides[get_ereignis_rate_limiter] = lambda: drossel
    return TestClient(app), app


@pytest.fixture
def dienst():
    return Mock()


def test_besucher_zaehlt_je_klick(dienst):
    client, _ = _client(dienst)

    for _ in range(3):
        antwort = client.post(PFAD, json=ART, headers=BESUCHER)
        assert antwort.status_code == 200
        assert antwort.json() == {"gezaehlt": True}

    assert dienst.melden.call_count == 3
    # Ohne Argument: weder Adresse noch Person noch Beitrag gehen an den Dienst.
    for aufruf in dienst.melden.call_args_list:
        assert aufruf.args == () and aufruf.kwargs == {}


def test_ohne_kopfzeile_wie_besucher(dienst):
    client, _ = _client(dienst)

    assert client.post(PFAD, json=ART).json() == {"gezaehlt": True}
    dienst.melden.assert_called_once_with()


@pytest.mark.parametrize(
    "schalter",
    [
        dict(gepostet_ohne_konto_aktiv=False),
        # Unterschalter: ohne "Ja, gepostet" auch keine Meldungen ohne Konto
        dict(gepostet_aktiv=False),
    ],
)
def test_schalter_aus_404_und_nichts_gezaehlt(dienst, schalter):
    client, _ = _client(dienst, **schalter)

    antwort = client.post(PFAD, json=ART, headers=BESUCHER)

    assert antwort.status_code == 404
    dienst.melden.assert_not_called()


def test_admin_wert_aus_404(dienst, schalter_admin_alle_an):
    schalter_admin_alle_an["gepostet_ohne_konto"] = False
    client, _ = _client(dienst)

    assert client.post(PFAD, json=ART).status_code == 404
    dienst.melden.assert_not_called()


def test_angemeldete_zaehlen_hier_nicht(dienst):
    """Sie zaehlen ueber /users/me/gepostet als Menschen, nicht zusaetzlich hier."""
    client, _ = _client(dienst)

    antwort = client.post(PFAD, json=ART, headers={"X-User": "kim-1"})

    assert antwort.json() == {"gezaehlt": False}
    dienst.melden.assert_not_called()


def test_drosselung_im_sekundenfenster(dienst):
    client, _ = _client(dienst, RateLimiter(max_requests=2, window_seconds=1))

    codes = [client.post(PFAD, json=ART).status_code for _ in range(3)]

    assert codes == [200, 200, 429]
    assert dienst.melden.call_count == 2


def test_drosselung_mit_einem_schluessel_fuer_alle(dienst):
    """Kein Schluessel aus Adresse oder Person: nur der feste Sammelschluessel."""
    limiter = RateLimiter(max_requests=100, window_seconds=1)
    client, _ = _client(dienst, limiter)

    client.post(PFAD, json=ART, headers={"X-Forwarded-For": "203.0.113.7"})
    client.post(PFAD, json=ART, headers={"X-Forwarded-For": "198.51.100.9"})

    assert set(limiter._requests) == {ereignis_modul.DROSSEL_SCHLUESSEL}


def test_drosselung_vergisst_nach_dem_fenster():
    limiter = RateLimiter(max_requests=1, window_seconds=0.05)

    async def lauf():
        assert await limiter.is_rate_limited("ereignis") is False
        assert await limiter.is_rate_limited("ereignis") is True
        await asyncio.sleep(0.1)
        return await limiter.is_rate_limited("ereignis")

    assert asyncio.run(lauf()) is False


@pytest.mark.parametrize(
    "body",
    [
        {
            "art": "gepostet_ohne_konto",
            "beitrag_id": "11111111-1111-4111-8111-111111111111",
        },
        {"art": "gepostet_ohne_konto", "content_id": "x"},
        {"art": "etwas_anderes"},
        {},
    ],
)
def test_nur_die_art_im_body(dienst, body):
    """Kein Beitrag, keine weiteren Felder: abgewiesen statt still verworfen."""
    client, _ = _client(dienst)

    assert client.post(PFAD, json=body).status_code == 422
    dienst.melden.assert_not_called()


def test_fehler_beim_zaehlen_500(dienst):
    dienst.melden.side_effect = RuntimeError("weg")
    client, _ = _client(dienst)

    assert client.post(PFAD, json=ART).status_code == 500


def test_pfad_enthaelt_keine_art():
    """Neutrale Adresse: die Art steht weder im Pfad noch in der Query."""
    _, app = _client(Mock())
    [route] = [r for r in app.routes if getattr(r, "path", "").startswith(PFAD)]
    schema = app.openapi()["paths"]

    assert route.path == PFAD
    for verboten in ("gepostet", "konto", "art", "beitrag"):
        assert verboten not in route.path.lower()
    # Nur die Kopfzeile X-User vom BFF; kein Pfad- und kein Query-Parameter.
    orte = {p["in"] for p in schema[PFAD]["post"].get("parameters", [])}
    assert orte <= {"header"}
    assert route.methods == {"POST"}
