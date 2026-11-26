"""
Schalter fuer die kurze Hinweiszeile unter dem Suchknopf (Designwichtel Nr. 5): eigene
Obergrenze, von Haus aus aus, oeffentlich (nur im Browser), mit Rechtsbedingung.
"""

import pytest

from core.config import Settings
from services.schalter_service import (
    GRUNDFUNKTIONEN,
    SCHALTER,
    SchalterService,
    oeffentliche_schalter,
)

pytestmark = pytest.mark.unit


def _dienst(werte):
    return SchalterService(
        admin_werte_lesen=lambda: dict(werte),
        admin_wert_setzen=lambda *a: None,
    )


def test_obergrenze_von_haus_aus_aus():
    art = SCHALTER["hinweiszeile_kurz"]
    assert art.umgebungsvariable == "SEMANTIC_SEARCH_HINWEISZEILE_KURZ_AKTIV"
    assert art.gruppe == GRUNDFUNKTIONEN
    assert getattr(Settings(hinweiszeile_kurz_aktiv=False), art.feld) is False
    assert Settings.model_fields[art.feld].default is False
    # Admin an, Obergrenze aus: wirkt nicht
    assert not _dienst({"hinweiszeile_kurz": True}).wirksam(
        "hinweiszeile_kurz", Settings(hinweiszeile_kurz_aktiv=False)
    )


def test_ohne_admin_wert_aus():
    an = Settings(hinweiszeile_kurz_aktiv=True)
    assert not _dienst({}).wirksam("hinweiszeile_kurz", an)
    assert _dienst({"hinweiszeile_kurz": True}).wirksam("hinweiszeile_kurz", an)


def test_oeffentlich_und_wartet_auf_recht():
    assert "hinweiszeile_kurz" in oeffentliche_schalter()
    stand = {
        s.name: s for s in _dienst({}).stand(Settings(hinweiszeile_kurz_aktiv=True))
    }["hinweiszeile_kurz"]
    assert stand.wartet_auf_recht
    assert "Jura" in stand.dsfa_hinweis
    assert not stand.wirksam
