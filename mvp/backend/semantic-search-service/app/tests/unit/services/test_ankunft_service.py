"""
Ankuenfte je Kampagnenwort und Tag (services/ankunft_service.py). Die Schalter
``k_begruessung`` (Paket) und ``k_ankuenfte`` prueft tests/unit/services/
test_schalter_service.py.
"""

from datetime import date
from unittest.mock import MagicMock

import pytest

from core.config import Settings
from services.ankunft_service import (
    ANKUNFT_TAGE,
    AnkuenfteAmTag,
    AnkunftService,
    kampagnenwort_pruefen,
)

pytestmark = pytest.mark.unit

HEUTE = date(2026, 12, 4)


def test_zaehlen_mit_heutigem_tag():
    repository = MagicMock()

    AnkunftService(repository).zaehlen("bdk", heute=HEUTE)

    repository.zaehlen.assert_called_once_with("bdk", HEUTE)


def test_letzte_tage_ab_dem_ersten_tag_des_fensters():
    repository = MagicMock()
    repository.tage.return_value = [(HEUTE, "bdk", 5)]

    zeilen = AnkunftService(repository).letzte_tage(tage=30, heute=HEUTE)

    repository.tage.assert_called_once_with(date(2026, 11, 5))
    assert zeilen == [AnkuenfteAmTag(tag=HEUTE, k="bdk", anzahl=5)]


@pytest.mark.parametrize(
    "wort,erwartet",
    [("sticker", "sticker"), ("BDK", "bdk"), (" g1 ", "g1"), ("x", None), ("", None)],
)
def test_kampagnenwort_pruefen(wort, erwartet):
    assert kampagnenwort_pruefen(wort, frozenset({"sticker", "bdk", "g1"})) == erwartet


def test_positivliste_von_haus_aus():
    assert Settings().kampagnenwoerter() == frozenset(
        {"vorhut", "g1", "g2", "g3", "g4", "bdk", "sticker", "karte", "technik"}
    )


def test_positivliste_ohne_zu_lange_woerter():
    """Die Spalte k hat 20 Zeichen: Laengere Woerter kaemen nie an."""
    assert Settings(k_woerter="ok," + "x" * 21).kampagnenwoerter() == frozenset({"ok"})


def test_frist_zwoelf_monate():
    assert ANKUNFT_TAGE == 365
