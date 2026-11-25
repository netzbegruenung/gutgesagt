"""Rangliste je Saison (#793): Wortlaut, Ranglistenname und Plaetze."""

import random

import pytest

from domain.rangliste import (
    AKTUELLER_WORTLAUT,
    EIGENSCHAFTEN,
    MIN_TEILNEHMENDE,
    OHNE_NAMEN,
    PLAETZE,
    TIERE,
    WORTLAUTE,
    neuer_ranglistenname,
    rangliste_bilden,
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


def test_ranglistenname_aus_den_listen():
    name = neuer_ranglistenname(set())

    eigenschaft, tier, zahl = name.split(" ")
    assert eigenschaft in EIGENSCHAFTEN
    assert tier in TIERE
    assert 10 <= int(zahl) <= 99


def test_ranglistenname_zufaellig_nicht_aus_der_kennung():
    """Wer eine Kennung kennt, kann den Namen nicht ausrechnen (Review zu #793)."""
    namen = {neuer_ranglistenname(set()) for _ in range(50)}

    assert len(namen) > 45


def test_ranglistenname_meidet_vergebene():
    zufall = random.Random(7)
    erster = neuer_ranglistenname(set(), random.Random(7))

    zweiter = neuer_ranglistenname({erster}, zufall)

    assert zweiter != erster


def test_ranglistenname_alle_vergeben_gibt_trotzdem_einen():
    class Immer:
        def choice(self, folge):
            return folge[0]

        def randint(self, a, b):
            return a

    vergeben = {f"{EIGENSCHAFTEN[0]} {TIERE[0]} 10"}

    assert neuer_ranglistenname(vergeben, Immer()) in vergeben


def test_gleiche_namen_in_der_liste_unterscheidbar():
    punkte = _punkte(10)
    namen = {k: "Flinke Amsel 42" for k in punkte}

    rangliste = rangliste_bilden(punkte, namen, "p00")

    gezeigt = [p.name for p in rangliste.oben]
    assert len(set(gezeigt)) == 10
    assert gezeigt[0] == "Flinke Amsel 42"
    assert gezeigt[1] == "Flinke Amsel 42 (2)"


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


def test_namen_aus_der_zuordnung_ohne_eintrag_ersatz():
    rangliste = rangliste_bilden(_punkte(10), {"p00": "Kim B."}, "p05")

    assert rangliste.oben[0].name == "Kim B."
    assert rangliste.oben[1].name == OHNE_NAMEN
