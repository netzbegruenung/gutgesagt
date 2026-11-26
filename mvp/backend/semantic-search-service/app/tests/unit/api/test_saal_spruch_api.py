"""
Saal-Spruch ueber die API: ``GET /heute`` ohne Anmeldung, nie 404, bei Schalter aus leer
mit ``aktiv: false``; Pflege nur fuer Admins, auch bei Schalter aus. Speicher als Attrappe.
"""

from datetime import date
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1 import saal_spruch as modul
from api.v1.saal_spruch import admin_router, router
from services.saal_spruch_service import SaalSpruchService, saal_spruch_service_setzen

pytestmark = [pytest.mark.unit, pytest.mark.api]

ADMIN = {"X-User": "admin", "X-Is-Admin": "true"}
PERSON = {"X-User": "konto-1"}
HEUTE = date(2026, 12, 4)
HEUTE_URL = "/api/v1/saal-spruch/heute"
ADMIN_URL = "/api/v1/moderation/saal-sprueche"


@pytest.fixture
def speicher():
    daten = {}
    saal_spruch_service_setzen(
        SaalSpruchService(
            fuer_tag=daten.get,
            ab=lambda t: {d: s for d, s in sorted(daten.items()) if d >= t},
            setzen=daten.__setitem__,
            loeschen=lambda t: daten.pop(t, None),
            heute=lambda: HEUTE,
            cache_sekunden=0,
        )
    )
    yield daten
    saal_spruch_service_setzen(None)


def _client(an: bool):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/saal-spruch")
    app.include_router(admin_router, prefix=ADMIN_URL)
    return patch.object(modul, "schalter_wirksam", return_value=an), TestClient(app)


def test_schalter_aus_leer_und_nie_404(speicher):
    speicher[HEUTE] = "Das bringt doch nichts"
    schalter, client = _client(False)
    with schalter:
        antwort = client.get(HEUTE_URL)

    assert antwort.status_code == 200
    assert antwort.json() == {"spruch": None, "aktiv": False}


def test_schalter_an_heutiger_spruch(speicher):
    speicher[HEUTE] = "Das bringt doch nichts"
    schalter, client = _client(True)
    with schalter:
        antwort = client.get(HEUTE_URL)

    assert antwort.status_code == 200
    assert antwort.json() == {"spruch": "Das bringt doch nichts", "aktiv": True}


def test_schalter_an_ohne_spruch_200_leer(speicher):
    speicher[date(2026, 12, 5)] = "erst morgen"
    schalter, client = _client(True)
    with schalter:
        antwort = client.get(HEUTE_URL)

    assert antwort.status_code == 200
    assert antwort.json() == {"spruch": None, "aktiv": True}


def test_pflege_nur_fuer_admins(speicher):
    schalter, client = _client(True)
    with schalter:
        assert client.get(ADMIN_URL, headers=PERSON).status_code == 403
        assert (
            client.put(
                f"{ADMIN_URL}/2026-12-05", json={"text": "x"}, headers=PERSON
            ).status_code
            == 403
        )
        assert (
            client.delete(f"{ADMIN_URL}/2026-12-05", headers=PERSON).status_code == 403
        )
    assert speicher == {}


def test_festlegen_auch_bei_schalter_aus(speicher):
    schalter, client = _client(False)
    with schalter:
        antwort = client.put(
            f"{ADMIN_URL}/2026-12-05",
            json={"text": "  Klimaschutz\n kostet nur "},
            headers=ADMIN,
        )

    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["sprueche"] == [
        {"datum": "2026-12-05", "text": "Klimaschutz kostet nur"}
    ]
    assert daten["schalter_wirksam"] is False
    assert daten["heute"] == "2026-12-04"
    assert daten["text_max"] == 200


def test_festlegen_ungueltig_422(speicher):
    schalter, client = _client(True)
    with schalter:
        leer = client.put(f"{ADMIN_URL}/2026-12-05", json={"text": "  "}, headers=ADMIN)
        vergangen = client.put(
            f"{ADMIN_URL}/2026-12-03", json={"text": "gestern"}, headers=ADMIN
        )
        zu_lang = client.put(
            f"{ADMIN_URL}/2026-12-05", json={"text": "x" * 201}, headers=ADMIN
        )

    assert leer.status_code == 422
    assert vergangen.status_code == 422
    assert "vergangene" in vergangen.json()["detail"]
    assert zu_lang.status_code == 422
    assert speicher == {}


def test_entfernen(speicher):
    speicher[date(2026, 12, 5)] = "weg"
    schalter, client = _client(True)
    with schalter:
        antwort = client.delete(f"{ADMIN_URL}/2026-12-05", headers=ADMIN)
        liste = client.get(ADMIN_URL, headers=ADMIN)

    assert antwort.status_code == 204
    assert liste.json()["sprueche"] == []
