"""
Admin-API "Herkunft pruefen" (#759): nur fuer Admins; mit Schalter aus ``aktiv: false``
ohne Inhalt und kein Lauf (404), mit Schalter an der Stand und ein Lauf (202, 409).
Obergrenze und Admin-Wert getrennt: Beide muessen an sein.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.v1.herkunft_pruefen as modul
from core.config import Settings
from dependencies import get_settings
from repositories.herkunft_pruefung_repository import (
    HerkunftPruefung,
    HerkunftPruefungStand,
)
from services.schalter_service import SchalterService, schalter_service_setzen

pytestmark = pytest.mark.unit

URL = "/api/v1/herkunft-pruefen"
ADMIN = {"X-User": "admin-1", "X-Is-Admin": "true"}
ZEIT = datetime(2026, 11, 22, 3, 0, tzinfo=timezone.utc)


@pytest.fixture
def admin_werte(schalter_admin_alle_an):
    werte = {"herkunft_pruefen": True}
    schalter_service_setzen(
        SchalterService(
            admin_werte_lesen=lambda: dict(werte),
            admin_wert_setzen=lambda n, a, w: werte.__setitem__(n, a),
        )
    )
    return werte


@pytest.fixture
def dienst():
    d = Mock()
    d.laeuft = False
    d.anstossen.return_value = True
    d.stand = AsyncMock(
        return_value=HerkunftPruefungStand(
            geprueft=3,
            letzter_lauf=ZEIT,
            auffaellig_gesamt=1,
            auffaellig=[
                HerkunftPruefung(
                    herkunft_id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
                    adresse="https://a.example/weg",
                    ergebnis="tot",
                    http_status=404,
                    ziel=None,
                    geprueft_am=ZEIT,
                    auffaellig_seit=ZEIT,
                )
            ],
        )
    )
    return d


def _client(dienst, obergrenze=True):
    app = FastAPI()
    app.include_router(modul.router, prefix=URL)
    app.dependency_overrides[get_settings] = lambda: Settings(
        herkunft_pruefen_aktiv=obergrenze
    )
    app.dependency_overrides[modul._dienst] = lambda: dienst
    return TestClient(app)


def test_nur_fuer_admins(admin_werte, dienst):
    client = _client(dienst)
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers={"X-User": "p-1"}).status_code == 403
    assert client.post(f"{URL}/lauf", headers={"X-User": "p-1"}).status_code == 403
    dienst.anstossen.assert_not_called()


@pytest.mark.parametrize("obergrenze, admin_wert", [(False, True), (False, False)])
def test_aus_nichts_sichtbar_kein_lauf(admin_werte, dienst, obergrenze, admin_wert):
    admin_werte["herkunft_pruefen"] = admin_wert
    client = _client(dienst, obergrenze)

    antwort = client.get(URL, headers=ADMIN)
    assert antwort.status_code == 200
    assert antwort.json() == {
        "aktiv": False,
        "laeuft": False,
        "geprueft": 0,
        "letzter_lauf": None,
        "auffaellig_gesamt": 0,
        "auffaellig": [],
    }
    assert client.post(f"{URL}/lauf", headers=ADMIN).status_code == 404
    dienst.stand.assert_not_called()
    dienst.anstossen.assert_not_called()


def test_an_zeigt_stand(admin_werte, dienst):
    antwort = _client(dienst).get(URL, headers=ADMIN)

    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["aktiv"] is True and daten["geprueft"] == 3
    assert daten["auffaellig"][0]["adresse"] == "https://a.example/weg"
    assert daten["auffaellig"][0]["ergebnis"] == "tot"


def test_an_lauf_anstossen(admin_werte, dienst):
    client = _client(dienst)

    assert client.post(f"{URL}/lauf", headers=ADMIN).status_code == 202
    dienst.anstossen.return_value = False
    assert client.post(f"{URL}/lauf", headers=ADMIN).status_code == 409


def test_stand_fehler_500_ohne_details(admin_werte, dienst):
    dienst.stand.side_effect = RuntimeError("geheim")
    antwort = _client(dienst).get(URL, headers=ADMIN)

    assert antwort.status_code == 500
    assert "geheim" not in antwort.text
