"""
Seitenaufrufe und Besucher je Tag (#761): Zaehlen ohne Anmeldung, nur mit Schalter;
gespeichert wird nur das Tagespseudonym, nie die Adresse. Admins sehen Tageszahlen.
Ohne Datenbank: das Repository ist ersetzt; gegen PostgreSQL pruefen
tests/integration/test_aufrufe_repository.py.
"""

import asyncio
from datetime import date
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.v1.aufrufe as modul
from core.config import Settings
from dependencies import get_settings
from repositories.aufrufe_repository import AufrufTag
from services import aufrufe_service
from services.schalter_service import SchalterService, schalter_service_setzen
from utils.besucher_pseudonym import besucher_tagespseudonym

pytestmark = pytest.mark.unit

URL = "/api/v1/aufrufe"
ADMIN = {"X-User": "admin-1", "X-Is-Admin": "true"}
ADRESSE = {"X-Real-IP": "203.0.113.7"}
HEUTE = date(2026, 11, 22)


@pytest.fixture
def werte(schalter_admin_alle_an):
    werte = {"aufrufe_zaehlen": True}
    schalter_service_setzen(
        SchalterService(
            admin_werte_lesen=lambda: dict(werte),
            admin_wert_setzen=lambda n, a, w: werte.__setitem__(n, a),
        )
    )
    return werte


@pytest.fixture
def repo():
    r = Mock()
    r.heute.return_value = AufrufTag(tag=HEUTE, aufrufe=9, besucher=4)
    r.tage.return_value = [AufrufTag(tag=date(2026, 11, 21), aufrufe=30, besucher=12)]
    return r


def _client(repo, obergrenze=True):
    app = FastAPI()
    app.include_router(modul.router, prefix=URL)
    app.dependency_overrides[get_settings] = lambda: Settings(
        aufrufe_zaehlen_aktiv=obergrenze
    )
    app.dependency_overrides[modul._repository] = lambda: repo
    return TestClient(app)


class TestZaehlen:
    def test_an_zaehlt_mit_pseudonym_ohne_adresse(self, werte, repo, monkeypatch):
        monkeypatch.setattr(aufrufe_service, "heute_utc", lambda: HEUTE)
        antwort = _client(repo).post(f"{URL}/zaehlen", headers=ADRESSE)

        assert antwort.status_code == 204
        tag, pseudonym = repo.zaehlen.call_args.args
        assert tag == HEUTE
        assert len(pseudonym) == 64 and "203.0.113" not in pseudonym
        assert pseudonym == aufrufe_service.aufruf_pseudonym("203.0.113.7", HEUTE)

    def test_ohne_anmeldung_und_ohne_inhalt(self, werte, repo):
        assert _client(repo).post(f"{URL}/zaehlen").status_code == 204

    @pytest.mark.parametrize(
        "obergrenze, admin_wert", [(True, False), (False, True), (False, False)]
    )
    def test_aus_404_nichts_gespeichert(self, werte, repo, obergrenze, admin_wert):
        werte["aufrufe_zaehlen"] = admin_wert
        antwort = _client(repo, obergrenze).post(f"{URL}/zaehlen", headers=ADRESSE)

        assert antwort.status_code == 404
        assert repo.method_calls == []

    def test_fehler_beim_speichern_kostet_nur_den_aufruf(self, werte, repo):
        repo.zaehlen.side_effect = RuntimeError("weg")
        assert _client(repo).post(f"{URL}/zaehlen", headers=ADRESSE).status_code == 204


class TestTageszahlen:
    def test_nur_fuer_admins(self, werte, repo):
        client = _client(repo)
        assert client.get(URL).status_code == 401
        assert client.get(URL, headers={"X-User": "p-1"}).status_code == 403

    def test_an_heute_und_vergangene_tage(self, werte, repo):
        daten = _client(repo).get(URL, headers=ADMIN).json()

        assert daten["aktiv"] is True
        assert daten["heute"]["aufrufe"] == 9 and daten["heute"]["besucher"] == 4
        assert daten["tage"] == [{"tag": "2026-11-21", "aufrufe": 30, "besucher": 12}]

    def test_aus_nichts_sichtbar(self, werte, repo):
        werte["aufrufe_zaehlen"] = False
        daten = _client(repo).get(URL, headers=ADMIN).json()

        assert daten == {"aktiv": False, "heute": None, "tage": []}
        assert repo.method_calls == []


class TestPseudonym:
    def test_anderer_raum_als_an_suchereignissen(self):
        """Dasselbe Merkmal am selben Tag ergibt ein anderes Pseudonym als bei der Suche."""
        assert aufrufe_service.aufruf_pseudonym(
            "203.0.113.7", HEUTE
        ) != besucher_tagespseudonym("203.0.113.7", HEUTE)

    def test_gleicher_besucher_gleicher_tag_gleiches_pseudonym(self):
        a = aufrufe_service.aufruf_pseudonym("203.0.113.7", HEUTE)
        assert a == aufrufe_service.aufruf_pseudonym("203.0.113.7", HEUTE)
        assert a != aufrufe_service.aufruf_pseudonym("203.0.113.8", HEUTE)


def test_verdichten_im_takt_laeuft_und_loggt_fehler_ohne_details(caplog):
    repo = Mock()
    repo.verdichten_vor.side_effect = [3, RuntimeError("geheim")]

    async def lauf():
        aufgabe = asyncio.create_task(
            aufrufe_service.verdichten_im_takt(
                repo, takt_sekunden=0.01, heute=lambda: HEUTE
            )
        )
        await asyncio.sleep(0.05)
        aufgabe.cancel()

    asyncio.run(lauf())

    assert repo.verdichten_vor.call_args_list[0].args == (HEUTE,)
    assert "geheim" not in caplog.text
