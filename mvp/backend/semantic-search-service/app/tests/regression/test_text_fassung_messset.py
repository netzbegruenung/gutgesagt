"""
Regressionstest Stimmenverfall bei geaendertem Text (#636): Keine Korrektur,
Ergaenzung, Kuerzung oder Umformulierung faellt unter die Schwelle, jeder ganz andere
Text liegt darunter. Laedt das Einbettungsmodell; deshalb langsam markiert und nicht in
der PR-CI. Der Nachtlauf (.woodpecker/nacht.yaml) nimmt ihn noch nicht mit; von Hand
bei jedem Wechsel von Modell oder Schwelle.

    cd mvp/backend/semantic-search-service/app
    ../venv/bin/python -m pytest tests/regression/test_text_fassung_messset.py -m langsam -v
"""

import pytest

from core.config import Settings
from tests.regression.text_fassung_messen import scores
from tests.regression.text_fassung_paare import PAARE

pytestmark = pytest.mark.langsam

# Abstand, den beide Seiten mindestens zur Schwelle halten (CPU/Bibliothek).
ABSTAND = 0.02
SCHWELLE = Settings().text_verfall_aehnlichkeit_unter


@pytest.mark.parametrize(
    "paar", [p for p in PAARE if p.label == "bleibt"], ids=lambda p: p.id
)
def test_kleine_korrekturen_kosten_nie_stimmen(paar):
    assert scores()[paar.id].pp >= SCHWELLE + ABSTAND


@pytest.mark.parametrize(
    "paar", [p for p in PAARE if p.phaenomen == "fremd"], ids=lambda p: p.id
)
def test_ganz_anderer_text_laesst_stimmen_verfallen(paar):
    assert scores()[paar.id].pp < SCHWELLE - ABSTAND
