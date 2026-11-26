"""
Schalter ``feedback_gestoert`` (Knopf "Was hat dich gestört?" fuer die Startphase):
Obergrenze von Haus aus aus, ohne Admin-Wert aus, oeffentlich ueber
GET /api/v1/funktionen, Gruppe Grundfunktionen, Einschalt-Hinweis mit der
Jura-Bedingung. Ab dem 31.12.2026 wirkt er nicht mehr, auch wenn beide Teile an sind.
"""

from datetime import date
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.funktionen import router as funktionen_router
from core.config import Settings
from dependencies import get_settings
from services.schalter_service import (
    GRUNDFUNKTIONEN,
    SCHALTER,
    ObergrenzeAus,
    SchalterService,
    oeffentliche_schalter,
    schalter_service_setzen,
)

pytestmark = pytest.mark.unit

NAME = "feedback_gestoert"
AN = Settings(feedback_gestoert_aktiv=True)
IN_DER_STARTPHASE = date(2026, 11, 27)


def _dienst(werte):
    return SchalterService(
        admin_werte_lesen=lambda: dict(werte),
        admin_wert_setzen=lambda name, an, admin: werte.__setitem__(name, an),
    )


@pytest.fixture(autouse=True)
def startphase():
    with patch(
        "services.schalter_service.heute_utc", return_value=IN_DER_STARTPHASE
    ) as heute:
        yield heute


def test_registrierung():
    art = SCHALTER[NAME]

    assert art.umgebungsvariable == "SEMANTIC_SEARCH_FEEDBACK_GESTOERT_AKTIV"
    assert art.feld == "feedback_gestoert_aktiv"
    assert art.gruppe == GRUNDFUNKTIONEN
    assert art.einschalt_hinweis.startswith(
        "Jura vorläufig ok 26.11. (interner Test), DSE-Absatz drin"
    )
    assert "31.12.2026" in art.einschalt_hinweis
    assert art.rechtlich_freigegeben is False
    assert NAME in oeffentliche_schalter()


def test_obergrenze_von_haus_aus_aus():
    dienst = _dienst({NAME: True})

    assert Settings.model_fields["feedback_gestoert_aktiv"].default is False
    assert dienst.wirksam(NAME, Settings(feedback_gestoert_aktiv=False)) is False
    with pytest.raises(ObergrenzeAus):
        dienst.setzen(NAME, True, "admin-1", Settings(feedback_gestoert_aktiv=False))


def test_ohne_admin_wert_aus_mit_admin_wert_an():
    assert _dienst({}).wirksam(NAME, AN) is False
    assert _dienst({NAME: True}).wirksam(NAME, AN) is True


@pytest.mark.parametrize(
    "heute, wirkt",
    [
        (date(2026, 12, 30), True),
        (date(2026, 12, 31), False),
        (date(2027, 2, 1), False),
    ],
)
def test_wirkt_nur_bis_zum_ende_der_startphase(startphase, heute, wirkt):
    startphase.return_value = heute

    assert _dienst({NAME: True}).wirksam(NAME, AN) is wirkt


def test_admin_seite_zeigt_ihn_als_wartet_auf_recht():
    stand = {s.name: s for s in _dienst({}).stand(AN)}[NAME]

    assert stand.dsfa_hinweis.startswith(
        "Jura vorläufig ok 26.11. (interner Test), DSE-Absatz drin"
    )
    assert "31.12.2026" in stand.dsfa_hinweis
    assert stand.wartet_auf_recht is True
    assert stand.gruppe == GRUNDFUNKTIONEN


def test_funktionen_meldet_den_wirksamen_wert():
    werte = {NAME: False}
    schalter_service_setzen(_dienst(werte))
    app = FastAPI()
    app.include_router(funktionen_router, prefix="/api/v1/funktionen")
    app.dependency_overrides[get_settings] = lambda: AN
    client = TestClient(app)

    assert client.get("/api/v1/funktionen").json()["funktionen"][NAME] is False
    werte[NAME] = True
    schalter_service_setzen(_dienst(werte))
    assert client.get("/api/v1/funktionen").json()["funktionen"][NAME] is True
