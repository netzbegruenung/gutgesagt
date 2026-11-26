"""
Feedback an das Team (#343): POST /api/v1/feedback/senden, die Admin-Liste
GET /api/v1/feedback und fuer Admins Erledigt-Setzen und Einzelloeschen (#425).

Senden darf jede Person, auch ohne Anmeldung. Gespeichert wird nur, was sie
eingibt (Freitext, optional Kontakt), und der Tag; keine Kennung, keine Sitzung.
Die Kategorie "gestoert" (Knopf "Was hat dich gestört?") nur mit wirksamem Schalter
feedback_gestoert und nie mit Kontakt.
"""

import uuid
from dataclasses import replace
from datetime import date
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.feedback import router as feedback_router
from core.config import Settings
from dependencies import get_feedback_service, get_settings
from services.feedback_service import FeedbackEintrag
from utils.rate_limiter import feedback_rate_limiter

pytestmark = [pytest.mark.unit, pytest.mark.api]

SENDEN = "/api/v1/feedback/senden"
LISTE = "/api/v1/feedback"
ADMIN = {"X-User": "admin", "X-Is-Admin": "true"}
EINTRAG = FeedbackEintrag(
    id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
    text="Der Kopieren-Knopf ist mobil schwer zu treffen.",
    kontakt="anna@example.org",
    eingegangen_am=date(2026, 10, 27),
    erledigt=False,
)
EINTRAG_URL = f"{LISTE}/{EINTRAG.id}"
UNBEKANNT_URL = f"{LISTE}/22222222-2222-2222-2222-222222222222"


@pytest.fixture
def service():
    service = Mock()
    service.neueste.return_value = [EINTRAG]
    service.erledigt_setzen.return_value = replace(EINTRAG, erledigt=True)
    service.loeschen.return_value = True
    return service


@pytest.fixture
def client(service):
    app = FastAPI()
    app.include_router(feedback_router, prefix="/api/v1/feedback")
    app.dependency_overrides[get_feedback_service] = lambda: service
    return TestClient(app)


@pytest.fixture(autouse=True)
def frisches_limit():
    feedback_rate_limiter._requests.clear()
    yield
    feedback_rate_limiter._requests.clear()


class TestSenden:
    def test_besucher_sendet_feedback_ohne_kontakt(self, client, service):
        response = client.post(SENDEN, json={"text": "Gefällt mir."})

        assert response.status_code == 201
        service.senden.assert_called_once_with("Gefällt mir.", None)

    def test_kontakt_wird_mitgespeichert(self, client, service):
        client.post(
            SENDEN, json={"text": "Bitte melden", "kontakt": " anna@example.org "}
        )

        service.senden.assert_called_once_with("Bitte melden", "anna@example.org")

    def test_leerer_kontakt_gilt_als_keiner(self, client, service):
        client.post(SENDEN, json={"text": "Hallo", "kontakt": "   "})

        service.senden.assert_called_once_with("Hallo", None)

    def test_angemeldete_person_wird_nicht_mitgespeichert(self, client, service):
        client.post(SENDEN, json={"text": "Hallo"}, headers={"X-User": "user-001"})

        # Nur Text und Kontakt gehen an den Service, keine Kennung.
        service.senden.assert_called_once_with("Hallo", None)

    @pytest.mark.parametrize("text", ["", "   ", "x" * 2001])
    def test_text_leer_oder_zu_lang_ist_ungueltig(self, client, service, text):
        response = client.post(SENDEN, json={"text": text})

        assert response.status_code == 422
        service.senden.assert_not_called()

    def test_kontakt_zu_lang_ist_ungueltig(self, client, service):
        response = client.post(SENDEN, json={"text": "Hallo", "kontakt": "x" * 201})

        assert response.status_code == 422

    def test_zu_viele_sendungen_werden_abgewiesen(self, client, service):
        antworten = [
            client.post(SENDEN, json={"text": f"Nummer {i}"}).status_code
            for i in range(6)
        ]

        assert antworten == [201] * 5 + [429]
        assert service.senden.call_count == 5


class TestErledigt:
    def test_anonym_ist_nicht_angemeldet(self, client, service):
        assert client.patch(EINTRAG_URL, json={"erledigt": True}).status_code == 401
        service.erledigt_setzen.assert_not_called()

    def test_angemeldet_ohne_admin_ist_verboten(self, client, service):
        response = client.patch(
            EINTRAG_URL, json={"erledigt": True}, headers={"X-User": "normalo"}
        )

        assert response.status_code == 403
        service.erledigt_setzen.assert_not_called()

    def test_admin_setzt_erledigt(self, client, service):
        response = client.patch(EINTRAG_URL, json={"erledigt": True}, headers=ADMIN)

        assert response.status_code == 200
        assert response.json()["erledigt"] is True
        service.erledigt_setzen.assert_called_once_with(EINTRAG.id, True)

    def test_admin_nimmt_erledigt_zurueck(self, client, service):
        service.erledigt_setzen.return_value = EINTRAG

        response = client.patch(EINTRAG_URL, json={"erledigt": False}, headers=ADMIN)

        assert response.json()["erledigt"] is False
        service.erledigt_setzen.assert_called_once_with(EINTRAG.id, False)

    def test_unbekanntes_feedback_ist_nicht_gefunden(self, client, service):
        service.erledigt_setzen.return_value = None

        response = client.patch(UNBEKANNT_URL, json={"erledigt": True}, headers=ADMIN)

        assert response.status_code == 404


class TestLoeschen:
    def test_anonym_ist_nicht_angemeldet(self, client, service):
        assert client.delete(EINTRAG_URL).status_code == 401
        service.loeschen.assert_not_called()

    def test_angemeldet_ohne_admin_ist_verboten(self, client, service):
        response = client.delete(EINTRAG_URL, headers={"X-User": "normalo"})

        assert response.status_code == 403
        service.loeschen.assert_not_called()

    def test_admin_loescht_einzelnes_feedback(self, client, service):
        response = client.delete(EINTRAG_URL, headers=ADMIN)

        assert response.status_code == 204
        service.loeschen.assert_called_once_with(EINTRAG.id)

    def test_unbekanntes_feedback_ist_nicht_gefunden(self, client, service):
        service.loeschen.return_value = False

        assert client.delete(UNBEKANNT_URL, headers=ADMIN).status_code == 404


class TestListe:
    def test_anonym_ist_nicht_angemeldet(self, client):
        assert client.get(LISTE).status_code == 401

    def test_angemeldet_ohne_admin_ist_verboten(self, client):
        assert client.get(LISTE, headers={"X-User": "normalo"}).status_code == 403

    def test_admin_sieht_feedback_mit_kontakt_und_tag(self, client, service):
        response = client.get(LISTE, headers=ADMIN)

        assert response.status_code == 200
        service.neueste.assert_called_once_with(100, None)
        assert response.json() == {
            "aufbewahrung_tage": 180,
            "eintraege": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "text": "Der Kopieren-Knopf ist mobil schwer zu treffen.",
                    "kontakt": "anna@example.org",
                    "eingegangen_am": "2026-10-27",
                    "erledigt": False,
                    "kategorie": None,
                }
            ],
        }

    @pytest.mark.parametrize("wert,nur_erledigte", [("false", False), ("true", True)])
    def test_admin_filtert_nach_offen_oder_erledigt(
        self, client, service, wert, nur_erledigte
    ):
        response = client.get(f"{LISTE}?erledigt={wert}", headers=ADMIN)

        assert response.status_code == 200
        service.neueste.assert_called_once_with(100, nur_erledigte)


class TestGestoert:
    """Knopf "Was hat dich gestört?" (Schalter feedback_gestoert, Jura 26.11. Punkt g)."""

    @pytest.fixture
    def obergrenze(self, client):
        def setzen(an: bool):
            client.app.dependency_overrides[get_settings] = lambda: Settings(
                feedback_gestoert_aktiv=an
            )

        setzen(True)
        return setzen

    def test_mit_schalter_speichert_kategorie_ohne_kontakt(
        self, client, service, obergrenze
    ):
        response = client.post(
            SENDEN, json={"text": "Zu viele Klicks", "kategorie": "gestoert"}
        )

        assert response.status_code == 201
        service.senden.assert_called_once_with(
            "Zu viele Klicks", None, kategorie="gestoert"
        )

    def test_obergrenze_aus_antwortet_409_nie_404(self, client, service, obergrenze):
        obergrenze(False)

        response = client.post(SENDEN, json={"text": "Hallo", "kategorie": "gestoert"})

        assert response.status_code == 409
        service.senden.assert_not_called()

    def test_ab_dem_31_12_nimmt_der_knopf_nichts_mehr_an(
        self, client, service, obergrenze
    ):
        with patch(
            "services.schalter_service.heute_utc", return_value=date(2026, 12, 31)
        ):
            response = client.post(
                SENDEN, json={"text": "Hallo", "kategorie": "gestoert"}
            )

        assert response.status_code == 409
        service.senden.assert_not_called()

    def test_kontakt_ist_bei_gestoert_ungueltig(self, client, service, obergrenze):
        response = client.post(
            SENDEN,
            json={
                "text": "Hallo",
                "kontakt": "anna@example.org",
                "kategorie": "gestoert",
            },
        )

        assert response.status_code == 422
        service.senden.assert_not_called()

    def test_unbekannte_kategorie_ist_ungueltig(self, client, service, obergrenze):
        response = client.post(SENDEN, json={"text": "Hallo", "kategorie": "lob"})

        assert response.status_code == 422

    def test_feedback_ohne_kategorie_braucht_den_schalter_nicht(
        self, client, service, obergrenze
    ):
        obergrenze(False)

        assert client.post(SENDEN, json={"text": "Hallo"}).status_code == 201
        service.senden.assert_called_once_with("Hallo", None)

    def test_admin_sieht_die_kategorie(self, client, service):
        service.neueste.return_value = [
            replace(EINTRAG, kontakt=None, kategorie="gestoert")
        ]

        eintrag = client.get(LISTE, headers=ADMIN).json()["eintraege"][0]

        assert eintrag["kategorie"] == "gestoert"
        assert eintrag["kontakt"] is None
