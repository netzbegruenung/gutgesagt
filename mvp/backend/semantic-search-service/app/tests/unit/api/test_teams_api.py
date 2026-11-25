"""
Teams ueber die API: Teamfelder an Einladungen (Admin), das Team in /pruefen,
/einladungen/beitreten, Meine Teams (/teams/meine, Team verlassen, Team öffentlich am
Namen zeigen), die aktuelle Saison auf der Seite Schalter und Teams am Namen einer
Beitragskarte. Repositories gemockt; der EinladungService und der TeamService sind
die echten.
"""

import uuid
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.v1.teams as teams_module
from api.v1.einladungen import router as einladungen_router
from api.v1.schalter import router as schalter_router
from api.v1.teams import router as teams_router
from core.config import Settings
from dependencies import get_einladung_service, get_settings
from domain.teams import EINWILLIGUNG_KENNUNG, OEFFENTLICH_KENNUNG
from repositories.team_repository import Mitgliedschaft, OeffentlichAntwort
from services.beitrag_fuer_aufrufer import BEITRAG, Aufrufer, personen_fuer_aufrufer
from services.einladung_service import EinladungService
from services.team_service import TeamService, team_service_setzen
from utils.rate_limiter import einladung_pruefen_rate_limiter, einladung_rate_limiter
from utils.utc_tag import heute_utc

pytestmark = [pytest.mark.unit, pytest.mark.api]

CODE = "Ab3dEf6hIj9kLm2nOp4qRs"
ADMIN = {"X-User": "admin", "X-Is-Admin": "true"}
PERSON = {"X-User": "konto-1"}
AN = Settings(teams_aktiv=True, teams_oeffentlich_aktiv=True)
NUR_TEAMS = Settings(teams_aktiv=True, teams_oeffentlich_aktiv=False)
AUS = Settings(teams_aktiv=False, teams_oeffentlich_aktiv=False)
MID = uuid.UUID("44444444-4444-4444-4444-444444444444")


def _zeile(**werte):
    standard = dict(
        id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        code=CODE,
        notiz="Vorhut",
        erlaubte_einloesungen=50,
        einloesungen=3,
        gueltig_bis=heute_utc() + timedelta(days=14),
        abgeschaltet=False,
        angelegt_am=heute_utc(),
        team_name="BDK 26 Berlin",
        team_motiv="vogel",
        team_saison="2026",
    )
    standard.update(werte)
    return SimpleNamespace(**standard)


def _mitgliedschaft(saison="2026", nummer=37):
    return Mitgliedschaft(
        id=MID,
        team_name="BDK 26 Berlin",
        team_motiv="vogel",
        saison=saison,
        nummer=nummer,
        eingetreten_am=date(2026, 11, 25),
    )


@pytest.fixture(autouse=True)
def frische_limits():
    einladung_rate_limiter._requests.clear()
    einladung_pruefen_rate_limiter._requests.clear()
    yield
    einladung_rate_limiter._requests.clear()
    einladung_pruefen_rate_limiter._requests.clear()


@pytest.fixture
def einladung_repo():
    repo = Mock()
    repo.nach_code.return_value = _zeile()
    repo.alle.return_value = [_zeile(), _zeile(id=uuid.uuid4(), team_name=None)]
    repo.anlegen.side_effect = lambda **w: _zeile(**w)
    repo.aendern.side_effect = lambda einladung_id, **w: _zeile(**w)
    repo.einloesung_zaehlen.return_value = True
    return repo


@pytest.fixture
def team_repo():
    repo = Mock()
    repo.mitglieder_je_team.side_effect = lambda teams: {t: 36 for t in teams}
    repo.letzte_nummer.return_value = 36
    repo.mitgliedschaft.return_value = None
    repo.beitreten.return_value = (_mitgliedschaft(), True)
    repo.meine.return_value = [_mitgliedschaft(), _mitgliedschaft("2025", 3)]
    repo.oeffentlich_lesen.return_value = None
    repo.verlassen.return_value = True
    repo.oeffentliche_teams.return_value = {}
    return repo


def _client(einladung_repo, team_repo, settings=AN):
    teams = TeamService(team_repo, settings, saison=lambda: "2026")
    team_service_setzen(teams)
    service = EinladungService(einladung_repo, Mock(), teams)
    app = FastAPI()
    app.include_router(einladungen_router, prefix="/api/v1/einladungen")
    app.include_router(teams_router, prefix="/api/v1/teams")
    app.include_router(schalter_router, prefix="/api/v1/moderation/schalter")
    app.dependency_overrides[get_einladung_service] = lambda: service
    app.dependency_overrides[teams_module._service] = lambda: teams
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


class TestAdmin:
    def test_liste_zeigt_je_team_nur_die_zahl(self, einladung_repo, team_repo):
        body = (
            _client(einladung_repo, team_repo)
            .get("/api/v1/einladungen", headers=ADMIN)
            .json()
        )

        assert body["teams_aktiv"] is True
        assert body["aktuelle_saison"] == "2026"
        assert {m["schluessel"] for m in body["motive"]} >= {"vogel", "laufschuh"}
        assert "Personen" in body["teamname_hinweis"]
        mit_team, ohne_team = body["einladungen"]
        assert mit_team["team"] == {
            "name": "BDK 26 Berlin",
            "motiv": "vogel",
            "saison": "2026",
            "mitglieder": 36,
        }
        assert ohne_team["team"] is None
        # Nirgends eine Kennung von Mitgliedern
        assert "konto" not in repr(body)
        team_repo.meine.assert_not_called()

    def test_liste_ohne_schalter_ohne_teams(self, einladung_repo, team_repo):
        body = (
            _client(einladung_repo, team_repo, AUS)
            .get("/api/v1/einladungen", headers=ADMIN)
            .json()
        )

        assert body["teams_aktiv"] is False
        assert all(e["team"] is None for e in body["einladungen"])
        team_repo.mitglieder_je_team.assert_not_called()

    def test_anlegen_mit_team_und_aktueller_saison(self, einladung_repo, team_repo):
        antwort = _client(einladung_repo, team_repo).post(
            "/api/v1/einladungen",
            headers=ADMIN,
            json={
                "notiz": "Vorhut",
                "erlaubte_einloesungen": 30,
                "gueltig_bis": (heute_utc() + timedelta(days=14)).isoformat(),
                "team_name": "  Netzfeuerwehr   Vorhut ",
                "team_motiv": "laufschuh",
            },
        )

        assert antwort.status_code == 201
        werte = einladung_repo.anlegen.call_args.kwargs
        assert werte["team_name"] == "Netzfeuerwehr Vorhut"
        assert werte["team_motiv"] == "laufschuh"
        assert werte["team_saison"] == "2026"
        assert antwort.json()["team"]["mitglieder"] == 36

    def test_anlegen_ohne_schalter_ignoriert_teamfelder(
        self, einladung_repo, team_repo
    ):
        antwort = _client(einladung_repo, team_repo, AUS).post(
            "/api/v1/einladungen",
            headers=ADMIN,
            json={
                "notiz": "Vorhut",
                "erlaubte_einloesungen": 30,
                "gueltig_bis": (heute_utc() + timedelta(days=14)).isoformat(),
                "team_name": "Vorhut",
                "team_motiv": "laufschuh",
            },
        )

        assert antwort.status_code == 201
        assert einladung_repo.anlegen.call_args.kwargs["team_name"] is None

    @pytest.mark.parametrize(
        "felder",
        [
            {"team_name": "x" * 41, "team_motiv": "vogel"},
            {"team_name": "Vorhut"},
            {"team_name": "Vorhut", "team_motiv": "drache"},
            {"team_name": "<b>Vorhut</b>", "team_motiv": "vogel"},
            {"team_motiv": "vogel"},
            {"team_name": "Vorhut", "team_motiv": "vogel", "team_saison": "x" * 21},
        ],
    )
    def test_ungueltige_teamfelder(self, einladung_repo, team_repo, felder):
        antwort = _client(einladung_repo, team_repo).post(
            "/api/v1/einladungen",
            headers=ADMIN,
            json={
                "notiz": "Vorhut",
                "erlaubte_einloesungen": 30,
                "gueltig_bis": (heute_utc() + timedelta(days=14)).isoformat(),
                **felder,
            },
        )

        assert antwort.status_code == 422
        einladung_repo.anlegen.assert_not_called()

    def test_team_aendern_und_wegnehmen(self, einladung_repo, team_repo):
        client = _client(einladung_repo, team_repo)
        url = f"/api/v1/einladungen/{uuid.uuid4()}"

        antwort = client.patch(
            url,
            headers=ADMIN,
            json={"team_name": "Bayreuth", "team_motiv": "waage", "team_saison": "26"},
        )
        assert antwort.status_code == 200
        assert einladung_repo.aendern.call_args.kwargs == {
            "team_name": "Bayreuth",
            "team_motiv": "waage",
            "team_saison": "26",
        }

        antwort = client.patch(url, headers=ADMIN, json={"team_name": None})
        assert antwort.status_code == 200
        assert einladung_repo.aendern.call_args.kwargs == {
            "team_name": None,
            "team_motiv": None,
            "team_saison": None,
        }

        antwort = client.patch(url, headers=ADMIN, json={"abgeschaltet": True})
        assert einladung_repo.aendern.call_args.kwargs == {"abgeschaltet": True}

    def test_patch_ohne_aenderung(self, einladung_repo, team_repo):
        antwort = _client(einladung_repo, team_repo).patch(
            f"/api/v1/einladungen/{uuid.uuid4()}", headers=ADMIN, json={}
        )

        assert antwort.status_code == 422


class TestPruefen:
    def test_liefert_team_mit_nummer_und_einwilligung(self, einladung_repo, team_repo):
        antwort = _client(einladung_repo, team_repo, NUR_TEAMS).post(
            "/api/v1/einladungen/pruefen", json={"code": CODE}
        )

        team = antwort.json()["team"]
        assert team["name"] == "BDK 26 Berlin"
        assert team["motiv"] == "vogel"
        assert team["saison"] == "2026"
        assert team["mitglieder"] == 36
        assert team["naechste_nummer"] == 37
        assert team["eigene_nummer"] is None
        assert team["einwilligung_kennung"] == EINWILLIGUNG_KENNUNG
        assert "im Team BDK 26 Berlin bin" in team["einwilligung_text"]
        assert team["knopf_ja"] == "Ja, speichert, dass ich im Team BDK 26 Berlin bin"
        assert team["knopf_nein"] == "Nein, ohne Team weiter"
        # Schalter teams_oeffentlich aus: keine zweite Frage
        assert team["oeffentlich_kennung"] is None
        assert team["oeffentlich_text"] is None

    def test_zweite_frage_nur_mit_schalter(self, einladung_repo, team_repo):
        team = (
            _client(einladung_repo, team_repo)
            .post("/api/v1/einladungen/pruefen", json={"code": CODE})
            .json()["team"]
        )

        assert team["oeffentlich_kennung"] == OEFFENTLICH_KENNUNG
        assert team["oeffentlich_text"]

    def test_angemeldet_schon_dabei(self, einladung_repo, team_repo):
        team_repo.mitgliedschaft.return_value = _mitgliedschaft(nummer=12)

        team = (
            _client(einladung_repo, team_repo)
            .post("/api/v1/einladungen/pruefen", json={"code": CODE}, headers=PERSON)
            .json()["team"]
        )

        assert team["eigene_nummer"] == 12
        team_repo.mitgliedschaft.assert_called_once_with(
            "konto-1", "BDK 26 Berlin", "2026"
        )

    def test_anonym_fragt_keine_mitgliedschaft(self, einladung_repo, team_repo):
        _client(einladung_repo, team_repo).post(
            "/api/v1/einladungen/pruefen",
            json={"code": CODE},
            headers={"X-User": "anonymous"},
        )

        team_repo.mitgliedschaft.assert_not_called()

    def test_ohne_schalter_kein_team(self, einladung_repo, team_repo):
        antwort = _client(einladung_repo, team_repo, AUS).post(
            "/api/v1/einladungen/pruefen", json={"code": CODE}
        )

        assert antwort.json() == {"einloesbar": True, "team": None}

    def test_nicht_einloesbar_kein_team(self, einladung_repo, team_repo):
        einladung_repo.nach_code.return_value = _zeile(einloesungen=50)

        antwort = _client(einladung_repo, team_repo).post(
            "/api/v1/einladungen/pruefen", json={"code": CODE}
        )

        assert antwort.json() == {"einloesbar": False, "team": None}


class TestBeitreten:
    def _beitreten(self, client, **json):
        return client.post(
            "/api/v1/einladungen/beitreten",
            json={"code": CODE, "einwilligung": True, **json},
            headers=PERSON,
        )

    def test_neu(self, einladung_repo, team_repo):
        antwort = self._beitreten(_client(einladung_repo, team_repo))

        assert antwort.status_code == 200
        assert antwort.json() == {
            "team": {"name": "BDK 26 Berlin", "motiv": "vogel", "saison": "2026"},
            "nummer": 37,
            "neu": True,
        }
        kw = team_repo.beitreten.call_args.kwargs
        assert kw["konto"] == "konto-1" and kw["code"] == CODE

    def test_schon_dabei(self, einladung_repo, team_repo):
        team_repo.beitreten.return_value = (_mitgliedschaft(nummer=12), False)

        antwort = self._beitreten(_client(einladung_repo, team_repo))

        assert antwort.json()["neu"] is False
        assert antwort.json()["nummer"] == 12

    def test_mit_oeffentlich(self, einladung_repo, team_repo):
        self._beitreten(_client(einladung_repo, team_repo), oeffentlich=True)

        args = team_repo.oeffentlich_setzen.call_args.args
        assert args[:3] == ("konto-1", True, OEFFENTLICH_KENNUNG)

    def test_oeffentlich_ohne_schalter_nicht(self, einladung_repo, team_repo):
        self._beitreten(_client(einladung_repo, team_repo, NUR_TEAMS), oeffentlich=True)

        team_repo.oeffentlich_setzen.assert_not_called()

    def test_ohne_anmeldung(self, einladung_repo, team_repo):
        antwort = _client(einladung_repo, team_repo).post(
            "/api/v1/einladungen/beitreten", json={"code": CODE, "einwilligung": True}
        )

        assert antwort.status_code == 401
        team_repo.beitreten.assert_not_called()

    def test_ohne_einwilligung(self, einladung_repo, team_repo):
        antwort = self._beitreten(
            _client(einladung_repo, team_repo), einwilligung=False
        )

        assert antwort.status_code == 422
        team_repo.beitreten.assert_not_called()

    def test_ohne_schalter(self, einladung_repo, team_repo):
        antwort = self._beitreten(_client(einladung_repo, team_repo, AUS))

        assert antwort.status_code == 404
        team_repo.beitreten.assert_not_called()

    def test_einladung_ohne_team(self, einladung_repo, team_repo):
        einladung_repo.nach_code.return_value = _zeile(
            team_name=None, team_motiv=None, team_saison=None
        )

        assert self._beitreten(_client(einladung_repo, team_repo)).status_code == 409

    def test_unbekannt(self, einladung_repo, team_repo):
        einladung_repo.nach_code.return_value = None

        assert self._beitreten(_client(einladung_repo, team_repo)).status_code == 410


class TestEinloesen:
    def test_einwilligung_geht_an_den_dienst(self, einladung_repo, team_repo):
        client = _client(einladung_repo, team_repo)
        service = client.app.dependency_overrides[get_einladung_service]()
        service._konten.konto_anlegen.return_value = None

        antwort = client.post(
            "/api/v1/einladungen/einloesen",
            json={
                "code": CODE,
                "email": "neu@example.org",
                "team_einwilligung": True,
            },
        )

        assert antwort.status_code == 202
        assert "bei_angelegt" in service._konten.konto_anlegen.call_args.kwargs

    def test_ohne_einwilligung_kein_team(self, einladung_repo, team_repo):
        client = _client(einladung_repo, team_repo)
        service = client.app.dependency_overrides[get_einladung_service]()

        client.post(
            "/api/v1/einladungen/einloesen",
            json={"code": CODE, "email": "neu@example.org", "team_oeffentlich": True},
        )

        assert service._konten.konto_anlegen.call_args.kwargs == {}


class TestMeineTeams:
    def test_alle_saisons_und_umschalter(self, einladung_repo, team_repo):
        team_repo.oeffentlich_lesen.return_value = OeffentlichAntwort(
            zeigen=True, einwilligung_kennung=OEFFENTLICH_KENNUNG, beantwortet_am=None
        )

        body = (
            _client(einladung_repo, team_repo)
            .get("/api/v1/teams/meine", headers=PERSON)
            .json()
        )

        assert body["aktuelle_saison"] == "2026"
        assert body["oeffentlich_verfuegbar"] is True
        assert body["oeffentlich_zeigen"] is True
        assert body["oeffentlich_kennung"] == OEFFENTLICH_KENNUNG
        jetzt, frueher = body["teams"]
        assert jetzt["id"] == str(MID)
        assert jetzt["motiv_name"] == "Vogel"
        assert jetzt["aktuelle_saison"] is True and jetzt["nummer"] == 37
        assert frueher["aktuelle_saison"] is False and frueher["saison"] == "2025"
        team_repo.meine.assert_called_once_with("konto-1")

    def test_ohne_oeffentlich_kein_umschalter(self, einladung_repo, team_repo):
        body = (
            _client(einladung_repo, team_repo, NUR_TEAMS)
            .get("/api/v1/teams/meine", headers=PERSON)
            .json()
        )

        assert body["oeffentlich_verfuegbar"] is False
        assert body["oeffentlich_text"] is None
        team_repo.oeffentlich_lesen.assert_not_called()

    def test_ohne_schalter_404(self, einladung_repo, team_repo):
        antwort = _client(einladung_repo, team_repo, AUS).get(
            "/api/v1/teams/meine", headers=PERSON
        )

        assert antwort.status_code == 404

    def test_ohne_anmeldung_401(self, einladung_repo, team_repo):
        client = _client(einladung_repo, team_repo)

        assert client.get("/api/v1/teams/meine").status_code == 401
        assert client.delete(f"/api/v1/teams/meine/{MID}").status_code == 401

    def test_verlassen(self, einladung_repo, team_repo):
        antwort = _client(einladung_repo, team_repo, AUS).delete(
            f"/api/v1/teams/meine/{MID}", headers=PERSON
        )

        assert antwort.status_code == 204
        team_repo.verlassen.assert_called_once_with("konto-1", MID)

    def test_fremde_mitgliedschaft_404(self, einladung_repo, team_repo):
        team_repo.verlassen.return_value = False

        antwort = _client(einladung_repo, team_repo).delete(
            f"/api/v1/teams/meine/{MID}", headers=PERSON
        )

        assert antwort.status_code == 404

    def test_oeffentlich_ja_und_nein(self, einladung_repo, team_repo):
        client = _client(einladung_repo, team_repo)

        for zeigen in (True, False):
            antwort = client.put(
                "/api/v1/teams/oeffentlich",
                json={"zeigen": zeigen, "wortlaut": OEFFENTLICH_KENNUNG},
                headers=PERSON,
            )
            assert antwort.status_code == 204
        assert team_repo.oeffentlich_setzen.call_count == 2

    def test_oeffentlich_ja_ohne_schalter_409(self, einladung_repo, team_repo):
        antwort = _client(einladung_repo, team_repo, NUR_TEAMS).put(
            "/api/v1/teams/oeffentlich",
            json={"zeigen": True, "wortlaut": OEFFENTLICH_KENNUNG},
            headers=PERSON,
        )

        assert antwort.status_code == 409

    def test_oeffentlich_unbekannter_wortlaut_422(self, einladung_repo, team_repo):
        antwort = _client(einladung_repo, team_repo).put(
            "/api/v1/teams/oeffentlich",
            json={"zeigen": True, "wortlaut": "erfunden"},
            headers=PERSON,
        )

        assert antwort.status_code == 422


class TestAktuelleSaison:
    def test_admin_setzt_die_saison(self, einladung_repo, team_repo):
        client = _client(einladung_repo, team_repo)

        antwort = client.put(
            "/api/v1/moderation/schalter/einstellungen/aktuelle_saison",
            json={"wert": "2027"},
            headers=ADMIN,
        )

        assert antwort.status_code == 200
        stand = {e["name"]: e for e in antwort.json()["einstellungen"]}
        assert stand["aktuelle_saison"]["wert"] == "2027"
        assert stand["aktuelle_saison"]["standard"] == str(heute_utc().year)
        schalter = {s["name"]: s for s in antwort.json()["schalter"]}
        assert schalter["teams"]["umgebungsvariable"] == "SEMANTIC_SEARCH_TEAMS_AKTIV"
        assert (
            schalter["teams_oeffentlich"]["umgebungsvariable"]
            == "SEMANTIC_SEARCH_TEAMS_OEFFENTLICH_AKTIV"
        )

    def test_nur_admins_und_gueltige_werte(self, einladung_repo, team_repo):
        client = _client(einladung_repo, team_repo)
        url = "/api/v1/moderation/schalter/einstellungen/aktuelle_saison"

        assert client.put(url, json={"wert": "2027"}, headers=PERSON).status_code == 403
        assert client.put(url, json={"wert": " "}, headers=ADMIN).status_code == 422
        antwort = client.put(
            "/api/v1/moderation/schalter/einstellungen/erfunden",
            json={"wert": "x"},
            headers=ADMIN,
        )
        assert antwort.status_code == 404


class TestAmNamen:
    def _beitrag(self):
        return SimpleNamespace(
            original_author="autorin-1",
            autor_name=None,
            ist_eigener_beitrag=None,
            autor_abzeichen=None,
            autor_teams=None,
        )

    def test_pillen_fuer_angemeldete(self, team_repo):
        team_repo.oeffentliche_teams.return_value = {
            "autorin-1": [("BDK 26 Berlin", "vogel"), ("Bayreuth", "waage")]
        }
        team_service_setzen(TeamService(team_repo, AN, saison=lambda: "2026"))
        beitrag = self._beitrag()

        personen_fuer_aufrufer(Aufrufer(kennung="leserin"), ([beitrag], BEITRAG))

        assert [(p.name, p.motiv, p.motiv_name) for p in beitrag.autor_teams] == [
            ("BDK 26 Berlin", "vogel", "Vogel"),
            ("Bayreuth", "waage", "Waage"),
        ]
        team_repo.oeffentliche_teams.assert_called_once_with(["autorin-1"], "2026")

    def test_keine_pillen_fuer_besucher(self, team_repo):
        team_service_setzen(TeamService(team_repo, AN, saison=lambda: "2026"))
        beitrag = self._beitrag()

        personen_fuer_aufrufer(Aufrufer(kennung="anonymous"), ([beitrag], BEITRAG))

        assert beitrag.autor_teams is None
        team_repo.oeffentliche_teams.assert_not_called()

    def test_keine_pillen_ohne_schalter(self, team_repo):
        team_service_setzen(TeamService(team_repo, NUR_TEAMS, saison=lambda: "2026"))
        beitrag = self._beitrag()

        personen_fuer_aufrufer(Aufrufer(kennung="leserin"), ([beitrag], BEITRAG))

        assert beitrag.autor_teams is None
        team_repo.oeffentliche_teams.assert_not_called()
