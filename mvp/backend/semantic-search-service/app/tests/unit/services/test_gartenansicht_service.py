"""
Gartenansicht (#783): Antworten und Aussagen ohne Antwort je Thema, nur sichtbare
Antworten, jede Antwort je Thema einmal, Reihenfolge der festen Liste, Zwischenspeicher.
"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from domain.models.content_type import ContentType
from domain.themen import THEMEN
from services import gartenansicht_service
from services.gartenansicht_service import GartenansichtService

pytestmark = pytest.mark.unit

A1, A2, A3 = (uuid.uuid4() for _ in range(3))
K1, K2, K3, GESPERRT, HINTERGRUND = (uuid.uuid4() for _ in range(5))


@pytest.fixture(autouse=True)
def leer():
    gartenansicht_service.zwischenspeicher_leeren()
    yield
    gartenansicht_service.zwischenspeicher_leeren()


def _aussage(id_, antworten):
    return SimpleNamespace(
        id=id_, replysuggestions=[SimpleNamespace(id=a) for a in antworten]
    )


def _dienst():
    themen = Mock()
    themen.alle.return_value = {
        A1: ["klima", "verkehr"],
        A2: ["klima"],
        A3: ["energie-heizen"],
    }
    aussagen = Mock()
    aussagen.kuratierte = AsyncMock(
        return_value=[
            _aussage(A1, [K1, K2]),
            # K1 haengt auch an A2: im Beet Klima nur einmal
            _aussage(A2, [K1, GESPERRT]),
            # Eine Hintergrundinfo zaehlt nicht als Antwort
            _aussage(A3, [K3, HINTERGRUND]),
        ]
    )
    aussagen.sichtbare_antworten = AsyncMock(
        side_effect=lambda ids: [
            SimpleNamespace(
                id=i,
                content_type=(
                    ContentType.GENERIC_TEXT
                    if i == HINTERGRUND
                    else ContentType.COMMENTARY
                ),
            )
            for i in ids
            if i in {K1, K2, K3, HINTERGRUND}
        ]
    )
    ohne = Mock()
    ohne.liste = AsyncMock(
        return_value=[
            SimpleNamespace(themen=("klima",)),
            SimpleNamespace(themen=("klima", "verkehr")),
            SimpleNamespace(themen=()),
        ]
    )
    return GartenansichtService(themen, aussagen, ohne), aussagen, ohne


def test_zahlen_je_thema():
    dienst, _, ohne = _dienst()

    beete = {b.schluessel: b for b in asyncio.run(dienst.beete())}

    assert (beete["klima"].antworten, beete["klima"].ohne_antwort) == (2, 2)
    assert (beete["verkehr"].antworten, beete["verkehr"].ohne_antwort) == (2, 1)
    assert (
        beete["energie-heizen"].antworten,
        beete["energie-heizen"].ohne_antwort,
    ) == (
        1,
        0,
    )
    # Dieselbe Liste wie "Hier fehlt eine Antwort", ohne Begrenzung, mit Themen
    assert ohne.liste.await_args.kwargs["mit_themen"] is True


def test_jedes_thema_in_der_reihenfolge_der_liste():
    dienst, _, _ = _dienst()

    beete = asyncio.run(dienst.beete())

    assert [b.schluessel for b in beete] == [t.schluessel for t in THEMEN]
    leer = [
        b for b in beete if b.schluessel not in {"klima", "verkehr", "energie-heizen"}
    ]
    assert all(b.antworten == 0 and b.ohne_antwort == 0 for b in leer)


def test_zwischenspeicher_fragt_nicht_bei_jedem_aufruf():
    dienst, aussagen, _ = _dienst()

    asyncio.run(dienst.beete())
    asyncio.run(dienst.beete())

    assert aussagen.kuratierte.await_count == 1


def test_gleichzeitige_aufrufe_rechnen_einmal():
    dienst, aussagen, _ = _dienst()

    async def drei():
        return await asyncio.gather(dienst.beete(), dienst.beete(), dienst.beete())

    a, b, c = asyncio.run(drei())

    assert a == b == c
    assert aussagen.kuratierte.await_count == 1


def test_fehler_wird_nicht_zwischengespeichert():
    dienst, aussagen, _ = _dienst()
    gut = aussagen.kuratierte.return_value
    aussagen.kuratierte.side_effect = [RuntimeError("weg"), gut]

    with pytest.raises(RuntimeError):
        asyncio.run(dienst.beete())
    assert len(asyncio.run(dienst.beete())) == len(THEMEN)


def test_ohne_zuordnungen_keine_abfrage_im_suchindex():
    dienst, aussagen, _ = _dienst()
    dienst._themen.alle.return_value = {}

    beete = asyncio.run(dienst.beete())

    aussagen.kuratierte.assert_not_awaited()
    assert sum(b.antworten for b in beete) == 0
