"""Aufbau des vorlaeufigen Messsets fuer Themenvorschlaege (#401), ohne Modell (in CI)."""

from collections import Counter

from domain.themen import HOECHSTENS_JE_AUSSAGE, NACH_SCHLUESSEL
from tests.regression import suche_testset as st
from tests.regression.themen_messset import BEISPIELE, QUELLEN


def test_ids_und_texte_eindeutig():
    assert len({b.id for b in BEISPIELE}) == len(BEISPIELE)
    assert len({b.text for b in BEISPIELE}) == len(BEISPIELE)


def test_themen_aus_der_liste_eins_bis_drei_ohne_doppelte():
    for b in BEISPIELE:
        assert 1 <= len(b.themen) <= HOECHSTENS_JE_AUSSAGE, b.id
        assert len(set(b.themen)) == len(b.themen), b.id
        assert set(b.themen) <= set(NACH_SCHLUESSEL), b.id
        assert b.quelle in QUELLEN, b.id


def test_jedes_thema_hat_mindestens_drei_aussagen():
    je_thema = Counter(t for b in BEISPIELE for t in b.themen)

    assert {s: je_thema[s] for s in NACH_SCHLUESSEL if je_thema[s] < 3} == {}


def test_der_ganze_startbestand_ist_dabei():
    texte = {b.text for b in BEISPIELE if b.quelle == "start"}

    assert texte == set(st.STARTBESTAND)
