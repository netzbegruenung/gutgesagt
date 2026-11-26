"""
Regeln der Saisons (#782, domain/saisons.py): Eingaben, Zustaende, was sich je Zustand
aendern darf, welche Wochen zur Saison gehoeren, die Saisonzahl aus abgeschlossenen
Wochen und die Schwelle fuer den oeffentlichen Balken.
"""

import uuid
from datetime import date, timedelta

import pytest

from domain.saisons import (
    Saison,
    SaisonEingabe,
    SaisonGesperrt,
    SaisonUngueltig,
    SaisonZustand,
    aenderung_pruefen,
    anlegen_pruefen,
    eingabe_pruefen,
    laufende_saison,
    loeschen_pruefen,
    naechste_saison,
    saison_fuer_teams,
    saison_fuer_vorschlag,
    saisonzahl,
    schwelle_erreicht,
    ueberschneidung,
)

pytestmark = pytest.mark.unit

# Montag, 30.11.2026
MO = date(2026, 11, 30)


def _saison(beginn=MO, ende=MO + timedelta(days=55), name="Winter 26", ziel=1000):
    return Saison(uuid.uuid4(), name, beginn, ende, ziel)


def _eingabe(beginn=MO, ende=MO + timedelta(days=55), name="Winter 26", ziel=1000):
    return SaisonEingabe(name, beginn, ende, ziel)


class TestEingabe:
    def test_bereinigt_leerraum(self):
        e = eingabe_pruefen("  Frühjahr   27 ", MO, MO, 5)
        assert e.name == "Frühjahr 27"

    @pytest.mark.parametrize("name", ["", "   ", "x" * 21, "Früh\njahr", "a\x07"])
    def test_ungueltiger_name(self, name):
        with pytest.raises(SaisonUngueltig):
            eingabe_pruefen(name, MO, MO, 5)

    @pytest.mark.parametrize("name", ["<b>W</b>", "A & B", 'Der "Winter"', "W\\27"])
    def test_zeichen_wie_am_teamlink_verboten(self, name):
        # Sonst liesse sich die Saison anlegen, aber kein Team in ihr (UX-Review 26.11.)
        with pytest.raises(SaisonUngueltig):
            eingabe_pruefen(name, MO, MO, 5)

    def test_schraegstrich_geht(self):
        assert eingabe_pruefen("Winter 26/27", MO, MO, 5).name == "Winter 26/27"

    def test_ende_vor_beginn(self):
        with pytest.raises(SaisonUngueltig):
            eingabe_pruefen("Winter", MO, MO - timedelta(days=1), 5)

    @pytest.mark.parametrize("ziel", [0, -1, 1_000_001])
    def test_ungueltiges_ziel(self, ziel):
        with pytest.raises(SaisonUngueltig):
            eingabe_pruefen("Winter", MO, MO, ziel)

    def test_ein_tag_ist_erlaubt(self):
        assert eingabe_pruefen("Tag", MO, MO, 1).ende == MO


class TestZustand:
    def test_zustaende(self):
        s = _saison(MO, MO + timedelta(days=6))
        assert s.zustand(MO - timedelta(days=1)) is SaisonZustand.GEPLANT
        assert s.zustand(MO) is SaisonZustand.LAUFEND
        assert s.zustand(MO + timedelta(days=6)) is SaisonZustand.LAUFEND
        assert s.zustand(MO + timedelta(days=7)) is SaisonZustand.VORBEI

    def test_laufende_saison(self):
        alt = _saison(MO - timedelta(days=30), MO - timedelta(days=1), name="Alt")
        jetzt = _saison(MO, MO + timedelta(days=10), name="Jetzt")
        assert laufende_saison([alt, jetzt], MO) == jetzt
        assert laufende_saison([alt], MO) is None


class TestUeberschneidung:
    def test_angrenzend_ist_keine(self):
        alt = _saison(MO - timedelta(days=10), MO - timedelta(days=1))
        assert ueberschneidung(_eingabe(MO), [alt]) is None

    def test_gleicher_tag_ist_eine(self):
        alt = _saison(MO - timedelta(days=10), MO)
        assert ueberschneidung(_eingabe(MO), [alt]) == alt

    def test_umschliessend(self):
        alt = _saison(MO + timedelta(days=3), MO + timedelta(days=4))
        assert ueberschneidung(_eingabe(MO), [alt]) == alt

    def test_sich_selbst_ausgenommen(self):
        alt = _saison()
        assert ueberschneidung(_eingabe(), [alt], ausser=alt.id) is None


class TestAendern:
    def test_geplant_alles(self):
        alt = _saison(MO + timedelta(days=7))
        aenderung_pruefen(alt, _eingabe(MO, name="Neu", ziel=5), heute=MO)

    def test_geplant_beginn_nicht_in_der_vergangenheit(self):
        alt = _saison(MO + timedelta(days=7))
        with pytest.raises(SaisonGesperrt):
            aenderung_pruefen(alt, _eingabe(MO - timedelta(days=1)), heute=MO)

    def test_laufend_ziel_und_ende(self):
        alt = _saison(MO - timedelta(days=7))
        aenderung_pruefen(
            alt, _eingabe(alt.beginn, MO, name=alt.name, ziel=2000), heute=MO
        )

    @pytest.mark.parametrize(
        "aenderung",
        [{"name": "Anders"}, {"beginn": MO - timedelta(days=6)}],
    )
    def test_laufend_name_und_beginn_stehen(self, aenderung):
        alt = _saison(MO - timedelta(days=7))
        werte = dict(beginn=alt.beginn, ende=alt.ende, name=alt.name, ziel=alt.ziel)
        werte.update(aenderung)
        with pytest.raises(SaisonGesperrt):
            aenderung_pruefen(alt, _eingabe(**werte), heute=MO)

    def test_laufend_ende_nicht_vor_heute(self):
        alt = _saison(MO - timedelta(days=7))
        with pytest.raises(SaisonGesperrt):
            aenderung_pruefen(
                alt,
                _eingabe(alt.beginn, MO - timedelta(days=1), name=alt.name),
                heute=MO,
            )

    def test_vorbei_nichts(self):
        alt = _saison(MO - timedelta(days=30), MO - timedelta(days=1))
        with pytest.raises(SaisonGesperrt):
            aenderung_pruefen(
                alt, _eingabe(alt.beginn, alt.ende, name=alt.name, ziel=1), heute=MO
            )

    def test_anlegen_nicht_rueckwirkend(self):
        anlegen_pruefen(_eingabe(MO), heute=MO)
        with pytest.raises(SaisonGesperrt):
            anlegen_pruefen(_eingabe(MO - timedelta(days=1)), heute=MO)

    def test_loeschen_nur_geplant(self):
        loeschen_pruefen(_saison(MO + timedelta(days=1)), heute=MO)
        with pytest.raises(SaisonGesperrt):
            loeschen_pruefen(_saison(MO), heute=MO)


class TestSaisonzahl:
    def test_wochen_auch_angebrochen(self):
        # Mittwoch bis Dienstag: zwei Kalenderwochen
        s = _saison(MO + timedelta(days=2), MO + timedelta(days=8))
        assert s.wochen() == [MO, MO + timedelta(weeks=1)]

    def test_nur_abgeschlossene_wochen_der_saison(self):
        s = _saison(MO, MO + timedelta(weeks=4) - timedelta(days=1))
        zahlen = {
            MO - timedelta(weeks=1): 99,  # vor der Saison
            MO: 30,
            MO + timedelta(weeks=1): 40,
            MO + timedelta(weeks=2): 7,  # laufende Woche
        }
        assert saisonzahl(s, zahlen, laufende=MO + timedelta(weeks=2)) == 70

    def test_ohne_zahlen_null(self):
        assert saisonzahl(_saison(), {}, laufende=MO) == 0

    def test_angrenzende_saisons_teilen_keine_randwoche(self):
        # Winter endet Mittwoch, Fruehjahr beginnt Donnerstag derselben Woche
        winter = _saison(MO - timedelta(weeks=2), MO + timedelta(days=2))
        fruehjahr = _saison(
            MO + timedelta(days=3), MO + timedelta(weeks=4), name="Frühjahr 27"
        )
        alle = [winter, fruehjahr]
        zahlen = {
            MO - timedelta(weeks=2): 10,
            MO - timedelta(weeks=1): 20,
            MO: 40,  # Randwoche: Montag liegt im Winter
            MO + timedelta(weeks=1): 5,
        }
        laufende = MO + timedelta(weeks=2)
        assert saisonzahl(winter, zahlen, laufende, alle) == 70
        assert saisonzahl(fruehjahr, zahlen, laufende, alle) == 5

    def test_angebrochene_erste_woche_ohne_vorgaengerin_zaehlt(self):
        s = _saison(MO + timedelta(days=3), MO + timedelta(weeks=2))
        andere = _saison(MO - timedelta(weeks=5), MO - timedelta(weeks=3), name="Alt")
        zahlen = {MO: 40, MO + timedelta(weeks=1): 5}
        assert saisonzahl(s, zahlen, MO + timedelta(weeks=2), [s, andere]) == 45


class TestSaisonFuerTeams:
    WINTER = _saison(MO, MO + timedelta(weeks=12) - timedelta(days=1))
    FRUEHJAHR = _saison(
        MO + timedelta(weeks=15), MO + timedelta(weeks=26), name="Frühjahr 27"
    )

    def test_laufende(self):
        alle = [self.FRUEHJAHR, self.WINTER]
        assert saison_fuer_teams(alle, MO + timedelta(days=3)) is self.WINTER

    def test_luecke_behaelt_die_zuletzt_beendete(self):
        alle = [self.FRUEHJAHR, self.WINTER]
        assert saison_fuer_teams(alle, MO + timedelta(weeks=13)) is self.WINTER

    def test_naechste_beginnt(self):
        alle = [self.FRUEHJAHR, self.WINTER]
        assert saison_fuer_teams(alle, MO + timedelta(weeks=15)) is self.FRUEHJAHR

    def test_vor_der_ersten_saison_keine(self):
        assert saison_fuer_teams([self.WINTER], MO - timedelta(days=1)) is None


class TestSaisonFuerVorschlag:
    WINTER = TestSaisonFuerTeams.WINTER
    FRUEHJAHR = TestSaisonFuerTeams.FRUEHJAHR

    def test_laufende(self):
        alle = [self.FRUEHJAHR, self.WINTER]
        assert saison_fuer_vorschlag(alle, MO + timedelta(days=3)) is self.WINTER

    def test_vor_der_ersten_die_naechste(self):
        alle = [self.FRUEHJAHR, self.WINTER]
        assert saison_fuer_vorschlag(alle, MO - timedelta(days=5)) is self.WINTER

    def test_luecke_die_naechste_nicht_die_beendete(self):
        alle = [self.FRUEHJAHR, self.WINTER]
        assert saison_fuer_vorschlag(alle, MO + timedelta(weeks=13)) is self.FRUEHJAHR

    def test_nach_der_letzten_keine(self):
        assert saison_fuer_vorschlag([self.WINTER], MO + timedelta(weeks=13)) is None

    def test_naechste_ist_die_frueheste_geplante(self):
        alle = [self.FRUEHJAHR, self.WINTER]
        assert naechste_saison(alle, MO - timedelta(days=1)) is self.WINTER
        assert naechste_saison(alle, MO) is self.FRUEHJAHR
        assert naechste_saison([], MO) is None


class TestSchwelle:
    def _folge(self, *zahlen, ab=MO):
        return {ab + timedelta(weeks=i): z for i, z in enumerate(zahlen)}

    def test_drei_wochen_in_folge(self):
        zahlen = self._folge(25, 30, 25)
        assert schwelle_erreicht(zahlen, MO + timedelta(weeks=3), 25, 3)

    def test_eine_schwache_woche_unterbricht(self):
        zahlen = self._folge(25, 24, 30, 30)
        assert not schwelle_erreicht(zahlen, MO + timedelta(weeks=4), 25, 3)

    def test_fehlende_woche_unterbricht(self):
        zahlen = self._folge(30, 30)
        zahlen[MO + timedelta(weeks=3)] = 30
        assert not schwelle_erreicht(zahlen, MO + timedelta(weeks=4), 25, 3)

    def test_laufende_woche_zaehlt_nicht(self):
        zahlen = self._folge(30, 30, 30)
        assert not schwelle_erreicht(zahlen, MO + timedelta(weeks=2), 25, 3)

    def test_einmal_erreicht_bleibt_erreicht(self):
        zahlen = self._folge(30, 30, 30, 0, 1)
        assert schwelle_erreicht(zahlen, MO + timedelta(weeks=5), 25, 3)

    def test_null_wochen_heisst_immer(self):
        assert schwelle_erreicht({}, MO, 25, 0)
