"""
Saisons ueber die API (#782): Balken ohne Anmeldung nur mit Schalter und nur Summen,
Pflege nur fuer Admins mit 409/422 aus den Regeln, Hinweis an der Einstellung
"aktuelle Saison", solange eine Saison laeuft. Repository als Attrappe.
"""

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.saisons import admin_router, router
from api.v1.schalter import router as schalter_router
from core.config import Settings
from dependencies import get_settings
from domain.saisons import Saison, SaisonUeberschneidung
from services.saison_service import SaisonService, saison_service_setzen
from utils.utc_tag import heute_utc, wochenbeginn

pytestmark = [pytest.mark.unit, pytest.mark.api]

ADMIN = {"X-User": "admin", "X-Is-Admin": "true"}
PERSON = {"X-User": "konto-1"}
HEUTE = heute_utc()
LAUFEND = Saison(
    uuid.uuid4(),
    "Winter 26",
    HEUTE - timedelta(days=30),
    HEUTE + timedelta(days=30),
    1000,
)
# Drei abgeschlossene Wochen mit je 30 Menschen vor der laufenden
STARK = {wochenbeginn(HEUTE) - timedelta(weeks=i): 30 for i in range(1, 4)}


@pytest.fixture
def repository():
    return MagicMock()


def _client(repository, wirksam=True, zahlen=None, saisons=(LAUFEND,)):
    repository.alle.return_value = list(saisons)
    saison_service_setzen(
        SaisonService(
            repository,
            lambda von, laufende: dict(zahlen if zahlen is not None else STARK),
            einstellungen=Settings(),
            wirksam=lambda _s: wirksam,
        )
    )
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/saisons")
    app.include_router(admin_router, prefix="/api/v1/moderation/saisons")
    app.include_router(schalter_router, prefix="/api/v1/moderation/schalter")
    app.dependency_overrides[get_settings] = lambda: Settings()
    return TestClient(app)


class TestAktuell:
    def test_schalter_aus_200_ohne_balken(self, repository):
        # Kein 404: Die Startseite fragt bei jedem Aufruf, und das Gateway sperrt eine
        # IP nach 50 Antworten 404 (Saal-WLAN, docs/ARCHITECTURE.md).
        antwort = _client(repository, wirksam=False).get("/api/v1/saisons/aktuell")
        assert antwort.status_code == 200
        assert antwort.json() == {"balken": None, "aktiv": False}
        repository.alle.assert_not_called()

    def test_balken_nur_summen(self, repository):
        antwort = _client(repository).get("/api/v1/saisons/aktuell")
        assert antwort.status_code == 200
        balken = antwort.json()["balken"]
        assert set(balken) == {"name", "ziel", "erreicht"}
        assert balken["name"] == "Winter 26"
        assert balken["ziel"] == 1000
        # Nur Wochen der Saison (seit 30 Tagen): hoechstens die drei starken
        assert 0 < balken["erreicht"] <= 90

    def test_unter_der_schwelle_null(self, repository):
        antwort = _client(repository, zahlen={}).get("/api/v1/saisons/aktuell")
        assert antwort.status_code == 200
        assert antwort.json() == {"balken": None, "aktiv": True}


class TestAdmin:
    def test_nur_admins(self, repository):
        client = _client(repository)
        assert (
            client.get("/api/v1/moderation/saisons", headers=PERSON).status_code == 403
        )
        assert (
            client.post(
                "/api/v1/moderation/saisons",
                headers=PERSON,
                json={"name": "X", "beginn": str(HEUTE), "ende": str(HEUTE), "ziel": 5},
            ).status_code
            == 403
        )
        repository.anlegen.assert_not_called()

    def test_liste(self, repository):
        antwort = _client(repository, zahlen={}).get(
            "/api/v1/moderation/saisons", headers=ADMIN
        )
        assert antwort.status_code == 200
        daten = antwort.json()
        assert daten["schalter_wirksam"] is True
        assert daten["schwelle_erreicht"] is False
        assert daten["schwelle_menschen"] == 25
        assert daten["schwelle_wochen"] == 3
        [saison] = daten["saisons"]
        assert saison["zustand"] == "laufend"
        assert saison["laufende_woche"] == 0

    def test_anlegen(self, repository):
        client = _client(repository)
        repository.anlegen.return_value = LAUFEND
        antwort = client.post(
            "/api/v1/moderation/saisons",
            headers=ADMIN,
            json={
                "name": " Frühjahr  27 ",
                "beginn": str(HEUTE + timedelta(days=31)),
                "ende": str(HEUTE + timedelta(days=90)),
                "ziel": 500,
            },
        )
        assert antwort.status_code == 201
        eingabe = repository.anlegen.call_args.args[0]
        assert eingabe.name == "Frühjahr 27"

    def test_ueberschneidung_409(self, repository):
        client = _client(repository)
        repository.anlegen.side_effect = SaisonUeberschneidung("Winter 26")
        antwort = client.post(
            "/api/v1/moderation/saisons",
            headers=ADMIN,
            json={"name": "X", "beginn": str(HEUTE), "ende": str(HEUTE), "ziel": 5},
        )
        assert antwort.status_code == 409
        assert "Winter 26" in antwort.json()["detail"]

    @pytest.mark.parametrize(
        "werte",
        [
            {"ziel": 0},
            {"name": ""},
            {"ende": str(HEUTE - timedelta(days=1))},
        ],
    )
    def test_ungueltig_422(self, repository, werte):
        client = _client(repository)
        daten = {"name": "X", "beginn": str(HEUTE), "ende": str(HEUTE), "ziel": 5}
        daten.update(werte)
        antwort = client.post("/api/v1/moderation/saisons", headers=ADMIN, json=daten)
        assert antwort.status_code == 422
        repository.anlegen.assert_not_called()

    def test_rueckwirkend_409(self, repository):
        client = _client(repository)
        gestern = str(HEUTE - timedelta(days=1))
        antwort = client.post(
            "/api/v1/moderation/saisons",
            headers=ADMIN,
            json={"name": "X", "beginn": gestern, "ende": str(HEUTE), "ziel": 5},
        )
        assert antwort.status_code == 409

    def test_laufende_loeschen_409(self, repository):
        client = _client(repository)
        repository.loeschen.side_effect = lambda saison_id, pruefen: pruefen(LAUFEND)
        antwort = client.delete(
            f"/api/v1/moderation/saisons/{LAUFEND.id}", headers=ADMIN
        )
        assert antwort.status_code == 409


class TestHinweisAnDerEinstellung:
    def _hinweis(self, client):
        antwort = client.get("/api/v1/moderation/schalter", headers=ADMIN)
        [einstellung] = [
            e for e in antwort.json()["einstellungen"] if e["name"] == "aktuelle_saison"
        ]
        return einstellung["hinweis"]

    def test_laufende_saison_ersetzt_die_einstellung(self, repository):
        assert "Winter 26" in self._hinweis(_client(repository))

    def test_schalter_aus_hinweis_trotzdem(self, repository):
        assert "Winter 26" in self._hinweis(_client(repository, wirksam=False))

    def test_ohne_laufende_saison_kein_hinweis(self, repository):
        assert self._hinweis(_client(repository, saisons=())) is None
