"""
Unit-Tests fuer Feedback an das Team (#343).

Das Repository ist gemockt. Geprueft werden der Tag beim Senden, Erledigt-Setzen
und Einzelloeschen (#425), die Frist von AUFBEWAHRUNG_TAGE, die eigene Frist der
Kategorie "gestoert" (Knopf "Was hat dich gestört?") und der Hintergrund-Task,
der nach einem Fehler weiterlaeuft.
"""

import asyncio
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from domain.feedback_gestoert import GESTOERT_GELOESCHT_AB, gestoert_offen
from services.feedback_service import (
    AUFBEWAHRUNG_TAGE,
    FeedbackEintrag,
    FeedbackService,
    aufbewahrungsgrenze,
    loeschen_im_takt,
)

pytestmark = pytest.mark.unit

HEUTE = date(2026, 10, 27)


@pytest.fixture
def repository():
    return Mock()


class TestSenden:
    def test_senden_speichert_text_kontakt_und_den_utc_tag(self, repository):
        with patch("services.feedback_service.heute_utc", return_value=HEUTE):
            FeedbackService(repository).senden("Hallo", "anna@example.org")

        repository.anlegen.assert_called_once_with(
            "Hallo", "anna@example.org", HEUTE, None
        )

    def test_senden_ohne_kontakt_speichert_keinen(self, repository):
        FeedbackService(repository).senden("Hallo", None, heute=HEUTE)

        repository.anlegen.assert_called_once_with("Hallo", None, HEUTE, None)

    def test_gestoert_speichert_die_kategorie_und_nie_einen_kontakt(self, repository):
        FeedbackService(repository).senden(
            "Die Suche war langsam",
            "anna@example.org",
            heute=HEUTE,
            kategorie="gestoert",
        )

        repository.anlegen.assert_called_once_with(
            "Die Suche war langsam", None, HEUTE, "gestoert"
        )


class TestNeueste:
    def test_neueste_liefert_eintraege_ohne_zeilenobjekt(self, repository):
        kennung = uuid.uuid4()
        repository.neueste.return_value = [
            SimpleNamespace(
                id=kennung,
                text="Gut",
                kontakt=None,
                eingegangen_am=HEUTE,
                erledigt=False,
                kategorie="gestoert",
            )
        ]

        eintraege = FeedbackService(repository).neueste(limit=5)

        repository.neueste.assert_called_once_with(5, None)
        assert eintraege == [
            FeedbackEintrag(kennung, "Gut", None, HEUTE, False, "gestoert")
        ]

    def test_neueste_reicht_den_filter_weiter(self, repository):
        repository.neueste.return_value = []

        FeedbackService(repository).neueste(limit=5, erledigt=True)

        repository.neueste.assert_called_once_with(5, True)


class TestErledigtUndLoeschen:
    def test_erledigt_setzen_liefert_eintrag_ohne_zeilenobjekt(self, repository):
        kennung = uuid.uuid4()
        repository.erledigt_setzen.return_value = SimpleNamespace(
            id=kennung,
            text="Gut",
            kontakt=None,
            eingegangen_am=HEUTE,
            erledigt=True,
            kategorie=None,
        )

        eintrag = FeedbackService(repository).erledigt_setzen(kennung, True)

        repository.erledigt_setzen.assert_called_once_with(kennung, True)
        assert eintrag == FeedbackEintrag(kennung, "Gut", None, HEUTE, True)

    def test_erledigt_setzen_fuer_unbekanntes_feedback(self, repository):
        repository.erledigt_setzen.return_value = None

        assert FeedbackService(repository).erledigt_setzen(uuid.uuid4(), True) is None

    @pytest.mark.parametrize("gefunden", [True, False])
    def test_loeschen_meldet_ob_es_das_feedback_gab(self, repository, gefunden):
        kennung = uuid.uuid4()
        repository.loeschen.return_value = gefunden

        assert FeedbackService(repository).loeschen(kennung) is gefunden
        repository.loeschen.assert_called_once_with(kennung)


class TestFrist:
    def test_aufbewahrungsgrenze_behaelt_genau_die_frist(self):
        assert AUFBEWAHRUNG_TAGE == 180
        assert aufbewahrungsgrenze(HEUTE) == date(2026, 4, 30)

    def test_alte_loeschen_loescht_vor_der_aufbewahrungsgrenze(self, repository):
        repository.loeschen_vor.return_value = 3

        assert FeedbackService(repository).alte_loeschen(heute=HEUTE) == 3
        repository.loeschen_vor.assert_called_once_with(date(2026, 4, 30))
        repository.loeschen_kategorie.assert_not_called()

    def test_gestoert_bleibt_bis_zum_letzten_tag_der_startphase(self, repository):
        repository.loeschen_vor.return_value = 0

        FeedbackService(repository).alte_loeschen(heute=date(2026, 12, 30))

        repository.loeschen_kategorie.assert_not_called()

    @pytest.mark.parametrize("heute", [date(2026, 12, 31), date(2027, 1, 5)])
    def test_gestoert_wird_ab_dem_31_12_ganz_geloescht(self, repository, heute):
        repository.loeschen_vor.return_value = 2
        repository.loeschen_kategorie.return_value = 5

        assert FeedbackService(repository).alte_loeschen(heute=heute) == 7
        repository.loeschen_kategorie.assert_called_once_with("gestoert")

    def test_startphase_endet_am_31_12_2026(self):
        assert GESTOERT_GELOESCHT_AB == date(2026, 12, 31)
        assert gestoert_offen(date(2026, 12, 30)) is True
        assert gestoert_offen(date(2026, 12, 31)) is False

    @pytest.mark.asyncio
    async def test_loeschen_im_takt_loescht_sofort_und_laeuft_nach_fehler_weiter(
        self, repository
    ):
        repository.loeschen_vor = Mock(side_effect=[RuntimeError("weg"), 0, 0])

        task = asyncio.create_task(
            loeschen_im_takt(FeedbackService(repository), takt_sekunden=0)
        )
        while repository.loeschen_vor.call_count < 2:
            await asyncio.sleep(0.01)
        task.cancel()

        assert repository.loeschen_vor.call_count >= 2
