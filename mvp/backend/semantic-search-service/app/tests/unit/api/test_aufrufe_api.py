"""
Seitenaufrufe und Besucher je Tag (#761): Gezaehlt wird am Server aus Abrufen, die die
App ohnehin macht, nur mit Schalter; gespeichert wird nur das Tagespseudonym, nie die
Adresse. Admins sehen Tageszahlen. Ohne Datenbank: das Repository ist ersetzt; gegen
PostgreSQL pruefen tests/integration/test_aufrufe_repository.py.
"""

import asyncio
from datetime import date
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.v1.aufrufe as modul
import middleware.aufrufe_zaehlen as mw
from core.config import Settings
from dependencies import get_settings
from repositories.aufrufe_repository import AufrufTag
from services import aufrufe_service
from services.aufrufe_service import Wiederholsperre, seite_von
from services.schalter_service import SchalterService, schalter_service_setzen
from utils.besucher_pseudonym import besucher_tagespseudonym

pytestmark = pytest.mark.unit

URL = "/api/v1/aufrufe"
ADMIN = {"X-User": "admin-1", "X-Is-Admin": "true"}
ADRESSE = {"X-Real-IP": "203.0.113.7"}
HEUTE = date(2026, 11, 22)


@pytest.fixture
def werte(schalter_admin_alle_an):
    werte = {"aufrufe_zaehlen": True}
    schalter_service_setzen(
        SchalterService(
            admin_werte_lesen=lambda: dict(werte),
            admin_wert_setzen=lambda n, a, w: werte.__setitem__(n, a),
        )
    )
    return werte


@pytest.fixture
def repo():
    r = Mock()
    r.heute.return_value = AufrufTag(tag=HEUTE, aufrufe=9, besucher=4)
    r.tage.return_value = [AufrufTag(tag=date(2026, 11, 21), aufrufe=30, besucher=12)]
    return r


@pytest.fixture(autouse=True)
def ohne_rate_limit(monkeypatch):
    limiter = Mock()

    async def frei(schluessel):
        return False

    limiter.is_rate_limited = frei
    monkeypatch.setattr(mw, "aufrufe_rate_limiter", limiter)
    return limiter


def _client(repo, obergrenze=True):
    app = FastAPI()
    app.include_router(modul.router, prefix=URL)
    app.dependency_overrides[get_settings] = lambda: Settings(
        aufrufe_zaehlen_aktiv=obergrenze
    )
    app.dependency_overrides[modul._repository] = lambda: repo
    return TestClient(app)


class Uhr:
    def __init__(self):
        self.jetzt = 1000.0

    def __call__(self):
        return self.jetzt


def _seiten_app(repo, obergrenze=True, sperre=None):
    """Eine App mit den gezaehlten Routen, wie die echten ohne Inhalt."""
    app = FastAPI()

    @app.get("/api/v1/content/recent")
    def recent():
        return {"results": []}

    @app.get("/api/v1/content/beitrag/{beitrag_id}")
    def beitrag(beitrag_id: str):
        if beitrag_id == "fehlt":
            from fastapi import HTTPException

            raise HTTPException(status_code=404)
        return {"id": beitrag_id}

    @app.post("/api/v1/search/searchByText")
    def suche():
        return {"treffer": []}

    @app.get("/api/v1/search/thema/{schluessel}")
    def thema(schluessel: str):
        return {"aussagen": []}

    @app.get("/api/v1/metrics/getMetrics")
    def anderes():
        return {}

    app.add_middleware(
        mw.AufrufeZaehlenMiddleware,
        einstellungen=lambda: Settings(aufrufe_zaehlen_aktiv=obergrenze),
        repository=lambda: repo,
        sperre=sperre or Wiederholsperre(uhr=Uhr()),
        heute=lambda: HEUTE,
    )
    return app


def _abrufen(app, *abrufe):
    """Abrufe ausfuehren und die Zaehl-Aufgaben danach abwarten."""

    async def abwarten():
        await asyncio.gather(*list(mw.AUSSTEHEND))

    with TestClient(app) as client:
        antworten = [
            client.request(methode, pfad, headers=ADRESSE) for methode, pfad in abrufe
        ]
        client.portal.call(abwarten)
    return antworten


class TestSeiten:
    @pytest.mark.parametrize(
        "methode, pfad, seite",
        [
            ("GET", "/api/v1/content/recent", "start"),
            ("GET", "/api/v1/content/beitrag/b-1", "beitrag|b-1"),
            ("POST", "/api/v1/search/searchByText", "suche"),
            ("GET", "/api/v1/search/thema/klima", "thema|klima"),
        ],
    )
    def test_gezaehlte_abrufe(self, methode, pfad, seite):
        assert seite_von(methode, pfad) == seite

    @pytest.mark.parametrize(
        "methode, pfad",
        [
            ("POST", "/api/v1/content/recent"),
            ("GET", "/api/v1/search/searchByText"),
            ("GET", "/api/v1/metrics/getMetrics"),
            ("GET", "/api/v1/aufrufe"),
            ("GET", "/api/v1/content/beitrag/b-1/weiter"),
            ("DELETE", "/api/v1/content/b-1"),
        ],
    )
    def test_andere_abrufe_zaehlen_nicht(self, methode, pfad):
        assert seite_von(methode, pfad) is None


class TestWiederholsperre:
    def test_dieselbe_seite_binnen_der_sperre_einmal(self):
        uhr = Uhr()
        sperre = Wiederholsperre(sekunden=300, uhr=uhr)

        assert sperre.neu("203.0.113.7", "start", HEUTE) is True
        uhr.jetzt += 30
        assert sperre.neu("203.0.113.7", "start", HEUTE) is False

    def test_nachladen_verlaengert_die_sperre(self):
        uhr = Uhr()
        sperre = Wiederholsperre(sekunden=300, uhr=uhr)
        sperre.neu("203.0.113.7", "start", HEUTE)
        for _ in range(20):
            uhr.jetzt += 30
            assert sperre.neu("203.0.113.7", "start", HEUTE) is False

    def test_nach_der_sperre_wieder(self):
        uhr = Uhr()
        sperre = Wiederholsperre(sekunden=300, uhr=uhr)
        sperre.neu("203.0.113.7", "start", HEUTE)
        uhr.jetzt += 301
        assert sperre.neu("203.0.113.7", "start", HEUTE) is True

    def test_andere_seite_anderer_besucher_neuer_tag_zaehlen(self):
        sperre = Wiederholsperre(uhr=Uhr())
        sperre.neu("203.0.113.7", "beitrag|b-1", HEUTE)

        assert sperre.neu("203.0.113.7", "beitrag|b-2", HEUTE) is True
        assert sperre.neu("203.0.113.8", "beitrag|b-1", HEUTE) is True
        assert sperre.neu("203.0.113.7", "beitrag|b-1", date(2026, 11, 23)) is True

    def test_haelt_keine_adresse_und_keine_seite(self):
        sperre = Wiederholsperre(uhr=Uhr())
        sperre.neu("203.0.113.7", "beitrag|b-1", HEUTE)

        schluessel = " ".join(sperre._zuletzt)
        assert "203.0.113" not in schluessel and "b-1" not in schluessel

    def test_voll_zaehlt_nichts_neues(self):
        uhr = Uhr()
        sperre = Wiederholsperre(sekunden=300, hoechstens=2, uhr=uhr)
        sperre.neu("a", "start", HEUTE)
        sperre.neu("b", "start", HEUTE)

        assert sperre.neu("c", "start", HEUTE) is False
        uhr.jetzt += 301
        assert sperre.neu("c", "start", HEUTE) is True


class TestZaehlenAusAbrufen:
    def test_an_zaehlt_mit_pseudonym_ohne_adresse(self, werte, repo):
        (antwort,) = _abrufen(_seiten_app(repo), ("GET", "/api/v1/content/recent"))

        assert antwort.status_code == 200
        tag, pseudonym = repo.zaehlen.call_args.args
        assert tag == HEUTE
        assert len(pseudonym) == 64 and "203.0.113" not in pseudonym
        assert pseudonym == aufrufe_service.aufruf_pseudonym("203.0.113.7", HEUTE)

    def test_jede_seite_zaehlt_wiederholung_nicht(self, werte, repo):
        _abrufen(
            _seiten_app(repo),
            ("GET", "/api/v1/content/recent"),
            ("GET", "/api/v1/content/recent"),
            ("POST", "/api/v1/search/searchByText"),
            ("GET", "/api/v1/content/beitrag/b-1"),
            ("GET", "/api/v1/content/beitrag/b-2"),
            ("GET", "/api/v1/search/thema/klima"),
        )
        assert repo.zaehlen.call_count == 5

    def test_andere_abrufe_und_fehler_zaehlen_nicht(self, werte, repo):
        antworten = _abrufen(
            _seiten_app(repo),
            ("GET", "/api/v1/metrics/getMetrics"),
            ("GET", "/api/v1/content/beitrag/fehlt"),
        )
        assert [a.status_code for a in antworten] == [200, 404]
        repo.zaehlen.assert_not_called()

    @pytest.mark.parametrize(
        "obergrenze, admin_wert", [(True, False), (False, True), (False, False)]
    )
    def test_schalter_aus_nichts_gezaehlt_antwort_gleich(
        self, werte, repo, obergrenze, admin_wert
    ):
        werte["aufrufe_zaehlen"] = admin_wert
        (antwort,) = _abrufen(
            _seiten_app(repo, obergrenze), ("GET", "/api/v1/content/recent")
        )

        assert antwort.status_code == 200 and antwort.json() == {"results": []}
        assert repo.method_calls == []

    def test_ueber_dem_rate_limit_still_nicht_gezaehlt(
        self, werte, repo, ohne_rate_limit
    ):
        async def begrenzt(schluessel):
            return True

        ohne_rate_limit.is_rate_limited = begrenzt
        (antwort,) = _abrufen(_seiten_app(repo), ("GET", "/api/v1/content/recent"))

        assert antwort.status_code == 200
        repo.zaehlen.assert_not_called()

    def test_fehler_beim_speichern_kostet_nur_den_aufruf(self, werte, repo, caplog):
        repo.zaehlen.side_effect = RuntimeError("geheim")
        (antwort,) = _abrufen(_seiten_app(repo), ("GET", "/api/v1/content/recent"))

        assert antwort.status_code == 200
        assert "geheim" not in caplog.text

    def test_keine_eigene_zaehl_route_mehr(self, werte, repo):
        """Variante B: Der Browser schickt nichts Zusaetzliches; die alte Route ist weg."""
        assert _client(repo).post(f"{URL}/zaehlen").status_code in (404, 405)


class TestTageszahlen:
    def test_nur_fuer_admins(self, werte, repo):
        client = _client(repo)
        assert client.get(URL).status_code == 401
        assert client.get(URL, headers={"X-User": "p-1"}).status_code == 403

    def test_an_heute_und_vergangene_tage(self, werte, repo):
        daten = _client(repo).get(URL, headers=ADMIN).json()

        assert daten["aktiv"] is True
        assert daten["heute"]["aufrufe"] == 9 and daten["heute"]["besucher"] == 4
        assert daten["tage"] == [{"tag": "2026-11-21", "aufrufe": 30, "besucher": 12}]

    def test_aus_nichts_sichtbar(self, werte, repo):
        werte["aufrufe_zaehlen"] = False
        daten = _client(repo).get(URL, headers=ADMIN).json()

        assert daten == {"aktiv": False, "heute": None, "tage": []}
        assert repo.method_calls == []


class TestPseudonym:
    def test_anderer_raum_als_an_suchereignissen(self):
        """Dasselbe Merkmal am selben Tag ergibt ein anderes Pseudonym als bei der Suche."""
        assert aufrufe_service.aufruf_pseudonym(
            "203.0.113.7", HEUTE
        ) != besucher_tagespseudonym("203.0.113.7", HEUTE)

    def test_gleicher_besucher_gleicher_tag_gleiches_pseudonym(self):
        a = aufrufe_service.aufruf_pseudonym("203.0.113.7", HEUTE)
        assert a == aufrufe_service.aufruf_pseudonym("203.0.113.7", HEUTE)
        assert a != aufrufe_service.aufruf_pseudonym("203.0.113.8", HEUTE)


def test_verdichten_im_takt_laeuft_und_loggt_fehler_ohne_details(caplog):
    repo = Mock()
    repo.verdichten_vor.side_effect = [3, RuntimeError("geheim")]

    async def lauf():
        aufgabe = asyncio.create_task(
            aufrufe_service.verdichten_im_takt(
                repo, takt_sekunden=0.01, heute=lambda: HEUTE
            )
        )
        await asyncio.sleep(0.05)
        aufgabe.cancel()

    asyncio.run(lauf())

    assert repo.verdichten_vor.call_args_list[0].args == (HEUTE,)
    assert "geheim" not in caplog.text
