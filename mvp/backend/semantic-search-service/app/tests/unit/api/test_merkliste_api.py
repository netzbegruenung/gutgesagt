"""
Merkliste (#758): nur mit Schalter, nur angemeldet, nur mit Art.-9-Einwilligung, nur
das eigene Konto. Ohne Schalter liefert der Abruf 200 mit ``aktiv: false``, Merken 404,
beides ohne Datenbank; Entfernen bleibt offen. Dazu der Schalter selbst in GET /api/v1/funktionen.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.v1.merkliste as merkliste_modul
from api.v1.funktionen import router as funktionen_router
from api.v1.merkliste import router as merkliste_router
from core.config import Settings
from dependencies import get_beitrag_laden, get_settings
from repositories.merkliste_repository import Gemerkt, MerklisteVoll
from services.schalter_service import SchalterService, schalter_service_setzen

pytestmark = pytest.mark.unit

URL = "/api/v1/merkliste"
KIM = {"X-User": "kim-1"}
BEITRAG = uuid.UUID("11111111-1111-4111-8111-111111111111")
UNBEKANNT = uuid.UUID("22222222-2222-4222-8222-222222222222")


GESPERRT = uuid.UUID("33333333-3333-4333-8333-333333333333")


@pytest.fixture
def suchindex(monkeypatch):
    """Zustand im Suchindex: BEITRAG sichtbar, GESPERRT gesperrt, UNBEKANNT fehlt."""
    index = Mock()

    async def zustaende_laden(ids):
        bekannt = {str(BEITRAG): "visible", str(GESPERRT): "blocked"}
        return {i: bekannt[i] for i in ids if i in bekannt}

    index.zustaende_laden = Mock(side_effect=zustaende_laden)
    monkeypatch.setattr(merkliste_modul, "get_moderation_repository", lambda: index)
    return index


@pytest.fixture
def merkliste(monkeypatch, art9_einwilligung_ohne_datenbank, suchindex):
    repo = Mock()
    repo.liste.return_value = [
        Gemerkt(BEITRAG, datetime(2026, 11, 22, 10, 0, tzinfo=timezone.utc))
    ]
    repo.entfernen.return_value = True
    monkeypatch.setattr(merkliste_modul, "get_merkliste_repository", lambda: repo)
    return repo


def _client(an: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(merkliste_router, prefix=URL)
    app.include_router(funktionen_router, prefix="/api/v1/funktionen")
    app.dependency_overrides[get_settings] = lambda: Settings(merkliste_aktiv=an)

    async def laden(content_id):
        return SimpleNamespace(id=content_id) if content_id == BEITRAG else None

    app.dependency_overrides[get_beitrag_laden] = lambda: laden
    return TestClient(app)


def test_liste_der_eigenen_person(merkliste):
    antwort = _client().get(URL, headers=KIM)

    assert antwort.status_code == 200
    assert antwort.json() == {
        "aktiv": True,
        "eintraege": [
            {
                "content_id": str(BEITRAG),
                "gemerkt_am": "2026-11-22T10:00:00Z",
                "sichtbar": True,
            }
        ],
    }
    merkliste.liste.assert_called_once_with("kim-1")


def test_gesperrte_und_entfernte_als_nicht_sichtbar_mit_einer_abfrage(
    merkliste, suchindex
):
    zeit = datetime(2026, 11, 22, 10, 0, tzinfo=timezone.utc)
    merkliste.liste.return_value = [
        Gemerkt(BEITRAG, zeit),
        Gemerkt(GESPERRT, zeit),
        Gemerkt(UNBEKANNT, zeit),
    ]

    eintraege = _client().get(URL, headers=KIM).json()["eintraege"]

    assert [e["sichtbar"] for e in eintraege] == [True, False, False]
    suchindex.zustaende_laden.assert_called_once()


def test_suchindex_weg_liste_laedt_trotzdem(merkliste, suchindex):
    suchindex.zustaende_laden.side_effect = RuntimeError("Qdrant weg")

    antwort = _client().get(URL, headers=KIM)

    assert antwort.status_code == 200
    assert antwort.json()["eintraege"][0]["sichtbar"] is None


def test_merken_eines_sichtbaren_beitrags(merkliste):
    antwort = _client().put(f"{URL}/{BEITRAG}", headers=KIM)

    assert antwort.status_code == 204
    merkliste.merken.assert_called_once_with("kim-1", BEITRAG)


def test_merken_eines_unbekannten_beitrags_404(merkliste):
    antwort = _client().put(f"{URL}/{UNBEKANNT}", headers=KIM)

    assert antwort.status_code == 404
    merkliste.merken.assert_not_called()


def test_volle_merkliste_409(merkliste):
    merkliste.merken.side_effect = MerklisteVoll("kim-1")

    antwort = _client().put(f"{URL}/{BEITRAG}", headers=KIM)

    assert antwort.status_code == 409
    assert "voll" in antwort.json()["detail"]


def test_entfernen(merkliste):
    antwort = _client().delete(f"{URL}/{BEITRAG}", headers=KIM)

    assert antwort.status_code == 204
    merkliste.entfernen.assert_called_once_with("kim-1", BEITRAG)


def test_ohne_schalter_unsichtbar_ohne_datenbank(
    merkliste, art9_einwilligung_ohne_datenbank
):
    client = _client(an=False)

    abruf = client.get(URL, headers=KIM)
    assert abruf.status_code == 200
    assert abruf.json() == {"aktiv": False, "eintraege": []}
    assert client.put(f"{URL}/{BEITRAG}", headers=KIM).status_code == 404
    merkliste.liste.assert_not_called()
    merkliste.merken.assert_not_called()
    art9_einwilligung_ohne_datenbank.lesen.assert_not_called()


def test_ohne_schalter_entfernen_bleibt_offen(
    merkliste, art9_einwilligung_ohne_datenbank
):
    """Was in einer Zeit „an“ gemerkt wurde, kann die Person immer selbst zuruecknehmen."""
    antwort = _client(an=False).delete(f"{URL}/{BEITRAG}", headers=KIM)

    assert antwort.status_code == 204
    merkliste.entfernen.assert_called_once_with("kim-1", BEITRAG)
    art9_einwilligung_ohne_datenbank.lesen.assert_not_called()


def test_ohne_admin_wert_aus(merkliste):
    """Obergrenze an, Admin-Wert aus (Standard): die Funktion gibt es nicht."""
    schalter_service_setzen(
        SchalterService(admin_werte_lesen=dict, admin_wert_setzen=Mock())
    )
    try:
        client = _client()
        assert client.get(URL, headers=KIM).json()["aktiv"] is False
        assert client.put(f"{URL}/{BEITRAG}", headers=KIM).status_code == 404
        assert (
            client.get("/api/v1/funktionen").json()["funktionen"]["merkliste"] is False
        )
    finally:
        schalter_service_setzen(None)


def test_schalter_an_in_funktionen(merkliste):
    assert _client().get("/api/v1/funktionen").json()["funktionen"]["merkliste"] is True


@pytest.mark.parametrize("kopf", [{}, {"X-User": "anonymous"}])
def test_besucher_401(merkliste, kopf):
    assert _client().get(URL, headers=kopf).status_code == 401
    assert _client().put(f"{URL}/{BEITRAG}", headers=kopf).status_code == 401
    merkliste.merken.assert_not_called()


def test_ohne_einwilligung_403(merkliste, art9_einwilligung_ohne_datenbank):
    art9_einwilligung_ohne_datenbank.lesen.return_value = None

    client = _client()
    assert client.put(f"{URL}/{BEITRAG}", headers=KIM).status_code == 403
    assert client.get(URL, headers=KIM).status_code == 403
    merkliste.merken.assert_not_called()
    merkliste.liste.assert_not_called()


def test_obergrenze_standard_aus_und_hinweis_auf_der_admin_seite():
    from services.schalter_service import EINZELSCHALTER, SCHALTER

    assert Settings().merkliste_aktiv is False
    art = SCHALTER["merkliste"]
    assert art.gruppe == EINZELSCHALTER
    assert not art.rechtlich_freigegeben
    for teil in ("Einwilligungswortlaut", "DSFA", "DSE"):
        assert teil in art.einschalt_hinweis
