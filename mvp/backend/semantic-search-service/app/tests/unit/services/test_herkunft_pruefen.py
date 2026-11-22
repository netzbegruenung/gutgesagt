"""
Herkunft pruefen (#759): Lauf, Takt und Schalter, ohne Netz und Datenbank. Der Abruf
ist ersetzt; ihn selbst pruefen tests/unit/utils/test_sicherer_abruf.py.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from services import herkunft_pruefen as modul
from services.herkunft_pruefen import (
    HerkunftLink,
    HerkunftPruefenService,
    ist_link,
    pruefen_im_takt,
)
from utils.sicherer_abruf import OK, TOT, Abrufergebnis

pytestmark = pytest.mark.unit

A = uuid.UUID("11111111-1111-4111-8111-111111111111")
B = uuid.UUID("22222222-2222-4222-8222-222222222222")
C = uuid.UUID("33333333-3333-4333-8333-333333333333")
JETZT = datetime(2026, 11, 22, 3, 0, tzinfo=timezone.utc)


def _dienst(herkuenfte, ergebnisse=None, an=True, repository=None):
    schalter = {"an": an}
    abgerufen = []
    geladen = []

    async def laden():
        geladen.append(True)
        return herkuenfte

    async def pruefen(adresse):
        abgerufen.append(adresse)
        if callable(ergebnisse):
            return ergebnisse(adresse)
        return (ergebnisse or {}).get(adresse, Abrufergebnis(OK, 200))

    repository = repository or Mock()
    repository.uebrige_loeschen.return_value = 0
    dienst = HerkunftPruefenService(
        repository,
        laden,
        lambda: schalter["an"],
        pruefen=pruefen,
        abstand_sekunden=0,
        uhr=lambda: JETZT,
    )
    return dienst, repository, abgerufen, geladen, schalter


class TestLauf:
    def test_schalter_aus_nichts_geladen_abgerufen_gespeichert(self):
        dienst, repo, abgerufen, geladen, _ = _dienst(
            [HerkunftLink(A, "https://a.example/")], an=False
        )

        assert asyncio.run(dienst.lauf()) == 0
        assert geladen == [] and abgerufen == []
        assert repo.method_calls == []

    def test_schalter_an_speichert_je_herkunft(self):
        dienst, repo, abgerufen, _, _ = _dienst(
            [
                HerkunftLink(A, "https://a.example/"),
                HerkunftLink(B, "https://b.example/weg"),
            ],
            {"https://b.example/weg": Abrufergebnis(TOT, 404)},
        )

        assert asyncio.run(dienst.lauf()) == 2
        assert abgerufen == ["https://a.example/", "https://b.example/weg"]
        aufrufe = [c.args for c in repo.speichern.call_args_list]
        assert aufrufe == [
            (A, "https://a.example/", OK, 200, None, JETZT, False),
            (B, "https://b.example/weg", TOT, 404, None, JETZT, True),
        ]
        repo.uebrige_loeschen.assert_called_once_with([A, B])

    def test_gleiche_adresse_nur_einmal_abgerufen(self):
        dienst, repo, abgerufen, _, _ = _dienst(
            [
                HerkunftLink(A, "https://a.example/"),
                HerkunftLink(B, " https://a.example/ "),
            ]
        )

        asyncio.run(dienst.lauf())

        assert abgerufen == ["https://a.example/"]
        assert repo.speichern.call_count == 2

    def test_ohne_link_kein_abruf(self):
        dienst, repo, abgerufen, _, _ = _dienst(
            [HerkunftLink(A, "Rede im Landtag, 3.5.2026"), HerkunftLink(B, "ftp://x")]
        )

        asyncio.run(dienst.lauf())

        assert abgerufen == []
        repo.uebrige_loeschen.assert_called_once_with([])

    def test_ausschalten_im_lauf_beendet_ihn(self):
        herkuenfte = [
            HerkunftLink(A, "https://a.example/"),
            HerkunftLink(B, "https://b.example/"),
            HerkunftLink(C, "https://c.example/"),
        ]
        stand = {}

        def ergebnis(adresse):
            stand["schalter"]["an"] = False
            return Abrufergebnis(OK, 200)

        dienst, repo, abgerufen, _, schalter = _dienst(herkuenfte, ergebnis)
        stand["schalter"] = schalter

        asyncio.run(dienst.lauf())

        assert abgerufen == ["https://a.example/"]
        repo.uebrige_loeschen.assert_not_called()

    def test_anstossen_nur_einmal_gleichzeitig(self):
        async def lauf():
            sperre = asyncio.Event()

            async def pruefen(adresse):
                await sperre.wait()
                return Abrufergebnis(OK, 200)

            dienst, _, _, _, _ = _dienst([HerkunftLink(A, "https://a.example/")])
            dienst._pruefen = pruefen
            assert dienst.anstossen() is True
            await asyncio.sleep(0)
            assert dienst.laeuft
            assert dienst.anstossen() is False
            sperre.set()
            await dienst._lauf
            assert not dienst.laeuft

        asyncio.run(lauf())


class TestTakt:
    @pytest.mark.parametrize(
        "stunde, letzter, faellig",
        [
            (3, None, True),
            (1, None, False),
            (3, datetime(2026, 11, 21, 3, 0, tzinfo=timezone.utc), True),
            (3, datetime(2026, 11, 22, 2, 10, tzinfo=timezone.utc), False),
        ],
    )
    def test_faellig_einmal_je_tag_ab_der_nacht(self, stunde, letzter, faellig):
        dienst, repo, _, _, _ = _dienst([])
        dienst._uhr = lambda: JETZT.replace(hour=stunde)
        repo.letzter_lauf.return_value = letzter

        assert asyncio.run(dienst.faellig()) is faellig

    def test_takt_bei_schalter_aus_liest_nichts(self, monkeypatch):
        dienst, repo, _, geladen, _ = _dienst(
            [HerkunftLink(A, "https://a.example/")], an=False
        )

        async def einmal():
            aufgabe = asyncio.create_task(pruefen_im_takt(dienst, takt_sekunden=0.01))
            await asyncio.sleep(0.05)
            aufgabe.cancel()

        asyncio.run(einmal())

        assert repo.method_calls == [] and geladen == []

    def test_takt_bei_schalter_an_stoesst_an(self):
        dienst, repo, abgerufen, _, _ = _dienst([HerkunftLink(A, "https://a.example/")])
        repo.letzter_lauf.return_value = None

        async def einmal():
            aufgabe = asyncio.create_task(pruefen_im_takt(dienst, takt_sekunden=10))
            await asyncio.sleep(0.05)
            aufgabe.cancel()

        asyncio.run(einmal())

        assert abgerufen == ["https://a.example/"]


@pytest.mark.parametrize(
    "adresse, link",
    [
        ("https://a.example/", True),
        ("HTTP://a.example", True),
        ("  https://a.example ", True),
        ("Rede im Landtag", False),
        ("", False),
        (None, False),
        ("javascript:alert(1)", False),
    ],
)
def test_ist_link(adresse, link):
    assert ist_link(adresse) is link


def test_herkuenfte_aus_index_nur_links():
    async def get_all(limit, offset):
        return [
            Mock(id=A, reference_string="https://a.example/"),
            Mock(id=B, reference_string="Rede"),
        ]

    laden = modul.herkuenfte_aus_index(Mock(get_all=get_all))

    assert asyncio.run(laden()) == [HerkunftLink(A, "https://a.example/")]
