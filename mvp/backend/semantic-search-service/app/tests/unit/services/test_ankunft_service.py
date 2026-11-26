"""
Ankuenfte je Kampagnenwort und Tag (services/ankunft_service.py) und ihre beiden
Schalter ``k_begruessung`` und ``k_ankuenfte``: Obergrenze von Haus aus aus, oeffentlich,
Grundfunktionen, Einschalt-Hinweis mit der Jura-Bedingung.
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
from services.schalter_service import (
    GRUNDFUNKTIONEN,
    SCHALTER,
    SchalterService,
    oeffentliche_schalter,
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
        {"vorhut", "g1", "g2", "g3", "g4", "bdk", "sticker"}
    )


def test_positivliste_ohne_zu_lange_woerter():
    """Die Spalte k hat 20 Zeichen: Laengere Woerter kaemen nie an."""
    assert Settings(k_woerter="ok," + "x" * 21).kampagnenwoerter() == frozenset({"ok"})


def test_frist_zwoelf_monate():
    assert ANKUNFT_TAGE == 365


class TestSchalter:
    @pytest.mark.parametrize("name", ["k_begruessung", "k_ankuenfte"])
    def test_registriert_oeffentlich_grundfunktionen(self, name):
        art = SCHALTER[name]
        assert art.gruppe == GRUNDFUNKTIONEN
        assert art.umgebungsvariable == f"SEMANTIC_SEARCH_{name.upper()}_AKTIV"
        assert Settings.model_fields[art.feld].default is False
        assert name in oeffentliche_schalter()
        assert art.einschalt_hinweis
        assert not art.rechtlich_freigegeben

    def test_hinweis_ankuenfte_wortlaut_jura(self):
        assert (
            SCHALTER["k_ankuenfte"].einschalt_hinweis
            == "Jura: nur Ankünfte je k und Tag, nie an Konto/Beitrag"
        )

    @pytest.mark.parametrize("name", ["k_begruessung", "k_ankuenfte"])
    def test_wirksam_nur_mit_obergrenze_und_admin_wert(self, name):
        werte = {}
        dienst = SchalterService(lambda: dict(werte), lambda n, a, w: None)
        an = Settings(**{SCHALTER[name].feld: True})

        assert dienst.wirksam(name, an) is False
        werte[name] = True
        dienst.admin_werte(frisch=True)
        assert dienst.wirksam(name, an) is True
        assert dienst.wirksam(name, Settings()) is False

    def test_stand_wartet_auf_recht(self):
        dienst = SchalterService(lambda: {}, lambda n, a, w: None)
        stand = {s.name: s for s in dienst.stand(Settings())}

        for name in ("k_begruessung", "k_ankuenfte"):
            assert stand[name].wartet_auf_recht is True
            assert stand[name].gruppe == GRUNDFUNKTIONEN
