"""
Spielgefuehl als eine Einstellung (api/v1/spielgefuehl.py): nur mit den Schaltern
spielgefuehl_buehne und punkte, nur fuer die angemeldete Person selbst.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.spielgefuehl import router
from core.config import Settings
from dependencies import get_settings
from domain.spielgefuehl import (
    AKTUELLER_WORTLAUT,
    HINWEIS_ABZEICHEN_NUR_RANGLISTE,
    NamenswahlFehlt,
    Stufe,
)
from services.spielgefuehl_service import (
    NichtInRangliste,
    SpielgefuehlStand,
    spielgefuehl_service_setzen,
)

pytestmark = pytest.mark.unit

URL = "/api/v1/usage/users/me/spielgefuehl"
KIM = {"X-User": "kim-1"}


@pytest.fixture
def dienst():
    dienst = MagicMock()
    dienst.stand.return_value = SpielgefuehlStand(None, None, None, False)
    spielgefuehl_service_setzen(dienst)
    yield dienst
    spielgefuehl_service_setzen(None)


def _client(buehne=True, punkte=True) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/usage")
    app.dependency_overrides[get_settings] = lambda: Settings(
        spielgefuehl_buehne_aktiv=buehne, punkte_aktiv=punkte, rangliste_aktiv=True
    )
    return TestClient(app)


@pytest.mark.parametrize("buehne, punkte", [(False, True), (True, False)])
def test_ohne_schalter_aktiv_false_ohne_abfrage(dienst, buehne, punkte):
    client = _client(buehne, punkte)

    antwort = client.get(URL, headers=KIM)

    assert antwort.status_code == 200
    assert antwort.json()["aktiv"] is False
    dienst.stand.assert_not_called()
    assert client.post(URL + "/ranglistenname", headers=KIM).status_code == 404


@pytest.mark.parametrize("buehne, punkte", [(False, True), (True, False)])
def test_ohne_schalter_aus_immer_speicherbar(dienst, buehne, punkte):
    """Widerruf so einfach wie die Einwilligung (Art. 7 Abs. 3 DSGVO), auch nach Not-Aus."""
    dienst.herabstufung.return_value = True

    antwort = _client(buehne, punkte).put(
        URL, json={"stufe": "aus", "wortlaut": AKTUELLER_WORTLAUT}, headers=KIM
    )

    assert antwort.status_code == 204
    dienst.herabstufung.assert_called_once_with("kim-1", Stufe.AUS)
    dienst.antworten.assert_called_once_with(
        "kim-1", Stufe.AUS, None, AKTUELLER_WORTLAUT
    )


def test_ohne_schalter_herabstufen_aus_der_rangliste(dienst):
    dienst.herabstufung.return_value = True

    antwort = _client(buehne=False).put(
        URL, json={"stufe": "fuer_mich", "wortlaut": AKTUELLER_WORTLAUT}, headers=KIM
    )

    assert antwort.status_code == 204
    dienst.antworten.assert_called_once_with(
        "kim-1", Stufe.FUER_MICH, None, AKTUELLER_WORTLAUT
    )


@pytest.mark.parametrize("stufe", ["fuer_mich", "rangliste"])
@pytest.mark.parametrize("buehne, punkte", [(False, True), (True, False)])
def test_ohne_schalter_kein_heraufstufen(dienst, buehne, punkte, stufe):
    """Ein Ja bleibt an die Schalter gebunden; 409 statt 404 (Gateway-fail2ban)."""
    dienst.herabstufung.return_value = False

    antwort = _client(buehne, punkte).put(
        URL,
        json={"stufe": stufe, "mit_anzeigename": False, "wortlaut": AKTUELLER_WORTLAUT},
        headers=KIM,
    )

    assert antwort.status_code == 409
    dienst.antworten.assert_not_called()


def test_ohne_schalter_lesefehler_500(dienst):
    dienst.herabstufung.side_effect = RuntimeError("geheim")

    antwort = TestClient(_client(buehne=False).app, raise_server_exceptions=False).put(
        URL, json={"stufe": "fuer_mich", "wortlaut": AKTUELLER_WORTLAUT}, headers=KIM
    )

    assert antwort.status_code == 500
    assert "geheim" not in antwort.text
    dienst.antworten.assert_not_called()


def test_mit_schalter_ohne_pruefung_der_herabstufung(dienst):
    _client().put(
        URL, json={"stufe": "fuer_mich", "wortlaut": AKTUELLER_WORTLAUT}, headers=KIM
    )

    dienst.herabstufung.assert_not_called()
    dienst.antworten.assert_called_once()


def test_ohne_anmeldung_401(dienst):
    assert _client().get(URL).status_code == 401


def test_frage_mit_wortlaut_in_der_reihenfolge_gemeinschaft_zuerst(
    dienst, anzeigenamen_ohne_datenbank
):
    anzeigenamen_ohne_datenbank.anzeigenamen.return_value = {"kim-1": "Kim B."}
    dienst.stand.return_value = SpielgefuehlStand(None, None, None, True)

    daten = _client().get(URL, headers=KIM).json()

    assert daten["aktiv"] is True
    assert daten["stufe"] is None
    assert daten["anzeigename"] == "Kim B."
    assert daten["abzeichen_hinweis"] == HINWEIS_ABZEICHEN_NUR_RANGLISTE
    wortlaut = daten["aktueller_wortlaut"]
    assert wortlaut["kennung"] == AKTUELLER_WORTLAUT
    assert [s["stufe"] for s in wortlaut["stufen"]] == [
        "rangliste",
        "fuer_mich",
        "aus",
    ]
    assert wortlaut["namenswahl"]["vorbelegung_anzeigename"] is None
    assert "Absprachen" in wortlaut["absprachen"]


def test_stand_mit_stufe(dienst):
    dienst.stand.return_value = SpielgefuehlStand(
        Stufe.RANGLISTE, False, "Kluge Eule 11", False
    )

    daten = _client().get(URL, headers=KIM).json()

    assert daten["stufe"] == "rangliste"
    assert daten["mit_anzeigename"] is False
    assert daten["ranglistenname"] == "Kluge Eule 11"
    assert daten["abzeichen_hinweis"] is None


def test_waehlen(dienst):
    antwort = _client().put(
        URL,
        json={
            "stufe": "rangliste",
            "mit_anzeigename": True,
            "wortlaut": AKTUELLER_WORTLAUT,
        },
        headers=KIM,
    )

    assert antwort.status_code == 204
    dienst.antworten.assert_called_once_with(
        "kim-1", Stufe.RANGLISTE, True, AKTUELLER_WORTLAUT
    )


def test_ohne_namenswahl_422(dienst):
    dienst.antworten.side_effect = NamenswahlFehlt()

    antwort = _client().put(
        URL, json={"stufe": "rangliste", "wortlaut": AKTUELLER_WORTLAUT}, headers=KIM
    )

    assert antwort.status_code == 422


def test_unbekannte_stufe_422(dienst):
    antwort = _client().put(
        URL, json={"stufe": "alles", "wortlaut": AKTUELLER_WORTLAUT}, headers=KIM
    )

    assert antwort.status_code == 422
    dienst.antworten.assert_not_called()


def test_neu_wuerfeln(dienst):
    dienst.neu_wuerfeln.return_value = "Kluge Eule 11"

    antwort = _client().post(URL + "/ranglistenname", headers=KIM)

    assert antwort.status_code == 200
    assert antwort.json() == {"ranglistenname": "Kluge Eule 11"}


def test_neu_wuerfeln_ausserhalb_der_rangliste_409(dienst):
    dienst.neu_wuerfeln.side_effect = NichtInRangliste()

    assert _client().post(URL + "/ranglistenname", headers=KIM).status_code == 409


def _client_ohne_rangliste() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/usage")
    app.dependency_overrides[get_settings] = lambda: Settings(
        spielgefuehl_buehne_aktiv=True, punkte_aktiv=True, rangliste_aktiv=False
    )
    return TestClient(app)


def test_ohne_schalter_rangliste_keine_stufe_rangliste(dienst):
    client = _client_ohne_rangliste()

    stufen = client.get(URL, headers=KIM).json()["aktueller_wortlaut"]["stufen"]
    antwort = client.put(
        URL,
        json={
            "stufe": "rangliste",
            "mit_anzeigename": False,
            "wortlaut": AKTUELLER_WORTLAUT,
        },
        headers=KIM,
    )

    assert [s["stufe"] for s in stufen] == ["fuer_mich", "aus"]
    assert antwort.status_code == 422
    dienst.antworten.assert_not_called()


def test_neu_wuerfeln_zu_oft_429(dienst):
    from services.spielgefuehl_service import ZuOftGewuerfelt

    dienst.neu_wuerfeln.side_effect = ZuOftGewuerfelt()

    assert _client().post(URL + "/ranglistenname", headers=KIM).status_code == 429
