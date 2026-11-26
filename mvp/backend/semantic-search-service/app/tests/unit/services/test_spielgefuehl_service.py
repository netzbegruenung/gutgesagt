"""
Spielgefuehl als eine Einstellung (services/spielgefuehl_service.py): Stufe waehlen,
Namenswahl, neu wuerfeln, Widerruf und die Umschaltung zwischen den Modellen.
"""

from dataclasses import replace
from datetime import datetime, timezone
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from domain.spielgefuehl import (
    AKTUELLER_WORTLAUT,
    NamenswahlFehlt,
    Stufe,
    UnbekannterWortlaut,
)
from repositories.rangliste_einwilligung_repository import Teilnahme
from repositories.spielgefuehl_repository import SpielgefuehlAntwort
from services import spielgefuehl_service
from services.spielgefuehl_service import (
    NichtInRangliste,
    RanglistenQuelle,
    SpielgefuehlService,
    zuruecknehmen,
)

pytestmark = pytest.mark.unit


class Speicher:
    """Ein Repository im Arbeitsspeicher mit derselben Regel wie das echte."""

    def __init__(self):
        self.zeilen: Dict[str, List[SpielgefuehlAntwort]] = {}

    def lesen(self, user_id) -> Optional[SpielgefuehlAntwort]:
        zeilen = self.zeilen.get(user_id)
        return zeilen[-1] if zeilen else None

    def antworten(self, user_id, stufe, mit_anzeigename, wortlaut, ranglistenname=None):
        juengste = self.lesen(user_id)
        if ranglistenname is None and juengste is not None:
            ranglistenname = juengste.ranglistenname
        neu = SpielgefuehlAntwort(
            stufe, mit_anzeigename, wortlaut, datetime.now(timezone.utc), ranglistenname
        )
        if (
            juengste is not None
            and replace(neu, beantwortet_am=juengste.beantwortet_am) == juengste
        ):
            return
        self.zeilen.setdefault(user_id, []).append(neu)

    def vergebene_namen(self):
        return {
            z.ranglistenname
            for zeilen in self.zeilen.values()
            for z in zeilen
            if z.ranglistenname
        }


@pytest.fixture
def speicher():
    return Speicher()


@pytest.fixture
def vergessen():
    return MagicMock()


@pytest.fixture
def dienst(speicher, vergessen):
    return SpielgefuehlService(
        speicher, lambda: set(), lambda user_id: False, vergessen
    )


def test_ohne_antwort_keine_stufe(dienst):
    stand = dienst.stand("kim")

    assert stand.stufe is None
    assert stand.abzeichen_hinweis is False


def test_hinweis_fuer_bisher_gezeigte_abzeichen_bis_zur_antwort(speicher):
    dienst = SpielgefuehlService(speicher, lambda: set(), lambda user_id: True)

    assert dienst.stand("kim").abzeichen_hinweis is True
    dienst.antworten("kim", Stufe.FUER_MICH, None, AKTUELLER_WORTLAUT)
    assert dienst.stand("kim").abzeichen_hinweis is False


def test_rangliste_ohne_namenswahl_geht_nicht(dienst, speicher):
    with pytest.raises(NamenswahlFehlt):
        dienst.antworten("kim", Stufe.RANGLISTE, None, AKTUELLER_WORTLAUT)
    assert speicher.lesen("kim") is None


@pytest.mark.parametrize("mit_anzeigename", [True, False])
def test_erstes_mitspielen_wuerfelt_den_zufallsnamen(dienst, speicher, mit_anzeigename):
    dienst.antworten("kim", Stufe.RANGLISTE, mit_anzeigename, AKTUELLER_WORTLAUT)

    antwort = speicher.lesen("kim")
    assert antwort.stufe is Stufe.RANGLISTE
    assert antwort.mit_anzeigename is mit_anzeigename
    # Auch mit Anzeigename: Der Zufallsname steht fuer den Wechsel bereit.
    assert antwort.ranglistenname
    assert dienst.stand("kim").mit_anzeigename is mit_anzeigename


def test_herabstufen_wirkt_sofort_und_behaelt_den_namen(dienst, speicher, vergessen):
    dienst.antworten("kim", Stufe.RANGLISTE, True, AKTUELLER_WORTLAUT)
    name = speicher.lesen("kim").ranglistenname

    dienst.antworten("kim", Stufe.FUER_MICH, True, AKTUELLER_WORTLAUT)

    antwort = speicher.lesen("kim")
    assert antwort.stufe is Stufe.FUER_MICH
    assert antwort.mit_anzeigename is False
    assert antwort.ranglistenname == name
    vergessen.assert_called_with("kim")
    assert len(speicher.zeilen["kim"]) == 2


def test_wieder_mitspielen_wuerfelt_nicht_neu(dienst, speicher):
    dienst.antworten("kim", Stufe.RANGLISTE, False, AKTUELLER_WORTLAUT)
    name = speicher.lesen("kim").ranglistenname
    dienst.antworten("kim", Stufe.AUS, None, AKTUELLER_WORTLAUT)
    dienst.antworten("kim", Stufe.RANGLISTE, False, AKTUELLER_WORTLAUT)

    assert speicher.lesen("kim").ranglistenname == name


def test_unbekannter_oder_alter_wortlaut(dienst):
    with pytest.raises(UnbekannterWortlaut):
        dienst.antworten("kim", Stufe.FUER_MICH, None, "spielgefuehl-1999")
    with pytest.raises(UnbekannterWortlaut):
        dienst.antworten("kim", Stufe.AUS, None, "gibt-es-nicht")


def test_neu_wuerfeln_nur_in_der_rangliste(dienst, speicher):
    dienst.antworten("kim", Stufe.FUER_MICH, None, AKTUELLER_WORTLAUT)
    with pytest.raises(NichtInRangliste):
        dienst.neu_wuerfeln("kim")

    dienst.antworten("kim", Stufe.RANGLISTE, True, AKTUELLER_WORTLAUT)
    alt = speicher.lesen("kim").ranglistenname
    with patch.object(
        spielgefuehl_service, "neuer_ranglistenname", return_value="Kluge Eule 11"
    ):
        neu = dienst.neu_wuerfeln("kim")

    assert neu == "Kluge Eule 11" != alt
    antwort = speicher.lesen("kim")
    assert antwort.ranglistenname == neu
    # Stufe und Namenswahl bleiben; der Wechsel ist eine neue Nachweiszeile.
    assert antwort.stufe is Stufe.RANGLISTE and antwort.mit_anzeigename is True
    assert len(speicher.zeilen["kim"]) == 3


def test_wuerfeln_meidet_namen_aus_beiden_tabellen(speicher):
    gesehen = {}

    def wuerfeln(vergeben):
        gesehen["vergeben"] = set(vergeben)
        return "Mutige Biene 12"

    dienst = SpielgefuehlService(speicher, lambda: {"Alte Amsel 10"}, lambda u: False)
    with patch.object(spielgefuehl_service, "neuer_ranglistenname", wuerfeln):
        dienst.antworten("kim", Stufe.RANGLISTE, False, AKTUELLER_WORTLAUT)

    assert "Alte Amsel 10" in gesehen["vergeben"]


def test_zuruecknehmen_haelt_aus_fest(speicher):
    zuruecknehmen("kim", speicher)
    assert speicher.lesen("kim") is None

    speicher.antworten(
        "kim", Stufe.RANGLISTE, True, AKTUELLER_WORTLAUT, "Kluge Eule 11"
    )
    zuruecknehmen("kim", speicher)

    antwort = speicher.lesen("kim")
    assert antwort.stufe is Stufe.AUS
    assert antwort.ranglistenname == "Kluge Eule 11"


def test_antwort_zu_altem_wortlaut_gilt_als_keine(dienst, speicher):
    speicher.antworten("kim", Stufe.RANGLISTE, True, "spielgefuehl-1999", "X")

    assert dienst.stand("kim").stufe is None
    assert speicher.lesen("kim").wirksame_stufe is Stufe.AUS


def _antwort(stufe):
    return SpielgefuehlAntwort(
        stufe, False, AKTUELLER_WORTLAUT, datetime.now(timezone.utc)
    )


class TestUmschaltung:
    def test_punkte_ohne_schalter_aus_der_alten_einwilligung(
        self, spielgefuehl_ohne_datenbank
    ):
        alt = MagicMock()
        alt.eingewilligt.return_value = True
        with patch.object(
            spielgefuehl_service, "buehne_aktiv", return_value=False
        ), patch("repositories.punkte_einwilligung_repository._repository", alt):
            assert spielgefuehl_service.punkte_eingewilligt("kim") is True
        spielgefuehl_ohne_datenbank.lesen.assert_not_called()

    @pytest.mark.parametrize(
        "stufe, erwartet",
        [
            (None, False),
            (Stufe.AUS, False),
            (Stufe.FUER_MICH, True),
            (Stufe.RANGLISTE, True),
        ],
    )
    def test_punkte_mit_schalter_nur_aus_der_stufe(
        self, spielgefuehl_ohne_datenbank, stufe, erwartet
    ):
        spielgefuehl_ohne_datenbank.lesen.return_value = (
            _antwort(stufe) if stufe else None
        )
        alt = MagicMock()
        alt.eingewilligt.return_value = True
        # Die alte Einwilligung "ja" zaehlt im neuen Modell nicht: neu fragen.
        with patch.object(
            spielgefuehl_service, "buehne_aktiv", return_value=True
        ), patch("repositories.punkte_einwilligung_repository._repository", alt):
            assert spielgefuehl_service.punkte_eingewilligt("kim") is erwartet
        alt.eingewilligt.assert_not_called()

    def test_punkte_eingewilligte_mit_schalter(self, spielgefuehl_ohne_datenbank):
        spielgefuehl_ohne_datenbank.wirksame_stufen.return_value = {
            "a": Stufe.AUS,
            "b": Stufe.FUER_MICH,
            "c": Stufe.RANGLISTE,
        }
        with patch.object(spielgefuehl_service, "buehne_aktiv", return_value=True):
            assert spielgefuehl_service.punkte_eingewilligte(["a", "b", "c", "d"]) == {
                "b",
                "c",
            }

    def test_ranglisten_quelle_waehlt_das_modell(self):
        alt, neu = MagicMock(), MagicMock()
        alt.teilnehmende.return_value = {"alt": Teilnahme(False, "A")}
        neu.teilnehmende.return_value = {"neu": Teilnahme(True, "N")}
        neu.lesen.return_value = SpielgefuehlAntwort(
            Stufe.FUER_MICH, False, AKTUELLER_WORTLAUT, datetime.now(timezone.utc), "N"
        )
        an = {"wert": False}
        quelle = RanglistenQuelle(alt, neu, lambda: an["wert"])

        assert set(quelle.teilnehmende()) == {"alt"}
        an["wert"] = True
        assert set(quelle.teilnehmende()) == {"neu"}
        antwort = quelle.lesen("kim")
        assert antwort.teilnehmen is False and antwort.ranglistenname == "N"
        with pytest.raises(RuntimeError):
            quelle.antworten("kim", True, False, "rangliste-2026-11-25")
        alt.antworten.assert_not_called()
