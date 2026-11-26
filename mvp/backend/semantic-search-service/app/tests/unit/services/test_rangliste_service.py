"""
Rangliste je Saison (#793, services/rangliste_service.py): wer darin steht, wer sie
sieht, Saisonpunkte und vergangene Saisons als Summe.
"""

import asyncio
import uuid
from datetime import date, datetime, timezone
from typing import Dict
from unittest.mock import Mock

import pytest

from domain.punkte import Punktestand
from domain.rangliste import AKTUELLER_WORTLAUT, UnbekannterWortlaut
from domain.saisons import Saison
from repositories.rangliste_einwilligung_repository import (
    RanglisteAntwort,
    Teilnahme,
)
from services import rangliste_service as modul
from services.rangliste_service import EigenePunkteFehlen, RanglisteService

pytestmark = pytest.mark.unit

HEUTE = date(2026, 12, 10)
LAUFEND = Saison(uuid.uuid4(), "Winter 26", date(2026, 12, 1), date(2027, 2, 28), 100)
VORBEI = Saison(uuid.uuid4(), "Herbst 26", date(2026, 10, 1), date(2026, 11, 30), 50)
ALT = Saison(uuid.uuid4(), "Sommer 26", date(2026, 6, 1), date(2026, 8, 31), 50)
ZEIT = datetime(2026, 12, 1, tzinfo=timezone.utc)


def _antwort(teilnehmen=True, mit_anzeigename=False, name=None) -> RanglisteAntwort:
    return RanglisteAntwort(
        teilnehmen, mit_anzeigename, AKTUELLER_WORTLAUT, ZEIT, ranglistenname=name
    )


def _zufallsname(kennung: str) -> str:
    return f"Zufall {kennung}"


class _Welt:
    def __init__(self, teilnehmende: Dict[str, bool], punkte: Dict[str, int]):
        self.repository = Mock()
        self.teilnehmende = {
            k: Teilnahme(mit, _zufallsname(k)) for k, mit in teilnehmende.items()
        }
        self.repository.teilnehmende.side_effect = lambda: self.teilnehmende
        self.repository.lesen.side_effect = lambda k: (
            _antwort(True, self.teilnehmende[k].mit_anzeigename, _zufallsname(k))
            if k in self.teilnehmende
            else None
        )
        self.repository.vergebene_namen.return_value = set()
        self.punkte = punkte
        self.ohne_voraussetzung: set = set()
        self.voraussetzungs_abfragen = []
        self.aufrufe = []
        self.saisons = [LAUFEND, VORBEI, ALT]

    def dazu(self, kennung: str, mit_anzeigename: bool = False) -> None:
        self.teilnehmende[kennung] = Teilnahme(mit_anzeigename, _zufallsname(kennung))

    async def saisonpunkte(self, kennung, zeitraum):
        self.aufrufe.append((kennung, zeitraum))
        if kennung not in self.punkte:
            return Punktestand(0, 0, 0, sammelt=False)
        return Punktestand(tun=0, quests=0, wirkung=self.punkte[kennung])

    def voraussetzungen(self, kennungen):
        kennungen = list(kennungen)
        self.voraussetzungs_abfragen.append(kennungen)
        return {k for k in kennungen if k not in self.ohne_voraussetzung}

    def dienst(self, uhr=lambda: 0.0, frist=90) -> RanglisteService:
        return RanglisteService(
            self.repository,
            lambda: self.saisons,
            lambda k, z: self.saisonpunkte(k, z),
            self.voraussetzungen,
            lambda kennungen: {k: f"Name {k}" for k in kennungen},
            nutzung_frist_tage=frist,
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
    assert stand.ranglistenname == "Zufall p3"
    assert stand.rangliste.teilnehmende == 10
    assert stand.rangliste.oben[0].punkte == 90
    assert stand.rangliste.oben[0].name == "Zufall p9"
    assert ("p3", (LAUFEND.beginn, LAUFEND.ende)) in welt.aufrufe


@pytest.mark.asyncio
async def test_voraussetzungen_aller_in_einer_abfrage():
    welt = _zehn()

    await welt.dienst().stand("p3")

    # Eine fuer die fragende Person, eine fuer alle anderen zusammen
    assert len(welt.voraussetzungs_abfragen) == 2
    assert sorted(welt.voraussetzungs_abfragen[1]) == sorted(
        f"p{i}" for i in range(10) if i != 3
    )


@pytest.mark.asyncio
async def test_ohne_eigene_einwilligung_keine_rangliste():
    welt = _zehn()

    stand = await welt.dienst().stand("draussen")

    assert stand.antwort is None
    assert stand.ranglistenname is None
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
    welt.dazu("p10")

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
    welt.dazu("start")

    stand = await welt.dienst().stand("p3")

    assert stand.rangliste.teilnehmende == 10


@pytest.mark.asyncio
async def test_anzeigename_nur_bei_aktiver_wahl():
    welt = _zehn()
    welt.dazu("p9", mit_anzeigename=True)

    stand = await welt.dienst().stand("p3")

    assert stand.rangliste.oben[0].name == "Name p9"
    assert all(p.name.startswith("Zufall") for p in stand.rangliste.oben[1:])


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

    stand = await welt.dienst(frist=90).stand("p3")

    # Sommer 26 begann vor mehr als 90 Tagen: Die Nutzung von damals ist verworfen.
    assert [(v.name, v.punkte) for v in stand.vergangene] == [("Herbst 26", 30)]


@pytest.mark.asyncio
async def test_frist_kommt_aus_der_einstellung():
    welt = _zehn()

    kurz = await welt.dienst(frist=30).stand("p3")
    ohne = await welt.dienst(frist=None).stand("p3")

    # Herbst 26 begann vor 70 Tagen: mit 30 Tagen Frist schon zu alt
    assert kurz.vergangene == []
    # Ohne Bereinigungsjob gilt keine Frist
    assert [v.name for v in ohne.vergangene] == ["Herbst 26", "Sommer 26"]


@pytest.mark.asyncio
async def test_saisonpunkte_kurz_im_cache():
    welt = _zehn()
    zeit = [0.0]
    dienst = welt.dienst(uhr=lambda: zeit[0])

    await dienst.stand("p3")
    erste = len(welt.aufrufe)
    await dienst.stand("p3")
    await dienst.stand("p5")
    assert len(welt.aufrufe) == erste + 1  # nur die vergangene Saison von p5

    zeit[0] = modul.CACHE_SEKUNDEN + 1
    await dienst.stand("p3")
    assert len(welt.aufrufe) == 2 * erste + 1


@pytest.mark.asyncio
async def test_gleichzeitige_abrufe_rechnen_die_liste_einmal():
    welt = _zehn()
    welt.saisons = [LAUFEND]
    dienst = welt.dienst()

    await asyncio.gather(*(dienst.stand(f"p{i}") for i in range(10)))

    assert len(welt.aufrufe) == 10


@pytest.mark.asyncio
async def test_hoechstens_parallel_gleichzeitig_gerechnet(monkeypatch):
    monkeypatch.setattr(modul, "PARALLEL", 3)
    welt = _zehn()
    welt.saisons = [LAUFEND]
    laufend = [0]
    hoechstens = [0]
    original = welt.saisonpunkte

    async def langsam(kennung, zeitraum):
        laufend[0] += 1
        hoechstens[0] = max(hoechstens[0], laufend[0])
        await asyncio.sleep(0)
        laufend[0] -= 1
        return await original(kennung, zeitraum)

    welt.saisonpunkte = langsam
    await welt.dienst().stand("p3")

    assert 1 < hoechstens[0] <= 3


@pytest.mark.asyncio
async def test_fehler_bei_einer_person_laesst_sie_aus():
    welt = _zehn()
    welt.punkte["p10"] = 5
    welt.dazu("p10")
    original = welt.saisonpunkte

    async def mit_fehler(kennung, zeitraum):
        if kennung == "p0":
            raise RuntimeError("Qdrant weg")
        return await original(kennung, zeitraum)

    welt.saisonpunkte = mit_fehler
    stand = await welt.dienst().stand("p3")

    assert stand.rangliste.teilnehmende == 10


@pytest.mark.asyncio
async def test_fehler_wird_beim_naechsten_abruf_erneut_versucht():
    welt = _zehn()
    welt.saisons = [LAUFEND]
    original = welt.saisonpunkte
    fehler = [True]

    async def mit_fehler(kennung, zeitraum):
        if kennung == "p0" and fehler[0]:
            raise RuntimeError("Qdrant weg")
        return await original(kennung, zeitraum)

    welt.saisonpunkte = mit_fehler
    dienst = welt.dienst()
    assert (await dienst.stand("p3")).rangliste is None
    fehler[0] = False

    assert (await dienst.stand("p3")).rangliste.teilnehmende == 10


@pytest.mark.asyncio
async def test_unvollstaendiger_stand_wird_nicht_gemerkt():
    """
    Fehlen einer Person die Quest-Punkte, waere ihre Summe zu niedrig; der Cache hielte
    den zu tiefen Platz 120 s lang. Sie fehlt lieber bis zum naechsten Abruf.
    """
    welt = _zehn()
    welt.punkte["p10"] = 5
    welt.dazu("p10")
    original = welt.saisonpunkte
    unvollstaendig = [True]

    async def ohne_quests(kennung, zeitraum):
        stand = await original(kennung, zeitraum)
        if kennung == "p0" and unvollstaendig[0]:
            return Punktestand(
                tun=stand.tun,
                quests=0,
                wirkung=stand.wirkung,
                vollstaendig=False,
            )
        return stand

    welt.saisonpunkte = ohne_quests
    dienst = welt.dienst()
    assert (await dienst.stand("p3")).rangliste.teilnehmende == 10
    unvollstaendig[0] = False

    assert (await dienst.stand("p3")).rangliste.teilnehmende == 11


@pytest.mark.asyncio
async def test_fehler_bei_der_fragenden_person_keine_liste():
    """Sehen darf die Liste nur, wer darin steht; 0 Punkte waeren falsch (Review zu #793)."""
    welt = _zehn()
    original = welt.saisonpunkte

    async def mit_fehler(kennung, zeitraum):
        if kennung == "p3":
            raise RuntimeError("Qdrant weg")
        return await original(kennung, zeitraum)

    welt.saisonpunkte = mit_fehler

    with pytest.raises(EigenePunkteFehlen):
        await welt.dienst().stand("p3")


def test_erstes_ja_wuerfelt_den_ranglistennamen():
    welt = _zehn()
    welt.repository.lesen.side_effect = lambda k: None
    welt.repository.vergebene_namen.return_value = {"Flinke Amsel 42"}

    welt.dienst().antworten("neu", True, False, AKTUELLER_WORTLAUT)

    args = welt.repository.antworten.call_args.args
    assert args[:4] == ("neu", True, False, AKTUELLER_WORTLAUT)
    assert args[4] and args[4] != "Flinke Amsel 42"


def test_weiteres_ja_behaelt_den_namen():
    welt = _zehn()
    welt.repository.lesen.side_effect = lambda k: _antwort(False, name="Kluge Eule 37")

    welt.dienst().antworten("p3", True, True, AKTUELLER_WORTLAUT)

    welt.repository.antworten.assert_called_with(
        "p3", True, True, AKTUELLER_WORTLAUT, None
    )
    welt.repository.vergebene_namen.assert_not_called()


def test_antworten_ja_nur_zum_aktuellen_wortlaut():
    welt = _zehn()
    dienst = welt.dienst()

    with pytest.raises(UnbekannterWortlaut):
        dienst.antworten("p3", True, False, "2020-01-01")
    welt.repository.antworten.assert_not_called()


def test_nein_nimmt_den_anzeigenamen_mit_zurueck():
    welt = _zehn()

    welt.dienst().antworten("p3", False, True, AKTUELLER_WORTLAUT)

    welt.repository.antworten.assert_called_with(
        "p3", False, False, AKTUELLER_WORTLAUT, None
    )


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
