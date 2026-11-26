"""Spielgefuehl in drei Stufen: Regeln und Wortlaut (domain/spielgefuehl.py)."""

import pytest

from domain.spielgefuehl import (
    AKTUELLER_WORTLAUT,
    GELTENDE_WORTLAUTE,
    NAMENS_VORBELEGUNG,
    REIHENFOLGE,
    VERANTWORTLICHER,
    WORTLAUTE,
    Stufe,
    in_rangliste,
    punkte_wirksam,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "stufe, punkte, rangliste",
    [
        (None, False, False),
        (Stufe.AUS, False, False),
        (Stufe.FUER_MICH, True, False),
        (Stufe.RANGLISTE, True, True),
    ],
)
def test_ableitung_je_stufe(stufe, punkte, rangliste):
    assert punkte_wirksam(stufe) is punkte
    assert in_rangliste(stufe) is rangliste


def test_gemeinschaft_zuerst_alle_stufen_genau_einmal():
    assert REIHENFOLGE[0] is Stufe.RANGLISTE
    assert REIHENFOLGE[-1] is Stufe.AUS
    assert sorted(REIHENFOLGE) == sorted(Stufe)


def test_keine_vorbelegung_des_namens():
    # Jura 26.11.: Vorbelegung "Anzeigename" unzulaessig.
    assert NAMENS_VORBELEGUNG is None


def test_aktueller_wortlaut_gilt_und_ist_vollstaendig():
    assert AKTUELLER_WORTLAUT in GELTENDE_WORTLAUTE
    wortlaut = WORTLAUTE[AKTUELLER_WORTLAUT]
    assert set(wortlaut.stufen) == set(Stufe)
    assert all(t.titel and t.text for t in wortlaut.stufen.values())
    # Name des Verantwortlichen genau wie in der Datenschutzerklaerung
    assert VERANTWORTLICHER in wortlaut.fuss
    # Ausdrueckliche Einwilligung nach Art. 9 in beiden Stufen ueber "aus"
    for stufe in (Stufe.FUER_MICH, Stufe.RANGLISTE):
        assert "Art. 9 Abs. 2 lit. a DSGVO" in wortlaut.stufen[stufe].text
