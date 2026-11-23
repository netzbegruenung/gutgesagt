"""
Der Tagesdeckel an den Anlege-Routen (middleware/tagesdeckel.py): je Person hoechstens
so viele Anlagen am Tag, Admins und Startkonten ausgenommen, und nur was wirklich
etwas anlegt, zaehlt.
"""

import logging
from datetime import date

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from core.config import Settings
from middleware.rate_limit import RateLimitMiddleware
from middleware.tagesdeckel import (
    TAGESDECKEL_KENNUNG,
    TagesdeckelMiddleware,
    nichts_angelegt,
)
from utils.tagesdeckel import Tagesdeckel

pytestmark = pytest.mark.unit

GEZAEHLT = [
    "/api/v1/commentary/addCommentary",
    "/api/v1/generic_text/addGenericText",
    "/api/v1/post/addPost",
    "/api/v1/image/addImage",
    "/api/v1/rawinput/addRawInput",
    "/api/v1/statement/vorab",
    "/api/v1/statement/addStatement",
]


def _app(deckel: Tagesdeckel, **einstellungen) -> TestClient:
    app = FastAPI()
    konfig = Settings(**einstellungen)
    app.add_middleware(
        TagesdeckelMiddleware, deckel=deckel, einstellungen=lambda: konfig
    )

    for pfad in GEZAEHLT + ["/api/v1/reference/add"]:
        app.add_api_route(pfad, lambda: {"ok": True}, methods=["POST"])

    @app.post("/api/v1/commentary/kaputt/addCommentary")
    async def kaputt():
        raise HTTPException(status_code=422, detail="passt nicht")

    @app.post("/api/v1/generic_text/dublette/addGenericText")
    async def dublette(request: Request):
        nichts_angelegt(request)
        return {"vorhanden": True}

    return TestClient(app)


def _deckel(je_tag: int = 2) -> Tagesdeckel:
    return Tagesdeckel(je_tag, lambda: date(2026, 12, 4))


@pytest.mark.parametrize("pfad", GEZAEHLT)
def test_ueber_dem_deckel_kommt_429_mit_kennung(pfad):
    client = _app(_deckel())
    kopf = {"X-User": "alice"}

    antworten = [client.post(pfad, headers=kopf) for _ in range(3)]

    assert [a.status_code for a in antworten] == [200, 200, 429]
    assert antworten[2].json()["error"] == TAGESDECKEL_KENNUNG


def test_alle_anlege_routen_teilen_einen_deckel():
    client = _app(_deckel())
    kopf = {"X-User": "alice"}
    client.post("/api/v1/post/addPost", headers=kopf)
    client.post("/api/v1/rawinput/addRawInput", headers=kopf)

    assert client.post("/api/v1/statement/vorab", headers=kopf).status_code == 429


def test_herkunft_anlegen_zaehlt_nicht():
    """/reference/add laeuft mehrmals je Beitrag und hat ein eigenes Rate-Limit."""
    client = _app(_deckel(1))
    kopf = {"X-User": "alice"}
    for _ in range(3):
        assert client.post("/api/v1/reference/add", headers=kopf).status_code == 200

    assert client.post("/api/v1/post/addPost", headers=kopf).status_code == 200


def test_lesen_zaehlt_nicht():
    client = _app(_deckel(1))
    kopf = {"X-User": "alice"}
    client.get("/api/v1/post/addPost", headers=kopf)

    assert client.post("/api/v1/post/addPost", headers=kopf).status_code == 200


def test_gescheiterte_anfrage_zaehlt_nicht():
    client = _app(_deckel(1))
    kopf = {"X-User": "alice"}
    assert (
        client.post("/api/v1/commentary/kaputt/addCommentary", headers=kopf).status_code
        == 422
    )

    assert client.post("/api/v1/post/addPost", headers=kopf).status_code == 200


def test_dublette_zaehlt_nicht():
    client = _app(_deckel(1))
    kopf = {"X-User": "alice"}
    for _ in range(2):
        client.post("/api/v1/generic_text/dublette/addGenericText", headers=kopf)

    assert client.post("/api/v1/post/addPost", headers=kopf).status_code == 200


def test_admin_aus_dem_bff_kopf_ist_ausgenommen():
    client = _app(_deckel(1))
    kopf = {"X-User": "redaktion", "X-Is-Admin": "true"}

    antworten = [client.post("/api/v1/post/addPost", headers=kopf) for _ in range(3)]

    assert [a.status_code for a in antworten] == [200, 200, 200]


def test_admin_aus_der_konfiguration_ist_ausgenommen():
    client = _app(_deckel(1), admin_users="redaktion, andere")
    kopf = {"X-User": "redaktion"}

    antworten = [client.post("/api/v1/post/addPost", headers=kopf) for _ in range(3)]

    assert [a.status_code for a in antworten] == [200, 200, 200]


def test_startkonto_ist_ausgenommen():
    client = _app(_deckel(1), startkonten="import")
    kopf = {"X-User": "import"}

    antworten = [client.post("/api/v1/post/addPost", headers=kopf) for _ in range(3)]

    assert [a.status_code for a in antworten] == [200, 200, 200]


def test_ohne_kennung_zaehlt_nichts():
    deckel = _deckel(1)
    client = _app(deckel)
    client.post("/api/v1/post/addPost")
    client.post("/api/v1/post/addPost", headers={"X-User": "anonymous"})

    assert deckel._zaehler == {}


def test_das_log_nennt_nur_das_pseudonym(caplog):
    client = _app(_deckel(1))
    kopf = {"X-User": "alice@example.org"}
    client.post("/api/v1/post/addPost", headers=kopf)

    with caplog.at_level(logging.WARNING, logger="middleware.tagesdeckel"):
        client.post("/api/v1/post/addPost", headers=kopf)

    assert "Tagesdeckel erreicht" in caplog.text
    assert "alice" not in caplog.text


def test_lehnt_das_rate_limit_ab_bleibt_der_platz_frei():
    """In main.py liegt der Tagesdeckel aussen um das Rate-Limit."""
    app = FastAPI()
    app.add_api_route("/api/v1/post/addPost", lambda: {"ok": True}, methods=["POST"])
    app.add_middleware(RateLimitMiddleware, requests_per_minute=1)
    deckel = _deckel(5)
    app.add_middleware(TagesdeckelMiddleware, deckel=deckel)
    client = TestClient(app)
    kopf = {"X-User": "alice"}

    antworten = [client.post("/api/v1/post/addPost", headers=kopf) for _ in range(3)]

    assert [a.status_code for a in antworten] == [200, 429, 429]
    assert deckel._zaehler["alice"][1] == 1


def test_main_traegt_den_deckel_ein_und_raeumt_ihn_auf():
    import inspect

    import main

    assert any(m.cls is TagesdeckelMiddleware for m in main.app.user_middleware)
    assert "tagesdeckel," in inspect.getsource(main.lifespan)
