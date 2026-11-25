"""
Rangliste je Saison (#793) gegen ein echtes PostgreSQL: die Einwilligung mit Nachweis
und die Saisonpunkte aus Stimmen und entdoppelter Nutzung eines Zeitraums.
Wegwerf-Schema aus der Fixture ``datenbank`` von ``test_loeschkommando.py``.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text

from infrastructure.database.models import UsageEvent, UsageTracking
from repositories.punkte_repository import PunkteRepository
from repositories.rangliste_einwilligung_repository import (
    RanglisteEinwilligungRepository,
)
from repositories.usage_tracking_repository import UsageTrackingRepository
from tests.integration.test_loeschkommando import datenbank  # noqa: F401

pytestmark = pytest.mark.integration

WORTLAUT = "rangliste-2026-11-25"


class TestRanglisteEinwilligung:
    def test_nie_gefragt(self, datenbank):  # noqa: F811
        assert RanglisteEinwilligungRepository(datenbank).lesen("kim-1") is None

    def test_es_gilt_die_juengste_antwort_frueheres_bleibt(
        self, datenbank
    ):  # noqa: F811
        repo = RanglisteEinwilligungRepository(datenbank)
        repo.antworten("kim-1", True, False, WORTLAUT)
        repo.antworten("kim-1", True, True, WORTLAUT)
        repo.antworten("kim-1", False, False, WORTLAUT)

        antwort = repo.lesen("kim-1")
        assert antwort.teilnehmen is False
        assert antwort.mit_anzeigename is False
        assert antwort.wortlaut == WORTLAUT
        assert antwort.beantwortet_am is not None
        with datenbank.get_session() as s:
            anzahl = s.execute(
                text(
                    "SELECT count(*) FROM rangliste_einwilligung"
                    " WHERE user_id = 'kim-1'"
                )
            ).scalar()
        assert anzahl == 3

    def test_dieselbe_antwort_zweimal_ist_eine_zeile(self, datenbank):  # noqa: F811
        repo = RanglisteEinwilligungRepository(datenbank)
        repo.antworten("kim-1", True, False, WORTLAUT)
        repo.antworten("kim-1", True, False, WORTLAUT)

        with datenbank.get_session() as s:
            anzahl = s.execute(
                text("SELECT count(*) FROM rangliste_einwilligung")
            ).scalar()
        assert anzahl == 1

    def test_teilnehmende_nur_mit_juengstem_ja(self, datenbank):  # noqa: F811
        repo = RanglisteEinwilligungRepository(datenbank)
        repo.antworten("kim-1", True, True, WORTLAUT)
        repo.antworten("bo-2", True, False, WORTLAUT)
        repo.antworten("bo-2", False, False, WORTLAUT)
        repo.antworten("ali-3", False, False, WORTLAUT)
        repo.antworten("eda-4", True, False, WORTLAUT)

        teilnehmende = repo.teilnehmende()
        assert {k: t.mit_anzeigename for k, t in teilnehmende.items()} == {
            "kim-1": True,
            "eda-4": False,
        }

    def test_ranglistenname_bleibt_ueber_jedes_nein(self, datenbank):  # noqa: F811
        repo = RanglisteEinwilligungRepository(datenbank)
        repo.antworten("kim-1", False, False, WORTLAUT)
        assert repo.lesen("kim-1").ranglistenname is None

        repo.antworten("kim-1", True, False, WORTLAUT, "Kluge Eule 37")
        repo.antworten("kim-1", False, False, WORTLAUT)
        repo.antworten("kim-1", True, True, WORTLAUT)

        assert repo.lesen("kim-1").ranglistenname == "Kluge Eule 37"
        assert repo.teilnehmende()["kim-1"].ranglistenname == "Kluge Eule 37"
        assert repo.vergebene_namen() == {"Kluge Eule 37"}


class TestVoraussetzungenFuerViele:
    def test_art9_nur_juengste_geltende(self, datenbank):  # noqa: F811
        from domain.art9_einwilligung import AKTUELLER_WORTLAUT as ART9
        from repositories.art9_einwilligung_repository import (
            Art9EinwilligungRepository,
        )

        repo = Art9EinwilligungRepository(datenbank)
        repo.einwilligen("kim-1", ART9)
        repo.einwilligen("bo-2", ART9)
        repo.widerrufen("bo-2")

        assert repo.zaehlende(["kim-1", "bo-2", "ali-3"]) == {"kim-1"}
        assert repo.zaehlende([]) == set()

    def test_punkte_nur_juengste_geltende(self, datenbank):  # noqa: F811
        from domain.punkte_einwilligung import AKTUELLER_WORTLAUT as PUNKTE
        from repositories.punkte_einwilligung_repository import (
            PunkteEinwilligungRepository,
        )

        repo = PunkteEinwilligungRepository(datenbank)
        repo.antworten("kim-1", True, PUNKTE)
        repo.antworten("bo-2", True, PUNKTE)
        repo.antworten("bo-2", False, PUNKTE)

        assert repo.eingewilligte(["kim-1", "bo-2", "ali-3"]) == {"kim-1"}
        assert repo.eingewilligte([]) == set()


def _stimme(datenbank, von, beitrag, am: datetime) -> None:  # noqa: F811
    with datenbank.get_session() as s:
        s.execute(
            text(
                "INSERT INTO votes (user_id, content_id, vote_type, created)"
                " VALUES (:u, :c, 'like', :am)"
            ),
            {"u": von, "c": str(beitrag), "am": am},
        )


class TestSaisonpunkte:
    def test_zustimmungen_nur_aus_dem_zeitraum(self, datenbank):  # noqa: F811
        beitrag = uuid.uuid4()
        _stimme(datenbank, "bo-2", beitrag, datetime(2026, 11, 30, 23, 59))
        _stimme(datenbank, "ali-3", beitrag, datetime(2026, 12, 1, 0, 0))
        _stimme(datenbank, "eda-4", beitrag, datetime(2026, 12, 31, 23, 59))
        _stimme(datenbank, "fin-5", beitrag, datetime(2027, 1, 1, 0, 0))
        repo = PunkteRepository(datenbank)

        assert (
            repo.zustimmungen(
                [beitrag], {"kim-1"}, (date(2026, 12, 1), date(2026, 12, 31))
            )
            == 2
        )
        assert repo.zustimmungen([beitrag], {"kim-1"}) == 4

    def test_entdoppelte_nutzung_nur_aus_dem_zeitraum(self, datenbank):  # noqa: F811
        beitrag, fremd = uuid.uuid4(), uuid.uuid4()
        with datenbank.get_session() as s:
            s.add(
                UsageTracking(content_id=beitrag, usage_count=4, nutzung_entdoppelt=3)
            )
            s.add(UsageTracking(content_id=fremd, usage_count=1, nutzung_entdoppelt=1))
            s.flush()
            for am, entdoppelt, inhalt in [
                (datetime(2026, 11, 30, 23, 0, tzinfo=timezone.utc), True, beitrag),
                (datetime(2026, 12, 1, 8, 0, tzinfo=timezone.utc), True, beitrag),
                (datetime(2026, 12, 1, 9, 0, tzinfo=timezone.utc), False, beitrag),
                (datetime(2026, 12, 31, 22, 0, tzinfo=timezone.utc), True, beitrag),
                (datetime(2026, 12, 5, 8, 0, tzinfo=timezone.utc), True, fremd),
            ]:
                s.add(
                    UsageEvent(
                        content_id=inhalt,
                        event_type="copy",
                        timestamp=am,
                        entdoppelt=entdoppelt,
                    )
                )
        repo = UsageTrackingRepository(datenbank)

        assert (
            repo.nutzung_entdoppelt_im_zeitraum(
                [beitrag], date(2026, 12, 1), date(2026, 12, 31)
            )
            == 2
        )
        assert (
            repo.nutzung_entdoppelt_im_zeitraum(
                [], date(2026, 12, 1), date(2026, 12, 31)
            )
            == 0
        )
