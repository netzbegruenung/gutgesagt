"""
GET /api/v1/usage/users/me/naechster-schritt (#789): ohne Schalter 404 und keine
Abfrage, nur fuer Angemeldete, Vorschlaege aus den Quellen; eine Quelle, die scheitert,
laesst nur ihre Regel aus. Die Quellen sind ersetzt, es gibt keine Datenbank.
"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.naechster_schritt import Quellen, get_quellen, router
from core.config import Settings
from dependencies import get_settings
from services.naechster_schritt import Brachflaeche
from services.schalter_service import SchalterService, schalter_service_setzen

pytestmark = pytest.mark.unit

URL = "/api/v1/usage/users/me/naechster-schritt"
ICH = {"X-User": "kim-1"}
AUSSAGE = uuid.UUID("11111111-1111-4111-8111-111111111111")
KOMMENTAR = uuid.UUID("22222222-2222-4222-8222-222222222222")


class FalscheQuellen:
    def __init__(self, **werte):
        self.werte = dict(
            einwuerfe=0,
            stimmen=0,
            beitraege=[],
            frische_antworten=5,
            brachflaeche=Brachflaeche(AUSSAGE, "Windräder töten Vögel", 4),
        )
        self.werte.update(werte)
        self.gefragt = []

    async def _wert(self, name):
        self.gefragt.append(name)
        wert = self.werte[name]
        if isinstance(wert, Exception):
            raise wert
        return wert

    async def einwuerfe(self, person):
        assert person == "kim-1"
        return await self._wert("einwuerfe")

    async def stimmen(self, person):
        return await self._wert("stimmen")

    async def beitraege(self, person):
        return await self._wert("beitraege")

    async def frische_antworten(self, person):
        return await self._wert("frische_antworten")

    async def brachflaeche(self):
        return await self._wert("brachflaeche")


@pytest.fixture
def werte():
    werte = {}
    schalter_service_setzen(
        SchalterService(
            admin_werte_lesen=lambda: dict(werte),
            admin_wert_setzen=lambda name, an, admin: werte.__setitem__(name, an),
        )
    )
    yield werte
    schalter_service_setzen(None)


def _client(quellen, obergrenze=True) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/usage")
    app.dependency_overrides[get_settings] = lambda: Settings(
        naechster_schritt_aktiv=obergrenze
    )
    app.dependency_overrides[get_quellen] = lambda: quellen
    return TestClient(app)


def test_schalter_aus_404_ohne_abfrage(werte):
    quellen = FalscheQuellen()

    antwort = _client(quellen).get(URL, headers=ICH)

    assert antwort.status_code == 404
    assert quellen.gefragt == []


def test_obergrenze_aus_schlaegt_admin_wert(werte):
    werte["naechster_schritt"] = True

    assert (
        _client(FalscheQuellen(), obergrenze=False).get(URL, headers=ICH).status_code
        == 404
    )


def test_obergrenze_von_haus_aus_aus():
    assert Settings().naechster_schritt_aktiv is False


def test_nur_fuer_angemeldete(werte):
    werte["naechster_schritt"] = True

    assert _client(FalscheQuellen()).get(URL).status_code == 401
    assert (
        _client(FalscheQuellen()).get(URL, headers={"X-User": "anonymous"}).status_code
        == 401
    )


def test_neue_person_bekommt_alle_ersten_schritte(werte):
    werte["naechster_schritt"] = True

    antwort = _client(FalscheQuellen()).get(URL, headers=ICH)

    assert antwort.status_code == 200
    vorschlaege = antwort.json()["vorschlaege"]
    assert [v["art"] for v in vorschlaege] == [
        "suchen",
        "einwerfen",
        "bewerten",
        "brachflaeche",
    ]
    assert vorschlaege[2]["anzahl"] == 3
    assert vorschlaege[3]["brachflaeche"] == {
        "statement_id": str(AUSSAGE),
        "statement_text": "Windräder töten Vögel",
        "personen_ohne_treffer": 4,
    }


def test_regel_3_haengt_nicht_an_der_einwilligung_punkte(werte):
    # Jura 25.11.: Vorschlaege aus eigenen Stimmen braucht keine Einwilligung "Punkte und
    # Meilensteine"; die Art.-9-Einwilligung zur Mitwirkung genuegt. Punkte sind aus, die
    # Punkte-Einwilligung fehlt und wird nicht gefragt, Regel 3 kommt trotzdem.
    werte["naechster_schritt"] = True
    punkte_einwilligung = Mock()
    punkte_einwilligung.eingewilligt.return_value = False
    punkte_einwilligung.lesen.return_value = None

    with patch(
        "repositories.punkte_einwilligung_repository._repository", punkte_einwilligung
    ):
        antwort = _client(FalscheQuellen(einwuerfe=1, stimmen=1, beitraege=[])).get(
            URL, headers=ICH
        )

    assert [v["art"] for v in antwort.json()["vorschlaege"]][0] == "bewerten"
    punkte_einwilligung.eingewilligt.assert_not_called()
    punkte_einwilligung.lesen.assert_not_called()


def test_quellen_lesen_stimmen_ohne_punkte_und_ohne_punkte_einwilligung():
    # Die echten Quellen mit Punkten aus: Die Stimmen kommen trotzdem, und die Klasse der
    # Einwilligung "Punkte und Meilensteine" wird weder angelegt noch gefragt (Jura 25.11.).
    quellen = Quellen(Mock(), Settings(punkte_aktiv=False), Mock())

    with patch("api.v1.naechster_schritt.PunkteRepository") as punkte, patch(
        "repositories.punkte_einwilligung_repository.PunkteEinwilligungRepository"
    ) as einwilligung:
        punkte.return_value.bewertungen_je_tag.return_value = {"a": 1}
        assert asyncio.run(quellen.stimmen("kim-1")) == 1

    einwilligung.assert_not_called()


def test_naechster_schritt_kennt_die_punkte_einwilligung_nicht():
    # Statische Sperre: Weder Abruf noch Regeln lesen die Einwilligung "Punkte und
    # Meilensteine" oder den Schalter punkte_aktiv.
    import api.v1.naechster_schritt as abruf
    import services.naechster_schritt as regeln

    for modul in (abruf, regeln):
        quelltext = open(modul.__file__, encoding="utf-8").read()
        code = quelltext.split('"""', 2)[2]  # ohne Modulkopf
        assert "punkte_einwilligung" not in code
        assert "PunkteEinwilligung" not in code
        assert "punkte_aktiv" not in code


def test_kurzfassung_aus_eigenen_beitraegen(werte):
    werte["naechster_schritt"] = True
    quellen = FalscheQuellen(
        einwuerfe=2,
        stimmen=8,
        beitraege=[
            {
                "id": str(KOMMENTAR),
                "content_type": "commentary",
                "title": "Windräder schützen Vögel",
                "short_text": None,
                "usage_count": 6,
            }
        ],
    )

    vorschlaege = _client(quellen).get(URL, headers=ICH).json()["vorschlaege"]

    assert [v["art"] for v in vorschlaege] == ["kurzfassung", "brachflaeche"]
    assert vorschlaege[0]["kommentar"] == {
        "content_id": str(KOMMENTAR),
        "titel": "Windräder schützen Vögel",
        "nutzung": 6,
    }


def test_gescheiterte_quelle_laesst_nur_ihre_regel_aus(werte):
    werte["naechster_schritt"] = True
    quellen = FalscheQuellen(einwuerfe=RuntimeError("weg"), stimmen=9, beitraege=[])

    vorschlaege = _client(quellen).get(URL, headers=ICH).json()["vorschlaege"]

    # Ohne Einwuerfe weder "suchen" noch "einwerfen"; kein Beitrag: Aussage ohne Antwort
    assert [v["art"] for v in vorschlaege] == ["brachflaeche"]


def test_antwort_nennt_keine_kennung(werte):
    werte["naechster_schritt"] = True

    assert "kim-1" not in _client(FalscheQuellen()).get(URL, headers=ICH).text


def test_quellen_lesen_eigene_einwuerfe_stimmen_und_die_erste_aussage():
    einwuerfe = Mock()
    einwuerfe.count.return_value = 2
    unbeantwortete = Mock()
    unbeantwortete.liste = AsyncMock(
        return_value=[
            SimpleNamespace(statement_id=AUSSAGE, text="X", personen_ohne_treffer=3)
        ]
    )
    quellen = Quellen(einwuerfe, Settings(), unbeantwortete)

    with patch("api.v1.naechster_schritt.PunkteRepository") as punkte:
        punkte.return_value.bewertungen_je_tag.return_value = {"a": 2, "b": 1}
        assert asyncio.run(quellen.stimmen("kim-1")) == 3
        punkte.return_value.bewertungen_je_tag.assert_called_once_with("kim-1", [])

    assert asyncio.run(quellen.einwuerfe("kim-1")) == 2
    einwuerfe.count.assert_called_once_with(submitted_by="kim-1")
    assert asyncio.run(quellen.brachflaeche()) == Brachflaeche(AUSSAGE, "X", 3)
    assert unbeantwortete.liste.await_args.kwargs == {"limit": 1, "mit_themen": False}

    unbeantwortete.liste = AsyncMock(return_value=[])
    assert asyncio.run(quellen.brachflaeche()) is None
