"""
Der Punktestand einer Person (#352): aus welchen Beitraegen, welcher Nutzung und
welchen Stimmen er entsteht. Die Rechnung selbst pruefen tests/unit/domain/test_punkte.py.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Dict, List
from unittest.mock import AsyncMock, patch

import pytest

from core.config import Settings
from services.punkte_service import PunkteService

pytestmark = pytest.mark.asyncio

JETZT = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
KIM = "kim-1"
START = "start-9"


def _beitrag(alter_tage: float) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), created=JETZT - timedelta(days=alter_tage))


class _Quellen:
    """Steht fuer Qdrant und PostgreSQL: liefert, was ihm gegeben wird."""

    def __init__(
        self, beitraege, nutzung=None, zustimmungen=0, einwuerfe=None, bewertungen=None
    ):
        self.beitraege = beitraege
        self.nutzung = nutzung or {}
        self.zustimmungen_zahl = zustimmungen
        self.einwuerfe = einwuerfe or {}
        self.bewertungen = bewertungen or {}
        self.ausgenommen = None
        self.bewertungen_ohne = None

    async def sichtbare_beitraege(self, user_id: str) -> List:
        return self.beitraege

    def get_nutzung_entdoppelt_batch(self, ids) -> Dict[str, int]:
        return {str(i): self.nutzung.get(i, 0) for i in ids}

    def zustimmungen(self, content_ids, ausgenommen) -> int:
        self.ausgenommen = ausgenommen
        return self.zustimmungen_zahl if content_ids else 0

    def einwuerfe_ausformuliert_je_tag(self, user_id: str, bis) -> Dict[date, int]:
        self.einwuerfe_bis = bis
        return self.einwuerfe

    def bewertungen_je_tag(self, user_id: str, ohne_beitraege) -> Dict[date, int]:
        self.bewertungen_ohne = list(ohne_beitraege)
        return self.bewertungen


def _service(
    quellen: _Quellen, eingewilligt=lambda user_id: True, **einstellungen
) -> PunkteService:
    settings = Settings(
        startkonten=START,
        punkte_nutzung=10,
        punkte_zustimmung=5,
        punkte_beitrag=1,
        punkte_einwurf_ausformuliert=1,
        punkte_deckel_tun_je_tag=3,
        **einstellungen,
    )
    return PunkteService(
        quellen.sichtbare_beitraege,
        quellen,
        quellen,
        settings,
        jetzt=lambda: JETZT,
        eingewilligt=eingewilligt,
    )


async def test_punkte_wirkung_aus_entdoppelter_nutzung_und_zustimmung():
    beitrag = _beitrag(10)
    quellen = _Quellen([beitrag], nutzung={beitrag.id: 2}, zustimmungen=3)

    stand = await _service(quellen).punkte(KIM)

    assert stand.wirkung == 35


async def test_punkte_zustimmung_ohne_eigene_und_ohne_startkonten():
    quellen = _Quellen([_beitrag(10)], zustimmungen=1)

    await _service(quellen).punkte(KIM)

    assert quellen.ausgenommen == {KIM, START}


async def test_punkte_beitrag_zaehlt_erst_nach_drei_tagen():
    quellen = _Quellen([_beitrag(2.9), _beitrag(3), _beitrag(4)])

    stand = await _service(quellen).punkte(KIM)

    assert stand.tun == 2


async def test_punkte_tun_mit_ausformulierten_einwuerfen_je_tag_gedeckelt():
    tag = (JETZT - timedelta(days=5)).date()
    quellen = _Quellen(
        [_beitrag(5), _beitrag(5)], einwuerfe={tag: 2, tag - timedelta(1): 1}
    )

    stand = await _service(quellen).punkte(KIM)

    assert stand.tun == 3 + 1
    # Einwuerfe warten wie Beitraege drei Tage.
    assert quellen.einwuerfe_bis == JETZT - timedelta(days=3)


async def test_punkte_bewerten_je_tag_eigens_gedeckelt():
    """
    Ein Punkt je Stimme, je Tag hoechstens drei (Entscheidung 20.11.2026), getrennt
    vom Deckel fuers Tun: Wer an einem Tag schreibt und abstimmt, bekommt beides.
    """
    tag = (JETZT - timedelta(days=5)).date()
    quellen = _Quellen(
        [_beitrag(5), _beitrag(5), _beitrag(5)],
        bewertungen={tag: 40, tag - timedelta(1): 2},
    )

    stand = await _service(
        quellen, punkte_bewertung=1, punkte_deckel_bewertungen_je_tag=3
    ).punkte(KIM)

    assert stand.tun == 3 + 3 + 2
    assert stand.wirkung == 0


async def test_punkte_bewerten_ohne_stimmen_zu_eigenen_beitraegen():
    eigener = _beitrag(1)
    quellen = _Quellen([eigener])

    await _service(quellen).punkte(KIM)

    assert quellen.bewertungen_ohne == [eigener.id]


async def test_punkte_bewerten_ausgeschaltet_mit_null():
    quellen = _Quellen([], bewertungen={JETZT.date(): 5})

    stand = await _service(quellen, punkte_bewertung=0).punkte(KIM)

    assert stand.gesamt == 0


async def test_punkte_startkonto_sammelt_keine():
    beitrag = _beitrag(10)
    quellen = _Quellen([beitrag], nutzung={beitrag.id: 5}, zustimmungen=5)

    stand = await _service(quellen).punkte(START)

    assert stand.gesamt == 0
    assert stand.sammelt is False


async def test_punkte_ohne_art9_einwilligung_keine():
    """Nie erteilt oder widerrufen (#559, F559-1): keine Punkte, auch keine Wirkung."""
    beitrag = _beitrag(10)
    quellen = _Quellen([beitrag], nutzung={beitrag.id: 5}, zustimmungen=5)

    stand = await _service(quellen, eingewilligt=lambda user_id: False).punkte(KIM)

    assert stand.gesamt == 0
    assert stand.sammelt is False


async def test_punkte_mit_einwilligung_sammelt_auch_bei_null():
    """Neu und noch ohne Wirkung: 0 Punkte, aber ein Punktestand (#352)."""
    stand = await _service(_Quellen([])).punkte(KIM)

    assert stand.gesamt == 0
    assert stand.sammelt is True


async def test_punkte_widerruf_wirkt_beim_naechsten_abruf():
    """Die Einwilligung wird je Abruf gefragt, nicht gemerkt."""
    beitrag = _beitrag(10)
    quellen = _Quellen([beitrag], nutzung={beitrag.id: 1})
    stand_der_einwilligung = {KIM: True}
    service = _service(
        quellen, eingewilligt=lambda user_id: stand_der_einwilligung[user_id]
    )

    vorher = await service.punkte(KIM)
    stand_der_einwilligung[KIM] = False
    nachher = await service.punkte(KIM)

    assert vorher.gesamt > 0
    assert nachher.gesamt == 0


async def test_punkte_ohne_beitraege_keine_wirkung():
    """Gesperrte und entfernte Beitraege liefert die Quelle nicht: keine Punkte."""
    stand = await _service(_Quellen([])).punkte(KIM)

    assert stand.gesamt == 0


async def test_get_punkte_service_liest_nur_sichtbare_beitraege_der_person():
    """
    Gesperrte und geloeschte Beitraege verlieren ihre Punkte, weil die Verdrahtung
    get_by_author nutzt; dass get_by_author sie auslaesst, prueft
    tests/unit/repositories/test_base_repository.py.
    """
    from dependencies import get_punkte_service
    from domain.content_registry import BEITRAGSTYPEN_WERTE

    with patch(
        "repositories.aggregated.content_repository.ContentRepository"
    ) as inhalte, patch(
        "repositories.usage_tracking_repository.get_usage_repository"
    ) as nutzung, patch(
        "repositories.punkte_repository.get_punkte_repository"
    ) as stimmen:
        inhalte.return_value.get_by_author = AsyncMock(return_value=[])
        nutzung.return_value.get_nutzung_entdoppelt_batch.return_value = {}
        stimmen.return_value.zustimmungen.return_value = 0
        stimmen.return_value.einwuerfe_ausformuliert_je_tag.return_value = {}
        stimmen.return_value.bewertungen_je_tag.return_value = {}

        stand = await get_punkte_service(Settings()).punkte(KIM)

    inhalte.return_value.get_by_author.assert_awaited_once_with(
        KIM, limit=10000, offset=0, content_types=BEITRAGSTYPEN_WERTE
    )
    assert stand.gesamt == 0


async def test_get_punkte_service_fragt_die_einwilligung_punkte(
    punkte_einwilligung_ohne_datenbank, art9_einwilligung_ohne_datenbank
):
    """
    Die Verdrahtung prueft die Einwilligung "Punkte und Meilensteine" (#351), nicht
    mehr die Art.-9-Einwilligung zur Mitwirkung.
    """
    from dependencies import get_punkte_service

    punkte_einwilligung_ohne_datenbank.eingewilligt.return_value = False
    with patch(
        "repositories.aggregated.content_repository.ContentRepository"
    ) as inhalte, patch(
        "repositories.usage_tracking_repository.get_usage_repository"
    ), patch(
        "repositories.punkte_repository.get_punkte_repository"
    ):
        inhalte.return_value.get_by_author = AsyncMock(return_value=[_beitrag(10)])

        stand = await get_punkte_service(Settings()).punkte(KIM)

    punkte_einwilligung_ohne_datenbank.eingewilligt.assert_called_once_with(KIM)
    art9_einwilligung_ohne_datenbank.lesen.assert_not_called()
    inhalte.return_value.get_by_author.assert_not_awaited()
    assert stand.gesamt == 0


class _QuellenImZeitraum(_Quellen):
    """Dazu die Abfragen fuer einen Zeitraum (Punkte je Saison, #793)."""

    def __init__(self, *args, nutzung_im_zeitraum=0, zustimmungen_im_zeitraum=0, **kw):
        super().__init__(*args, **kw)
        self.nutzung_im_zeitraum = nutzung_im_zeitraum
        self.zustimmungen_im_zeitraum = zustimmungen_im_zeitraum
        self.zeitraeume = []

    def nutzung_entdoppelt_im_zeitraum(self, ids, von, bis) -> int:
        self.zeitraeume.append(("nutzung", von, bis))
        return self.nutzung_im_zeitraum

    def zustimmungen(self, content_ids, ausgenommen, zeitraum=None) -> int:
        if zeitraum is None:
            return super().zustimmungen(content_ids, ausgenommen)
        self.zeitraeume.append(("zustimmung", *zeitraum))
        self.ausgenommen = ausgenommen
        return self.zustimmungen_im_zeitraum


async def test_punkte_im_zeitraum_zaehlen_nur_tage_der_saison():
    """Saisonpunkte (#793): Tun, Bewerten, Nutzung und Zustimmung nur aus der Saison."""
    heute = JETZT.date()
    von, bis = heute - timedelta(days=10), heute
    vor_der_saison = heute - timedelta(days=20)
    quellen = _QuellenImZeitraum(
        [_beitrag(5), _beitrag(20)],
        nutzung={},
        einwuerfe={heute - timedelta(days=4): 1, vor_der_saison: 1},
        bewertungen={heute: 1, vor_der_saison: 3},
        nutzung_im_zeitraum=2,
        zustimmungen_im_zeitraum=1,
    )

    stand = await _service(
        quellen, punkte_bewertung=1, punkte_deckel_bewertungen_je_tag=3
    ).punkte(KIM, (von, bis))

    assert stand.wirkung == 2 * 10 + 1 * 5
    # Ein Beitrag und ein Einwurf in der Saison, eine Bewertung heute
    assert stand.tun == 1 + 1 + 1
    assert ("nutzung", von, bis) in quellen.zeitraeume
    assert ("zustimmung", von, bis) in quellen.zeitraeume
    assert quellen.ausgenommen == {KIM, START}


async def test_quest_punkte_zaehlen_fuer_die_saison_ihrer_quest_woche():
    """
    Saisonpunkte (#793) mit Team-Quests (#792): Es zaehlt die Woche der Quest, nicht
    der Montag der Gutschrift danach (Entscheidung 25.11.). Eine Quest aus der letzten
    Saisonwoche zaehlt also fuer diese Saison, eine aus der Woche davor nicht.
    """
    von, bis = date(2026, 10, 5), date(2026, 10, 25)  # Mo bis So, drei Wochen
    quellen = _QuellenImZeitraum([], nutzung={})
    quest_tage = lambda user_id, erstellt, grenze: {  # noqa: E731
        date(2026, 10, 5): 1,  # Woche ab 28.09., vor der Saison
        date(2026, 10, 19): 1,  # Woche ab 12.10., mitten in der Saison
        date(2026, 10, 26): 2,  # Woche ab 19.10., letzte Saisonwoche, zwei Teams
    }
    settings = Settings(
        startkonten=START, punkte_quest=4, punkte_deckel_quests_je_tag=8
    )
    dienst = PunkteService(
        quellen.sichtbare_beitraege,
        quellen,
        quellen,
        settings,
        jetzt=lambda: JETZT,
        eingewilligt=lambda user_id: True,
        quest_tage=quest_tage,
    )

    # Nach dem Tag der Gutschrift waeren es 1 + 1 (5.10. und 19.10.)
    assert (await dienst.punkte(KIM, (von, bis))).quests == 3 * 4
    assert (await dienst.punkte(KIM)).quests == 4 * 4


async def test_punkte_ohne_zeitraum_fragen_die_gesamtzahlen():
    beitrag = _beitrag(10)
    quellen = _QuellenImZeitraum([beitrag], nutzung={beitrag.id: 1}, zustimmungen=1)

    stand = await _service(quellen).punkte(KIM)

    assert stand.wirkung == 15
    assert quellen.zeitraeume == []
