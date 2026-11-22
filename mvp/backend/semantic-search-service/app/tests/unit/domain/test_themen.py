"""
Unit-Tests fuer die Themenliste (domain/themen.json): die feste, kurze Liste, mit
der Aussagen geordnet werden, und die Pruefung einer Zuordnung (hoechstens drei
Themen, nur aus der Liste).
"""

import pytest

from domain.themen import (
    HOECHSTENS_JE_AUSSAGE,
    HOECHSTENS_JE_EINWURF,
    THEMEN,
    ThemaUngueltig,
    einwurf_themen_pruefen,
    themen_pruefen,
)

pytestmark = pytest.mark.unit


def test_liste_ist_kurz_und_eindeutig():
    schluessel = [t.schluessel for t in THEMEN]
    assert 8 <= len(THEMEN) <= 20
    assert len(set(schluessel)) == len(schluessel)
    assert len({t.name for t in THEMEN}) == len(THEMEN)


def test_schluessel_sind_kleingeschrieben_mit_bindestrichen():
    for thema in THEMEN:
        assert thema.schluessel.replace("-", "").isalpha()
        assert thema.schluessel == thema.schluessel.lower()
        assert thema.name.strip() == thema.name and thema.name


def test_pruefen_laesst_keine_bis_drei_themen_durch():
    erstes, zweites, drittes = (t.schluessel for t in THEMEN[:3])

    assert themen_pruefen([]) == []
    assert themen_pruefen([erstes]) == [erstes]
    assert themen_pruefen([erstes, zweites]) == [erstes, zweites]
    assert themen_pruefen([erstes, zweites, drittes]) == [erstes, zweites, drittes]
    assert HOECHSTENS_JE_AUSSAGE == 3


def test_pruefen_entfernt_doppelte():
    erstes = THEMEN[0].schluessel
    assert themen_pruefen([erstes, erstes]) == [erstes]


def test_pruefen_weist_vier_themen_ab():
    vier = [t.schluessel for t in THEMEN[:4]]
    with pytest.raises(ThemaUngueltig):
        themen_pruefen(vier)


def test_pruefen_weist_freie_schlagworte_ab():
    with pytest.raises(ThemaUngueltig):
        themen_pruefen(["heizungsgesetz"])


def test_jedes_thema_hat_ein_motiv():
    # Das Album in "Meine Beitraege" zeigt es neben dem Namen; ob die Datei unter
    # public/ liegt, prueft scripts/tests/test_themen_motive.py.
    for thema in THEMEN:
        assert thema.motiv == f"themen/{thema.schluessel}.svg", thema.schluessel


def test_einwurf_laesst_keine_bis_zwei_themen_durch():
    erstes, zweites = (t.schluessel for t in THEMEN[:2])

    assert einwurf_themen_pruefen([]) == []
    assert einwurf_themen_pruefen([zweites]) == [zweites]
    assert einwurf_themen_pruefen([zweites, erstes]) == [zweites, erstes]
    assert HOECHSTENS_JE_EINWURF == 2


def test_einwurf_weist_drei_themen_ab():
    with pytest.raises(ThemaUngueltig):
        einwurf_themen_pruefen([t.schluessel for t in THEMEN[:3]])


def test_einwurf_weist_doppelte_ab():
    erstes = THEMEN[0].schluessel
    with pytest.raises(ThemaUngueltig):
        einwurf_themen_pruefen([erstes, erstes])


def test_einwurf_weist_freie_schlagworte_ab():
    with pytest.raises(ThemaUngueltig):
        einwurf_themen_pruefen(["heizungsgesetz"])
