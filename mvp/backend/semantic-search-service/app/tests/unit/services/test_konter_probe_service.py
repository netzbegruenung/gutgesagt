"""
Konter-Probe (#786, services/konter_probe_service.py): Auswahl der Aussagen, Mischen
der Antworten und der Fall ohne passende Aussage.
"""

import asyncio
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


def _service(aussagen, kommentare, nutzung, andere_typen=(), entdoppelt=None):
    """
    kommentare: id -> (stil, zweck); nutzung: id -> angezeigte Zahl; entdoppelt:
    id -> Zahl fuer die Auswahl, ohne Angabe dieselbe wie nutzung.
    """
    entdoppelt = nutzung if entdoppelt is None else entdoppelt
    quelle = MagicMock()

    async def kuratierte(ids=None):
        if ids is None:
            return list(aussagen)
        gesucht = set(ids)
        return [a for a in aussagen if a.id in gesucht]

    quelle.kuratierte = AsyncMock(side_effect=kuratierte)
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
    zaehler_entdoppelt = MagicMock(
        side_effect=lambda ids: {str(i): entdoppelt.get(i, 0) for i in ids}
    )
    return (
        KonterProbeService(quelle, zaehler, beitrag_laden, zaehler_entdoppelt),
        quelle,
        beitrag_laden,
    )


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

    async def test_vorrat_zwischengespeichert_inhalte_je_abruf_frisch(self):
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

        # Alle kuratierten Aussagen nur einmal; je Abruf nur die gezogenen.
        ohne_ids = [
            aufruf
            for aufruf in quelle.kuratierte.await_args_list
            if aufruf.kwargs.get("ids") is None
        ]
        assert len(ohne_ids) == 1
        assert quelle.kuratierte.await_count == 3
        assert 999 not in {x["usage_count"] for x in zweite[0].antworten}

    async def test_nach_aufbau_gesperrt_nicht_mehr_ausgeliefert(self):
        a, b, c = (uuid.uuid4() for _ in range(3))
        service, quelle, beitrag_laden = _service(
            [_aussage("Spruch", [a, b, c])],
            {
                a: ("sachlich", "kommentarspalte"),
                b: ("humorvoll", "kommentarspalte"),
                c: ("persoenlich", "kommentarspalte"),
            },
            {a: 2, b: 7, c: 1},
        )
        assert len(await service.proben()) == 1
        laden = beitrag_laden.side_effect

        async def b_gesperrt(beitrag_id):
            return None if beitrag_id == b else await laden(beitrag_id)

        beitrag_laden.side_effect = b_gesperrt

        assert await service.proben() == []
        # Ohne Neuaufbau des Vorrats: Die Pruefung geschieht bei jedem Abruf.
        assert (
            sum(
                1
                for aufruf in quelle.kuratierte.await_args_list
                if aufruf.kwargs.get("ids") is None
            )
            == 1
        )

    async def test_nach_aufbau_unsichtbare_aussage_nicht_mehr_ausgeliefert(self):
        a, b, c = (uuid.uuid4() for _ in range(3))
        aussagen = [_aussage("Spruch", [a, b, c])]
        service, _, _ = _service(
            aussagen,
            {
                a: ("sachlich", "kommentarspalte"),
                b: ("humorvoll", "kommentarspalte"),
                c: ("persoenlich", "kommentarspalte"),
            },
            {a: 2, b: 7, c: 1},
        )
        assert len(await service.proben()) == 1

        aussagen.clear()
        assert await service.proben() == []

    async def test_weggefallene_probe_wird_ersetzt(self):
        aussagen, kommentare, nutzung = [], {}, {}
        for i in range(3):
            ids = [uuid.uuid4() for _ in range(3)]
            aussagen.append(_aussage(f"Spruch {i}", ids))
            for stil, beitrag_id, zahl in zip(
                ("sachlich", "humorvoll", "persoenlich"), ids, (5, 2, 1)
            ):
                kommentare[beitrag_id] = (stil, "kommentarspalte")
                nutzung[beitrag_id] = zahl
        service, _, beitrag_laden = _service(aussagen, kommentare, nutzung)
        await service.proben()
        gesperrt = aussagen[0].replysuggestions[0].id
        laden = beitrag_laden.side_effect

        async def ohne(beitrag_id):
            return None if beitrag_id == gesperrt else await laden(beitrag_id)

        beitrag_laden.side_effect = ohne

        for saat in range(10):
            proben = await service.proben(hoechstens=2, zufall=random.Random(saat))
            assert len(proben) == 2
            assert aussagen[0].id not in {p.statement_id for p in proben}

    async def test_eine_person_macht_keine_probe(self):
        """Roh oft kopiert, entdoppelt nur einmal je Antwort: keine Probe."""
        a, b, c = (uuid.uuid4() for _ in range(3))
        service, _, _ = _service(
            [_aussage("Spruch", [a, b, c])],
            {
                a: ("sachlich", "kommentarspalte"),
                b: ("humorvoll", "kommentarspalte"),
                c: ("persoenlich", "kommentarspalte"),
            },
            {a: 1, b: 6, c: 1},
            entdoppelt={a: 1, b: 1, c: 1},
        )
        assert await service.proben() == []

    async def test_spitzenreiter_nach_entdoppelter_nutzung(self):
        """
        Roh liegt eine andere Antwort vorn als entdoppelt: Der Browser laese den
        falschen Spitzenreiter ab, die Probe entfaellt.
        """
        a, b, c = (uuid.uuid4() for _ in range(3))
        service, _, _ = _service(
            [_aussage("Spruch", [a, b, c])],
            {
                a: ("sachlich", "kommentarspalte"),
                b: ("humorvoll", "kommentarspalte"),
                c: ("persoenlich", "kommentarspalte"),
            },
            {a: 9, b: 4, c: 1},
            entdoppelt={a: 2, b: 4, c: 1},
        )
        assert await service.proben() == []

    async def test_angezeigt_wird_die_zahl_der_karte(self):
        a, b, c = (uuid.uuid4() for _ in range(3))
        service, _, _ = _service(
            [_aussage("Spruch", [a, b, c])],
            {
                a: ("sachlich", "kommentarspalte"),
                b: ("humorvoll", "kommentarspalte"),
                c: ("persoenlich", "kommentarspalte"),
            },
            {a: 3, b: 12, c: 2},
            entdoppelt={a: 2, b: 5, c: 1},
        )
        [probe] = await service.proben()
        assert {x["style"]: x["usage_count"] for x in probe.antworten} == {
            "sachlich": 3,
            "humorvoll": 12,
            "persoenlich": 2,
        }

    async def test_gleichzeitige_abrufe_bauen_den_vorrat_einmal(self):
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
        langsam = quelle.sichtbare_antworten.return_value

        async def verzoegert(ids):
            await asyncio.sleep(0.01)
            return langsam

        quelle.sichtbare_antworten = AsyncMock(side_effect=verzoegert)

        ergebnisse = await asyncio.gather(*(service.proben() for _ in range(5)))

        assert all(len(e) == 1 for e in ergebnisse)
        quelle.sichtbare_antworten.assert_awaited_once()

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
