"""
Saisons (#782) gegen ein echtes PostgreSQL: Anlegen, Aendern, Loeschen; keine zwei
Saisons ueberschneiden sich, auch nicht bei gleichzeitigen Anfragen; Namen sind
eindeutig; Balken und Admin-Stand aus den echten Wochenzahlen von "Ja, gepostet".
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
from sqlalchemy import text

from core.config import Settings
from domain.saisons import SaisonGesperrt, SaisonUeberschneidung, SaisonUngueltig
from infrastructure.database.models import (
    Base,
    EinladungZeile,
    GepostetPruefwert,
    GepostetWoche,
    SaisonZeile,
    TeamMitgliedschaftZeile,
    TeamNummerZeile,
    TeamQuestZeile,
    TeamWocheZeile,
)
from repositories.gepostet_repository import GepostetRepository
from repositories.saison_repository import SaisonRepository
from services.saison_service import SaisonService
from tests.integration import postgres

pytestmark = pytest.mark.integration

# Montag
MO = date(2026, 11, 30)
TABELLEN = [
    SaisonZeile.__table__,
    GepostetPruefwert.__table__,
    GepostetWoche.__table__,
    # Umbenennen zieht die Teams mit (Befund 6)
    EinladungZeile.__table__,
    TeamMitgliedschaftZeile.__table__,
    TeamNummerZeile.__table__,
    TeamWocheZeile.__table__,
    TeamQuestZeile.__table__,
]


@pytest.fixture
def db(wegwerf_schema):
    Base.metadata.create_all(wegwerf_schema.engine, tables=TABELLEN)
    return wegwerf_schema


def _service(db):
    gepostet = GepostetRepository(db)
    return SaisonService(
        SaisonRepository(db),
        gepostet.wochen,
        einstellungen=Settings(),
        wirksam=lambda _s: True,
    )


def test_anlegen_und_lesen(db):
    service = _service(db)
    service.anlegen("Winter 26", MO, MO + timedelta(weeks=8), 1000, heute=MO)

    [saison] = service.alle()
    assert (saison.name, saison.beginn, saison.ziel) == ("Winter 26", MO, 1000)
    assert service.saison_fuer_teams(MO) == "Winter 26"


def test_vorschlag_vor_dem_beginn_ohne_schalter(db):
    # Saisons im Jahreszeiten-Takt: Teamlinks vor dem Beginn bekommen schon ihren Namen,
    # die aktuelle Saison der Teams wechselt erst mit dem Beginn, auch bei Schalter aus
    vorher = MO - timedelta(days=5)
    service = SaisonService(
        SaisonRepository(db),
        GepostetRepository(db).wochen,
        einstellungen=Settings(),
        wirksam=lambda _s: False,
    )
    service.anlegen("Winter 26/27", MO, MO + timedelta(days=90), 1000, heute=vorher)
    service.anlegen(
        "Frühjahr 27",
        MO + timedelta(days=91),
        MO + timedelta(days=182),
        1000,
        heute=vorher,
    )

    assert service.vorschlag(vorher) == "Winter 26/27"
    assert service.saison_fuer_teams(vorher) is None
    assert service.vorschlag(MO) == "Winter 26/27"
    assert service.saison_fuer_teams(MO) == "Winter 26/27"


def test_ueberschneidung_abgewiesen(db):
    service = _service(db)
    service.anlegen("Winter 26", MO, MO + timedelta(weeks=8), 1000, heute=MO)

    with pytest.raises(SaisonUeberschneidung):
        service.anlegen(
            "Frühjahr 27",
            MO + timedelta(weeks=8),
            MO + timedelta(weeks=20),
            5,
            heute=MO,
        )
    # Direkt danach geht
    service.anlegen(
        "Frühjahr 27",
        MO + timedelta(weeks=8, days=1),
        MO + timedelta(weeks=20),
        5,
        heute=MO,
    )
    assert len(service.alle()) == 2


def test_gleichzeitig_angelegt_entsteht_eine(db):
    service = _service(db)

    def anlegen(i):
        try:
            service.anlegen(f"Saison {i}", MO, MO + timedelta(weeks=4), 10, heute=MO)
            return True
        except SaisonUeberschneidung:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        ergebnisse = list(pool.map(anlegen, range(8)))

    assert ergebnisse.count(True) == 1
    assert len(service.alle()) == 1


def test_name_eindeutig(db):
    service = _service(db)
    service.anlegen("Winter 26", MO, MO + timedelta(weeks=1), 10, heute=MO)

    with pytest.raises(SaisonUngueltig):
        service.anlegen(
            "Winter 26", MO + timedelta(weeks=2), MO + timedelta(weeks=3), 10, heute=MO
        )


def test_aendern_und_loeschen_je_zustand(db):
    service = _service(db)
    laufend = service.anlegen("Winter 26", MO, MO + timedelta(weeks=8), 1000, heute=MO)
    geplant = service.anlegen(
        "Frühjahr 27", MO + timedelta(weeks=10), MO + timedelta(weeks=20), 5, heute=MO
    )
    heute = MO + timedelta(days=3)

    service.aendern(laufend.id, "Winter 26", MO, heute, 2000, heute=heute)
    with pytest.raises(SaisonGesperrt):
        service.aendern(laufend.id, "Anders", MO, heute, 2000, heute=heute)
    with pytest.raises(SaisonGesperrt):
        service.loeschen(laufend.id, heute=heute)
    service.loeschen(geplant.id, heute=heute)

    [saison] = service.alle()
    assert (saison.ende, saison.ziel) == (heute, 2000)


def test_umbenennen_zieht_teamlinks_und_teams_mit(db):
    """
    Befund 6: Eine geplante Saison umbenennen nimmt Teamlinks (per ID) und alle
    Kopien ihres Namens mit; andere Saisons bleiben unberuehrt.
    """
    service = _service(db)
    geplant = service.anlegen(
        "Winter 26", MO + timedelta(weeks=1), MO + timedelta(weeks=8), 5, heute=MO
    )
    with db.engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO einladungen (id, code, notiz, erlaubte_einloesungen, "
                "einloesungen, gueltig_bis, abgeschaltet, angelegt_am, team_name, "
                "team_saison, team_saison_id) VALUES (gen_random_uuid(), 'c1', '', 5, 0, "
                ":t, false, :t, 'BDK', 'Winter 26', :id)"
            ),
            {"t": MO, "id": geplant.id},
        )
        for saison in ("Winter 26", "Sommer 26"):
            c.execute(
                text(
                    "INSERT INTO team_mitgliedschaften (id, konto_kennung, team_name, "
                    "saison, nummer, eingetreten_am, einwilligung_kennung, "
                    "einwilligung_zeitpunkt) VALUES (gen_random_uuid(), 'k', 'BDK', "
                    ":s, 1, :t, 'team', now())"
                ),
                {"s": saison, "t": MO},
            )
            c.execute(
                text(
                    "INSERT INTO team_nummern (team_name, saison, letzte_nummer) "
                    "VALUES ('BDK', :s, 1)"
                ),
                {"s": saison},
            )

    service.aendern(
        geplant.id,
        "Winter 26/27",
        geplant.beginn,
        geplant.ende,
        5,
        heute=MO,
    )

    with db.engine.begin() as c:
        assert c.execute(text("SELECT team_saison FROM einladungen")).scalar() == (
            "Winter 26/27"
        )
        assert sorted(
            c.execute(text("SELECT saison FROM team_mitgliedschaften")).scalars()
        ) == ["Sommer 26", "Winter 26/27"]
        assert sorted(c.execute(text("SELECT saison FROM team_nummern")).scalars()) == [
            "Sommer 26",
            "Winter 26/27",
        ]


def test_balken_aus_den_wochenzahlen(db):
    with db.engine.begin() as c:
        for i, personen in enumerate([30, 26, 25, 40, 12]):
            c.execute(
                text("INSERT INTO gepostet_wochen (woche, personen) VALUES (:w, :p)"),
                {"w": MO - timedelta(weeks=5 - i), "p": personen},
            )
    service = _service(db)
    service.anlegen(
        "Winter 26",
        MO - timedelta(weeks=2),
        MO + timedelta(weeks=6),
        1000,
        heute=MO - timedelta(weeks=2),
    )
    # Laufende Woche: eine Meldung, zaehlt erst nach Wochenende
    GepostetRepository(db).melden("pruefwert-1", MO)

    balken = service.balken(MO + timedelta(days=2))
    assert balken is not None
    assert balken.erreicht == 40 + 12

    stand = service.admin_stand(MO + timedelta(days=2))
    assert stand.schwelle_erreicht
    assert stand.saisons[0].laufende_woche == 1


def test_migration_legt_dasselbe_an_wie_das_modell(db):
    """Laeuft auf der Tabelle aus create_all ohne Wirkung durch (zweimal)."""
    skript = postgres.MIGRATIONEN / "2026-11-26-saisons.sql"
    postgres.migration(db, skript)
    postgres.migration(db, skript)
