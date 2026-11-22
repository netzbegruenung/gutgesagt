"""
Kurze Sucheingaben einem Thema zuordnen (#754, domain/themen_abgleich.py): normalisiert,
nur bei einem bis drei Woertern, hoechstens zwei Themen.
"""

import pytest

from domain.themen_abgleich import HOECHSTENS_THEMEN, passende_themen

pytestmark = pytest.mark.unit


def _schluessel(eingabe):
    return [t.schluessel for t in passende_themen(eingabe)]


@pytest.mark.parametrize(
    "eingabe",
    ["Heizung", "heizung", "HEIZUNG", " Heizung ", "Heizungen", "Heizung?"],
)
def test_stichwort_trifft_unabhaengig_von_schreibweise(eingabe):
    assert _schluessel(eingabe) == ["energie-heizen"]


@pytest.mark.parametrize(
    "eingabe, thema",
    [
        ("Wärmepumpe", "energie-heizen"),
        ("Waermepumpe", "energie-heizen"),
        ("Wärmepumpen", "energie-heizen"),
        ("Flüchtling", "migration"),
        ("Fluechtlinge", "migration"),
        ("E-Auto", "verkehr"),
        ("EAuto", "verkehr"),
        ("Rentner", "soziales"),
        ("ÖPNV", "verkehr"),
    ],
)
def test_umlaute_bindestriche_und_wortformen(eingabe, thema):
    assert _schluessel(eingabe) == [thema]


def test_themenname_und_seine_teile_treffen():
    assert _schluessel("Landwirtschaft und Ernährung") == ["landwirtschaft-ernaehrung"]
    assert _schluessel("Ernährung") == ["landwirtschaft-ernaehrung"]
    assert _schluessel("Gesundheit") == ["gesundheit"]


def test_stichwort_in_kurzer_eingabe():
    assert _schluessel("neue Heizung") == ["energie-heizen"]
    assert _schluessel("Wärmepumpe zu teuer") == ["energie-heizen"]
    # Mehrteilige Stichwoerter nur zusammenhaengend.
    assert _schluessel("Letzte Generation") == ["klima"]
    assert _schluessel("Generation letzte") == []


def test_wortanfang_nur_bei_langen_stichwoertern():
    assert _schluessel("Heizungskosten") == ["energie-heizen"]
    # "Auto" und "trans" sind zu kurz: sonst trafen "Autor" und "Transport".
    assert _schluessel("Autor") == []
    assert _schluessel("Transport") == []
    # Kein Wortanfang: "Schulden" ist nicht "Schule".
    assert _schluessel("Schulden") == ["haushalt-steuern"]


def test_mehr_als_drei_woerter_kein_thema():
    assert _schluessel("Die neue Heizung ist zu teuer") == []
    assert _schluessel("Heizung Heizung Heizung") == ["energie-heizen"]


def test_ohne_treffer_oder_leer():
    assert _schluessel("Grüne") == []
    assert _schluessel("") == []
    assert _schluessel("?!") == []


def test_mehrere_themen_hoechstens_zwei_genaue_zuerst():
    assert _schluessel("Klimaschutz Heizung") == ["klima", "energie-heizen"]
    assert _schluessel("Heizung Miete Schule") == ["energie-heizen", "wohnen"]
    assert HOECHSTENS_THEMEN == 2
    # Genau vor Wortanfang, unabhaengig von der Reihenfolge in der Liste.
    assert _schluessel("Heizungskosten Wohnung") == ["wohnen", "energie-heizen"]
