"""
Wo der Wochenzaehler der Teams (#784) erhoeht wird: nach dem Speichern eines Beitrags
(Kommentar, Hintergrundinfo, Post, Bild), nach einer Stimme und nach "Ja, gepostet".
Nicht, wenn nichts angelegt wurde (Dublette) oder die Anfrage scheitert. Ein Fehler des
Zaehlers laesst die Anfrage gelingen. Wer zaehlt und wie entdoppelt wird, pruefen
tests/unit/services/test_team_fortschritt_service.py und die Integrationstests.
"""

import uuid
from functools import partial
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.commentary import router as commentary_router
from api.v1.generic_text import router as generic_text_router
from api.v1.image import router as image_router
from api.v1.post import router as post_router
from api.v1.usage import router as usage_router
from api.v1.voting import router as voting_router
from core.config import Settings
from dependencies import (
    get_aussage_themen_service,
    get_beitrag_laden,
    get_commentary_service,
    get_generic_text_service,
    get_image_service,
    get_post_service,
    get_reference_service,
    get_settings,
    get_statement_service,
    get_voting_service,
)
from domain.models.vote import VoteResponse
from domain.team_fortschritt import Art
from services import gepostet_service as gepostet_modul
from services.beitrag_laden import beitrag_laden
from services.content.base_content_service import Dublettenpruefung
from services.team_fortschritt_service import team_fortschritt_service_setzen
from utils.text_normalisierung import SperreJeText

pytestmark = [pytest.mark.unit, pytest.mark.api]

PERSON = {"X-User": "person-1"}


@pytest.fixture
def zaehler():
    dienst = Mock()
    dienst.zaehlen.return_value = 1
    team_fortschritt_service_setzen(dienst)
    yield dienst
    team_fortschritt_service_setzen(None)


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(commentary_router, prefix="/api/v1/commentary")
    app.include_router(generic_text_router, prefix="/api/v1/generictext")
    app.include_router(image_router, prefix="/api/v1/image")
    app.include_router(post_router, prefix="/api/v1/post")
    app.include_router(voting_router, prefix="/api/v1/voting")
    app.include_router(usage_router, prefix="/api/v1/usage")
    statement_service = MagicMock()
    statement_service.beitrag_als_antwort_verknuepfen = AsyncMock()
    app.dependency_overrides[get_statement_service] = lambda: statement_service
    app.dependency_overrides[get_aussage_themen_service] = lambda: MagicMock()
    return app


def _kommentar_anfrage() -> dict:
    return {
        "commentary": {
            "title": "Waermepumpen lohnen sich auch im Altbau",
            "text": "Mit Foerderung rechnet sich die Pumpe schon nach wenigen Jahren.",
            "content_type": "commentary",
            "references": [],
        },
        "references": [],
    }


def _kommentar_dienst(vorhanden=None):
    neu = uuid.uuid4()
    dienst = MagicMock()
    dienst.add_commentary = AsyncMock(return_value=(True, neu, "text"))
    dienst.pruefe_dublette = AsyncMock(
        return_value=Dublettenpruefung(vorhanden=vorhanden, aehnlichster=vorhanden)
    )
    dienst.sperre = lambda text: SperreJeText().halten(text)
    return dienst, neu


def _mit_kommentar(app, dienst):
    referenzen = MagicMock()
    referenzen.find_exact_match = AsyncMock(return_value=None)
    app.dependency_overrides[get_commentary_service] = lambda: dienst
    app.dependency_overrides[get_reference_service] = lambda: referenzen


class TestBeitrag:
    def test_neuer_kommentar_zaehlt(self, app, zaehler):
        dienst, neu = _kommentar_dienst()
        _mit_kommentar(app, dienst)

        antwort = TestClient(app).post(
            "/api/v1/commentary/addCommentary",
            json=_kommentar_anfrage(),
            headers=PERSON,
        )

        assert antwort.status_code == 200
        zaehler.zaehlen.assert_called_once_with("person-1", Art.BEITRAG, str(neu))

    def test_dublette_ohne_neuen_kommentar_zaehlt_nicht(self, app, zaehler):
        vorhanden = MagicMock(
            id=uuid.uuid4(), original_author="person-2", title="Vorhanden"
        )
        dienst, _ = _kommentar_dienst(vorhanden=vorhanden)
        _mit_kommentar(app, dienst)

        antwort = TestClient(app).post(
            "/api/v1/commentary/addCommentary",
            json=_kommentar_anfrage(),
            headers=PERSON,
        )

        assert antwort.status_code == 200
        dienst.add_commentary.assert_not_awaited()
        zaehler.zaehlen.assert_not_called()

    def test_fehler_im_zaehler_laesst_den_kommentar_gelten(self, app, zaehler):
        zaehler.zaehlen.side_effect = RuntimeError("Datenbank weg")
        dienst, neu = _kommentar_dienst()
        _mit_kommentar(app, dienst)

        antwort = TestClient(app).post(
            "/api/v1/commentary/addCommentary",
            json=_kommentar_anfrage(),
            headers=PERSON,
        )

        assert antwort.status_code == 200
        assert antwort.json()["id"] == str(neu)

    def test_neue_hintergrundinfo_zaehlt(self, app, zaehler):
        neu = uuid.uuid4()
        dienst = MagicMock()
        dienst.add_generic_text = AsyncMock(return_value=(True, neu, "text"))
        dienst.pruefe_dublette = AsyncMock(
            return_value=Dublettenpruefung(vorhanden=None, aehnlichster=None)
        )
        dienst.sperre = lambda text: SperreJeText().halten(text)
        _mit_kommentar(app, MagicMock())
        app.dependency_overrides[get_generic_text_service] = lambda: dienst

        antwort = TestClient(app).post(
            "/api/v1/generictext/addGenericText",
            json={
                "generictext": {
                    "title": "Waermepumpen sparen im Altbau 40 Prozent Heizkosten",
                    "text": "Laut Feldtest erreichen Waermepumpen im Altbau gute Werte.",
                    "content_type": "generic_text",
                    "references": [],
                },
                "references": [],
            },
            headers=PERSON,
        )

        assert antwort.status_code == 200
        zaehler.zaehlen.assert_called_once_with("person-1", Art.BEITRAG, str(neu))

    @pytest.mark.parametrize(
        "url, abhaengigkeit, anfrage",
        [
            (
                "/api/v1/post/addPost",
                get_post_service,
                {
                    "post": {
                        "title": "So erklaert man das Heizungsgesetz",
                        "text": "Ein kurzer Post, der die Foerderung erklaert.",
                        "platform": "Instagram",
                        "author": "@gruene",
                        "url": "https://www.instagram.com/p/abc",
                    }
                },
            ),
            (
                "/api/v1/image/addImage",
                get_image_service,
                {
                    "image": {
                        "title": "Solardach auf der Grundschule",
                        "image_url": "https://example.com/dach.jpg",
                        "text": "Die Stadt hat alle Schuldaecher belegt.",
                    }
                },
            ),
        ],
        ids=["post", "bild"],
    )
    def test_post_und_bild_zaehlen(self, app, zaehler, url, abhaengigkeit, anfrage):
        typ_dienst = MagicMock()
        typ_dienst.add = AsyncMock(side_effect=lambda entry: entry.id)
        app.dependency_overrides[abhaengigkeit] = lambda: typ_dienst

        antwort = TestClient(app).post(url, json=anfrage, headers=PERSON)

        assert antwort.status_code in (200, 201)
        zaehler.zaehlen.assert_called_once_with(
            "person-1", Art.BEITRAG, antwort.json()["id"]
        )


class TestStimme:
    @pytest.fixture
    def stimmen(self, app):
        beitrag = uuid.uuid4()
        repository = MagicMock()
        repository.get = AsyncMock(return_value=object())
        dienst = MagicMock()
        for methode in ("set_like", "set_dislike", "remove_like"):
            getattr(dienst, methode).return_value = VoteResponse(
                content_id=beitrag, vote_type=None, message="ok"
            )
        app.dependency_overrides[get_beitrag_laden] = lambda: partial(
            beitrag_laden, repository=repository
        )
        app.dependency_overrides[get_voting_service] = lambda: dienst
        return beitrag, dienst

    @pytest.mark.parametrize("art", ["like", "dislike"])
    def test_stimme_zaehlt(self, app, zaehler, stimmen, art):
        beitrag, _ = stimmen

        antwort = TestClient(app).put(
            f"/api/v1/voting/content/{beitrag}/{art}", headers=PERSON
        )

        assert antwort.status_code == 200
        zaehler.zaehlen.assert_called_once_with("person-1", Art.BEWERTUNG, str(beitrag))

    def test_zuruecknehmen_zaehlt_nicht(self, app, zaehler, stimmen):
        beitrag, _ = stimmen
        TestClient(app).delete(f"/api/v1/voting/content/{beitrag}/like", headers=PERSON)
        zaehler.zaehlen.assert_not_called()

    def test_gescheiterte_stimme_zaehlt_nicht(self, app, zaehler, stimmen):
        beitrag, dienst = stimmen
        dienst.set_like.side_effect = ValueError("weg")

        antwort = TestClient(app).put(
            f"/api/v1/voting/content/{beitrag}/like", headers=PERSON
        )

        assert antwort.status_code == 400
        zaehler.zaehlen.assert_not_called()


class TestGepostet:
    @pytest.fixture
    def gepostet(self, app, monkeypatch, art9_einwilligung_ohne_datenbank):
        dienst = Mock()
        dienst.melden.return_value = 3
        monkeypatch.setattr(gepostet_modul, "_service", dienst)
        app.dependency_overrides[get_settings] = lambda: Settings(gepostet_aktiv=True)
        return dienst

    def test_ja_gepostet_zaehlt(self, app, zaehler, gepostet):
        antwort = TestClient(app).post(
            "/api/v1/usage/users/me/gepostet", headers=PERSON
        )

        assert antwort.status_code == 200
        zaehler.zaehlen.assert_called_once_with("person-1", Art.GEPOSTET, "")

    def test_ohne_art9_einwilligung_403_und_nichts_gezaehlt(
        self, app, zaehler, gepostet, art9_einwilligung_ohne_datenbank
    ):
        art9_einwilligung_ohne_datenbank.lesen.return_value = None

        antwort = TestClient(app).post(
            "/api/v1/usage/users/me/gepostet", headers=PERSON
        )

        assert antwort.status_code == 403
        zaehler.zaehlen.assert_not_called()
