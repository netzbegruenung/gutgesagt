"""
Teams ueber Einladungen gegen ein echtes PostgreSQL.

Service und Repositories bis in die Tabellen, Keycloak als Attrappe: Nummern laufen
je Team und Saison ohne Luecke und ohne Doppel, auch bei gleichzeitigen Beitritten;
derselbe Beitritt zweimal zaehlt einmal; der Deckel der Einladung gilt; ohne
Schalter und ohne Einwilligung entsteht nichts; "Team verlassen" und das
Loeschkommando loeschen; Admins bekommen nur Zahlen; die Mitgliedschaft traegt
keinen Bezug zur Einladung.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import inspect, text

from core.config import Settings
from domain.interfaces.konten_im_realm import KontoErgebnis
from domain.teams import EINWILLIGUNG_KENNUNG, OEFFENTLICH_KENNUNG
from infrastructure.database.models import (
    Base,
    EinladungZeile,
    EinstellungZeile,
    TeamMitgliedschaftZeile,
    TeamNummerZeile,
    TeamOeffentlichZeile,
)
from repositories.einladung_repository import EinladungRepository
from repositories.einstellung_repository import EinstellungRepository
from repositories.team_repository import TeamRepository
from services.einladung_service import EinladungService, EinladungUngueltig
from services.team_service import Team, TeamService, TeamsAus
from tests.integration import postgres

pytestmark = pytest.mark.integration

HEUTE = date(2026, 11, 25)
LETZTER_TAG = date(2026, 12, 31)
TEAM = Team("BDK 26 Berlin", "vogel", "2026")
AN = Settings(teams_aktiv=True, teams_oeffentlich_aktiv=True)
AUS = Settings(teams_aktiv=False, teams_oeffentlich_aktiv=False)
LOESCHSKRIPT = (
    postgres.REPO_WURZEL / "mvp" / "scripts" / "manual" / "person_loeschen.sql"
)
MIGRATION = postgres.MIGRATIONEN / "2026-11-25-teams.sql"

TABELLEN = [
    EinladungZeile.__table__,
    TeamMitgliedschaftZeile.__table__,
    TeamNummerZeile.__table__,
    TeamOeffentlichZeile.__table__,
    EinstellungZeile.__table__,
]


class KontenAttrappe:
    """Legt "Konten" an und ruft bei_angelegt wie KeycloakKonten."""

    def __init__(self, ergebnis=KontoErgebnis.ANGELEGT):
        self.ergebnis = ergebnis
        self.angelegt = []

    def konto_anlegen(self, email, vorname=None, nachname=None, bei_angelegt=None):
        if self.ergebnis is KontoErgebnis.ANGELEGT:
            kennung = f"konto-{email}"
            self.angelegt.append(kennung)
            if bei_angelegt is not None:
                bei_angelegt(kennung)
        return self.ergebnis


@pytest.fixture
def db(wegwerf_schema):
    Base.metadata.create_all(wegwerf_schema.engine, tables=TABELLEN)
    return wegwerf_schema


def _dienste(db, settings=AN, konten=None):
    teams = TeamService(TeamRepository(db), settings, saison=lambda: "2026")
    with patch("repositories.einladung_repository.get_app_database", return_value=db):
        einladungen = EinladungService(EinladungRepository(), konten, teams)
    return einladungen, teams


def _teamlink(service, erlaubt=50, team=TEAM) -> str:
    return service.anlegen(
        "Teamlink", erlaubt, LETZTER_TAG, heute=HEUTE, team=team
    ).code


def _einloesungen(service) -> int:
    [einladung] = service.alle()
    return einladung.einloesungen


def test_gleichzeitige_beitritte_bekommen_jede_nummer_genau_einmal(db):
    einladungen, _ = _dienste(db)
    code = _teamlink(einladungen)

    with ThreadPoolExecutor(max_workers=10) as pool:
        ergebnisse = list(
            pool.map(
                lambda i: einladungen.beitreten(code, f"konto-{i}", heute=HEUTE),
                range(20),
            )
        )

    nummern = sorted(m.nummer for _, m, neu in ergebnisse)
    assert nummern == list(range(1, 21))
    assert all(neu for _, _, neu in ergebnisse)
    assert _einloesungen(einladungen) == 20


def test_derselbe_beitritt_gleichzeitig_zaehlt_einmal(db):
    einladungen, teams = _dienste(db)
    code = _teamlink(einladungen)

    with ThreadPoolExecutor(max_workers=8) as pool:
        ergebnisse = list(
            pool.map(
                lambda _: einladungen.beitreten(code, "konto-a", heute=HEUTE), range(8)
            )
        )

    assert [neu for _, _, neu in ergebnisse].count(True) == 1
    assert {m.nummer for _, m, _ in ergebnisse} == {1}
    assert _einloesungen(einladungen) == 1
    # Der Zaehler der Nummern ist mit zurueckgerollt: die naechste ist 2
    _, m, _ = einladungen.beitreten(code, "konto-b", heute=HEUTE)
    assert m.nummer == 2


def test_schon_dabei_zaehlt_nicht(db):
    einladungen, _ = _dienste(db)
    code = _teamlink(einladungen)

    _, erste, neu = einladungen.beitreten(code, "konto-a", heute=HEUTE)
    _, zweite, nochmal = einladungen.beitreten(code, "konto-a", heute=HEUTE)

    assert neu is True and nochmal is False
    assert erste.nummer == zweite.nummer == 1
    assert _einloesungen(einladungen) == 1


def test_deckel_der_einladung_gilt(db):
    einladungen, _ = _dienste(db)
    code = _teamlink(einladungen, erlaubt=2)

    einladungen.beitreten(code, "konto-a", heute=HEUTE)
    einladungen.beitreten(code, "konto-b", heute=HEUTE)
    with pytest.raises(EinladungUngueltig):
        einladungen.beitreten(code, "konto-c", heute=HEUTE)

    # Wer schon dabei ist, bekommt seine Nummer auch bei voller Einladung
    _, m, neu = einladungen.beitreten(code, "konto-b", heute=HEUTE)
    assert neu is False and m.nummer == 2
    assert _einloesungen(einladungen) == 2


def test_zwei_links_fuer_dasselbe_team_zaehlen_gemeinsam(db):
    einladungen, teams = _dienste(db)
    erster = _teamlink(einladungen)
    zweiter = _teamlink(einladungen)

    einladungen.beitreten(erster, "konto-a", heute=HEUTE)
    _, m, neu = einladungen.beitreten(zweiter, "konto-a", heute=HEUTE)
    _, b, _ = einladungen.beitreten(zweiter, "konto-b", heute=HEUTE)

    assert neu is False and m.nummer == 1
    assert b.nummer == 2
    assert teams.mitglieder([TEAM]) == {(TEAM.name, TEAM.saison): 2}


def test_verlassen_loescht_sofort_und_die_nummer_bleibt_vergeben(db):
    einladungen, teams = _dienste(db)
    code = _teamlink(einladungen)
    _, a, _ = einladungen.beitreten(code, "konto-a", heute=HEUTE)
    _, b, _ = einladungen.beitreten(code, "konto-b", heute=HEUTE)

    # Fremde Mitgliedschaft: nichts passiert
    assert teams.verlassen("konto-a", b.id) is False
    assert teams.verlassen("konto-b", b.id) is True

    assert [m.team_name for m in teams.meine("konto-b")] == []
    _, c, _ = einladungen.beitreten(code, "konto-c", heute=HEUTE)
    assert c.nummer == 3
    assert teams.info(TEAM).mitglieder == 2


def test_einloesen_mit_einwilligung_legt_mitgliedschaft_beim_konto_an(db):
    konten = KontenAttrappe()
    einladungen, teams = _dienste(db, konten=konten)
    code = _teamlink(einladungen)

    einladungen.einloesen(code, "neu@example.org", heute=HEUTE, team_einwilligung=True)

    [m] = teams.meine("konto-neu@example.org")
    assert (m.team_name, m.saison, m.nummer) == (TEAM.name, TEAM.saison, 1)
    with db.engine.connect() as c:
        kennung, zeitpunkt = c.execute(
            text(
                "SELECT einwilligung_kennung, einwilligung_zeitpunkt "
                "FROM team_mitgliedschaften"
            )
        ).one()
    assert kennung == EINWILLIGUNG_KENNUNG and zeitpunkt is not None
    # Einmal gezaehlt, nicht noch einmal beim Beitritt
    assert _einloesungen(einladungen) == 1


def test_einloesen_ohne_einwilligung_keine_mitgliedschaft(db):
    konten = KontenAttrappe()
    einladungen, teams = _dienste(db, konten=konten)
    code = _teamlink(einladungen)

    einladungen.einloesen(code, "neu@example.org", heute=HEUTE)

    assert konten.angelegt == ["konto-neu@example.org"]
    assert teams.meine("konto-neu@example.org") == []
    assert _einloesungen(einladungen) == 1


def test_einloesen_mit_vorhandenem_konto_keine_mitgliedschaft(db):
    einladungen, _ = _dienste(db, konten=KontenAttrappe(KontoErgebnis.VORHANDEN))
    code = _teamlink(einladungen)

    einladungen.einloesen(code, "alt@example.org", heute=HEUTE, team_einwilligung=True)

    with db.engine.connect() as c:
        assert (
            c.execute(text("SELECT count(*) FROM team_mitgliedschaften")).scalar() == 0
        )


def test_ohne_schalter_wie_bisher(db):
    konten = KontenAttrappe()
    einladungen, teams = _dienste(db, AUS, konten)
    code = einladungen.anlegen("Teamlink", 5, LETZTER_TAG, heute=HEUTE, team=TEAM).code

    [einladung] = einladungen.alle()
    assert einladung.team is None
    einladungen.einloesen(code, "neu@example.org", heute=HEUTE, team_einwilligung=True)
    with pytest.raises(TeamsAus):
        einladungen.beitreten(code, "konto-a", heute=HEUTE)
    with db.engine.connect() as c:
        assert (
            c.execute(text("SELECT count(*) FROM team_mitgliedschaften")).scalar() == 0
        )


def test_admin_sieht_nur_zahlen_und_mitgliedschaft_kennt_die_einladung_nicht(db):
    einladungen, teams = _dienste(db)
    code = _teamlink(einladungen)
    einladungen.beitreten(code, "konto-a", heute=HEUTE)
    einladungen.beitreten(code, "konto-b", heute=HEUTE)

    assert teams.mitglieder([TEAM, Team("Bayreuth", "waage", "2026")]) == {
        (TEAM.name, TEAM.saison): 2,
        ("Bayreuth", "2026"): 0,
    }
    spalten = {
        s["name"]
        for s in inspect(db.engine).get_columns(
            "team_mitgliedschaften", schema=db.schema
        )
    }
    assert spalten == {
        "id",
        "konto_kennung",
        "team_name",
        "team_motiv",
        "saison",
        "nummer",
        "eingetreten_am",
        "einwilligung_kennung",
        "einwilligung_zeitpunkt",
    }
    # Keine Spalte und kein Wert verweist auf die Einladung
    with db.engine.connect() as c:
        inhalt = c.execute(text("SELECT * FROM team_mitgliedschaften")).all()
    assert code not in repr(inhalt)


def test_oeffentliche_teams_nur_mit_einwilligung_und_aktueller_saison(db):
    einladungen, teams = _dienste(db)
    jetzt = _teamlink(einladungen)
    frueher = _teamlink(einladungen, team=Team("BDK 25 Hamburg", "waage", "2025"))
    for konto in ("konto-a", "konto-b"):
        einladungen.beitreten(jetzt, konto, heute=HEUTE)
        einladungen.beitreten(frueher, konto, heute=HEUTE)

    teams.oeffentlich_antworten("konto-a", True, OEFFENTLICH_KENNUNG)
    assert teams.pillen(["konto-a", "konto-b"]) == {"konto-a": [(TEAM.name, "vogel")]}

    teams.oeffentlich_antworten("konto-a", False, OEFFENTLICH_KENNUNG)
    assert teams.pillen(["konto-a", "konto-b"]) == {}
    assert teams.oeffentlich_stand("konto-a").zeigen is False


def test_loeschkommando_loescht_mitgliedschaften_und_einwilligung(db):
    einladungen, teams = _dienste(db)
    code = _teamlink(einladungen)
    einladungen.beitreten(code, "person-die-loescht", heute=HEUTE)
    einladungen.beitreten(code, "andere-person", heute=HEUTE)
    teams.oeffentlich_antworten("person-die-loescht", True, OEFFENTLICH_KENNUNG)
    EinstellungRepository(db).setzen("aktuelle_saison", "2026", "person-die-loescht")

    # Nur die Anweisungen fuer die Team-Tabellen und einstellungen: Die uebrigen
    # Tabellen des Kommandos prueft tests/integration/test_loeschkommando.py.
    skript = LOESCHSKRIPT.read_text(encoding="utf-8")
    eigene = [
        a.replace(":'uid'", ":uid")
        for a in postgres.anweisungen(skript)
        if any(t in a for t in ("team_", "einstellungen"))
    ]
    assert len(eigene) == 3
    with db.engine.begin() as c:
        for anweisung in eigene:
            c.execute(text(anweisung), {"uid": "person-die-loescht"})

    assert teams.meine("person-die-loescht") == []
    assert len(teams.meine("andere-person")) == 1
    assert teams.oeffentlich_stand("person-die-loescht") is None
    with db.engine.connect() as c:
        assert (
            c.execute(text("SELECT geaendert_von FROM einstellungen")).scalar() is None
        )


def test_migration_auf_bestehender_einladungstabelle(postgres_url):
    with postgres.schema(postgres_url, "itest_teams") as db:
        postgres.migration(db, postgres.MIGRATIONEN / "2026-10-30-429-einladungen.sql")
        postgres.migration(db, MIGRATION)
        postgres.migration(db, MIGRATION)

        einladungen, teams = _dienste(db)
        code = _teamlink(einladungen)
        _, m, _ = einladungen.beitreten(code, "konto-a", heute=HEUTE)

        assert m.nummer == 1
        assert einladungen.alle()[0].team == TEAM


def test_nie_benutztes_konto_nimmt_seine_teamdaten_mit(db):
    """
    Die Mitgliedschaft entsteht beim Anlegen des Kontos. Loescht die Frist das nie
    benutzte Konto im Realm (loeschfristen_service), gehen auch seine Teamdaten.
    """
    einladungen, teams = _dienste(db)
    code = _teamlink(einladungen)
    einladungen.beitreten(code, "nie-benutzt", heute=HEUTE)
    einladungen.beitreten(code, "andere-person", heute=HEUTE)
    teams.oeffentlich_antworten("nie-benutzt", True, OEFFENTLICH_KENNUNG)

    assert TeamRepository(db).konten_loeschen(["nie-benutzt"]) == 1

    assert teams.meine("nie-benutzt") == []
    assert teams.oeffentlich_stand("nie-benutzt") is None
    assert len(teams.meine("andere-person")) == 1
    assert TeamRepository(db).konten_loeschen([]) == 0
