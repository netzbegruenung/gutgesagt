"""
Rangliste je Saison (#793): nur mit wirksamem Schalter (und damit nur mit Punkten),
nur fuer die angemeldete Person selbst.
"""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.rangliste import router
from core.config import Settings
from dependencies import get_settings
from domain.rangliste import AKTUELLER_WORTLAUT, Platz, Rangliste, UnbekannterWortlaut
from domain.saisons import Saison
from repositories.rangliste_einwilligung_repository import RanglisteAntwort
from services.rangliste_service import (
    RanglisteStand,
    VergangeneSaison,
    rangliste_service_setzen,
)

pytestmark = pytest.mark.unit

URL = "/api/v1/rangliste"
KIM = {"X-User": "kim-1"}
SAISON = Saison(uuid.uuid4(), "Winter 26", date(2026, 12, 1), date(2027, 2, 28), 100)


def _stand(**anders) -> RanglisteStand:
    werte = dict(
        antwort=None,
        voraussetzungen=True,
        ranglistenname="Flinke Amsel 42",
        anzeigename="Kim B.",
        saison=SAISON,
        eigene_punkte=None,
        rangliste=None,
        vergangene=[],
    )
    werte.update(anders)
    return RanglisteStand(**werte)


@pytest.fixture
def dienst():
    dienst = Mock()
    dienst.stand = AsyncMock(return_value=_stand())
    rangliste_service_setzen(dienst)
    yield dienst
    rangliste_service_setzen(None)


def _client(rangliste: bool = True, punkte: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix=URL)
    app.dependency_overrides[get_settings] = lambda: Settings(
        punkte_aktiv=punkte, rangliste_aktiv=rangliste
    )
    return TestClient(app)


def test_nie_gefragt(dienst):
    antwort = _client().get(URL, headers=KIM)

    assert antwort.status_code == 200
    body = antwort.json()
    assert body["gefragt"] is False
    assert body["teilnehmen"] is None
    assert body["mit_anzeigename"] is False
    assert body["ranglistenname"] == "Flinke Amsel 42"
    assert body["rangliste"] is None
    assert body["min_teilnehmende"] == 10
    assert body["aktueller_wortlaut"]["kennung"] == AKTUELLER_WORTLAUT
    assert body["aktueller_wortlaut"]["text"].startswith("Ich willige ausdrücklich ein")
    dienst.stand.assert_awaited_once_with("kim-1")


def test_teilnehmend_mit_rangliste(dienst):
    oben = [Platz(i + 1, f"Name {i}", 100 - i, i == 2) for i in range(10)]
    dienst.stand.return_value = _stand(
        antwort=RanglisteAntwort(
            True, True, AKTUELLER_WORTLAUT, datetime(2026, 12, 1, tzinfo=timezone.utc)
        ),
        eigene_punkte=98,
        rangliste=Rangliste(oben=oben, eigener=None, teilnehmende=12),
        vergangene=[VergangeneSaison("Herbst 26", 40)],
    )

    body = _client().get(URL, headers=KIM).json()

    assert body["teilnehmen"] is True
    assert body["mit_anzeigename"] is True
    assert body["saison"] == {"name": "Winter 26", "ende": "2027-02-28"}
    assert body["eigene_punkte"] == 98
    assert len(body["rangliste"]["oben"]) == 10
    assert body["rangliste"]["oben"][2]["ich"] is True
    assert body["rangliste"]["eigener"] is None
    assert body["vergangene"] == [{"name": "Herbst 26", "punkte": 40}]


@pytest.mark.parametrize("rangliste,punkte", [(False, True), (True, False)])
def test_ohne_schalter_oder_ohne_punkte_lesen_aus_ja_409(dienst, rangliste, punkte):
    client = _client(rangliste=rangliste, punkte=punkte)

    # Lesen laedt die Seite selbst nach: 200 mit aktiv false statt 404 (Gateway-fail2ban)
    stand = client.get(URL, headers=KIM)
    assert stand.status_code == 200
    body = stand.json()
    assert body["aktiv"] is False
    assert body["gefragt"] is False
    assert body["voraussetzungen"] is False
    assert body["rangliste"] is None
    dienst.stand.assert_not_called()
    antwort = client.put(
        f"{URL}/einwilligung",
        json={"teilnehmen": True, "wortlaut": AKTUELLER_WORTLAUT},
        headers=KIM,
    )
    assert antwort.status_code == 409
    dienst.antworten.assert_not_called()


@pytest.mark.parametrize(
    "rangliste,punkte,buehne",
    [
        (False, True, False),
        (True, False, False),
        (True, True, True),
        (True, True, False),
    ],
)
def test_nein_immer_speicherbar(
    dienst,
    rangliste_ohne_datenbank,
    spielgefuehl_ohne_datenbank,
    rangliste,
    punkte,
    buehne,
):
    """Widerruf so einfach wie die Einwilligung, auch nach Not-Aus und im neuen Modell."""
    from domain.spielgefuehl import AKTUELLER_WORTLAUT as SPIELGEFUEHL_WORTLAUT
    from domain.spielgefuehl import Stufe
    from repositories.spielgefuehl_repository import SpielgefuehlAntwort

    spielgefuehl_ohne_datenbank.lesen.return_value = SpielgefuehlAntwort(
        Stufe.RANGLISTE,
        True,
        SPIELGEFUEHL_WORTLAUT,
        datetime(2026, 12, 1, tzinfo=timezone.utc),
        "Kluge Eule 11",
    )
    app = FastAPI()
    app.include_router(router, prefix=URL)
    app.dependency_overrides[get_settings] = lambda: Settings(
        punkte_aktiv=punkte, rangliste_aktiv=rangliste, spielgefuehl_buehne_aktiv=buehne
    )

    antwort = TestClient(app).put(
        f"{URL}/einwilligung",
        json={"teilnehmen": False, "wortlaut": AKTUELLER_WORTLAUT},
        headers=KIM,
    )

    assert antwort.status_code == 204
    rangliste_ohne_datenbank.antworten.assert_called_once_with(
        "kim-1", False, False, AKTUELLER_WORTLAUT
    )
    # Auch im Spielgefuehl: rangliste -> fuer_mich, sonst gaelte das Ja nach dem
    # Umschalten weiter.
    spielgefuehl_ohne_datenbank.antworten.assert_called_once_with(
        "kim-1", Stufe.FUER_MICH, False, SPIELGEFUEHL_WORTLAUT
    )
    dienst.antworten.assert_not_called()


def test_nein_nimmt_die_abzeichen_nach_herabstufen_sofort(
    dienst, spielgefuehl_ohne_datenbank, monkeypatch
):
    from domain.spielgefuehl import AKTUELLER_WORTLAUT as SPIELGEFUEHL_WORTLAUT
    from domain.spielgefuehl import Stufe
    from repositories.spielgefuehl_repository import SpielgefuehlAntwort

    vergessen = Mock()
    monkeypatch.setattr("services.spielgefuehl_service._abzeichen_vergessen", vergessen)
    body = {"teilnehmen": False, "wortlaut": AKTUELLER_WORTLAUT}

    _client().put(f"{URL}/einwilligung", json=body, headers=KIM)
    vergessen.assert_not_called()

    spielgefuehl_ohne_datenbank.lesen.return_value = SpielgefuehlAntwort(
        Stufe.RANGLISTE,
        False,
        SPIELGEFUEHL_WORTLAUT,
        datetime(2026, 12, 1, tzinfo=timezone.utc),
    )
    _client().put(f"{URL}/einwilligung", json=body, headers=KIM)
    vergessen.assert_called_once_with("kim-1")


def test_nein_unbekannter_wortlaut_422(dienst, rangliste_ohne_datenbank):
    antwort = _client(rangliste=False).put(
        f"{URL}/einwilligung",
        json={"teilnehmen": False, "wortlaut": "1999"},
        headers=KIM,
    )

    assert antwort.status_code == 422
    rangliste_ohne_datenbank.antworten.assert_not_called()


def test_ohne_anmeldung_401(dienst):
    assert _client().get(URL).status_code == 401
    assert (
        _client()
        .put(
            f"{URL}/einwilligung",
            json={"teilnehmen": True, "wortlaut": AKTUELLER_WORTLAUT},
        )
        .status_code
        == 401
    )


def test_einwilligen_speichert(dienst):
    antwort = _client().put(
        f"{URL}/einwilligung",
        json={
            "teilnehmen": True,
            "mit_anzeigename": True,
            "wortlaut": AKTUELLER_WORTLAUT,
        },
        headers=KIM,
    )

    assert antwort.status_code == 204
    dienst.antworten.assert_called_once_with("kim-1", True, True, AKTUELLER_WORTLAUT)


def test_unbekannter_wortlaut_422(dienst):
    dienst.antworten.side_effect = UnbekannterWortlaut("alt")

    antwort = _client().put(
        f"{URL}/einwilligung",
        json={"teilnehmen": True, "wortlaut": "alt"},
        headers=KIM,
    )

    assert antwort.status_code == 422


def test_fehler_500_ohne_details(dienst):
    dienst.stand.side_effect = RuntimeError("geheim")

    antwort = TestClient(_client().app, raise_server_exceptions=False).get(
        URL, headers=KIM
    )

    assert antwort.status_code == 500
    assert "geheim" not in antwort.text


def _client_buehne() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix=URL)
    app.dependency_overrides[get_settings] = lambda: Settings(
        punkte_aktiv=True, rangliste_aktiv=True, spielgefuehl_buehne_aktiv=True
    )
    return TestClient(app)


def test_spielgefuehl_modell_liste_mit_abzeichen_ohne_eigene_frage(dienst):
    oben = [Platz(i + 1, f"Name {i}", 100 - i, i == 0, i) for i in range(10)]
    dienst.stand.return_value = _stand(
        antwort=RanglisteAntwort(
            True,
            False,
            "spielgefuehl-2026-11-26",
            datetime(2026, 12, 1, tzinfo=timezone.utc),
        ),
        rangliste=Rangliste(oben=oben, eigener=None, teilnehmende=10),
    )
    client = _client_buehne()

    body = client.get(URL, headers=KIM).json()

    assert body["buehne"] is True
    assert body["rangliste"]["oben"][3]["abzeichen"] == 3
    # Teilnahme und Name waehlt die Person im Spielgefuehl, nicht hier.
    antwort = client.put(
        URL + "/einwilligung",
        json={"teilnehmen": True, "wortlaut": AKTUELLER_WORTLAUT},
        headers=KIM,
    )
    assert antwort.status_code == 409
    dienst.antworten.assert_not_called()


def test_bisheriges_modell_ohne_abzeichen(dienst):
    body = _client().get(URL, headers=KIM).json()

    assert body["buehne"] is False
