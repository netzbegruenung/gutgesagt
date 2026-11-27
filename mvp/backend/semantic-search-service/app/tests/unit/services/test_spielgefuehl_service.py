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


def test_art9_widerruf_nimmt_nur_die_rangliste_zurueck(speicher):
    zuruecknehmen("kim", speicher)
    assert speicher.lesen("kim") is None

    speicher.antworten("bo", Stufe.FUER_MICH, False, AKTUELLER_WORTLAUT)
    zuruecknehmen("bo", speicher)
    # "Nur fuer mich" bleibt wie die bisherige Einwilligung "Punkte und Meilensteine".
    assert len(speicher.zeilen["bo"]) == 1

    speicher.antworten(
        "kim", Stufe.RANGLISTE, True, AKTUELLER_WORTLAUT, "Kluge Eule 11"
    )
    zuruecknehmen("kim", speicher)

    antwort = speicher.lesen("kim")
    assert antwort.stufe is Stufe.FUER_MICH
    assert antwort.mit_anzeigename is False
    assert antwort.ranglistenname == "Kluge Eule 11"


def test_jede_antwort_gilt_auch_im_bisherigen_modell(speicher):
    """
    Auch Stufe rangliste: Ein altes Ja zu Abzeichen am Namen lebte sonst nach dem
    Ausschalten des Schalters wieder auf (_alt_zuruecknehmen schreibt dort nur Neins).
    """
    alt = MagicMock()
    dienst = SpielgefuehlService(
        speicher, lambda: set(), lambda u: False, alt_zuruecknehmen=alt
    )

    dienst.antworten("kim", Stufe.RANGLISTE, True, AKTUELLER_WORTLAUT)
    alt.assert_called_with("kim", Stufe.RANGLISTE)
    dienst.antworten("kim", Stufe.FUER_MICH, None, AKTUELLER_WORTLAUT)
    alt.assert_called_with("kim", Stufe.FUER_MICH)
    dienst.antworten("kim", Stufe.AUS, None, AKTUELLER_WORTLAUT)
    alt.assert_called_with("kim", Stufe.AUS)


def test_aus_loescht_die_muster_hinweise(speicher):
    vergessen = MagicMock()
    dienst = SpielgefuehlService(
        speicher, lambda: set(), lambda u: False, hinweise_vergessen=vergessen
    )

    dienst.antworten("kim", Stufe.RANGLISTE, True, AKTUELLER_WORTLAUT)
    dienst.antworten("kim", Stufe.FUER_MICH, None, AKTUELLER_WORTLAUT)
    vergessen.assert_not_called()
    dienst.antworten("kim", Stufe.AUS, None, AKTUELLER_WORTLAUT)
    vergessen.assert_called_once_with("kim")


def test_aus_gilt_auch_wenn_das_loeschen_der_hinweise_scheitert(speicher):
    dienst = SpielgefuehlService(
        speicher,
        lambda: set(),
        lambda u: False,
        hinweise_vergessen=MagicMock(side_effect=RuntimeError("weg")),
    )

    dienst.antworten("kim", Stufe.AUS, None, AKTUELLER_WORTLAUT)

    assert speicher.lesen("kim").stufe is Stufe.AUS


@pytest.mark.parametrize(
    "bisher, stufe, erwartet",
    [
        (None, Stufe.AUS, True),
        (None, Stufe.FUER_MICH, False),
        (None, Stufe.RANGLISTE, False),
        (Stufe.RANGLISTE, Stufe.FUER_MICH, True),
        (Stufe.RANGLISTE, Stufe.RANGLISTE, False),
        (Stufe.FUER_MICH, Stufe.FUER_MICH, False),
        (Stufe.FUER_MICH, Stufe.RANGLISTE, False),
        (Stufe.AUS, Stufe.AUS, True),
    ],
)
def test_herabstufung(dienst, speicher, bisher, stufe, erwartet):
    if bisher is not None:
        speicher.antworten("kim", bisher, False, AKTUELLER_WORTLAUT, "X")

    assert dienst.herabstufung("kim", stufe) is erwartet


def test_herabstufung_zu_altem_wortlaut_gilt_als_aus(dienst, speicher):
    speicher.antworten("kim", Stufe.RANGLISTE, True, "spielgefuehl-1999", "X")

    assert dienst.herabstufung("kim", Stufe.FUER_MICH) is False
    assert dienst.herabstufung("kim", Stufe.AUS) is True


def test_zuruecknehmen_bis_aus(speicher):
    speicher.antworten("kim", Stufe.RANGLISTE, True, AKTUELLER_WORTLAUT, "X")
    speicher.antworten("bo", Stufe.FUER_MICH, False, AKTUELLER_WORTLAUT)

    zuruecknehmen("kim", speicher, bis=Stufe.AUS)
    zuruecknehmen("bo", speicher, bis=Stufe.AUS)
    zuruecknehmen("ida", speicher, bis=Stufe.AUS)

    assert speicher.lesen("kim").stufe is Stufe.AUS
    assert speicher.lesen("bo").stufe is Stufe.AUS
    assert speicher.lesen("ida") is None


def test_alt_zuruecknehmen_schreibt_nur_neins(monkeypatch):
    """Herabstufen haelt fruehere Ja-Antworten im bisherigen Modell als Nein fest."""
    from repositories.abzeichen_sichtbarkeit_repository import Sichtbarkeit
    from repositories.punkte_einwilligung_repository import PunkteEinwilligung

    sichtbarkeit, punkte = MagicMock(), MagicMock()
    sichtbarkeit.lesen.return_value = Sichtbarkeit(True, "2026-11-09", None)
    punkte.lesen.return_value = PunkteEinwilligung(True, "2026-11-13", None)
    monkeypatch.setattr(
        "repositories.abzeichen_sichtbarkeit_repository._repository", sichtbarkeit
    )
    monkeypatch.setattr(
        "repositories.punkte_einwilligung_repository._repository", punkte
    )
    rangliste = MagicMock()
    monkeypatch.setattr("services.rangliste_service.zuruecknehmen", rangliste)

    spielgefuehl_service._alt_zuruecknehmen("kim", Stufe.FUER_MICH)
    sichtbarkeit.antworten.assert_called_once_with("kim", False, "2026-11-09")
    rangliste.assert_called_once_with("kim")
    punkte.antworten.assert_not_called()

    spielgefuehl_service._alt_zuruecknehmen("kim", Stufe.AUS)
    punkte.antworten.assert_called_once_with("kim", False, "2026-11-13")


def test_alt_zuruecknehmen_bei_rangliste_nur_die_abzeichen(monkeypatch):
    """Stufe rangliste: Abzeichen am Namen Nein, Rangliste und Punkte unberuehrt."""
    from repositories.abzeichen_sichtbarkeit_repository import Sichtbarkeit
    from repositories.punkte_einwilligung_repository import PunkteEinwilligung

    sichtbarkeit, punkte = MagicMock(), MagicMock()
    sichtbarkeit.lesen.return_value = Sichtbarkeit(True, "2026-11-09", None)
    punkte.lesen.return_value = PunkteEinwilligung(True, "2026-11-13", None)
    monkeypatch.setattr(
        "repositories.abzeichen_sichtbarkeit_repository._repository", sichtbarkeit
    )
    monkeypatch.setattr(
        "repositories.punkte_einwilligung_repository._repository", punkte
    )
    rangliste = MagicMock()
    monkeypatch.setattr("services.rangliste_service.zuruecknehmen", rangliste)

    spielgefuehl_service._alt_zuruecknehmen("kim", Stufe.RANGLISTE)

    sichtbarkeit.antworten.assert_called_once_with("kim", False, "2026-11-09")
    rangliste.assert_not_called()
    punkte.antworten.assert_not_called()


def test_neu_wuerfeln_gedrosselt(speicher):
    uhr = {"t": 100.0}
    dienst = SpielgefuehlService(
        speicher, lambda: set(), lambda u: False, uhr=lambda: uhr["t"]
    )
    dienst.antworten("kim", Stufe.RANGLISTE, False, AKTUELLER_WORTLAUT)

    dienst.neu_wuerfeln("kim")
    with pytest.raises(spielgefuehl_service.ZuOftGewuerfelt):
        dienst.neu_wuerfeln("kim")
    uhr["t"] += spielgefuehl_service.WUERFELN_ABSTAND_SEKUNDEN
    dienst.neu_wuerfeln("kim")


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


class TestMusterHinweiseImNeuenModell:
    """Paar-Pruefwert und Muster-Hinweis wie bisher, im neuen Modell ab Stufe fuer_mich."""

    @pytest.mark.parametrize(
        "stufe, erwartet",
        [
            (None, False),
            (Stufe.AUS, False),
            (Stufe.FUER_MICH, True),
            (Stufe.RANGLISTE, True),
        ],
    )
    def test_ab_stufe_fuer_mich(self, spielgefuehl_ohne_datenbank, stufe, erwartet):
        import asyncio

        from api.v1.usage import _punkte_eingewilligt
        from core.config import Settings

        spielgefuehl_ohne_datenbank.lesen.return_value = (
            _antwort(stufe) if stufe else None
        )
        alt = MagicMock()
        alt.eingewilligt.return_value = True
        settings = Settings(punkte_aktiv=True, spielgefuehl_buehne_aktiv=True)
        with patch("repositories.punkte_einwilligung_repository._repository", alt):
            assert asyncio.run(_punkte_eingewilligt("kim", settings)) is erwartet
        # Die bisherige Einwilligung zaehlt im neuen Modell nicht.
        alt.eingewilligt.assert_not_called()

    def test_ohne_schalter_die_bisherige_einwilligung(
        self, spielgefuehl_ohne_datenbank
    ):
        import asyncio

        from api.v1.usage import _punkte_eingewilligt
        from core.config import Settings

        alt = MagicMock()
        alt.eingewilligt.return_value = True
        settings = Settings(punkte_aktiv=True, spielgefuehl_buehne_aktiv=False)
        with patch("repositories.punkte_einwilligung_repository._repository", alt):
            assert asyncio.run(_punkte_eingewilligt("kim", settings)) is True
        spielgefuehl_ohne_datenbank.lesen.assert_not_called()


def test_muster_im_neuen_modell_bei_lesefehler_nicht(spielgefuehl_ohne_datenbank):
    import asyncio

    from api.v1.usage import _punkte_eingewilligt
    from core.config import Settings

    spielgefuehl_ohne_datenbank.lesen.side_effect = RuntimeError("weg")
    settings = Settings(punkte_aktiv=True, spielgefuehl_buehne_aktiv=True)

    assert asyncio.run(_punkte_eingewilligt("kim", settings)) is False


class TestQuestEinwilligungSeit:
    """Juristische Vorgabe vom 27.11.: Quest-Punkte nur mit spielgefuehl_buehne und -28."""

    SEIT = datetime(2026, 11, 28, 9, tzinfo=timezone.utc)

    def test_mit_schalter_aus_der_tabelle(self, spielgefuehl_ohne_datenbank):
        spielgefuehl_ohne_datenbank.quest_einwilligung_seit.return_value = self.SEIT
        with patch.object(spielgefuehl_service, "buehne_aktiv", return_value=True):
            assert spielgefuehl_service.quest_einwilligung_seit("kim-1") == self.SEIT
        spielgefuehl_ohne_datenbank.quest_einwilligung_seit.assert_called_once_with(
            "kim-1"
        )

    def test_ohne_schalter_keine_und_ohne_abfrage(self, spielgefuehl_ohne_datenbank):
        spielgefuehl_ohne_datenbank.quest_einwilligung_seit.return_value = self.SEIT
        with patch.object(spielgefuehl_service, "buehne_aktiv", return_value=False):
            assert spielgefuehl_service.quest_einwilligung_seit("kim-1") is None
        spielgefuehl_ohne_datenbank.quest_einwilligung_seit.assert_not_called()
