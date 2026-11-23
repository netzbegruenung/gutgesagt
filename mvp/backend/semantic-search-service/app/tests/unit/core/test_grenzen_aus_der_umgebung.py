"""
Tagesdeckel und die Rate-Limits ohne Anmeldung kommen aus der Umgebung
(SEMANTIC_SEARCH_*), damit der Betrieb sie fuer das Saal-WLAN eines Parteitags anheben
kann. Ohne Angabe gelten die bisherigen Werte.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.config import Settings

pytestmark = pytest.mark.unit

APP = Path(__file__).resolve().parents[3]

# Feld in Settings, Standardwert, Limiter in utils/rate_limiter.py (None: Tagesdeckel)
GRENZEN = [
    ("tagesdeckel_beitraege", 20, None),
    ("aehnliche_aussagen_rate_limit_anfragen", 60, "aehnliche_aussagen_rate_limiter"),
    ("suchaussage_rate_limit_anfragen", 60, "search_query_statement_rate_limiter"),
    ("feedback_rate_limit_anfragen", 5, "feedback_rate_limiter"),
    ("meldung_rate_limit_anfragen", 5, "report_rate_limiter"),
    ("einladung_rate_limit_anfragen", 30, "einladung_rate_limiter"),
    ("einladung_pruefen_rate_limit_anfragen", 60, "einladung_pruefen_rate_limiter"),
]


def _ohne_grenzen_aus_der_umgebung(monkeypatch):
    for feld, _, _ in GRENZEN:
        monkeypatch.delenv(f"SEMANTIC_SEARCH_{feld.upper()}", raising=False)


@pytest.mark.parametrize("feld,standard,_limiter", GRENZEN)
def test_ohne_angabe_bleibt_der_bisherige_wert(monkeypatch, feld, standard, _limiter):
    _ohne_grenzen_aus_der_umgebung(monkeypatch)

    assert getattr(Settings(), feld) == standard


@pytest.mark.parametrize("feld,_standard,_limiter", GRENZEN)
def test_wert_aus_der_umgebung(monkeypatch, feld, _standard, _limiter):
    monkeypatch.setenv(f"SEMANTIC_SEARCH_{feld.upper()}", "123")

    assert getattr(Settings(), feld) == 123


@pytest.mark.parametrize("feld,_standard,_limiter", GRENZEN)
def test_null_ist_kein_gueltiger_wert(monkeypatch, feld, _standard, _limiter):
    monkeypatch.setenv(f"SEMANTIC_SEARCH_{feld.upper()}", "0")

    with pytest.raises(ValueError):
        Settings()


def test_die_limiter_lesen_die_werte_beim_start():
    """
    In einem frischen Prozess: Die Limiter entstehen beim Import, die Werte
    muessen also dann schon aus der Umgebung kommen. Die Fenster bleiben fest.
    """
    umgebung = {**os.environ}
    for i, (feld, _, _) in enumerate(GRENZEN):
        umgebung[f"SEMANTIC_SEARCH_{feld.upper()}"] = str(100 + i)
    skript = (
        "import json; from utils import rate_limiter as r; "
        "from utils.tagesdeckel import tagesdeckel; "
        "print(json.dumps({'tagesdeckel': tagesdeckel.je_tag, **{n: "
        "[getattr(r, n).max_requests, getattr(r, n).window.total_seconds() / 60] "
        f"for n in {[l for _, _, l in GRENZEN if l]!r}}}}}))"
    )

    ausgabe = subprocess.run(
        [sys.executable, "-c", skript],
        cwd=APP,
        env=umgebung,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    werte = json.loads(ausgabe.strip().splitlines()[-1])

    assert werte == {
        "tagesdeckel": 100,
        "aehnliche_aussagen_rate_limiter": [101, 10],
        "search_query_statement_rate_limiter": [102, 10],
        "feedback_rate_limiter": [103, 15],
        "report_rate_limiter": [104, 15],
        "einladung_rate_limiter": [105, 15],
        "einladung_pruefen_rate_limiter": [106, 15],
    }
