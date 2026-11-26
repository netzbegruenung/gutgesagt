"""
Ankuenfte je Kampagnenwort und Tag: ``POST /api/v1/ankunft`` zaehlt nur mit Schalter und
nur Woerter der Positivliste, antwortet beim Laden nie 401 oder 404 (#824), gibt weder
Kennung noch Adresse an den Dienst; ``GET /api/v1/ankuenfte`` nur fuer Admins.
"""

from datetime import date
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1 import ankunft as ankunft_modul
from api.v1.ankunft import admin_router, router
from core.config import Settings
from dependencies import get_ankunft_rate_limiter, get_settings
from services.ankunft_service import AnkuenfteAmTag, get_ankunft_service
from utils.rate_limiter import RateLimiter

pytestmark = pytest.mark.unit

PFAD = "/api/v1/ankunft"
ADMIN_PFAD = "/api/v1/ankuenfte"
ADMIN = {"X-User": "admin-1", "X-Is-Admin": "true"}


def _client(dienst, limiter=None, **einstellungen):
    app = FastAPI()
    app.include_router(router, prefix=PFAD)
    app.include_router(admin_router, prefix=ADMIN_PFAD)
    werte = dict(k_ankuenfte_aktiv=True)
    werte.update(einstellungen)
    app.dependency_overrides[get_settings] = lambda: Settings(**werte)
    app.dependency_overrides[get_ankunft_service] = lambda: dienst
    drossel = limiter or RateLimiter(max_requests=100, window_seconds=1)
    app.dependency_overrides[get_ankunft_rate_limiter] = lambda: drossel
    return TestClient(app), app


@pytest.fixture
def dienst():
    return Mock()


def test_erlaubtes_wort_zaehlt_je_aufruf(dienst):
    client, _ = _client(dienst)

    for _ in range(2):
        antwort = client.post(PFAD, json={"k": "sticker"})
        assert antwort.status_code == 200
        assert antwort.json() == {"gezaehlt": True}

    # Nur das Wort: weder Person noch Adresse gehen an den Dienst.
    assert [a.args for a in dienst.zaehlen.call_args_list] == [
        ("sticker",),
        ("sticker",),
    ]
    assert all(a.kwargs == {} for a in dienst.zaehlen.call_args_list)


def test_gross_geschrieben_zaehlt_klein(dienst):
    client, _ = _client(dienst)

    client.post(PFAD, json={"k": " BDK "})

    dienst.zaehlen.assert_called_once_with("bdk")


def test_angemeldete_zaehlen_ohne_kennung(dienst):
    """Die Kennung liest der Endpunkt nicht; gezaehlt wird nur das Wort."""
    client, _ = _client(dienst)

    antwort = client.post(PFAD, json={"k": "g1"}, headers={"X-User": "kim-1"})

    assert antwort.json() == {"gezaehlt": True}
    dienst.zaehlen.assert_called_once_with("g1")


@pytest.mark.parametrize("wort", ["unbekannt", "g5", "sticker2", "../g1"])
def test_wort_ausserhalb_der_positivliste_200_ohne_zaehlen(dienst, wort):
    client, _ = _client(dienst)

    antwort = client.post(PFAD, json={"k": wort})

    assert antwort.status_code == 200
    assert antwort.json() == {"gezaehlt": False}
    dienst.zaehlen.assert_not_called()


def test_positivliste_aus_der_konfiguration(dienst):
    client, _ = _client(dienst, k_woerter="stand, Flyer")

    assert client.post(PFAD, json={"k": "flyer"}).json() == {"gezaehlt": True}
    assert client.post(PFAD, json={"k": "sticker"}).json() == {"gezaehlt": False}


def test_obergrenze_aus_200_ohne_zaehlen(dienst):
    """Beim Laden ohne Zutun gefragt: nie 404 (CODING_STANDARDS.md "Endpoints")."""
    client, _ = _client(dienst, k_ankuenfte_aktiv=False)

    antwort = client.post(PFAD, json={"k": "sticker"})

    assert antwort.status_code == 200
    assert antwort.json() == {"gezaehlt": False}
    dienst.zaehlen.assert_not_called()


def test_admin_wert_aus_200_ohne_zaehlen(dienst, schalter_admin_alle_an):
    schalter_admin_alle_an["k_ankuenfte"] = False
    client, _ = _client(dienst)

    antwort = client.post(PFAD, json={"k": "sticker"})

    assert antwort.status_code == 200
    assert antwort.json() == {"gezaehlt": False}
    dienst.zaehlen.assert_not_called()


def test_drosselung_mit_einem_schluessel_fuer_alle(dienst):
    limiter = RateLimiter(max_requests=2, window_seconds=1)
    client, _ = _client(dienst, limiter)

    codes = [
        client.post(
            PFAD, json={"k": "bdk"}, headers={"X-Forwarded-For": f"203.0.113.{i}"}
        ).status_code
        for i in range(3)
    ]

    assert codes == [200, 200, 429]
    assert set(limiter._requests) == {ankunft_modul.DROSSEL_SCHLUESSEL}


@pytest.mark.parametrize(
    "body",
    [
        {"k": "bdk", "beitrag_id": "11111111-1111-4111-8111-111111111111"},
        {"k": "bdk", "kennung": "x"},
        {"k": ""},
        {"k": "x" * 41},
        {},
    ],
)
def test_nur_das_wort_im_body(dienst, body):
    client, _ = _client(dienst)

    assert client.post(PFAD, json=body).status_code == 422
    dienst.zaehlen.assert_not_called()


def test_fehler_beim_zaehlen_500(dienst):
    dienst.zaehlen.side_effect = RuntimeError("weg")
    client, _ = _client(dienst)

    assert client.post(PFAD, json={"k": "bdk"}).status_code == 500


def test_pfad_ohne_wort_und_ohne_query():
    _, app = _client(Mock())
    schema = app.openapi()["paths"]

    orte = {p["in"] for p in schema[PFAD]["post"].get("parameters", [])}
    assert orte <= {"header"}


def test_echte_einbindung():
    from main import app

    pfade = {
        r.path: r.methods
        for r in app.routes
        if getattr(r, "path", "").startswith(("/api/v1/ankunft", "/api/v1/ankuenfte"))
    }
    assert pfade == {PFAD: {"POST"}, ADMIN_PFAD: {"GET"}}


class TestAdminUebersicht:
    def test_nur_admins(self, dienst):
        client, _ = _client(dienst)

        assert client.get(ADMIN_PFAD, headers={"X-User": "kim-1"}).status_code == 403
        dienst.letzte_tage.assert_not_called()

    def test_zahlen_je_tag_und_wort(self, dienst):
        dienst.letzte_tage.return_value = [
            AnkuenfteAmTag(tag=date(2026, 12, 4), k="bdk", anzahl=12),
            AnkuenfteAmTag(tag=date(2026, 12, 3), k="sticker", anzahl=3),
        ]
        client, _ = _client(dienst)

        antwort = client.get(ADMIN_PFAD, headers=ADMIN)

        assert antwort.status_code == 200
        assert antwort.json() == {
            "aktiv": True,
            "tage": [
                {"tag": "2026-12-04", "k": "bdk", "anzahl": 12},
                {"tag": "2026-12-03", "k": "sticker", "anzahl": 3},
            ],
        }

    def test_schalter_aus_leer(self, dienst):
        client, _ = _client(dienst, k_ankuenfte_aktiv=False)

        antwort = client.get(ADMIN_PFAD, headers=ADMIN)

        assert antwort.status_code == 200
        assert antwort.json() == {"aktiv": False, "tage": []}
        dienst.letzte_tage.assert_not_called()
