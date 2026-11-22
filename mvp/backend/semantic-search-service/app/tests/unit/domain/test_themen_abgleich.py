"""
Kurze Sucheingaben einem Thema zuordnen (#754, domain/themen_abgleich.py): normalisiert,
nur bei einem bis drei Woertern, hoechstens zwei Themen.
"""

import pytest

from domain.themen_abgleich import (
    _VERZEICHNIS,
    HOECHSTENS_THEMEN,
    _am_anfang,
    passende_themen,
)

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


def test_stichwort_mit_bindestrich_auch_getrennt():
    # Getrennt geschrieben zaehlt es als zwei Woerter und schlaegt "Verbote" allein.
    assert _schluessel("AfD Verbot") == ["extremismus", "demokratie-freiheit"]
    assert _schluessel("AfD-Verbot") == ["extremismus"]
    assert _schluessel("E Auto") == ["verkehr"]


@pytest.mark.parametrize(
    "eingabe, thema",
    [
        ("Rentenreform", "soziales"),
        ("Asylbewerber", "migration"),
        ("Solaranlage", "energie-heizen"),
        ("Strompreis", "energie-heizen"),
        ("Mieterhöhung", "wohnen"),
        ("Kriegsgefahr", "frieden-sicherheit"),
        ("Kitaplätze", "bildung"),
    ],
)
def test_zusammensetzungen_kurzer_stichwoerter(eingabe, thema):
    assert _schluessel(eingabe) == [thema]


@pytest.mark.parametrize("eingabe", ["autoritär", "Transparenz", "Landtag"])
def test_keine_falschen_wortanfaenge(eingabe):
    # Sie beginnen nur zufaellig wie "Auto", "trans" oder der Namensteil "Land".
    assert _schluessel(eingabe) == []


def test_woerter_zaehlen_wie_abgeglichen():
    assert _schluessel("Heizung,Miete,Schule,Rente") == []


def test_kein_begriff_beginnt_mit_dem_eines_anderen_themas():
    # Sonst traefe ein Stichwort des einen Themas am Wortanfang immer das andere mit.
    for thema, liste in _VERZEICHNIS:
        for begriff in liste:
            for anderes, andere in _VERZEICHNIS:
                if anderes is thema:
                    continue
                for fremd in andere:
                    assert not (fremd.flach and _am_anfang(begriff, fremd.flach)), (
                        f"{begriff.flach} ({thema.schluessel}) am Anfang von "
                        f"{fremd.flach} ({anderes.schluessel})"
                    )
