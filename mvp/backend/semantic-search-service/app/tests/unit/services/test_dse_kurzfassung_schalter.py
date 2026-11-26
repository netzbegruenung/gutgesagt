"""
Schalter dse_kurzfassung (Kasten "Kurz gesagt" oben in der Datenschutzerklaerung, Jura b):
Gruppe Grundfunktionen, Obergrenze von Haus aus aus, ohne Admin-Wert aus, oeffentlich
ueber GET /api/v1/funktionen, Einschalt-Hinweis nennt den Wortlaut von Jura.
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
        admin_wert_setzen=lambda name, an, admin: werte.__setitem__(name, an),
    )


def test_eintrag():
    art = SCHALTER["dse_kurzfassung"]
    assert art.gruppe == GRUNDFUNKTIONEN
    assert art.umgebungsvariable == "SEMANTIC_SEARCH_DSE_KURZFASSUNG_AKTIV"
    assert art.feld == "dse_kurzfassung_aktiv"
    assert "dse_kurzfassung" in oeffentliche_schalter()


def test_obergrenze_von_haus_aus_aus():
    """Der Standard im Code, unabhaengig von der Umgebung der Entwicklerin."""
    assert Settings.model_fields["dse_kurzfassung_aktiv"].default is False
    aus = Settings(dse_kurzfassung_aktiv=False)
    assert _dienst({"dse_kurzfassung": True}).wirksam("dse_kurzfassung", aus) is False


def test_ohne_admin_wert_aus():
    an = Settings(dse_kurzfassung_aktiv=True)
    assert _dienst({}).wirksam("dse_kurzfassung", an) is False
    assert _dienst({"dse_kurzfassung": True}).wirksam("dse_kurzfassung", an) is True


def test_hinweis_nennt_wortlaut_von_jura_und_wartet_auf_recht():
    stand = {s.name: s for s in _dienst({}).stand(Settings())}["dse_kurzfassung"]
    assert "Wortlaut von Jura" in stand.dsfa_hinweis
    assert "Absatz im Volltext" in stand.dsfa_hinweis
    assert stand.wartet_auf_recht is True
