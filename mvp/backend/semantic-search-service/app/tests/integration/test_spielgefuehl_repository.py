"""
Spielgefuehl (domain/spielgefuehl.py) gegen ein echtes PostgreSQL: juengste Zeile gilt,
Nachweis bleibt, Teilnehmende und Stufen in einer Abfrage; dazu das Zaehlen im
Einwilligungs-Moment nach dem neuen Modell. Wegwerf-Schema aus der Fixture
``datenbank`` von ``test_loeschkommando.py``.
"""

import pytest
from sqlalchemy import text

from domain.spielgefuehl import AKTUELLER_WORTLAUT, Stufe
from repositories.einwilligungs_moment_repository import EinwilligungsMomentRepository
from repositories.spielgefuehl_repository import SpielgefuehlRepository
from tests.integration.test_loeschkommando import datenbank  # noqa: F401

pytestmark = pytest.mark.integration


def _zeilen(datenbank, kennung) -> int:  # noqa: F811
    with datenbank.get_session() as session:
        return session.execute(
            text("SELECT count(*) FROM spielgefuehl WHERE user_id = :u"),
            {"u": kennung},
        ).scalar_one()


class TestSpielgefuehlRepository:
    def test_juengste_zeile_gilt_und_nachweis_bleibt(self, datenbank):  # noqa: F811
        repo = SpielgefuehlRepository(datenbank)
        assert repo.lesen("kim") is None

        repo.antworten(
            "kim", Stufe.RANGLISTE, True, AKTUELLER_WORTLAUT, "Kluge Eule 11"
        )
        # Dieselbe Antwort noch einmal: keine neue Zeile.
        repo.antworten("kim", Stufe.RANGLISTE, True, AKTUELLER_WORTLAUT)
        repo.antworten("kim", Stufe.FUER_MICH, False, AKTUELLER_WORTLAUT)

        antwort = repo.lesen("kim")
        assert antwort.stufe is Stufe.FUER_MICH
        # Der Name bleibt ueber das Herabstufen.
        assert antwort.ranglistenname == "Kluge Eule 11"
        assert _zeilen(datenbank, "kim") == 2

    def test_teilnehmende_stufen_und_namen(self, datenbank):  # noqa: F811
        repo = SpielgefuehlRepository(datenbank)
        repo.antworten("a", Stufe.RANGLISTE, True, AKTUELLER_WORTLAUT, "Name A")
        repo.antworten("b", Stufe.RANGLISTE, False, AKTUELLER_WORTLAUT, "Name B")
        repo.antworten("b", Stufe.AUS, False, AKTUELLER_WORTLAUT)
        repo.antworten("c", Stufe.FUER_MICH, False, AKTUELLER_WORTLAUT)
        # Zu einem nicht mehr geltenden Wortlaut: wirkt wie aus.
        repo.antworten("d", Stufe.RANGLISTE, False, "spielgefuehl-alt", "Name D")

        teilnehmende = repo.teilnehmende()
        assert set(teilnehmende) == {"a"}
        assert teilnehmende["a"].mit_anzeigename is True
        assert teilnehmende["a"].ranglistenname == "Name A"
        assert repo.wirksame_stufen(["a", "b", "c", "d", "e"]) == {
            "a": Stufe.RANGLISTE,
            "b": Stufe.AUS,
            "c": Stufe.FUER_MICH,
            "d": Stufe.AUS,
        }
        assert repo.vergebene_namen() == {"Name A", "Name B", "Name D"}


class TestEinwilligungsMomentImNeuenModell:
    def test_alte_antworten_zaehlen_nicht_das_spielgefuehl_schon(
        self, datenbank  # noqa: F811
    ):
        with datenbank.get_session() as session:
            session.execute(
                text(
                    "INSERT INTO punkte_einwilligung (id, user_id, eingewilligt,"
                    " wortlaut, beantwortet_am) VALUES (gen_random_uuid(), 'kim',"
                    " true, 'w', now())"
                )
            )
        moment = EinwilligungsMomentRepository(datenbank)
        assert moment.lesen("kim").beantwortet == 1
        assert moment.lesen("kim", buehne=True).beantwortet == 0

        SpielgefuehlRepository(datenbank).antworten(
            "kim", Stufe.AUS, False, AKTUELLER_WORTLAUT
        )
        assert moment.lesen("kim", buehne=True).beantwortet == 1
