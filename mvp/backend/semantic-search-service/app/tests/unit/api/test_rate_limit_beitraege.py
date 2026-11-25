"""
Das Anlegen von Beitraegen ist je Person gedrosselt (RateLimitMiddleware).

Der Post hat mit #297 ein Formular bekommen und zaehlt damit zu den Wegen, auf
denen jemand schnell viele Beitraege anlegen kann.

Startkonten sind ausgenommen (Import des Startbestands), Admins nicht.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.config import Settings
from middleware.rate_limit import RateLimitMiddleware


def _client(pfad: str, **einstellungen) -> TestClient:
    app = FastAPI()
    konfig = Settings(**einstellungen)
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=2,
        requests_per_hour=3,
        einstellungen=lambda: konfig,
    )

    @app.post(pfad)
    async def anlegen():
        return {"ok": True}

    return TestClient(app)


@pytest.mark.parametrize(
    "pfad",
    [
        "/api/v1/post/addPost",
        "/api/v1/commentary/addCommentary",
        "/api/v1/statement/vorab",
    ],
)
def test_anlegen_ueber_dem_limit_ist_429(pfad):
    client = _client(pfad)
    kopf = {"X-User": "alice"}

    antworten = [client.post(pfad, headers=kopf).status_code for _ in range(3)]

    assert antworten == [200, 200, 429]


def test_andere_person_hat_ein_eigenes_limit():
    pfad = "/api/v1/post/addPost"
    client = _client(pfad)
    for _ in range(2):
        client.post(pfad, headers={"X-User": "alice"})

    assert client.post(pfad, headers={"X-User": "bob"}).status_code == 200


@pytest.mark.parametrize(
    "pfad",
    [
        "/api/v1/commentary/addCommentary",
        "/api/v1/generic_text/addGenericText",
        "/api/v1/statement/addStatement",
    ],
)
def test_startkonto_wird_nicht_gedrosselt(pfad):
    client = _client(pfad, startkonten="redaktion, andere")

    antworten = {
        client.post(pfad, headers={"X-User": "redaktion"}).status_code
        for _ in range(10)
    }

    assert antworten == {200}


def test_normales_konto_wird_weiter_gedrosselt():
    pfad = "/api/v1/commentary/addCommentary"
    client = _client(pfad, startkonten="redaktion")
    kopf = {"X-User": "alice"}

    antworten = [client.post(pfad, headers=kopf).status_code for _ in range(3)]

    assert antworten == [200, 200, 429]


def test_admin_wird_weiter_gedrosselt():
    pfad = "/api/v1/commentary/addCommentary"
    client = _client(pfad, startkonten="redaktion", admin_users="chefin")
    kopf = {"X-User": "chefin", "X-Is-Admin": "true"}

    antworten = [client.post(pfad, headers=kopf).status_code for _ in range(3)]

    assert antworten == [200, 200, 429]


def test_ohne_kennung_kein_startkonto():
    pfad = "/api/v1/commentary/addCommentary"
    client = _client(pfad, startkonten="anonymous")

    antworten = [client.post(pfad).status_code for _ in range(3)]

    assert antworten == [200, 200, 429]


def test_startkonto_auch_ueber_dem_stundenlimit():
    """Das Stundenlimit (hier 3) haelt den Import nicht auf."""
    pfad = "/api/v1/commentary/addCommentary"
    app = FastAPI()
    konfig = Settings(startkonten="redaktion")
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=100,
        requests_per_hour=3,
        einstellungen=lambda: konfig,
    )
    app.add_api_route(pfad, lambda: {"ok": True}, methods=["POST"])
    client = TestClient(app)

    start = [
        client.post(pfad, headers={"X-User": "redaktion"}).status_code for _ in range(5)
    ]
    andere = [
        client.post(pfad, headers={"X-User": "alice"}).status_code for _ in range(4)
    ]

    assert start == [200] * 5
    assert andere == [200, 200, 200, 429]
