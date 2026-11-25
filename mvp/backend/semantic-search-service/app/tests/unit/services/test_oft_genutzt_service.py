"""
"Diese Woche oft genutzt" (#364): welche Beitraege die Startseite zeigt und wann
der Bereich ganz entfaellt.
"""

import logging
import uuid
from types import SimpleNamespace
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, ValidationError

from domain.models.content_type import ContentType
from core.config import Settings
from services.oft_genutzt_service import (
    ANZAHL,
    OftGenutztService,
    sichtbaren_beitrag_laden,
)

pytestmark = pytest.mark.asyncio


class _Nutzung:
    """Steht fuer die Nutzungsabfrage: liefert, was ihr gegeben wird, und merkt sich den Aufruf."""

    def __init__(self, kandidaten: List[Dict]):
        self.kandidaten = kandidaten
        self.aufrufe: List[Dict] = []

    def get_trending_content(
        self, limit: int = 10, hours: int = 24, nur_entdoppelt: bool = False
    ):
        self.aufrufe.append(
            {"limit": limit, "hours": hours, "nur_entdoppelt": nur_entdoppelt}
        )
        return self.kandidaten[:limit]


def _kandidaten(*nutzungen: int) -> List[Dict]:
    return [
        {"content_id": str(uuid.uuid4()), "recent_uses": n, "total_uses": n + 10}
        for n in nutzungen
    ]


def _service(
    kandidaten: List[Dict],
    unsichtbar: frozenset = frozenset(),
    mindest_nutzungen: int = 2,
    mindest_beitraege: int = 3,
):
    async def beitrag_laden(beitrag_id: uuid.UUID) -> Optional[Dict]:
        if str(beitrag_id) in unsichtbar:
            return None
        return {"id": str(beitrag_id), "title": f"Titel {beitrag_id}"}

    nutzung = _Nutzung(kandidaten)
    return (
        OftGenutztService(
            nutzung,
            beitrag_laden,
            mindest_nutzungen=mindest_nutzungen,
            mindest_beitraege=mindest_beitraege,
        ),
        nutzung,
    )


async def test_beitraege_zu_wenig_nutzung_leer():
    # Nur zwei Beitraege erreichen die Mindestnutzung - zu wenig fuer einen Bereich.
    service, _ = _service(_kandidaten(5, 3, 1, 1))

    assert await service.beitraege() == []


async def test_beitraege_mindestzahl_aus_dem_aufruf():
    """Mit Mindestzahl 2 reichen die zwei Beitraege, die bei 3 nicht reichten."""
    kandidaten = _kandidaten(5, 3, 1, 1)
    service, _ = _service(kandidaten, mindest_beitraege=2)

    beitraege = await service.beitraege()

    assert [b["id"] for b in beitraege] == [k["content_id"] for k in kandidaten[:2]]


async def test_beitraege_mindestnutzung_aus_dem_aufruf():
    """Mit Mindestnutzung 3 faellt der Beitrag mit zwei Nutzungen heraus."""
    service, _ = _service(
        _kandidaten(5, 3, 2), mindest_beitraege=2, mindest_nutzungen=3
    )

    assert [b["recent_uses"] for b in await service.beitraege()] == [5, 3]


async def test_beitraege_ein_beitrag_reicht_bei_mindestzahl_zwei_nicht():
    service, _ = _service(_kandidaten(9, 1), mindest_beitraege=2)

    assert await service.beitraege() == []


async def test_beitraege_genug_nutzung_meistgenutzte_zuerst():
    kandidaten = _kandidaten(7, 4, 2, 1)
    service, _ = _service(kandidaten)

    beitraege = await service.beitraege()

    assert [b["id"] for b in beitraege] == [t["content_id"] for t in kandidaten[:3]]
    assert [b["recent_uses"] for b in beitraege] == [7, 4, 2]


async def test_beitraege_fragt_die_letzten_sieben_tage_ab():
    service, nutzung = _service(_kandidaten(3, 3, 3))

    await service.beitraege()

    assert nutzung.aufrufe[0]["hours"] == 7 * 24


async def test_beitraege_zaehlt_nur_entdoppelte_nutzung():
    """Nur Nutzung verschiedener Personen zaehlt (#352), nicht jede Kopie."""
    service, nutzung = _service(_kandidaten(3, 3, 3))

    await service.beitraege()

    assert nutzung.aufrufe[0]["nur_entdoppelt"] is True


async def test_beitraege_hoechstens_fuenf():
    service, _ = _service(_kandidaten(9, 8, 7, 6, 5, 4, 3))

    assert len(await service.beitraege()) == 5


async def test_beitraege_unsichtbare_fallen_weg_und_zaehlen_nicht():
    # Gesperrt oder geloescht: Der Beitrag fehlt, und ohne ihn bleiben zwei -
    # der Bereich entfaellt, statt mit einer Luecke dazustehen.
    kandidaten = _kandidaten(6, 5, 4)
    service, _ = _service(
        kandidaten, unsichtbar=frozenset({kandidaten[1]["content_id"]})
    )

    assert await service.beitraege() == []


async def test_beitraege_unsichtbare_machen_platz_fuer_naechste():
    kandidaten = _kandidaten(9, 8, 7, 6, 5, 4)
    service, _ = _service(
        kandidaten, unsichtbar=frozenset({kandidaten[0]["content_id"]})
    )

    beitraege = await service.beitraege()

    assert [b["recent_uses"] for b in beitraege] == [8, 7, 6, 5, 4]


async def test_beitraege_ohne_nutzung_leer():
    service, _ = _service([])

    assert await service.beitraege() == []


def _validierungsfehler() -> ValidationError:
    class _Pflicht(BaseModel):
        text: str

    try:
        _Pflicht()
    except ValidationError as fehler:
        return fehler
    raise AssertionError("ValidationError erwartet")


def _lader(typ_get, beitrag_get):
    """sichtbaren_beitrag_laden mit Repositories, die nur ``get`` kennen."""
    alle_typen = MagicMock()
    alle_typen.get = AsyncMock(side_effect=typ_get)
    des_typs = MagicMock()
    des_typs.get = AsyncMock(side_effect=beitrag_get)
    factory = MagicMock()
    factory.create_registry_repository.return_value = des_typs
    herkunft = MagicMock()
    herkunft.herkunft_ergaenzen = AsyncMock()
    return (
        sichtbaren_beitrag_laden(MagicMock(), alle_typen, factory, herkunft),
        herkunft,
    )


def _post(_id):
    return SimpleNamespace(content_type=ContentType.POST)


async def test_laden_sichtbarer_post_mit_herkunft_und_typ():
    beitrag = MagicMock()
    beitrag.model_dump.return_value = {"id": "p-1"}
    laden, herkunft = _lader(_post, lambda _id: beitrag)

    daten = await laden(uuid.uuid4())

    assert daten == {"id": "p-1", "result_type": "post"}
    herkunft.herkunft_ergaenzen.assert_awaited_once_with(beitrag)


async def test_laden_gesperrt_oder_geloescht_ist_none(caplog):
    def weg(_id):
        raise ValueError("not found")

    laden, _ = _lader(_post, weg)

    with caplog.at_level(logging.ERROR):
        assert await laden(uuid.uuid4()) is None
    assert caplog.records == []


async def test_laden_kaputter_datensatz_fehlt_und_wird_geloggt(caplog):
    fehler = _validierungsfehler()

    def kaputt(_id):
        raise fehler

    laden, _ = _lader(_post, kaputt)

    with caplog.at_level(logging.ERROR):
        assert await laden(uuid.uuid4()) is None
    assert any("not readable" in r.getMessage() for r in caplog.records)


def _ohne_schwellen_aus_der_umgebung(monkeypatch):
    for feld in ("OFT_GENUTZT_MINDEST_NUTZUNGEN", "OFT_GENUTZT_MINDEST_BEITRAEGE"):
        monkeypatch.delenv(f"SEMANTIC_SEARCH_{feld}", raising=False)


def test_schwellen_standard_fuer_die_startphase(monkeypatch):
    """Startphase zur BDK: zwei Beitraege mit je zwei Nutzungen (vorher drei Beitraege)."""
    _ohne_schwellen_aus_der_umgebung(monkeypatch)

    einstellungen = Settings()

    assert einstellungen.oft_genutzt_mindest_nutzungen == 2
    assert einstellungen.oft_genutzt_mindest_beitraege == 2


def test_schwellen_aus_der_umgebung(monkeypatch):
    """Der Betrieb hebt die Schwellen an, ohne Code zu aendern."""
    monkeypatch.setenv("SEMANTIC_SEARCH_OFT_GENUTZT_MINDEST_NUTZUNGEN", "4")
    monkeypatch.setenv("SEMANTIC_SEARCH_OFT_GENUTZT_MINDEST_BEITRAEGE", "3")

    einstellungen = Settings()

    assert einstellungen.oft_genutzt_mindest_nutzungen == 4
    assert einstellungen.oft_genutzt_mindest_beitraege == 3


@pytest.mark.parametrize(
    "feld,wert",
    [
        # Eine einzelne Kopie ist Zufall, kein "oft".
        ("OFT_GENUTZT_MINDEST_NUTZUNGEN", "1"),
        ("OFT_GENUTZT_MINDEST_BEITRAEGE", "0"),
        # Mehr als der Bereich zeigt (ANZAHL), und er erschiene nie.
        ("OFT_GENUTZT_MINDEST_BEITRAEGE", "6"),
    ],
)
def test_schwellen_ausserhalb_der_grenzen_abgelehnt(monkeypatch, feld, wert):
    _ohne_schwellen_aus_der_umgebung(monkeypatch)
    monkeypatch.setenv(f"SEMANTIC_SEARCH_{feld}", wert)

    with pytest.raises(ValueError):
        Settings()


def test_hoechste_mindestzahl_ist_die_anzahl_des_bereichs():
    """Die Obergrenze in core/config.py folgt ANZAHL; aendert sich eins, das andere mit."""
    obergrenze = next(
        m.le
        for m in Settings.model_fields["oft_genutzt_mindest_beitraege"].metadata
        if getattr(m, "le", None) is not None
    )

    assert obergrenze == ANZAHL
