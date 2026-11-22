"""
Themenvorschlaege (#401) gegen das echte Einbettungsmodell: Die Schwellen in
core/config.py sind fuer EMBEDDING_MODELL am vorlaeufigen Messset gemessen
(tests/regression/THEMEN.md). Aendern sich Modell, Praefix oder Mitte, faellt hier auf,
ob die Vorschlaege noch tragen. Die Unit-Tests (tests/unit/services/
test_themen_vorschlag.py) arbeiten nur mit Vektoren von Hand.
"""

import pytest

from core.config import settings
from services.themen_vorschlag import Schwellen, ThemenVorschlagService
from tests.regression.themen_messset import BEISPIELE

# Untergrenzen mit Luft: Ohne Stichwoerter und ohne die anderen Aussagen des
# Startbestands in den Prototypen trafen am 22.11.2026 27 von 47 Themen (R 0,57), bei
# P ueber 0,75 (THEMEN.md misst mit allen anderen Aussagen: P 0,76, R 0,66).
PRECISION_MINDESTENS = 0.7
RECALL_MINDESTENS = 0.5


def _service(manager, beispiele):
    async def laden():
        return beispiele

    return ThemenVorschlagService(
        einbetter=manager,
        beispiele_laden=laden,
        schwellen=Schwellen(
            settings.themen_vorschlag_ab,
            settings.themen_vorschlag_abstand_hoechstens,
        ),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_neue_aussage_bekommt_ihr_thema(real_embeddings_manager):
    service = _service(
        real_embeddings_manager, [(b.text, list(b.themen)) for b in BEISPIELE]
    )

    vorschlag = await service.vorschlagen("Auf der Autobahn sollte man 130 fahren.", 3)

    assert vorschlag and vorschlag[0] == "verkehr"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_startbestand_leave_one_out_ueber_der_untergrenze(
    real_embeddings_manager,
):
    start = [b for b in BEISPIELE if b.quelle == "start"]
    andere = [(b.text, list(b.themen)) for b in BEISPIELE if b.quelle != "start"]
    # Die Aussagen des Startbestands kennt der Service nicht: Prototypen nur aus den
    # anderen, wie ein neuer Text.
    service = _service(real_embeddings_manager, andere)
    richtig = falsch = verpasst = 0
    for b in start:
        vorschlag = set(await service.vorschlagen(b.text, 3))
        richtig += len(vorschlag & set(b.themen))
        falsch += len(vorschlag - set(b.themen))
        verpasst += len(set(b.themen) - vorschlag)

    assert richtig / (richtig + falsch) >= PRECISION_MINDESTENS
    assert richtig / (richtig + verpasst) >= RECALL_MINDESTENS
