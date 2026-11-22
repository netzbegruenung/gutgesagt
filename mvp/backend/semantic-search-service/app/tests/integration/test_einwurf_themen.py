"""
Themen am Einwurf gegen ein echtes PostgreSQL: lesen und mit dem Einwurf loeschen.

Die Unit-Tests pruefen, was das Repository beim Anlegen in die Session legt; hier zeigt
sich, dass die Themen je Einwurf zurueckkommen, jedes nur einmal steht und sie per
CASCADE mit dem Einwurf gehen (Loeschfrist, Loeschkommando). Wegwerf-Schema aus der
Fixture ``datenbank`` von ``test_loeschkommando.py``.
"""

import uuid

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from infrastructure.database.models import Einwurf, EinwurfThemaZeile
from repositories.einwurf_repository import EinwurfRepository
from tests.integration.test_loeschkommando import datenbank  # noqa: F401

pytestmark = pytest.mark.integration


def _einwurf(datenbank, content: str, themen=()) -> uuid.UUID:
    """
    Einen Einwurf mit Themen anlegen, wie ``EinwurfRepository.create`` es tut: Einwurf
    einfuegen, dann die Themen an die vergebene ID. Ueber die Session des Wegwerf-Schemas,
    weil ``create`` selbst committet und das Schema die Transaktion haelt.
    """
    with datenbank.get_session() as s:
        einwurf = Einwurf(content=content, status="open")
        s.add(einwurf)
        s.flush()
        s.add_all(EinwurfThemaZeile(raw_input_id=einwurf.id, thema=t) for t in themen)
        return einwurf.id


def test_themen_werden_je_einwurf_gelesen(datenbank):  # noqa: F811
    _einwurf(datenbank, "mit Themen", ["verkehr", "klima"])
    ohne = _einwurf(datenbank, "ohne Themen")
    repository = EinwurfRepository(datenbank)

    gelesen = {z["content"]: z["themen"] for z in repository.get_all()}
    assert gelesen == {"mit Themen": ["klima", "verkehr"], "ohne Themen": []}
    assert repository.get_by_id(ohne)["themen"] == []


def test_themen_gehen_mit_dem_einwurf(datenbank):  # noqa: F811
    einwurf = _einwurf(datenbank, "weg damit", ["europa"])

    with datenbank.get_session() as s:
        s.execute(delete(Einwurf).where(Einwurf.id == einwurf))
    with datenbank.get_session() as s:
        uebrig = s.scalar(select(func.count()).select_from(EinwurfThemaZeile))

    assert uebrig == 0


def test_ein_thema_nur_einmal_je_einwurf(datenbank):  # noqa: F811
    with pytest.raises(IntegrityError):
        _einwurf(datenbank, "doppelt", ["klima", "klima"])
