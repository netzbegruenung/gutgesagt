"""
Schalter fuer das Spielgefuehl zur BDK (#782 bis #793): je Baustein ein Schalter,
Obergrenze von Haus aus aus, ohne Admin-Wert aus. ``danke_ohne_konto`` wirkt nur mit
``danke_knopf``, ``rangliste`` nur mit ``punkte``. Wo das Issue eine Bedingung fuers
Einschalten nennt, zeigt die Admin-Seite sie als Hinweis.
"""

import pytest

from core.config import Settings
from services.schalter_service import (
    SCHALTER,
    SPIEL_SCHALTER,
    ObergrenzeAus,
    SchalterService,
    oeffentliche_schalter,
)

pytestmark = pytest.mark.unit

# Name -> Umgebungsvariable; die Bausteine bauen auf genau diesen Namen auf.
ERWARTET = {
    "saison_ziel": "SEMANTIC_SEARCH_SAISON_ZIEL_AKTIV",
    "gartenansicht": "SEMANTIC_SEARCH_GARTENANSICHT_AKTIV",
    "kopiert_erfolg": "SEMANTIC_SEARCH_KOPIERT_ERFOLG_AKTIV",
    "konter_probe": "SEMANTIC_SEARCH_KONTER_PROBE_AKTIV",
    "luecke_zu_gross": "SEMANTIC_SEARCH_LUECKE_ZU_GROSS_AKTIV",
    "einwilligung_im_gewinn": "SEMANTIC_SEARCH_EINWILLIGUNG_IM_GEWINN_AKTIV",
    "naechster_schritt": "SEMANTIC_SEARCH_NAECHSTER_SCHRITT_AKTIV",
    "wirkungs_echo": "SEMANTIC_SEARCH_WIRKUNGS_ECHO_AKTIV",
    "danke_knopf": "SEMANTIC_SEARCH_DANKE_KNOPF_AKTIV",
    "danke_ohne_konto": "SEMANTIC_SEARCH_DANKE_OHNE_KONTO_AKTIV",
    "rangliste": "SEMANTIC_SEARCH_RANGLISTE_AKTIV",
    "saal_spruch": "SEMANTIC_SEARCH_SAAL_SPRUCH_AKTIV",
}

ALLE_AN = Settings(**{SCHALTER[n].feld: True for n in ERWARTET}, punkte_aktiv=True)


def _dienst(werte):
    return SchalterService(
        admin_werte_lesen=lambda: dict(werte),
        admin_wert_setzen=lambda name, an, admin: werte.__setitem__(name, an),
    )


def test_namen_und_umgebungsvariablen():
    assert {s.name: s.umgebungsvariable for s in SPIEL_SCHALTER} == ERWARTET
    for name in ERWARTET:
        assert SCHALTER[name].umgebungsvariable == (
            "SEMANTIC_SEARCH_" + SCHALTER[name].feld.upper()
        )


def test_kein_schalter_fuer_team_fortschritt_und_team_quests():
    """#784 und #792 bekommen ihre Schalter spaeter."""
    assert not any(n.startswith("team_") for n in ERWARTET)


@pytest.mark.parametrize("name", list(ERWARTET))
def test_obergrenze_von_haus_aus_aus(name):
    """Der Standard im Code, unabhaengig von der Umgebung der Entwicklerin."""
    dienst = _dienst({name: True, "danke_knopf": True, "punkte": True})
    aus = Settings(**{SCHALTER[name].feld: False})

    assert Settings.model_fields[SCHALTER[name].feld].default is False
    assert dienst.wirksam(name, aus) is False
    with pytest.raises(ObergrenzeAus):
        dienst.setzen(name, True, "admin-1", aus)


@pytest.mark.parametrize("name", list(ERWARTET))
def test_ohne_admin_wert_aus_mit_admin_wert_an(name):
    werte = {"danke_knopf": True, "punkte": True}
    werte.pop(name, None)
    assert _dienst(werte).wirksam(name, ALLE_AN) is False

    werte[name] = True
    assert _dienst(werte).wirksam(name, ALLE_AN) is True


def test_danke_ohne_konto_nur_mit_danke_knopf():
    dienst = _dienst({"danke_ohne_konto": True, "danke_knopf": False})

    assert dienst.wirksam("danke_ohne_konto", ALLE_AN) is False


def test_rangliste_nur_mit_punkten():
    dienst = _dienst({"rangliste": True, "punkte": False})

    assert dienst.wirksam("rangliste", ALLE_AN) is False


def test_einschalt_hinweise_laut_issue():
    stand = {s.name: s for s in _dienst({}).stand(ALLE_AN)}

    assert "V31" in stand["wirkungs_echo"].dsfa_hinweis
    assert "V31" in stand["danke_knopf"].dsfa_hinweis
    assert "Besuchermerkmal" in stand["danke_ohne_konto"].dsfa_hinweis
    assert "Jura" in stand["rangliste"].dsfa_hinweis
    assert (
        stand["naechster_schritt"].dsfa_hinweis
        == "Einschalten erst nach dem DSFA-Nachtrag Spielgefühl (V10)"
    )
    for name in (
        "saison_ziel",
        "gartenansicht",
        "kopiert_erfolg",
        "konter_probe",
        "luecke_zu_gross",
        "einwilligung_im_gewinn",
        "saal_spruch",
    ):
        assert stand[name].dsfa_hinweis is None
        assert stand[name].erklaerung


def test_oeffentlich_nur_ohne_eigenen_angemeldeten_endpunkt():
    """Wirkungs-Echo und Rangliste sehen nur Angemeldete ueber eigene Abrufe."""
    oeffentlich = set(oeffentliche_schalter())

    assert "wirkungs_echo" not in oeffentlich
    assert "rangliste" not in oeffentlich
    assert {
        "kopiert_erfolg",
        "konter_probe",
        "danke_ohne_konto",
        "saal_spruch",
    } <= oeffentlich
