"""
GET /api/v1/konter-probe (#786): Proben fuer die Konter-Probe, ohne Anmeldung.

Hinter dem Schalter konter_probe: aus heisst leer mit aktiv false. Besucher sehen weder Anzeigenamen
noch Kennungen (wie "Diese Woche oft genutzt").
"""

import uuid
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1 import konter_probe as modul
from api.v1.konter_probe import router
from dependencies import get_settings
from repositories.varianten_repository import get_varianten_repository
from services.konter_probe_service import KonterProbe

URL = "/api/v1/konter-probe"
AUTORIN = "kim-1"
AUSSAGE = uuid.UUID("00000000-0000-4000-8000-0000000000aa")


def _beitrag(nummer: int, stil: str, nutzung: int) -> dict:
    return {
        "id": f"00000000-0000-4000-8000-00000000000{nummer}",
        "result_type": "commentary",
        "content_type": "commentary",
        "title": f"Titel {nummer}",
        "text": f"Text {nummer}",
        "style": stil,
        "created": "2026-10-20T10:00:00",
        "status": "visible",
        "original_author": AUTORIN,
        "last_modified_by": AUTORIN,
        "authors": [{"name": AUTORIN}],
        "edit_history": [],
        "usage_count": nutzung,
    }


def _client(an: bool, proben):
    app = FastAPI()
    app.include_router(router, prefix=URL)
    app.dependency_overrides[get_settings] = lambda: Mock()
    varianten = Mock()
    varianten.anzahl_je_original.return_value = {}
    app.dependency_overrides[get_varianten_repository] = lambda: varianten

    service = Mock()

    async def liefern():
        return proben

    service.proben = liefern
    return (
        patch.multiple(
            modul,
            schalter_wirksam=Mock(return_value=an),
            get_konter_probe_service=Mock(return_value=service),
            get_reference_service=Mock(),
        ),
        TestClient(app),
    )


@pytest.fixture
def namen(anzeigenamen_ohne_datenbank):
    anzeigenamen_ohne_datenbank.anzeigenamen.return_value = {AUTORIN: "Kim L."}
    return anzeigenamen_ohne_datenbank


@pytest.mark.unit
class TestKonterProbeApi:
    def test_schalter_aus_leer(self):
        # 200 statt 404: Die Startseite fragt automatisch (Gateway-fail2ban)
        patcher, client = _client(False, [])
        with patcher:
            antwort = client.get(URL)
        assert antwort.status_code == 200
        assert antwort.json() == {"proben": [], "aktiv": False}

    def test_ohne_passende_aussage_leer(self):
        patcher, client = _client(True, [])
        with patcher:
            antwort = client.get(URL)
        assert antwort.status_code == 200
        assert antwort.json() == {"proben": [], "aktiv": True}

    def test_probe_besucher_ohne_namen_mit_nutzung(self, namen):
        probe = KonterProbe(
            statement_id=AUSSAGE,
            text="Spruch",
            antworten=[
                _beitrag(1, "sachlich", 2),
                _beitrag(2, "humorvoll", 7),
                _beitrag(3, "persoenlich", 1),
            ],
        )
        patcher, client = _client(True, [probe])
        with patcher:
            antwort = client.get(URL)

        assert antwort.status_code == 200
        [eintrag] = antwort.json()["proben"]
        assert eintrag["aussage"] == {"id": str(AUSSAGE), "text": "Spruch"}
        antworten = eintrag["antworten"]
        assert [(a["title"], a["style"], a["usage_count"]) for a in antworten] == [
            ("Titel 1", "sachlich", 2),
            ("Titel 2", "humorvoll", 7),
            ("Titel 3", "persoenlich", 1),
        ]
        assert {a["result_type"] for a in antworten} == {"commentary"}
        assert {a["original_author"] for a in antworten} == {None}
        assert {a["autor_name"] for a in antworten} == {None}

    def test_fehler_500(self):
        patcher, client = _client(True, [])
        with patcher:
            with patch.object(
                modul, "get_konter_probe_service", Mock(side_effect=RuntimeError)
            ):
                antwort = client.get(URL)
        assert antwort.status_code == 500
