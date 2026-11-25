"""Rangliste je Saison (#793): Wortlaut, Ranglistenname und Plaetze."""

import pytest

from domain.rangliste import (
    AKTUELLER_WORTLAUT,
    EIGENSCHAFTEN,
    MIN_TEILNEHMENDE,
    PLAETZE,
    TIERE,
    WORTLAUTE,
    rangliste_bilden,
    ranglistenname,
)

pytestmark = pytest.mark.unit

# Wortgleich aus #793; aendert sich der Text, braucht er eine neue Kennung.
WORTLAUT_AUS_DEM_ISSUE = (
    "Ich willige ausdrücklich ein, dass ich in der Rangliste der laufenden Saison "
    "erscheine, mit meinem Ranglistennamen, meinem Platz und meinen Punkten (Art. 9 "
    "Abs. 2 lit. a DSGVO). Der Ranglistenname wird zufällig vergeben, außer ich wähle "
    "selbst meinen Anzeigenamen. Sehen können die Rangliste nur Angemeldete, die selbst "
    "mitmachen, und erst ab zehn Teilnehmenden. Daraus lässt sich schließen, dass und "
    "wie stark ich mich bei Gut gesagt engagiere. Angemeldet sind nicht nur Mitglieder, "
    "und Screenshots kann Gut gesagt nicht verhindern. Ich kann die Einwilligung "
    "jederzeit unter „Meine Beiträge“ widerrufen; dann verschwinde ich sofort aus der "
    "Rangliste."
)


def test_wortlaut_wortgleich_mit_kennung():
    assert AKTUELLER_WORTLAUT == "rangliste-2026-11-25"
    assert WORTLAUTE[AKTUELLER_WORTLAUT] == WORTLAUT_AUS_DEM_ISSUE


def test_ranglistenname_fest_je_kennung_aus_den_listen():
    name = ranglistenname("kim-1")

    assert name == ranglistenname("kim-1")
    eigenschaft, tier, zahl = name.split(" ")
    assert eigenschaft in EIGENSCHAFTEN
    assert tier in TIERE
    assert 10 <= int(zahl) <= 99
    assert "kim" not in name


def test_ranglistennamen_verschieden_fuer_verschiedene_kennungen():
    namen = {ranglistenname(f"person-{i}") for i in range(50)}

    assert len(namen) > 45


def _punkte(anzahl: int) -> dict:
    return {f"p{i:02d}": 100 - i for i in range(anzahl)}


def test_unter_zehn_teilnehmenden_keine_rangliste():
    assert rangliste_bilden(_punkte(MIN_TEILNEHMENDE - 1), {}, "p00") is None


def test_ab_zehn_teilnehmenden_die_ersten_zehn():
    rangliste = rangliste_bilden(_punkte(MIN_TEILNEHMENDE), {}, "p03")

    assert rangliste is not None
    assert [p.platz for p in rangliste.oben] == list(range(1, 11))
    assert rangliste.oben[3].ich is True
    assert rangliste.eigener is None
    assert rangliste.teilnehmende == 10


def test_eigener_platz_unter_den_ersten_zehn_kommt_dazu():
    rangliste = rangliste_bilden(_punkte(14), {}, "p12")

    assert len(rangliste.oben) == PLAETZE
    assert not any(p.ich for p in rangliste.oben)
    assert rangliste.eigener.platz == 13
    assert rangliste.eigener.ich is True
    assert rangliste.eigener.punkte == 88


def test_gleiche_punkte_teilen_den_platz():
    punkte = _punkte(10)
    punkte["p01"] = punkte["p02"] = 50

    rangliste = rangliste_bilden(punkte, {}, "p00")
    plaetze = {p.punkte: p.platz for p in rangliste.oben}

    assert plaetze[50] == 9
    assert [p.platz for p in rangliste.oben].count(9) == 2
    assert rangliste.oben[-1].platz == 9


def test_namen_nur_wenn_gegeben_sonst_ranglistenname():
    rangliste = rangliste_bilden(_punkte(10), {"p00": "Kim B."}, "p05")

    assert rangliste.oben[0].name == "Kim B."
    assert rangliste.oben[1].name == ranglistenname("p01")
