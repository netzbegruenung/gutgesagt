"""
Rangliste je Saison (#793, services/rangliste_service.py): wer darin steht, wer sie
sieht, Saisonpunkte und vergangene Saisons als Summe.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Dict
from unittest.mock import Mock

import pytest

from domain.punkte import Punktestand
from domain.rangliste import AKTUELLER_WORTLAUT, UnbekannterWortlaut
from domain.saisons import Saison
from repositories.rangliste_einwilligung_repository import RanglisteAntwort
from services import rangliste_service as modul
from services.rangliste_service import RanglisteService

pytestmark = pytest.mark.unit

HEUTE = date(2026, 12, 10)
LAUFEND = Saison(uuid.uuid4(), "Winter 26", date(2026, 12, 1), date(2027, 2, 28), 100)
VORBEI = Saison(uuid.uuid4(), "Herbst 26", date(2026, 10, 1), date(2026, 11, 30), 50)
ALT = Saison(uuid.uuid4(), "Sommer 26", date(2026, 6, 1), date(2026, 8, 31), 50)
ZEIT = datetime(2026, 12, 1, tzinfo=timezone.utc)


def _antwort(teilnehmen=True, mit_anzeigename=False) -> RanglisteAntwort:
    return RanglisteAntwort(teilnehmen, mit_anzeigename, AKTUELLER_WORTLAUT, ZEIT)


class _Welt:
    def __init__(self, teilnehmende: Dict[str, bool], punkte: Dict[str, int]):
        self.repository = Mock()
        self.repository.teilnehmende.return_value = teilnehmende
        self.repository.lesen.side_effect = lambda k: (
            _antwort(True, teilnehmende[k]) if k in teilnehmende else None
        )
        self.punkte = punkte
        self.ohne_voraussetzung: set = set()
        self.aufrufe = []
        self.saisons = [LAUFEND, VORBEI, ALT]

    async def saisonpunkte(self, kennung, zeitraum):
        self.aufrufe.append((kennung, zeitraum))
        if kennung not in self.punkte:
            return Punktestand(0, 0, 0, sammelt=False)
        return Punktestand(tun=0, quests=0, wirkung=self.punkte[kennung])

    def dienst(self, uhr=lambda: 0.0) -> RanglisteService:
        return RanglisteService(
            self.repository,
            lambda: self.saisons,
            self.saisonpunkte,
            lambda k: k not in self.ohne_voraussetzung,
            lambda kennungen: {k: f"Name {k}" for k in kennungen},
            heute=lambda: HEUTE,
            uhr=uhr,
        )


def _zehn() -> _Welt:
    kennungen = [f"p{i}" for i in range(10)]
    return _Welt(
        {k: False for k in kennungen}, {k: 10 * i for i, k in enumerate(kennungen)}
    )


@pytest.mark.asyncio
async def test_teilnehmende_person_sieht_rangliste_der_laufenden_saison():
    welt = _zehn()

    stand = await welt.dienst().stand("p3")

    assert stand.teilnehmend
    assert stand.saison == LAUFEND
    assert stand.eigene_punkte == 30
    assert stand.rangliste.teilnehmende == 10
    assert stand.rangliste.oben[0].punkte == 90
    assert ("p3", (LAUFEND.beginn, LAUFEND.ende)) in welt.aufrufe


@pytest.mark.asyncio
async def test_ohne_eigene_einwilligung_keine_rangliste():
    welt = _zehn()

    stand = await welt.dienst().stand("draussen")

    assert stand.antwort is None
    assert stand.rangliste is None
    assert stand.eigene_punkte is None
    assert stand.vergangene == []
    assert welt.aufrufe == []


@pytest.mark.asyncio
async def test_nein_sieht_nichts():
    welt = _zehn()
    welt.repository.lesen.side_effect = lambda k: _antwort(False)

    stand = await welt.dienst().stand("p3")

    assert not stand.teilnehmend
    assert stand.rangliste is None


@pytest.mark.asyncio
async def test_fehlende_voraussetzung_wirft_sofort_raus_und_andere_ruecken_nach():
    welt = _zehn()
    welt.punkte["p10"] = 1
    welt.repository.teilnehmende.return_value = {
        **welt.repository.teilnehmende.return_value,
        "p10": False,
    }

    welt.ohne_voraussetzung = {"p9"}
    stand = await welt.dienst().stand("p3")

    namen = [p.name for p in stand.rangliste.oben]
    assert stand.rangliste.teilnehmende == 10
    assert all("p9" not in n for n in namen)


@pytest.mark.asyncio
async def test_eigene_fehlende_voraussetzung_keine_rangliste():
    welt = _zehn()
    welt.ohne_voraussetzung = {"p3"}

    stand = await welt.dienst().stand("p3")

    assert stand.voraussetzungen is False
    assert stand.rangliste is None


@pytest.mark.asyncio
async def test_unter_zehn_keine_plaetze_aber_eigene_punkte():
    welt = _zehn()
    welt.ohne_voraussetzung = {"p9"}

    stand = await welt.dienst().stand("p3")

    assert stand.rangliste is None
    assert stand.eigene_punkte == 30


@pytest.mark.asyncio
async def test_startkonto_oder_ohne_punkte_zaehlt_nicht_mit():
    welt = _zehn()
    welt.repository.teilnehmende.return_value = {
        **welt.repository.teilnehmende.return_value,
        "start": False,
    }

    stand = await welt.dienst().stand("p3")

    assert stand.rangliste.teilnehmende == 10


@pytest.mark.asyncio
async def test_anzeigename_nur_bei_aktiver_wahl():
    welt = _zehn()
    welt.repository.teilnehmende.return_value = {
        **welt.repository.teilnehmende.return_value,
        "p9": True,
    }

    stand = await welt.dienst().stand("p3")

    assert stand.rangliste.oben[0].name == "Name p9"
    assert all(not p.name.startswith("Name") for p in stand.rangliste.oben[1:])


@pytest.mark.asyncio
async def test_ohne_laufende_saison_keine_rangliste():
    welt = _zehn()
    welt.saisons = [VORBEI]

    stand = await welt.dienst().stand("p3")

    assert stand.saison is None
    assert stand.rangliste is None


@pytest.mark.asyncio
async def test_vergangene_nur_als_summe_und_nur_in_der_frist():
    welt = _zehn()

    stand = await welt.dienst().stand("p3")

    # Sommer 26 begann vor mehr als 90 Tagen: Die Nutzung von damals ist verworfen.
    assert [(v.name, v.punkte) for v in stand.vergangene] == [("Herbst 26", 30)]


@pytest.mark.asyncio
async def test_saisonpunkte_kurz_im_cache():
    welt = _zehn()
    zeit = [0.0]
    dienst = welt.dienst(uhr=lambda: zeit[0])

    await dienst.stand("p3")
    erste = len(welt.aufrufe)
    await dienst.stand("p3")
    assert len(welt.aufrufe) == erste

    zeit[0] = modul.CACHE_SEKUNDEN + 1
    await dienst.stand("p3")
    assert len(welt.aufrufe) == 2 * erste


@pytest.mark.asyncio
async def test_fehler_bei_einer_person_laesst_sie_aus():
    welt = _zehn()
    welt.punkte["p10"] = 5
    welt.repository.teilnehmende.return_value = {
        **welt.repository.teilnehmende.return_value,
        "p10": False,
    }
    original = welt.saisonpunkte

    async def mit_fehler(kennung, zeitraum):
        if kennung == "p0":
            raise RuntimeError("Qdrant weg")
        return await original(kennung, zeitraum)

    welt.saisonpunkte = mit_fehler
    stand = await welt.dienst().stand("p3")

    assert stand.rangliste.teilnehmende == 10


def test_antworten_ja_nur_zum_aktuellen_wortlaut():
    welt = _zehn()
    dienst = welt.dienst()

    with pytest.raises(UnbekannterWortlaut):
        dienst.antworten("p3", True, False, "2020-01-01")
    welt.repository.antworten.assert_not_called()

    dienst.antworten("p3", True, True, AKTUELLER_WORTLAUT)
    welt.repository.antworten.assert_called_with("p3", True, True, AKTUELLER_WORTLAUT)


def test_nein_nimmt_den_anzeigenamen_mit_zurueck():
    welt = _zehn()

    welt.dienst().antworten("p3", False, True, AKTUELLER_WORTLAUT)

    welt.repository.antworten.assert_called_with("p3", False, False, AKTUELLER_WORTLAUT)


def test_zuruecknehmen_haelt_ja_als_nein_fest():
    repository = Mock()
    repository.lesen.return_value = _antwort(True, True)

    modul.zuruecknehmen("p3", repository)

    repository.antworten.assert_called_once_with("p3", False, False, AKTUELLER_WORTLAUT)


@pytest.mark.parametrize("antwort", [None, _antwort(False)])
def test_zuruecknehmen_ohne_ja_schreibt_nichts(antwort):
    repository = Mock()
    repository.lesen.return_value = antwort

    modul.zuruecknehmen("p3", repository)

    repository.antworten.assert_not_called()


def test_fuer_vergangene_tage_ohne_frist_kein_zeitraum_vor_der_frist():
    assert HEUTE - timedelta(days=modul.NUTZUNG_FRIST_TAGE) > ALT.beginn
    assert HEUTE - timedelta(days=modul.NUTZUNG_FRIST_TAGE) <= VORBEI.beginn
