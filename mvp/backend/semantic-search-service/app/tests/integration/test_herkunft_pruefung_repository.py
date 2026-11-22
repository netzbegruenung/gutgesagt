"""
Ergebnisse von "Herkunft pruefen" (#759) gegen ein echtes PostgreSQL. Wegwerf-Schema
aus der Fixture ``datenbank`` von ``test_loeschkommando.py``.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from repositories.herkunft_pruefung_repository import HerkunftPruefungRepository
from tests.integration.test_loeschkommando import datenbank  # noqa: F401

pytestmark = pytest.mark.integration

A = uuid.UUID("11111111-1111-4111-8111-111111111111")
B = uuid.UUID("22222222-2222-4222-8222-222222222222")
T0 = datetime(2026, 11, 20, 3, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(days=1)
T2 = T0 + timedelta(days=2)


def _speichern(repo, id_, adresse, ergebnis, zeit, status=None):
    repo.speichern(id_, adresse, ergebnis, status, None, zeit, ergebnis != "ok")


class TestHerkunftPruefungRepository:
    def test_leer(self, datenbank):  # noqa: F811
        repo = HerkunftPruefungRepository(datenbank)
        stand = repo.stand("ok", 10)
        assert (stand.geprueft, stand.letzter_lauf, stand.auffaellig) == (0, None, [])
        assert repo.letzter_lauf() is None

    def test_auffaellig_seit_bleibt_bis_der_link_wieder_geht(
        self, datenbank  # noqa: F811
    ):
        repo = HerkunftPruefungRepository(datenbank)
        _speichern(repo, A, "https://a.example/", "tot", T0, 404)
        _speichern(repo, A, "https://a.example/", "fehler", T1, 500)

        stand = repo.stand("ok", 10)
        assert stand.geprueft == 1 and stand.letzter_lauf == T1
        [eintrag] = stand.auffaellig
        assert (eintrag.ergebnis, eintrag.http_status) == ("fehler", 500)
        assert eintrag.auffaellig_seit == T0

        _speichern(repo, A, "https://a.example/", "ok", T2, 200)
        assert repo.stand("ok", 10).auffaellig == []

    def test_neue_adresse_faengt_neu_an(self, datenbank):  # noqa: F811
        repo = HerkunftPruefungRepository(datenbank)
        _speichern(repo, A, "https://a.example/alt", "tot", T0, 404)
        _speichern(repo, A, "https://a.example/neu", "tot", T1, 404)

        [eintrag] = repo.stand("ok", 10).auffaellig
        assert eintrag.adresse == "https://a.example/neu"
        assert eintrag.auffaellig_seit == T1

    def test_uebrige_loeschen(self, datenbank):  # noqa: F811
        repo = HerkunftPruefungRepository(datenbank)
        _speichern(repo, A, "https://a.example/", "tot", T0)
        _speichern(repo, B, "https://b.example/", "tot", T0)

        assert repo.uebrige_loeschen([A]) == 1
        assert [e.herkunft_id for e in repo.stand("ok", 10).auffaellig] == [A]
        assert repo.uebrige_loeschen([]) == 1
        assert repo.stand("ok", 10).geprueft == 0

    def test_laengste_zuerst_und_grenze(self, datenbank):  # noqa: F811
        repo = HerkunftPruefungRepository(datenbank)
        _speichern(repo, A, "https://a.example/", "tot", T1)
        _speichern(repo, B, "https://b.example/", "tot", T0)

        _speichern(repo, uuid.uuid4(), "https://c.example/", "ok", T0)
        stand = repo.stand("ok", 1)
        assert stand.geprueft == 3 and stand.auffaellig_gesamt == 2
        assert [e.herkunft_id for e in stand.auffaellig] == [B]
