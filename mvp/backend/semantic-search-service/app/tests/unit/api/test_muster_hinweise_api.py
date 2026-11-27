"""
Muster-Hinweise im Admin-Dashboard (#352): nur fuer Admins, mit Anzeigenamen.
"""

from datetime import date
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.metrics import router as metrics_router
from core.config import Settings
from dependencies import get_muster_hinweise_service, get_settings
from domain.spielgefuehl import Stufe
from repositories.muster_hinweis_repository import MusterHinweis
from services.muster_hinweise_service import MusterHinweiseService

URL = "/api/v1/metrics/muster-hinweise"
ADMIN = {"X-User": "admin-1", "X-Is-Admin": "true"}


@pytest.fixture
def dienst():
    dienst = Mock()
    dienst.hinweise.return_value = [
        MusterHinweis("bo-2", "kim-1", 3, date(2026, 10, 20), date(2026, 10, 29))
    ]
    return dienst


def _client(dienst, aktiv: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(metrics_router, prefix="/api/v1/metrics")
    app.dependency_overrides[get_settings] = lambda: Settings(punkte_aktiv=aktiv)
    app.dependency_overrides[get_muster_hinweise_service] = lambda: dienst
    return TestClient(app)


def test_muster_hinweise_mit_kennung_und_anzeigename(
    dienst, anzeigenamen_ohne_datenbank
):
    anzeigenamen_ohne_datenbank.anzeigenamen.return_value = {"kim-1": "Kim A."}

    antwort = _client(dienst).get(URL, headers=ADMIN)

    assert antwort.status_code == 200
    assert antwort.json() == {
        "aktiv": True,
        "frist_tage": 56,
        "hinweise": [
            {
                "konto_a": "bo-2",
                "name_a": None,
                "konto_b": "kim-1",
                "name_b": "Kim A.",
                "art": "nutzung",
                "tage": 3,
                "erster_tag": "2026-10-20",
                "letzter_tag": "2026-10-29",
            }
        ],
    }


def _echter_dienst(*hinweise) -> MusterHinweiseService:
    repository = Mock()
    repository.hinweise.return_value = list(hinweise)
    return MusterHinweiseService(repository)


def _paar(a: str, b: str) -> MusterHinweis:
    return MusterHinweis(a, b, 1, date(2026, 10, 29), date(2026, 10, 29))


def test_nur_paare_mit_aktueller_punkte_einwilligung(
    punkte_einwilligung_ohne_datenbank,
):
    """Nach einem Widerruf erscheint die Person nicht mehr (Art. 7 Abs. 3 DSGVO)."""
    punkte_einwilligung_ohne_datenbank.eingewilligte.side_effect = None
    punkte_einwilligung_ohne_datenbank.eingewilligte.return_value = {"bo-2", "kim-1"}
    dienst = _echter_dienst(_paar("bo-2", "kim-1"), _paar("ali-3", "kim-1"))

    hinweise = _client(dienst).get(URL, headers=ADMIN).json()["hinweise"]

    assert [(h["konto_a"], h["konto_b"]) for h in hinweise] == [("bo-2", "kim-1")]


def test_im_spielgefuehl_modell_ab_stufe_fuer_mich(
    spielgefuehl_ohne_datenbank, punkte_einwilligung_ohne_datenbank
):
    """Mit Schalter spielgefuehl_buehne zaehlt die Stufe, nicht die alte Einwilligung."""
    spielgefuehl_ohne_datenbank.wirksame_stufen.return_value = {
        "bo-2": Stufe.RANGLISTE,
        "kim-1": Stufe.FUER_MICH,
        "ali-3": Stufe.AUS,
    }
    dienst = _echter_dienst(
        _paar("bo-2", "kim-1"), _paar("ali-3", "kim-1"), _paar("bo-2", "eda-4")
    )
    app = FastAPI()
    app.include_router(metrics_router, prefix="/api/v1/metrics")
    app.dependency_overrides[get_settings] = lambda: Settings(
        punkte_aktiv=True, spielgefuehl_buehne_aktiv=True
    )
    app.dependency_overrides[get_muster_hinweise_service] = lambda: dienst

    hinweise = TestClient(app).get(URL, headers=ADMIN).json()["hinweise"]

    assert [(h["konto_a"], h["konto_b"]) for h in hinweise] == [("bo-2", "kim-1")]
    punkte_einwilligung_ohne_datenbank.eingewilligte.assert_not_called()


def test_muster_hinweise_ohne_punkte_aus(dienst):
    antwort = _client(dienst, aktiv=False).get(URL, headers=ADMIN)

    assert antwort.json()["aktiv"] is False
    assert antwort.json()["hinweise"] == []


def test_muster_hinweise_nur_admins(dienst):
    client = _client(dienst)

    assert client.get(URL, headers={"X-User": "kim-1"}).status_code == 403
    assert client.get(URL).status_code == 401
    dienst.hinweise.assert_not_called()
