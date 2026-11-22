"""
Die meistgenutzten Aussagen eines Themas (#754, services/themen_aussagen_service.py):
nur kuratierte mit sichtbarer Antwort, nach Nutzung der Antworten geordnet.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.models.statement import AntwortKurz
from services import themen_aussagen_service
from services.themen_aussagen_service import (
    IM_KASTEN,
    ThemenAussagenService,
    zwischenspeicher_leeren,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def leerer_zwischenspeicher():
    zwischenspeicher_leeren()
    yield
    zwischenspeicher_leeren()


def _aussage(text, antworten):
    return SimpleNamespace(
        id=uuid.uuid4(),
        text=text,
        replysuggestions=[SimpleNamespace(id=a) for a in antworten],
    )


def _service(ids, aussagen, sichtbar, nutzung):
    themen = MagicMock()
    themen.aussagen_mit_thema.return_value = ids
    quelle = MagicMock()
    quelle.kuratierte = AsyncMock(return_value=aussagen)
    quelle.sichtbare_antworten = AsyncMock(
        return_value=[
            AntwortKurz(id=i, content_type="commentary", titel="t") for i in sichtbar
        ]
    )
    zaehler = MagicMock(
        side_effect=lambda ids: {str(i): nutzung.get(i, 0) for i in ids}
    )
    return ThemenAussagenService(themen, quelle, zaehler), themen, quelle, zaehler


async def test_nach_nutzung_der_sichtbaren_antworten():
    a1, a2, a3, versteckt = (uuid.uuid4() for _ in range(4))
    wenig = _aussage("Wenig genutzt", [a1])
    viel = _aussage(" Viel genutzt ", [a2, a3])
    gesperrt = _aussage("Nur gesperrte Antwort", [versteckt])
    service, themen, quelle, _ = _service(
        [wenig.id, viel.id, gesperrt.id],
        [wenig, viel, gesperrt],
        sichtbar=[a1, a2, a3],
        nutzung={a1: 3, a2: 2, a3: 2, versteckt: 100},
    )

    aussagen, anzahl = await service.meistgenutzte("energie-heizen")

    assert [(a.text, a.antworten) for a in aussagen] == [
        ("Viel genutzt", 2),
        ("Wenig genutzt", 1),
    ]
    assert anzahl == 2
    themen.aussagen_mit_thema.assert_called_once_with("energie-heizen")
    quelle.kuratierte.assert_awaited_once_with([wenig.id, viel.id, gesperrt.id])


async def test_gleichstand_mehr_antworten_dann_text():
    a, b, c = (uuid.uuid4() for _ in range(3))
    zwei = _aussage("Zwei", [a, b])
    beta = _aussage("beta", [c])
    alpha = _aussage("Alpha", [])
    service, *_ = _service(
        [zwei.id, beta.id, alpha.id],
        [beta, alpha, zwei],
        sichtbar=[a, b, c],
        nutzung={},
    )

    aussagen, anzahl = await service.meistgenutzte("klima")

    # Ohne Antwort ("Alpha") faellt sie weg; ein Klick fuehrte ins Leere.
    assert [x.text for x in aussagen] == ["Zwei", "beta"]
    assert anzahl == 2


async def test_hoechstens_und_gesamtzahl():
    antworten = [uuid.uuid4() for _ in range(7)]
    aussagen = [_aussage(f"A{i}", [antworten[i]]) for i in range(7)]
    service, *_ = _service(
        [a.id for a in aussagen],
        aussagen,
        sichtbar=antworten,
        nutzung={antworten[i]: i for i in range(7)},
    )

    gezeigt, anzahl = await service.meistgenutzte("klima")

    assert [a.text for a in gezeigt] == ["A6", "A5", "A4", "A3", "A2"]
    assert len(gezeigt) == IM_KASTEN
    assert anzahl == 7
    alle, _ = await service.meistgenutzte("klima", hoechstens=50)
    assert len(alle) == 7


async def test_unbekanntes_thema_oder_ohne_aussagen():
    service, themen, quelle, zaehler = _service([], [], sichtbar=[], nutzung={})

    assert await service.meistgenutzte("gibt-es-nicht") == ([], 0)
    themen.aussagen_mit_thema.assert_not_called()
    assert await service.meistgenutzte("klima") == ([], 0)
    quelle.kuratierte.assert_not_awaited()
    zaehler.assert_not_called()


async def test_rangliste_je_thema_zwischengespeichert(monkeypatch):
    a = uuid.uuid4()
    aussage = _aussage("Eine", [a])
    service, themen, quelle, _ = _service(
        [aussage.id], [aussage], sichtbar=[a], nutzung={}
    )

    await service.meistgenutzte("klima")
    await service.meistgenutzte("klima", hoechstens=50)
    assert themen.aussagen_mit_thema.call_count == 1
    assert quelle.kuratierte.await_count == 1

    # Abgelaufen: neu nachschlagen.
    jetzt = themen_aussagen_service._uhr()
    monkeypatch.setattr(
        themen_aussagen_service,
        "_uhr",
        lambda: jetzt + themen_aussagen_service.ZWISCHENSPEICHER_SEKUNDEN + 1,
    )
    await service.meistgenutzte("klima")
    assert themen.aussagen_mit_thema.call_count == 2
