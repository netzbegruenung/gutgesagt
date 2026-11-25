"""
Meldungen ohne Konto (#799): Schalter (Standard aus, nur mit "Ja, gepostet"), der
Wochenzaehler und dass Nordstern und Saison-Ziel sie nie als Menschen zaehlen.
"""

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.metrics import router as metrics_router
from core.config import Settings
from dependencies import get_settings, require_admin
from domain.saisons import Saison
from services.gepostet_ohne_konto_service import (
    GepostetOhneKontoService,
    OhneKontoWoche,
    get_gepostet_ohne_konto_service,
)
from services.gepostet_service import GepostetWoche, get_gepostet_service
from services.saison_service import SaisonService
from services.schalter_service import (
    SCHALTER,
    ObergrenzeAus,
    SchalterService,
    oeffentliche_schalter,
)

pytestmark = pytest.mark.unit

MO = date(2026, 11, 30)


def _schalter(werte):
    return SchalterService(
        admin_werte_lesen=lambda: dict(werte),
        admin_wert_setzen=lambda name, an, admin: werte.__setitem__(name, an),
    )


class TestSchalter:
    def test_obergrenze_von_haus_aus_aus(self):
        art = SCHALTER["gepostet_ohne_konto"]
        assert art.umgebungsvariable == "SEMANTIC_SEARCH_GEPOSTET_OHNE_KONTO_AKTIV"
        assert Settings.model_fields[art.feld].default is False
        with pytest.raises(ObergrenzeAus):
            _schalter({}).setzen("gepostet_ohne_konto", True, "admin-1", Settings())

    def test_wirkt_nur_mit_gepostet(self):
        an = Settings(gepostet_aktiv=True, gepostet_ohne_konto_aktiv=True)

        assert (
            _schalter({"gepostet_ohne_konto": True}).wirksam("gepostet_ohne_konto", an)
            is False
        )
        assert (
            _schalter({"gepostet_ohne_konto": True, "gepostet": True}).wirksam(
                "gepostet_ohne_konto", an
            )
            is True
        )
        assert _schalter({"gepostet": True}).wirksam("gepostet_ohne_konto", an) is False

    def test_einschalt_hinweis_und_oeffentlich(self):
        stand = {s.name: s for s in _schalter({}).stand(Settings())}

        assert stand["gepostet_ohne_konto"].dsfa_hinweis.endswith(
            "DSE-Absatz und DSFA-Nachtrag (Jura) nötig"
        )
        # Besucher haben keinen eigenen Abruf, der mit 404 antworten koennte, bevor
        # sie kopieren: das Frontend fragt GET /api/v1/funktionen.
        assert "gepostet_ohne_konto" in oeffentliche_schalter()


class TestWochenzaehler:
    def test_melden_zaehlt_auf_den_montag(self):
        repository = Mock()
        GepostetOhneKontoService(repository).melden(heute=MO + timedelta(days=3))

        repository.zaehlen.assert_called_once_with(MO)

    def test_wochen_mit_nullen(self):
        repository = Mock()
        repository.wochen.return_value = {MO: 4}

        wochen = GepostetOhneKontoService(repository).wochen(2, heute=MO)

        assert wochen == [
            OhneKontoWoche(MO - timedelta(weeks=1), 0),
            OhneKontoWoche(MO, 4),
        ]


class TestNichtAlsMenschen:
    def test_saison_ziel_und_schwelle_ohne_meldungen_ohne_konto(self):
        """Viele Meldungen ohne Konto heben weder ``erreicht`` noch die Schwelle."""
        saison = Saison(
            id=uuid.uuid4(),
            name="Winter 26",
            beginn=MO,
            ende=MO + timedelta(weeks=8),
            ziel=100,
        )
        repository = MagicMock()
        repository.alle.return_value = [saison]
        heute = MO + timedelta(weeks=4)
        wochen = [MO + timedelta(weeks=i) for i in range(5)]
        menschen = {w: 2 for w in wochen}
        ohne_konto = {w: 1000 for w in wochen}
        dienst = SaisonService(
            repository,
            lambda von, laufende: dict(menschen),
            einstellungen=Settings(
                saison_ziel_schwelle_menschen=25, saison_ziel_schwelle_wochen=3
            ),
            ohne_konto_wochenzahlen=lambda von, laufende: dict(ohne_konto),
            wirksam=lambda _s: True,
        )

        stand = dienst.admin_stand(heute=heute)
        [s] = stand.saisons

        assert s.erreicht == 8  # 4 abgeschlossene Wochen je 2 Menschen
        assert s.laufende_woche == 2
        assert s.meldungen_ohne_konto == 4000
        assert s.laufende_woche_ohne_konto == 1000
        assert stand.schwelle_erreicht is False
        assert dienst.balken(heute=heute) is None

    def test_admin_wochenzahlen_getrennt(self):
        app = FastAPI()
        app.include_router(metrics_router, prefix="/api/v1/metrics")
        app.dependency_overrides[get_settings] = lambda: Settings(
            gepostet_aktiv=True, gepostet_ohne_konto_aktiv=True
        )
        app.dependency_overrides[require_admin] = lambda: "admin-1"
        gepostet = Mock()
        gepostet.wochen.return_value = [
            GepostetWoche(MO - timedelta(weeks=1), 3),
            GepostetWoche(MO, 5),
        ]
        ohne = Mock()
        ohne.wochen.return_value = [
            OhneKontoWoche(MO - timedelta(weeks=1), 0),
            OhneKontoWoche(MO, 40),
        ]
        app.dependency_overrides[get_gepostet_service] = lambda: gepostet
        app.dependency_overrides[get_gepostet_ohne_konto_service] = lambda: ohne

        antwort = TestClient(app).get("/api/v1/metrics/gepostet?wochen=2").json()

        assert antwort["ohne_konto_aktiv"] is True
        assert antwort["woechentlich"] == [
            {"woche": "2026-11-23", "personen": 3, "meldungen_ohne_konto": 0},
            {"woche": "2026-11-30", "personen": 5, "meldungen_ohne_konto": 40},
        ]
