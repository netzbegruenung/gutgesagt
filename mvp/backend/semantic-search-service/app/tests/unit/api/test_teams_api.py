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
from domain.saisons import Saison
from core.config import Settings
from dependencies import get_einladung_service, get_settings
from domain.teams import (
    EINWILLIGUNG_GELTEND,
    EINWILLIGUNG_KENNUNG,
    EINWILLIGUNG_WORTLAUTE,
    OEFFENTLICH_KENNUNG,
)
from repositories.team_repository import Mitgliedschaft, OeffentlichAntwort
from services.beitrag_fuer_aufrufer import BEITRAG, Aufrufer, personen_fuer_aufrufer
from services.einladung_service import EinladungService
from services.team_service import TeamService, team_service_setzen
from utils.rate_limiter import (
    einladung_pruefen_rate_limiter,
    einladung_rate_limiter,
    team_beitreten_rate_limiter,
)
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
    limiter = (
        einladung_rate_limiter,
        einladung_pruefen_rate_limiter,
        team_beitreten_rate_limiter,
    )
    for l in limiter:
        l._requests.clear()
    yield
    for l in limiter:
        l._requests.clear()


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


def _client(einladung_repo, team_repo, settings=AN, vorschlag=None, saisons=None):
    teams = TeamService(
        team_repo,
        settings,
        saison=lambda: "2026",
        vorschlag=(lambda: vorschlag) if vorschlag else None,
        saisons=(lambda: saisons) if saisons is not None else None,
    )
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
        # Ohne angelegte Saison ist der Vorschlag die aktuelle Saison
        assert body["saison_vorschlag"] == "2026"
        # Zur Auswahl die Emoji der Positivliste mit Name und Kategorie; die sechs
        # frueheren Schluessel bleiben gueltig, stehen aber nicht mehr zur Wahl.
        motive = {m["schluessel"]: m for m in body["motive"]}
        assert motive["🌻"]["name"] == "Sonnenblume"
        assert motive["🌻"]["kategorie"] == "tiere-natur"
        assert "vogel" not in motive
        assert [k["name"] for k in body["motiv_kategorien"]][0] == "Tiere & Natur"
        assert body["teamname_hinweis"] == (
            "Anlass, Ort, Saison oder öffentliche Gruppe mit schriftlicher "
            "Zustimmung; keine Namen zu Religion, Gesundheit, sexueller "
            "Orientierung, Herkunft oder Gewerkschaft."
        )
        mit_team, ohne_team = body["einladungen"]
        assert mit_team["team"] == {
            "name": "BDK 26 Berlin",
            "motiv": "vogel",
            "motiv_name": "Vogel",
            "saison": "2026",
            "art": "anlass",
            "zustimmung_am": None,
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
        # Ohne Angabe ein Team nach Anlass, Ort oder Saison, ohne Datum
        assert werte["team_art"] == "anlass"
        assert werte["team_zustimmung_am"] is None
        assert antwort.json()["team"]["mitglieder"] == 36
        assert antwort.json()["team"]["art"] == "anlass"

    def test_vorschlag_ist_die_naechste_saison(self, einladung_repo, team_repo):
        # Vor dem Beginn von "Winter 26/27": Formular und leere Saison bekommen schon sie
        client = _client(einladung_repo, team_repo, vorschlag="Winter 26/27")
        body = client.get("/api/v1/einladungen", headers=ADMIN).json()
        assert body["saison_vorschlag"] == "Winter 26/27"
        assert body["aktuelle_saison"] == "2026"

        antwort = client.post(
            "/api/v1/einladungen",
            headers=ADMIN,
            json={
                "notiz": "BDK",
                "erlaubte_einloesungen": 30,
                "gueltig_bis": (heute_utc() + timedelta(days=14)).isoformat(),
                "team_name": "BDK 26 Berlin",
                "team_motiv": "vogel",
            },
        )
        assert antwort.status_code == 201
        assert einladung_repo.anlegen.call_args.kwargs["team_saison"] == "Winter 26/27"

    def test_saison_mit_schraegstrich_geht_wie_bei_den_saisons(
        self, einladung_repo, team_repo
    ):
        # Als Saison anlegbar, am Teamlink frueher 422 (UX-Review 26.11.): jetzt gleich
        antwort = _client(einladung_repo, team_repo).post(
            "/api/v1/einladungen",
            headers=ADMIN,
            json={
                "notiz": "BDK",
                "erlaubte_einloesungen": 30,
                "gueltig_bis": (heute_utc() + timedelta(days=14)).isoformat(),
                "team_name": "BDK-Stand",
                "team_motiv": "vogel",
                "team_saison": "Winter 26/27",
            },
        )
        assert antwort.status_code == 201
        assert einladung_repo.anlegen.call_args.kwargs["team_saison"] == "Winter 26/27"

    def test_anlegen_team_nach_gruppe_mit_datum(self, einladung_repo, team_repo):
        tag = (heute_utc() - timedelta(days=3)).isoformat()
        antwort = _client(einladung_repo, team_repo).post(
            "/api/v1/einladungen",
            headers=ADMIN,
            json={
                "notiz": "Gruppe",
                "erlaubte_einloesungen": 30,
                "gueltig_bis": (heute_utc() + timedelta(days=14)).isoformat(),
                "team_name": "Die grüne Welle",
                "team_motiv": "vogel",
                "team_art": "gruppe",
                "team_zustimmung_am": tag,
            },
        )

        assert antwort.status_code == 201
        werte = einladung_repo.anlegen.call_args.kwargs
        assert werte["team_art"] == "gruppe"
        assert werte["team_zustimmung_am"].isoformat() == tag
        # Admin-Antwort: Art und Datum als Nachweis, weiter nur die Zahl der Mitglieder
        team = antwort.json()["team"]
        assert team["art"] == "gruppe"
        assert team["zustimmung_am"] == tag
        assert set(team) == {
            "name",
            "motiv",
            "motiv_name",
            "saison",
            "art",
            "zustimmung_am",
            "mitglieder",
        }

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

    @pytest.mark.parametrize("motiv", ["🌻", "⚖️", "vogel", "sprechblase"])
    def test_anlegen_mit_emoji_oder_frueherem_motiv(
        self, einladung_repo, team_repo, motiv
    ):
        # Neue Teams waehlen aus der Positivliste; Teams mit Vogel und Sprechblase gibt
        # es auf Prod schon, ihre Schluessel gelten weiter.
        antwort = _client(einladung_repo, team_repo).post(
            "/api/v1/einladungen",
            headers=ADMIN,
            json={
                "notiz": "Vorhut",
                "erlaubte_einloesungen": 30,
                "gueltig_bis": (heute_utc() + timedelta(days=14)).isoformat(),
                "team_name": "Vorhut",
                "team_motiv": motiv,
            },
        )

        assert antwort.status_code == 201
        assert einladung_repo.anlegen.call_args.kwargs["team_motiv"] == motiv

    @pytest.mark.parametrize(
        "motiv",
        [
            # Religion
            "✝️",
            "☪️",
            "🕉️",
            "✡️",
            "☸️",
            "☦️",
            "🛐",
            "📿",
            "⛪",
            "🕌",
            "🕍",
            "⛩️",
            "🕋",
            "🕎",
            "🧿",
            # Gender, Trans, Sexualitaet
            "⚧️",
            "♀️",
            "♂️",
            "🏳️\u200d🌈",
            "🌈",
            # Gesundheit, Behinderung, Medizin, Koerper
            "♿",
            "🦽",
            "🦼",
            "🦯",
            "🦻",
            "💉",
            "💊",
            "🩸",
            "🦠",
            "🧬",
            "🧠",
            # Smileys & Personen, Flaggen
            "😀",
            "🤰",
            "💏",
            "💑",
            "🇩🇪",
            "🏴",
            # Hautton, Waffen, mehrdeutig
            "👍🏽",
            "🔫",
            "🗡️",
            "✊",
            "🙏",
            "🍆",
            "🍑",
            # Nicht genau der Eintrag: ohne Variantenwaehler, ZWJ-Sequenz, Freitext
            "⚖",
            "🌻\ufe0f",
            "🐦\u200d⬛",
            "🌻🌻",
            "drache",
            "",
        ],
    )
    def test_motiv_ausserhalb_der_liste_abgelehnt(
        self, einladung_repo, team_repo, motiv
    ):
        antwort = _client(einladung_repo, team_repo).post(
            "/api/v1/einladungen",
            headers=ADMIN,
            json={
                "notiz": "Vorhut",
                "erlaubte_einloesungen": 30,
                "gueltig_bis": (heute_utc() + timedelta(days=14)).isoformat(),
                "team_name": "Vorhut",
                "team_motiv": motiv,
            },
        )

        assert antwort.status_code == 422
        einladung_repo.anlegen.assert_not_called()

    @pytest.mark.parametrize(
        "felder",
        [
            {"team_name": "x" * 41, "team_motiv": "vogel"},
            {"team_name": "Vorhut"},
            {"team_name": "Vorhut", "team_motiv": "drache"},
            {"team_name": "<b>Vorhut</b>", "team_motiv": "vogel"},
            {"team_motiv": "vogel"},
            {"team_name": "Vorhut", "team_motiv": "vogel", "team_saison": "x" * 21},
            # Der Teamname bleibt ohne Schraegstrich, die Saison ohne Markup
            {"team_name": "BDK/Stand", "team_motiv": "vogel"},
            {"team_name": "Vorhut", "team_motiv": "vogel", "team_saison": "<b>W</b>"},
            # Team nach Gruppe ohne Datum der Zustimmung
            {"team_name": "Netzfeuerwehr", "team_motiv": "vogel", "team_art": "gruppe"},
            # Datum in der Zukunft
            {
                "team_name": "Netzfeuerwehr",
                "team_motiv": "vogel",
                "team_art": "gruppe",
                "team_zustimmung_am": (heute_utc() + timedelta(days=1)).isoformat(),
            },
            # Datum nur bei Team nach Gruppe
            {
                "team_name": "Bayreuth",
                "team_motiv": "vogel",
                "team_zustimmung_am": "2026-11-20",
            },
            {
                "team_name": "Bayreuth",
                "team_motiv": "vogel",
                "team_art": "anlass",
                "team_zustimmung_am": "2026-11-20",
            },
            # Unbekannte Art, Art ohne Teamname
            {"team_name": "Bayreuth", "team_motiv": "vogel", "team_art": "verein"},
            {"team_art": "gruppe", "team_zustimmung_am": "2026-11-20"},
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
            "team_saison_id": None,
            "team_art": "anlass",
            "team_zustimmung_am": None,
        }

        antwort = client.patch(
            url,
            headers=ADMIN,
            json={
                "team_name": "Netzfeuerwehr",
                "team_motiv": "waage",
                "team_saison": "26",
                "team_art": "gruppe",
                "team_zustimmung_am": "2026-11-20",
            },
        )
        assert antwort.status_code == 200
        assert einladung_repo.aendern.call_args.kwargs["team_art"] == "gruppe"
        assert einladung_repo.aendern.call_args.kwargs["team_zustimmung_am"] == date(
            2026, 11, 20
        )

        antwort = client.patch(
            url,
            headers=ADMIN,
            json={
                "team_name": "Netzfeuerwehr",
                "team_motiv": "waage",
                "team_art": "gruppe",
            },
        )
        assert antwort.status_code == 422

        antwort = client.patch(url, headers=ADMIN, json={"team_name": None})
        assert antwort.status_code == 200
        assert einladung_repo.aendern.call_args.kwargs == {
            "team_name": None,
            "team_motiv": None,
            "team_saison": None,
            "team_saison_id": None,
            "team_art": None,
            "team_zustimmung_am": None,
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
        # Name fuer Alt-Text und Beschriftung, auch fuer die frueheren Schluessel
        assert team["motiv_name"] == "Vogel"
        assert team["saison"] == "2026"
        assert team["art"] == "anlass"
        assert team["mitglieder"] == 36
        assert team["naechste_nummer"] == 37
        assert team["eigene_nummer"] is None
        assert team["einwilligung_kennung"] == "team-2026-11-26"
        # Wortlaut vom 26.11.2026, wortgleich (Mitgliedschaft und Team-Summe mit
        # Kommentaren und Meldungen "Ja, gepostet")
        assert team["einwilligung_text"] == (
            "Ich willige ausdrücklich ein, dass Gut gesagt an meinem Konto speichert, "
            "dass ich im Team BDK 26 Berlin bin, mit meiner Nummer und dem Tag des "
            "Beitritts, und dass die Zahl meiner Beiträge, Bewertungen und "
            "Kommentare und meiner Meldungen „Ja, gepostet“ in eine Summe meines "
            "Teams eingeht (Art. 9 Abs. 2 lit. a DSGVO). Meine Teams sehe nur ich, "
            "die Summe nur Mitglieder des Teams, nie mit einzelnen Namen. Ich kann "
            "die Einwilligung jederzeit unter „Meine Teams“ mit „Team verlassen“ "
            "widerrufen; dann wird der Eintrag sofort gelöscht."
        )
        assert team["knopf_ja"] == "Ja, speichert, dass ich im Team BDK 26 Berlin bin"
        assert team["knopf_nein"] == "Nein, ohne Team weiter"
        # Schalter teams_oeffentlich aus: keine zweite Frage
        assert team["oeffentlich_kennung"] is None
        assert team["oeffentlich_text"] is None

    def test_team_nach_gruppe_liefert_art_ohne_datum(self, einladung_repo, team_repo):
        einladung_repo.nach_code.return_value = _zeile(
            team_name="Netzfeuerwehr",
            team_art="gruppe",
            team_zustimmung_am=date(2026, 11, 20),
        )

        team = (
            _client(einladung_repo, team_repo)
            .post("/api/v1/einladungen/pruefen", json={"code": CODE})
            .json()["team"]
        )

        assert team["name"] == "Netzfeuerwehr"
        assert team["art"] == "gruppe"
        # Das Datum der Zustimmung ist nur fuer Admins
        assert "zustimmung_am" not in team
        assert "2026-11-20" not in repr(team)

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

    def test_nicht_einloesbar_fuer_mitglied_schon_dabei(
        self, einladung_repo, team_repo
    ):
        # Aufgebraucht oder abgelaufen: Ein Mitglied sieht trotzdem seine Nummer.
        einladung_repo.nach_code.return_value = _zeile(einloesungen=50)
        team_repo.mitgliedschaft.return_value = _mitgliedschaft(nummer=12)

        body = (
            _client(einladung_repo, team_repo)
            .post("/api/v1/einladungen/pruefen", json={"code": CODE}, headers=PERSON)
            .json()
        )

        assert body["einloesbar"] is False
        assert body["team"]["eigene_nummer"] == 12

    def test_nicht_einloesbar_angemeldet_ohne_mitgliedschaft_kein_team(
        self, einladung_repo, team_repo
    ):
        einladung_repo.nach_code.return_value = _zeile(abgeschaltet=True)

        antwort = _client(einladung_repo, team_repo).post(
            "/api/v1/einladungen/pruefen", json={"code": CODE}, headers=PERSON
        )

        assert antwort.json() == {"einloesbar": False, "team": None}


class TestBeitreten:
    def _beitreten(self, client, headers=PERSON, **json):
        return client.post(
            "/api/v1/einladungen/beitreten",
            json={
                "code": CODE,
                "einwilligung": True,
                "einwilligung_kennung": EINWILLIGUNG_KENNUNG,
                **json,
            },
            headers=headers,
        )

    def test_neu(self, einladung_repo, team_repo):
        antwort = self._beitreten(_client(einladung_repo, team_repo))

        assert antwort.status_code == 200
        assert antwort.json() == {
            "team": {
                "name": "BDK 26 Berlin",
                "motiv": "vogel",
                "motiv_name": "Vogel",
                "saison": "2026",
            },
            "nummer": 37,
            "neu": True,
        }
        kw = team_repo.beitreten.call_args.kwargs
        assert kw["konto"] == "konto-1" and kw["code"] == CODE
        assert kw["einwilligung_kennung"] == EINWILLIGUNG_KENNUNG

    def test_nur_der_aktuelle_wortlaut_gilt(self):
        # Fuer neue Einwilligungen gilt nur die Kennung vom 26.11.2026; die vom
        # 25.11.2026 bleibt als frueherer Eintrag stehen (vorhandene Nachweise).
        assert EINWILLIGUNG_KENNUNG == "team-2026-11-26"
        assert EINWILLIGUNG_GELTEND == {"team-2026-11-26"}
        assert list(EINWILLIGUNG_WORTLAUTE) == ["team-2026-11-25", "team-2026-11-26"]

    @pytest.mark.parametrize("kennung", ["team-1999-01-01", "team-2026-11-25", None])
    def test_unbekannter_frueherer_oder_fehlender_wortlaut_422(
        self, einladung_repo, team_repo, kennung
    ):
        antwort = self._beitreten(
            _client(einladung_repo, team_repo), einwilligung_kennung=kennung
        )

        assert antwort.status_code == 422
        team_repo.beitreten.assert_not_called()

    def test_oeffentlich_ohne_kennung_422(self, einladung_repo, team_repo):
        antwort = self._beitreten(_client(einladung_repo, team_repo), oeffentlich=True)

        assert antwort.status_code == 422
        team_repo.beitreten.assert_not_called()

    def test_rate_limit_je_person_nicht_je_anschluss(self, einladung_repo, team_repo):
        client = _client(einladung_repo, team_repo)
        for _ in range(team_beitreten_rate_limiter.max_requests):
            assert self._beitreten(client).status_code == 200

        assert self._beitreten(client).status_code == 429
        # Andere Person am selben Anschluss (Saal-WLAN): eigenes Budget
        anders = {"X-User": "konto-2"}
        assert self._beitreten(client, headers=anders).status_code == 200
        # Und das Einloesen ohne Konto bleibt unberuehrt
        assert einladung_rate_limiter._requests == {}

    def test_schon_dabei(self, einladung_repo, team_repo):
        team_repo.beitreten.return_value = (_mitgliedschaft(nummer=12), False)

        antwort = self._beitreten(_client(einladung_repo, team_repo))

        assert antwort.json()["neu"] is False
        assert antwort.json()["nummer"] == 12

    def test_mit_oeffentlich(self, einladung_repo, team_repo):
        self._beitreten(
            _client(einladung_repo, team_repo),
            oeffentlich=True,
            oeffentlich_kennung=OEFFENTLICH_KENNUNG,
        )

        args = team_repo.oeffentlich_setzen.call_args.args
        assert args[:3] == ("konto-1", True, OEFFENTLICH_KENNUNG)

    def test_oeffentlich_ohne_schalter_nicht(self, einladung_repo, team_repo):
        self._beitreten(
            _client(einladung_repo, team_repo, NUR_TEAMS),
            oeffentlich=True,
            oeffentlich_kennung=OEFFENTLICH_KENNUNG,
        )

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
                "team_einwilligung_kennung": EINWILLIGUNG_KENNUNG,
            },
        )

        assert antwort.status_code == 202
        bei_angelegt = service._konten.konto_anlegen.call_args.kwargs["bei_angelegt"]
        bei_angelegt("konto-neu")
        kw = team_repo.beitreten.call_args.kwargs
        assert kw["konto"] == "konto-neu"
        assert kw["einwilligung_kennung"] == EINWILLIGUNG_KENNUNG

    @pytest.mark.parametrize("kennung", [None, "team-1999-01-01", "team-2026-11-25"])
    def test_einwilligung_ohne_geltenden_wortlaut_422(
        self, einladung_repo, team_repo, kennung
    ):
        client = _client(einladung_repo, team_repo)
        service = client.app.dependency_overrides[get_einladung_service]()

        antwort = client.post(
            "/api/v1/einladungen/einloesen",
            json={
                "code": CODE,
                "email": "neu@example.org",
                "team_einwilligung": True,
                "team_einwilligung_kennung": kennung,
            },
        )

        assert antwort.status_code == 422
        assert "team_einwilligung_kennung" in repr(antwort.json()["detail"])
        service._konten.konto_anlegen.assert_not_called()
        einladung_repo.einloesung_zaehlen.assert_not_called()

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

    def test_team_der_naechsten_saison_ist_nicht_vergangen(
        self, einladung_repo, team_repo
    ):
        # Teamlink vor dem Saisonbeginn: das Team steht nicht unter "Vergangene Saisons"
        team_repo.meine.return_value = [
            _mitgliedschaft("Winter 26/27", 1),
            _mitgliedschaft("2026", 37),
            _mitgliedschaft("2025", 3),
        ]
        body = (
            _client(einladung_repo, team_repo, vorschlag="Winter 26/27")
            .get("/api/v1/teams/meine", headers=PERSON)
            .json()
        )
        assert body["aktuelle_saison"] == "2026"
        assert [t["aktuelle_saison"] for t in body["teams"]] == [True, True, False]

    def test_ohne_oeffentlich_kein_umschalter(self, einladung_repo, team_repo):
        body = (
            _client(einladung_repo, team_repo, NUR_TEAMS)
            .get("/api/v1/teams/meine", headers=PERSON)
            .json()
        )

        assert body["oeffentlich_verfuegbar"] is False
        assert body["oeffentlich_text"] is None
        team_repo.oeffentlich_lesen.assert_not_called()

    def test_ohne_schalter_und_ohne_teams_leer(self, einladung_repo, team_repo):
        # 200 statt 404: "Meine Beitraege" laedt selbst nach (Gateway-fail2ban)
        team_repo.meine.return_value = []
        antwort = _client(einladung_repo, team_repo, AUS).get(
            "/api/v1/teams/meine", headers=PERSON
        )

        assert antwort.status_code == 200
        body = antwort.json()
        assert body["teams_aktiv"] is False
        assert body["teams"] == []
        assert body["oeffentlich_verfuegbar"] is False

    def test_ohne_schalter_eigene_teams_zum_verlassen(self, einladung_repo, team_repo):
        # Widerruf so leicht wie die Einwilligung: auch nach dem Ausschalten sichtbar.
        body = (
            _client(einladung_repo, team_repo, AUS)
            .get("/api/v1/teams/meine", headers=PERSON)
            .json()
        )

        assert body["teams_aktiv"] is False
        assert body["oeffentlich_verfuegbar"] is False
        assert len(body["teams"]) == 2

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


class TestSaisonPerId:
    """Befund 6: Ein Teamlink verweist auf eine vorhandene Saison per ID."""

    WINTER = Saison(
        uuid.UUID("33333333-3333-4333-8333-333333333333"),
        "Winter 26/27",
        date(2026, 11, 27),
        date(2027, 2, 24),
        5,
    )

    def _anlegen(self, client, saison):
        return client.post(
            "/api/v1/einladungen",
            headers=ADMIN,
            json={
                "notiz": "BDK",
                "erlaubte_einloesungen": 5,
                "gueltig_bis": "2026-12-06",
                "team_name": "BDK",
                "team_motiv": "waage",
                "team_saison": saison,
            },
        )

    def test_saison_mit_schraegstrich_bekommt_ihre_id(self, einladung_repo, team_repo):
        client = _client(einladung_repo, team_repo, saisons=[self.WINTER])
        self._anlegen(client, "Winter 26/27")
        kwargs = einladung_repo.anlegen.call_args.kwargs
        assert (kwargs["team_saison"], kwargs["team_saison_id"]) == (
            "Winter 26/27",
            self.WINTER.id,
        )

    def test_unbekannte_saison_ergibt_422(self, einladung_repo, team_repo):
        client = _client(einladung_repo, team_repo, saisons=[self.WINTER])
        antwort = self._anlegen(client, "2026")
        assert antwort.status_code == 422
        assert "Diese Saison gibt es nicht" in antwort.json()["detail"]
        einladung_repo.anlegen.assert_not_called()
