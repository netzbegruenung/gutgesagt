"""
Kein Weg an den Admin-Werten vorbei (#708, Review zu PR #711, Befund 3).

Das Autouse-Fixture ``schalter_admin_alle_an`` (tests/conftest.py) setzt alle
Admin-Werte auf an; die Bestandstests pruefen deshalb nur die Obergrenze. Ein Zugriff,
der die Settings direkt liest, bliebe dort gruen. Diese Datei schliesst die Luecke:

- ``TestObergrenzeAnAdminAus``: Jede Stelle, die einen der drei Schalter nutzt, ist bei
  eingeschalteter Obergrenze und ausgeschaltetem Admin-Wert aus. Die Tests ersetzen den
  Dienst des Autouse-Fixtures ausdruecklich (``admin_werte``). Die Gegenprobe mit allen
  Admin-Werten an zeigt, dass jeder Fall wirklich am Schalter haengt.
- ``test_kein_direktzugriff_auf_die_obergrenze``: Ausserhalb von core/config.py,
  services/schalter_service.py und dem Start der Takte fuer Abzeichen und Stundenbloecke
  in main.py liest kein
  Code die Obergrenze direkt.
"""

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.v1.funktionen as funktionen_module
import api.v1.merkliste as merkliste_module
import api.v1.metrics as metrics_module
import api.v1.rangliste as rangliste_module
import api.v1.usage as usage_module
from core.config import Settings
from dependencies import (
    get_beitrag_laden,
    get_meilensteine_service,
    get_punkte_service,
    get_settings,
)
from services.abzeichen_service import AbzeichenService, abzeichen_service_setzen
from services.schalter_service import (
    NOTAUS,
    SCHALTER,
    SchalterService,
    schalter_service_setzen,
)

pytestmark = pytest.mark.unit

APP = Path(__file__).resolve().parents[2]
BEITRAG_ID = "11111111-1111-4111-8111-111111111111"
PERSON = {"X-User": "bo-2"}
ADMIN = {"X-User": "admin-1", "X-Is-Admin": "true"}

ALLE_OBERGRENZEN_AN = {schalter.feld: True for schalter in SCHALTER.values()}


@pytest.fixture
def admin_werte(schalter_admin_alle_an):
    """
    Ueberschreibt das Autouse-Fixture: ein eigener Dienst, dessen Admin-Werte der Test
    vor dem ersten Aufruf setzt (``admin_werte["punkte"] = False``).
    """
    werte = {name: True for name in SCHALTER}
    schalter_service_setzen(
        SchalterService(
            admin_werte_lesen=lambda: dict(werte),
            admin_wert_setzen=lambda name, an, admin: werte.__setitem__(name, an),
        )
    )
    return werte


@pytest.fixture
def muster():
    return Mock()


@pytest.fixture
def abzeichen():
    """Ein Abzeichen-Dienst mit einem vorhandenen Abzeichen, ohne Datenbank."""
    repository = Mock()
    repository.lesen.return_value = None
    repository.zeigende.return_value = ["kim-1"]
    dienst = AbzeichenService(repository, Mock(), Settings(**ALLE_OBERGRENZEN_AN))
    dienst._abzeichen["kim-1"] = 1
    abzeichen_service_setzen(dienst)
    yield SimpleNamespace(dienst=dienst, repository=repository)
    abzeichen_service_setzen(None)


@pytest.fixture
def client(
    muster, abzeichen, art9_einwilligung_ohne_datenbank, spielgefuehl_ohne_datenbank
):
    app = FastAPI()
    app.include_router(usage_module.router, prefix="/api/v1/usage")
    app.include_router(metrics_module.router, prefix="/api/v1/metrics")
    app.include_router(merkliste_module.router, prefix="/api/v1/merkliste")
    app.include_router(funktionen_module.router, prefix="/api/v1/funktionen")
    app.include_router(rangliste_module.router, prefix="/api/v1/rangliste")
    app.dependency_overrides[get_settings] = lambda: Settings(**ALLE_OBERGRENZEN_AN)
    app.dependency_overrides[get_punkte_service] = lambda: Mock(
        punkte=AsyncMock(side_effect=RuntimeError("nur bis hierher"))
    )
    app.dependency_overrides[get_meilensteine_service] = lambda: Mock(
        meilensteine=AsyncMock(side_effect=RuntimeError("nur bis hierher"))
    )
    gepostet = Mock()
    gepostet.wochen.side_effect = RuntimeError("nur bis hierher")
    gepostet.stand.side_effect = RuntimeError("nur bis hierher")
    app.dependency_overrides[metrics_module.get_gepostet_service] = lambda: gepostet
    app.dependency_overrides[metrics_module.get_muster_hinweise_service] = lambda: Mock(
        **{"hinweise.side_effect": RuntimeError("nur bis hierher")}
    )

    async def laden(content_id):
        return SimpleNamespace(id=content_id, original_author="kim-1")

    app.dependency_overrides[get_beitrag_laden] = lambda: laden
    nutzung = Mock()
    nutzung.track_content_usage.return_value = True
    nutzung.get_content_usage.return_value = 1
    with patch.object(
        usage_module, "get_usage_service", return_value=nutzung
    ), patch.object(
        usage_module, "get_muster_hinweise_service", return_value=muster
    ), patch.object(
        usage_module, "get_gepostet_service", return_value=gepostet
    ), patch.object(
        merkliste_module,
        "get_merkliste_repository",
        return_value=Mock(**{"liste.return_value": []}),
    ):
        yield TestClient(app, raise_server_exceptions=False)


def _status_aus(feld):
    def pruefen(client, muster, abzeichen):
        antwort = client.get("/api/v1/usage/punkte/status")
        return antwort.status_code == 200 and antwort.json()[feld] is False

    return pruefen


def _feld_aus(pfad, feld="aktiv"):
    """Automatisch abgefragte Endpunkte: 200 mit ``feld`` false statt 404 (Gateway)."""

    def pruefen(client, muster, abzeichen):
        antwort = client.get(pfad, headers=PERSON)
        return antwort.status_code == 200 and antwort.json()[feld] is False

    return pruefen


def _admin_aktiv_aus(pfad):
    def pruefen(client, muster, abzeichen):
        antwort = client.get(pfad, headers=ADMIN)
        return antwort.status_code == 200 and antwort.json()["aktiv"] is False

    return pruefen


def _keine_abzeichen(client, muster, abzeichen):
    return abzeichen.dienst.abzeichen(["kim-1"]) == {}


def _takt_rechnet_nicht(client, muster, abzeichen):
    asyncio.run(abzeichen.dienst.alle_aktualisieren())
    return not abzeichen.repository.zeigende.called


# Paket Spielgefuehl (Schalter-Umbau 27.11.): Punkte, Meilensteine, Muster-Hinweise
# und Rangliste haengen alle am Admin-Wert spielgefuehl_buehne.
STELLEN = {
    "status_punkte": (_status_aus("aktiv"), ("spielgefuehl_buehne",)),
    "eigene_punkte": (
        _feld_aus("/api/v1/usage/users/me/punkte"),
        ("spielgefuehl_buehne",),
    ),
    "meilensteine": (
        _feld_aus("/api/v1/usage/users/me/meilensteine"),
        ("spielgefuehl_buehne",),
    ),
    "muster_hinweise_admin": (
        _admin_aktiv_aus("/api/v1/metrics/muster-hinweise"),
        ("spielgefuehl_buehne",),
    ),
    "merkliste": (_feld_aus("/api/v1/merkliste"), ("merkliste",)),
    "rangliste": (_feld_aus("/api/v1/rangliste"), ("spielgefuehl_buehne",)),
}

FAELLE = [
    pytest.param(stelle, schalter, id=f"{stelle}-{schalter}-aus")
    for stelle, (_, alle) in STELLEN.items()
    for schalter in alle
]


class TestAbzeichenAmNamenNie:
    """
    Schalter-Umbau 27.11.: abzeichen_sichtbar ist weg, Abzeichen gibt es nur in der
    Rangliste. Auch mit allen Obergrenzen und Admin-Werten an keine am Namen.
    """

    def test_status_meldet_keine_abzeichen(self, client):
        antwort = client.get("/api/v1/usage/punkte/status")
        assert antwort.status_code == 200
        assert antwort.json()["abzeichen_sichtbar"] is False

    def test_keine_am_namen(self, client, muster, abzeichen):
        assert _keine_abzeichen(client, muster, abzeichen)

    def test_frage_zur_sichtbarkeit_aus(self, client):
        antwort = client.get(
            "/api/v1/usage/users/me/abzeichen-sichtbarkeit", headers=PERSON
        )
        assert antwort.status_code == 200
        assert antwort.json()["aktiv"] is False

    def test_punkte_einwilligung_altes_modell_aus(self, client):
        antwort = client.get(
            "/api/v1/usage/users/me/punkte-einwilligung", headers=PERSON
        )
        assert antwort.status_code == 200
        assert antwort.json()["aktiv"] is False


class TestObergrenzeAnAdminAus:
    @pytest.mark.parametrize("stelle, schalter", FAELLE)
    def test_aus(self, stelle, schalter, admin_werte, client, muster, abzeichen):
        admin_werte[schalter] = False

        assert STELLEN[stelle][0](client, muster, abzeichen)

    @pytest.mark.parametrize("stelle", list(STELLEN))
    def test_gegenprobe_alle_admin_werte_an(
        self, stelle, admin_werte, client, muster, abzeichen
    ):
        assert not STELLEN[stelle][0](client, muster, abzeichen)


class TestZustimmungFuerMusterAdminAus:
    """
    Muster-Hinweise aus Zustimmungen (muster_stimmen): Obergrenzen an, je ein
    Admin-Wert der Kette punkte -> spielgefuehl_buehne -> muster_stimmen aus, keine
    Meldung. Eigener Client, weil das Spielgefuehl-Modell die anderen Stellen oben
    umschaltet.
    """

    @pytest.fixture
    def abstimmen(self, admin_werte, spielgefuehl_ohne_datenbank):
        import api.v1.voting as voting_module
        from domain.models.vote import VoteResponse
        from dependencies import get_voting_service

        dienst = Mock()
        dienst.set_like.return_value = VoteResponse(
            content_id=BEITRAG_ID, vote_type=None, message="ok"
        )

        async def laden(content_id):
            return SimpleNamespace(id=content_id, original_author="kim-1")

        app = FastAPI()
        app.include_router(voting_module.router, prefix="/api/v1/voting")
        app.dependency_overrides[get_settings] = lambda: Settings(
            spielgefuehl_buehne_aktiv=True, muster_stimmen_aktiv=True
        )
        app.dependency_overrides[get_beitrag_laden] = lambda: laden
        app.dependency_overrides[get_voting_service] = lambda: dienst
        spielgefuehl_ohne_datenbank.stimmen_eingewilligte.side_effect = set
        muster = Mock()
        with patch.object(
            voting_module, "get_muster_hinweise_service", return_value=muster
        ):
            yield TestClient(app), muster

    def _gemeldet(self, abstimmen) -> bool:
        client, muster = abstimmen
        antwort = client.put(
            f"/api/v1/voting/content/{BEITRAG_ID}/like", headers=PERSON
        )
        assert antwort.status_code == 200
        return muster.zustimmung_melden.called

    @pytest.mark.parametrize("schalter", ["muster_stimmen", "spielgefuehl_buehne"])
    def test_aus(self, schalter, admin_werte, abstimmen):
        admin_werte[schalter] = False

        assert not self._gemeldet(abstimmen)

    def test_gegenprobe_alle_admin_werte_an(self, abstimmen):
        assert self._gemeldet(abstimmen)


# Felder der Obergrenze in Settings und die Felder des Not-Aus (notaus_wirksam).
FELDER = {schalter.feld for schalter in SCHALTER.values()} | set(NOTAUS.values())
OBERGRENZE = FELDER
# Wo die Obergrenze direkt gelesen werden darf: die Definition, der Dienst, und der
# Start des Abzeichen-Takts (laeuft nur mit Obergrenze; ob er rechnet, entscheidet je
# Lauf der Admin-Wert).
ERLAUBT = {
    Path("core/config.py"): None,
    Path("services/schalter_service.py"): None,
    Path("main.py"): {
        # Der Takt rechnet die Abzeichen fuer die Rangliste des Pakets Spielgefuehl.
        "settings.spielgefuehl_buehne_aktiv",
        # Der Takt rechnet die Stundenbloecke des Team-Fortschritts quasi-live vor.
        "settings.teams_aktiv",
        "settings.team_live_aktiv",
    },
}


def _direktzugriffe():
    for datei in sorted(APP.rglob("*.py")):
        relativ = datei.relative_to(APP)
        if relativ.parts[0] in ("tests", ".venv", "venv"):
            continue
        erlaubt = ERLAUBT.get(relativ, set())
        if erlaubt is None:
            continue
        for knoten in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            if isinstance(knoten, ast.Attribute) and knoten.attr in OBERGRENZE:
                zugriff = ast.unparse(knoten)
            elif isinstance(knoten, ast.Constant) and knoten.value in FELDER:
                # getattr(settings, "teams_aktiv") ginge sonst am Waechter vorbei
                zugriff = repr(knoten.value)
            else:
                continue
            if zugriff not in erlaubt:
                yield f"{relativ}:{knoten.lineno}: {zugriff}"


def test_kein_direktzugriff_auf_die_obergrenze():
    """Alle Stellen fragen schalter_wirksam (services/schalter_service.py)."""
    assert list(_direktzugriffe()) == []


def test_waechter_erkennt_einen_direktzugriff(tmp_path, monkeypatch):
    """Der Waechter selbst: ein Direktzugriff in einer neuen Datei macht ihn rot."""
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "neu.py").write_text(
        "def f(settings):\n    return settings.teams_aktiv\n", encoding="utf-8"
    )
    (tmp_path / "api" / "auch.py").write_text(
        "def g(s):\n    return getattr(s, 'gepostet_ohne_konto_aktiv')\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(globals(), "APP", tmp_path)

    assert list(_direktzugriffe()) == [
        "api/auch.py:2: 'gepostet_ohne_konto_aktiv'",
        "api/neu.py:2: settings.teams_aktiv",
    ]
