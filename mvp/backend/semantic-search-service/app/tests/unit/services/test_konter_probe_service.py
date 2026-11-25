"""
Konter-Probe (#786, services/konter_probe_service.py): Auswahl der Aussagen, Mischen
der Antworten und der Fall ohne passende Aussage.
"""

import random
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.models.statement import AntwortKurz
from services.konter_probe_service import (
    MINDEST_NUTZUNG,
    KonterProbeService,
    probe_aus_kommentaren,
    zwischenspeicher_leeren,
)

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def leerer_zwischenspeicher():
    zwischenspeicher_leeren()
    yield
    zwischenspeicher_leeren()


def _kommentar(stil, nutzung, zweck="kommentarspalte", beitrag_id=None):
    return {
        "id": str(beitrag_id or uuid.uuid4()),
        "style": stil,
        "zweck": zweck,
        "usage_count": nutzung,
        "result_type": "commentary",
    }


class TestProbeAusKommentaren:
    def test_drei_stile_meistgenutzte_zuerst(self):
        aussage = uuid.uuid4()
        probe = probe_aus_kommentaren(
            aussage,
            " Spruch ",
            [
                _kommentar("sachlich", 2),
                _kommentar("humorvoll", 9),
                _kommentar("persoenlich", 1),
                _kommentar("sachlich", 4),  # zaehlt statt der sachlichen mit 2
            ],
        )

        assert probe is not None
        assert probe.statement_id == aussage
        assert probe.text == "Spruch"
        assert [(a["style"], a["usage_count"]) for a in probe.antworten] == [
            ("humorvoll", 9),
            ("sachlich", 4),
            ("persoenlich", 1),
        ]

    def test_von_vier_stilen_die_drei_meistgenutzten(self):
        probe = probe_aus_kommentaren(
            uuid.uuid4(),
            "Spruch",
            [
                _kommentar("sachlich", 5),
                _kommentar("humorvoll", 1),
                _kommentar("persoenlich", 3),
                _kommentar("brueckenbauend", 2),
            ],
        )
        assert [a["style"] for a in probe.antworten] == [
            "sachlich",
            "persoenlich",
            "brueckenbauend",
        ]

    def test_weniger_als_drei_stile_keine_probe(self):
        assert (
            probe_aus_kommentaren(
                uuid.uuid4(),
                "Spruch",
                [
                    _kommentar("sachlich", 9),
                    _kommentar("sachlich", 5),
                    _kommentar("humorvoll", 3),
                    _kommentar(None, 8),
                ],
            )
            is None
        )

    def test_fuer_gleichgesinnte_zaehlt_nicht(self):
        assert (
            probe_aus_kommentaren(
                uuid.uuid4(),
                "Spruch",
                [
                    _kommentar("sachlich", 9),
                    _kommentar("humorvoll", 5),
                    _kommentar("bissig", 30, zweck="eigene_leute"),
                ],
            )
            is None
        )

    def test_zu_wenig_nutzung_keine_probe(self):
        assert (
            probe_aus_kommentaren(
                uuid.uuid4(),
                "Spruch",
                [
                    _kommentar("sachlich", MINDEST_NUTZUNG - 3),
                    _kommentar("humorvoll", 1),
                    _kommentar("persoenlich", 1),
                ],
            )
            is None
        )

    def test_gleichstand_an_der_spitze_keine_probe(self):
        assert (
            probe_aus_kommentaren(
                uuid.uuid4(),
                "Spruch",
                [
                    _kommentar("sachlich", 4),
                    _kommentar("humorvoll", 4),
                    _kommentar("persoenlich", 1),
                ],
            )
            is None
        )


def _aussage(text, antworten):
    return SimpleNamespace(
        id=uuid.uuid4(),
        text=text,
        replysuggestions=[SimpleNamespace(id=a) for a in antworten],
    )


def _service(aussagen, kommentare, nutzung, andere_typen=()):
    """kommentare: id -> (stil, zweck); nutzung: id -> Zahl."""
    quelle = MagicMock()
    quelle.kuratierte = AsyncMock(return_value=aussagen)
    quelle.sichtbare_antworten = AsyncMock(
        return_value=[
            AntwortKurz(id=i, content_type="commentary", titel="t") for i in kommentare
        ]
        + [
            AntwortKurz(id=i, content_type="generic_text", titel="t")
            for i in andere_typen
        ]
    )
    zaehler = MagicMock(
        side_effect=lambda ids: {str(i): nutzung.get(i, 0) for i in ids}
    )

    async def laden(beitrag_id):
        stil, zweck = kommentare[beitrag_id]
        return {
            "id": str(beitrag_id),
            "style": stil,
            "zweck": zweck,
            "result_type": "commentary",
        }

    beitrag_laden = AsyncMock(side_effect=laden)
    return KonterProbeService(quelle, zaehler, beitrag_laden), quelle, beitrag_laden


@pytest.mark.asyncio
class TestKonterProbeService:
    async def test_passende_aussage_mit_nutzung_gemischt(self):
        a, b, c = (uuid.uuid4() for _ in range(3))
        aussage = _aussage("Spruch", [a, b, c])
        service, _, _ = _service(
            [aussage],
            {
                a: ("sachlich", "kommentarspalte"),
                b: ("humorvoll", "kommentarspalte"),
                c: ("persoenlich", "kommentarspalte"),
            },
            {a: 2, b: 7, c: 1},
        )

        reihenfolgen = set()
        for saat in range(20):
            proben = await service.proben(zufall=random.Random(saat))
            assert len(proben) == 1
            assert proben[0].statement_id == aussage.id
            nutzung = {x["style"]: x["usage_count"] for x in proben[0].antworten}
            assert nutzung == {"sachlich": 2, "humorvoll": 7, "persoenlich": 1}
            reihenfolgen.add(tuple(x["style"] for x in proben[0].antworten))
        # Die Reihenfolge verraet den Spitzenreiter nicht.
        assert len(reihenfolgen) > 1

    async def test_ohne_passende_aussage_leer(self):
        a, b, c, d = (uuid.uuid4() for _ in range(4))
        zwei_stile = _aussage("Zwei Stile", [a, b])
        wenig = _aussage("Wenig genutzt", [c, d])
        service, _, beitrag_laden = _service(
            [zwei_stile, wenig],
            {
                a: ("sachlich", "kommentarspalte"),
                b: ("humorvoll", "kommentarspalte"),
                c: ("sachlich", "kommentarspalte"),
                d: ("persoenlich", "kommentarspalte"),
            },
            {a: 10, b: 10},
        )

        assert await service.proben() == []
        # Unter drei Kommentaren wird gar nichts geladen.
        beitrag_laden.assert_not_awaited()

    async def test_nur_kommentare_zaehlen(self):
        a, b, text = (uuid.uuid4() for _ in range(3))
        aussage = _aussage("Spruch", [a, b, text])
        service, _, beitrag_laden = _service(
            [aussage],
            {a: ("sachlich", "kommentarspalte"), b: ("humorvoll", "kommentarspalte")},
            {a: 5, b: 3, text: 9},
            andere_typen=[text],
        )

        assert await service.proben() == []
        beitrag_laden.assert_not_awaited()

    async def test_unsichtbarer_beitrag_faellt_weg(self):
        a, b, c = (uuid.uuid4() for _ in range(3))
        aussage = _aussage("Spruch", [a, b, c])
        service, _, beitrag_laden = _service(
            [aussage],
            {
                a: ("sachlich", "kommentarspalte"),
                b: ("humorvoll", "kommentarspalte"),
                c: ("persoenlich", "kommentarspalte"),
            },
            {a: 2, b: 7, c: 1},
        )
        laden = beitrag_laden.side_effect

        async def ohne_c(beitrag_id):
            return None if beitrag_id == c else await laden(beitrag_id)

        beitrag_laden.side_effect = ohne_c
        assert await service.proben() == []

    async def test_vorrat_zwischengespeichert_kopien_herausgegeben(self):
        a, b, c = (uuid.uuid4() for _ in range(3))
        service, quelle, _ = _service(
            [_aussage("Spruch", [a, b, c])],
            {
                a: ("sachlich", "kommentarspalte"),
                b: ("humorvoll", "kommentarspalte"),
                c: ("persoenlich", "kommentarspalte"),
            },
            {a: 2, b: 7, c: 1},
        )

        erste = await service.proben()
        erste[0].antworten[0]["usage_count"] = 999
        zweite = await service.proben()

        assert quelle.kuratierte.await_count == 1
        assert 999 not in {x["usage_count"] for x in zweite[0].antworten}

    async def test_hoechstens(self):
        aussagen, kommentare, nutzung = [], {}, {}
        for i in range(5):
            ids = [uuid.uuid4() for _ in range(3)]
            aussagen.append(_aussage(f"Spruch {i}", ids))
            for stil, beitrag_id, zahl in zip(
                ("sachlich", "humorvoll", "persoenlich"), ids, (5, 2, 1)
            ):
                kommentare[beitrag_id] = (stil, "kommentarspalte")
                nutzung[beitrag_id] = zahl
        service, _, _ = _service(aussagen, kommentare, nutzung)

        proben = await service.proben(hoechstens=3, zufall=random.Random(1))
        assert len(proben) == 3
        assert len({p.statement_id for p in proben}) == 3
