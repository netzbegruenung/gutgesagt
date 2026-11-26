"""
Saal-Sprueche gegen ein echtes PostgreSQL: festlegen, ersetzen, ab einem Tag lesen und
entfernen; je Tag hoechstens einer.
"""

from datetime import date

import pytest

from infrastructure.database.models import Base, SaalSpruchZeile
from repositories.saal_spruch_repository import SaalSpruchRepository

pytestmark = pytest.mark.integration

FREITAG = date(2026, 12, 4)
SAMSTAG = date(2026, 12, 5)


@pytest.fixture
def repository(wegwerf_schema):
    Base.metadata.create_all(wegwerf_schema.engine, tables=[SaalSpruchZeile.__table__])
    return SaalSpruchRepository(wegwerf_schema)


def test_festlegen_ersetzen_lesen_entfernen(repository):
    assert repository.fuer_tag(FREITAG) is None

    repository.setzen(FREITAG, "Das bringt doch nichts")
    repository.setzen(SAMSTAG, "Klimaschutz kostet nur")
    repository.setzen(FREITAG, "Ersetzt")

    assert repository.fuer_tag(FREITAG) == "Ersetzt"
    assert repository.ab(FREITAG) == {
        FREITAG: "Ersetzt",
        SAMSTAG: "Klimaschutz kostet nur",
    }
    assert repository.ab(SAMSTAG) == {SAMSTAG: "Klimaschutz kostet nur"}

    repository.loeschen(FREITAG)
    repository.loeschen(FREITAG)  # ohne Spruch passiert nichts

    assert repository.fuer_tag(FREITAG) is None
    assert repository.ab(FREITAG) == {SAMSTAG: "Klimaschutz kostet nur"}
