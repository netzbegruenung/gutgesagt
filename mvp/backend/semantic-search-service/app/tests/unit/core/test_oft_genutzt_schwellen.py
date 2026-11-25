"""
Schwellen fuer "Diese Woche oft genutzt" kommen aus der Umgebung
(SEMANTIC_SEARCH_OFT_GENUTZT_*), damit der Betrieb sie nach der Startphase anheben kann.
"""

import pytest

from core.config import Settings
from services.oft_genutzt_service import ANZAHL

pytestmark = pytest.mark.unit


def _ohne_schwellen_aus_der_umgebung(monkeypatch):
    for feld in ("OFT_GENUTZT_MINDEST_NUTZUNGEN", "OFT_GENUTZT_MINDEST_BEITRAEGE"):
        monkeypatch.delenv(f"SEMANTIC_SEARCH_{feld}", raising=False)


def test_schwellen_standard_fuer_die_startphase(monkeypatch):
    """Startphase zur BDK: zwei Beitraege mit je zwei Nutzungen (vorher drei Beitraege)."""
    _ohne_schwellen_aus_der_umgebung(monkeypatch)

    einstellungen = Settings()

    assert einstellungen.oft_genutzt_mindest_nutzungen == 2
    assert einstellungen.oft_genutzt_mindest_beitraege == 2


def test_schwellen_aus_der_umgebung(monkeypatch):
    """Der Betrieb hebt die Schwellen an, ohne Code zu aendern."""
    monkeypatch.setenv("SEMANTIC_SEARCH_OFT_GENUTZT_MINDEST_NUTZUNGEN", "4")
    monkeypatch.setenv("SEMANTIC_SEARCH_OFT_GENUTZT_MINDEST_BEITRAEGE", "3")

    einstellungen = Settings()

    assert einstellungen.oft_genutzt_mindest_nutzungen == 4
    assert einstellungen.oft_genutzt_mindest_beitraege == 3


@pytest.mark.parametrize(
    "feld,wert",
    [
        # Eine einzelne Kopie ist Zufall, kein "oft".
        ("OFT_GENUTZT_MINDEST_NUTZUNGEN", "1"),
        ("OFT_GENUTZT_MINDEST_BEITRAEGE", "0"),
        # Mehr als der Bereich zeigt (ANZAHL), und er erschiene nie.
        ("OFT_GENUTZT_MINDEST_BEITRAEGE", "6"),
    ],
)
def test_schwellen_ausserhalb_der_grenzen_abgelehnt(monkeypatch, feld, wert):
    _ohne_schwellen_aus_der_umgebung(monkeypatch)
    monkeypatch.setenv(f"SEMANTIC_SEARCH_{feld}", wert)

    with pytest.raises(ValueError):
        Settings()


def test_hoechste_mindestzahl_ist_die_anzahl_des_bereichs():
    """Die Obergrenze in core/config.py folgt ANZAHL; aendert sich eins, das andere mit."""
    obergrenze = next(
        m.le
        for m in Settings.model_fields["oft_genutzt_mindest_beitraege"].metadata
        if getattr(m, "le", None) is not None
    )

    assert obergrenze == ANZAHL
