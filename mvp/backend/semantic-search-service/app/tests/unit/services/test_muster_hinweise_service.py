"""
Fristen der Muster-Hinweise und der Pruefwerte (#352). Das Erkennen selbst pruefen
tests/integration/test_muster_hinweise.py gegen PostgreSQL.
"""

import asyncio
from datetime import date
from unittest.mock import Mock

import pytest

from repositories.muster_hinweis_repository import MusterHinweis
from services.entdoppelung import pruefwerte_verwerfen_im_takt
from services.muster_hinweise_service import MusterHinweiseService, loeschen_im_takt


def test_fristen_anwenden_verwirft_paare_und_loescht_nach_acht_wochen():
    hinweise = Mock()

    MusterHinweiseService(hinweise).fristen_anwenden(date(2026, 10, 30))

    # Paar-Pruefwerte bleiben sieben Tage: den heutigen und die sechs davor.
    hinweise.paare_verwerfen_vor.assert_called_once_with(date(2026, 10, 24))
    hinweise.loeschen_vor.assert_called_once_with(date(2026, 9, 4))


@pytest.mark.asyncio
async def test_loeschen_im_takt_laeuft_nach_fehler_weiter():
    hinweise = Mock()
    hinweise.loeschen_vor = Mock(side_effect=[RuntimeError("weg"), 0, 0])

    task = asyncio.create_task(
        loeschen_im_takt(MusterHinweiseService(hinweise), takt_sekunden=0)
    )
    while hinweise.loeschen_vor.call_count < 2:
        await asyncio.sleep(0.01)
    task.cancel()

    assert hinweise.loeschen_vor.call_count >= 2


@pytest.mark.asyncio
async def test_pruefwerte_verwerfen_im_takt_laeuft_nach_fehler_weiter():
    """Die Pruefwerte der Entdoppelung gehen auch ohne Punkte und Muster-Hinweise."""
    nutzung = Mock()
    nutzung.vergangene_tage_verwerfen = Mock(side_effect=[RuntimeError("weg"), 0, 0])

    task = asyncio.create_task(pruefwerte_verwerfen_im_takt(nutzung, takt_sekunden=0))
    while nutzung.vergangene_tage_verwerfen.call_count < 2:
        await asyncio.sleep(0.01)
    task.cancel()

    assert nutzung.vergangene_tage_verwerfen.call_count >= 2


@pytest.mark.asyncio
async def test_pruefwerte_verwerfen_im_takt_verdichtet_gepostet_auch_nach_fehler():
    """Die Pruefwerte "Ja, gepostet" (#643) gehen nach ihrer Woche auch ohne neue Meldung."""
    nutzung = Mock()
    nutzung.vergangene_tage_verwerfen = Mock(return_value=0)
    gepostet = Mock(side_effect=[RuntimeError("weg"), None, None])

    task = asyncio.create_task(
        pruefwerte_verwerfen_im_takt(nutzung, takt_sekunden=0, gepostet=gepostet)
    )
    while gepostet.call_count < 2:
        await asyncio.sleep(0.01)
    task.cancel()

    assert nutzung.vergangene_tage_verwerfen.call_count >= 2


def _hinweis(a: str, b: str) -> MusterHinweis:
    return MusterHinweis(a, b, 1, date(2026, 10, 26), date(2026, 10, 26))


def test_hinweise_nur_wenn_beide_eingewilligt_haben():
    """Nach einem Widerruf erscheint die Person nicht mehr im Admin-Dashboard."""
    repository = Mock()
    repository.hinweise.return_value = [
        _hinweis("bo-2", "kim-1"),
        _hinweis("ali-3", "bo-2"),
        _hinweis("ali-3", "eda-4"),
    ]
    gefragt = []

    def eingewilligte(kennungen):
        gefragt.append(set(kennungen))
        return {"bo-2", "kim-1", "eda-4"}

    hinweise = MusterHinweiseService(repository).hinweise(eingewilligte)

    assert hinweise == [_hinweis("bo-2", "kim-1")]
    # Eine Abfrage fuer alle Kennungen
    assert gefragt == [{"bo-2", "kim-1", "ali-3", "eda-4"}]


def test_hinweise_ohne_eintraege_fragen_keine_einwilligung():
    repository = Mock()
    repository.hinweise.return_value = []
    eingewilligte = Mock()

    assert MusterHinweiseService(repository).hinweise(eingewilligte) == []
    eingewilligte.assert_not_called()


def test_vergessen_loescht_die_hinweise_der_person():
    repository = Mock()

    MusterHinweiseService(repository).vergessen("kim-1")
    MusterHinweiseService(repository).vergessen("anonymous")
    MusterHinweiseService(repository).vergessen("")

    repository.vergessen.assert_called_once_with("kim-1")
