"""
Einwilligungs-Moment (#788) gegen ein echtes PostgreSQL: liest Stimmen, Antworten auf
die Einwilligungsfragen und den Beginn des Kontos, ohne etwas zu speichern.
Wegwerf-Schema aus der Fixture ``datenbank`` von ``test_loeschkommando.py``.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from repositories.einwilligungs_moment_repository import EinwilligungsMomentRepository
from tests.integration.test_loeschkommando import datenbank  # noqa: F401

pytestmark = pytest.mark.integration

KIM = "kim-1"


def _ausfuehren(datenbank, sql: str, **werte) -> None:  # noqa: F811
    with datenbank.get_session() as session:
        session.execute(text(sql), werte)


def _tabellen_zeilen(datenbank) -> int:  # noqa: F811
    with datenbank.get_session() as session:
        return sum(
            session.execute(text(f"SELECT count(*) FROM {t}")).scalar_one()
            for t in (
                "votes",
                "art9_einwilligungen",
                "punkte_einwilligung",
                "abzeichen_sichtbarkeit",
                "team_mitgliedschaften",
                "nutzungsbedingungen_zustimmungen",
            )
        )


class TestEinwilligungsMoment:
    def test_neue_person_hat_nichts(self, datenbank):  # noqa: F811
        moment = EinwilligungsMomentRepository(datenbank).lesen(KIM)

        assert moment.abgestimmt is False
        assert moment.beantwortet == 0
        assert moment.konto_seit is None

    def test_zaehlt_beantwortete_fragen_und_stimme(self, datenbank):  # noqa: F811
        _ausfuehren(
            datenbank,
            "INSERT INTO votes (user_id, content_id, vote_type)"
            " VALUES (:u, gen_random_uuid(), 'like')",
            u=KIM,
        )
        # Zwei Antworten auf Art. 9 zaehlen als eine Frage.
        for am in ("2026-11-20 10:00+00", "2026-11-22 10:00+00"):
            _ausfuehren(
                datenbank,
                "INSERT INTO art9_einwilligungen (id, user_id, wortlaut, eingewilligt_am)"
                " VALUES (gen_random_uuid(), :u, 'w', CAST(:am AS timestamptz))",
                u=KIM,
                am=am,
            )
        _ausfuehren(
            datenbank,
            "INSERT INTO punkte_einwilligung (id, user_id, eingewilligt, wortlaut,"
            " beantwortet_am) VALUES (gen_random_uuid(), :u, false, 'w', now())",
            u=KIM,
        )
        _ausfuehren(
            datenbank,
            "INSERT INTO nutzungsbedingungen_zustimmungen (id, user_id, stand,"
            " zugestimmt_am) VALUES (gen_random_uuid(), :u, 's',"
            " '2026-11-19 08:00+00')",
            u=KIM,
        )
        # Eine andere Person zaehlt nicht mit.
        _ausfuehren(
            datenbank,
            "INSERT INTO abzeichen_sichtbarkeit (id, user_id, zeigen, wortlaut,"
            " beantwortet_am) VALUES (gen_random_uuid(), 'bo-2', true, 'w', now())",
        )
        vorher = _tabellen_zeilen(datenbank)

        moment = EinwilligungsMomentRepository(datenbank).lesen(KIM)

        assert moment.abgestimmt is True
        assert moment.beantwortet == 2
        assert moment.konto_seit == datetime(2026, 11, 19, 8, 0, tzinfo=timezone.utc)
        assert _tabellen_zeilen(datenbank) == vorher

    def test_ohne_einwilligung_weiter_und_team(self, datenbank):  # noqa: F811
        _ausfuehren(
            datenbank,
            "INSERT INTO art9_ohne_einwilligung (user_id, wortlaut, entschieden_am)"
            " VALUES (:u, 'w', '2026-11-21 12:00+00')",
            u=KIM,
        )
        _ausfuehren(
            datenbank,
            "INSERT INTO team_mitgliedschaften (id, konto_kennung, team_name, saison,"
            " nummer, eingetreten_am, einwilligung_kennung, einwilligung_zeitpunkt)"
            " VALUES (gen_random_uuid(), :u, 'BDK', '2026', 1, '2026-11-21', 't',"
            " now())",
            u=KIM,
        )
        _ausfuehren(
            datenbank,
            "INSERT INTO abzeichen_sichtbarkeit (id, user_id, zeigen, wortlaut,"
            " beantwortet_am) VALUES (gen_random_uuid(), :u, false, 'w', now())",
            u=KIM,
        )

        moment = EinwilligungsMomentRepository(datenbank).lesen(KIM)

        assert moment.abgestimmt is False
        assert moment.beantwortet == 3
        assert moment.konto_seit == datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
