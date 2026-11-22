"""
Merkliste (#758) gegen ein echtes PostgreSQL: Reihenfolge nach zuletzt gemerkt,
erneutes Merken, Entfernen, Obergrenze, und das Loeschen beim Widerruf der
Art.-9-Einwilligung (in derselben Transaktion) und mit dem entfernten Beitrag.
Wegwerf-Schema aus der Fixture ``datenbank`` von ``test_loeschkommando.py``; das
Loeschkommando selbst prueft dort ``spuren``.
"""

import time
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text

import repositories.merkliste_repository as merkliste_modul
from domain.art9_einwilligung import AKTUELLER_WORTLAUT
from repositories.art9_einwilligung_repository import Art9EinwilligungRepository
from repositories.merkliste_repository import MerklisteRepository, MerklisteVoll
from services.art9_einwilligung_service import Art9EinwilligungService
from tests.integration.test_loeschkommando import datenbank  # noqa: F401

pytestmark = pytest.mark.integration

PERSON = "merkt-sich-was"
ANDERE = "andere-person"


@pytest.fixture
def merkliste(datenbank):  # noqa: F811
    return MerklisteRepository(datenbank)


def _ids(merkliste, person=PERSON):
    return [e.content_id for e in merkliste.liste(person)]


class TestMerkliste:
    def test_zuletzt_gemerkt_zuerst_und_nur_die_eigene(self, merkliste):
        a, b = uuid.uuid4(), uuid.uuid4()
        merkliste.merken(PERSON, a)
        time.sleep(0.01)
        merkliste.merken(PERSON, b)
        merkliste.merken(ANDERE, a)

        assert _ids(merkliste) == [b, a]
        assert _ids(merkliste, ANDERE) == [a]

    def test_erneut_merken_holt_nach_oben_ohne_doppelte_zeile(self, merkliste):
        a, b = uuid.uuid4(), uuid.uuid4()
        merkliste.merken(PERSON, a)
        time.sleep(0.01)
        merkliste.merken(PERSON, b)
        time.sleep(0.01)
        merkliste.merken(PERSON, a)

        assert _ids(merkliste) == [a, b]

    def test_entfernen(self, merkliste):
        a = uuid.uuid4()
        merkliste.merken(PERSON, a)

        assert merkliste.entfernen(PERSON, a) is True
        assert merkliste.entfernen(PERSON, a) is False
        assert _ids(merkliste) == []

    def test_obergrenze(self, merkliste, monkeypatch):
        monkeypatch.setattr(merkliste_modul, "MERKLISTE_MAX", 2)
        a, b = uuid.uuid4(), uuid.uuid4()
        merkliste.merken(PERSON, a)
        merkliste.merken(PERSON, b)

        with pytest.raises(MerklisteVoll):
            merkliste.merken(PERSON, uuid.uuid4())
        # Schon Gemerktes nach oben holen geht weiter
        merkliste.merken(PERSON, a)
        assert len(_ids(merkliste)) == 2

    def test_mit_dem_beitrag_weg(self, merkliste):
        a, b = uuid.uuid4(), uuid.uuid4()
        merkliste.merken(PERSON, a)
        merkliste.merken(ANDERE, a)
        merkliste.merken(PERSON, b)

        assert merkliste.loeschen_fuer_beitrag(a) == 2
        assert _ids(merkliste) == [b]
        assert _ids(merkliste, ANDERE) == []


class TestWiderruf:
    def test_widerruf_loescht_die_merkliste(self, datenbank, merkliste):  # noqa: F811
        merkliste.merken(PERSON, uuid.uuid4())
        merkliste.merken(ANDERE, uuid.uuid4())
        dienst = Art9EinwilligungService(
            Art9EinwilligungRepository(datenbank), merkliste=merkliste
        )
        dienst.einwilligen(PERSON, AKTUELLER_WORTLAUT)

        dienst.widerrufen(PERSON)

        assert _ids(merkliste) == []
        assert len(_ids(merkliste, ANDERE)) == 1
        assert not dienst.eingewilligt(PERSON)

    def test_scheitert_das_loeschen_gilt_die_einwilligung_weiter(
        self, datenbank, merkliste  # noqa: F811
    ):
        kaputt = MagicMock()
        kaputt.loeschen_fuer_person.side_effect = RuntimeError("Datenbank weg")
        dienst = Art9EinwilligungService(
            Art9EinwilligungRepository(datenbank), merkliste=kaputt
        )
        dienst.einwilligen(PERSON, AKTUELLER_WORTLAUT)

        with pytest.raises(RuntimeError):
            dienst.widerrufen(PERSON)

        assert dienst.eingewilligt(PERSON)
        with datenbank.engine.connect() as c:
            assert c.execute(text("SELECT count(*) FROM merkliste")).scalar() == 0
