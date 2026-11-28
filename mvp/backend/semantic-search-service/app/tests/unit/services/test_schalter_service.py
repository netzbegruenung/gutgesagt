"""
Schalter mit Obergrenze und Admin-Wert (#708): wirksam nur, wenn beide an sind; ohne
Admin-Wert aus; Einschalten ueber die Obergrenze hinaus abgelehnt; kurzer Cache.

Seit dem Schalter-Umbau (27.11.2026): vier Pakete, acht Einzelschalter (seit 28.11. mit
team_live), vier
Basisfunktionen mit Not-Aus; die uebrigen Basisfunktionen haben keinen Schalter mehr.
"""

import re
from datetime import date
from pathlib import Path

import pytest

from core.config import Settings
from services.schalter_service import (
    EINZELSCHALTER,
    GRUPPEN,
    NOTAUS,
    PAKETE,
    SCHALTER,
    ObergrenzeAus,
    SchalterService,
    UnbekannterSchalter,
    notaus_wirksam,
    oeffentliche_schalter,
    schalter_service_setzen,
    schalter_wirksam,
)

PAKET_NAMEN = {"teams", "spielgefuehl_buehne", "wirkungs_echo", "k_begruessung"}
EINZEL_NAMEN = {
    "team_quests",
    "team_live",
    "muster_stimmen",
    "teams_oeffentlich",
    "merkliste",
    "aufrufe_zaehlen",
    "danke_ohne_konto",
    "k_ankuenfte",
}
HEIKEL = {
    "teams_oeffentlich",
    "merkliste",
    "aufrufe_zaehlen",
    "danke_ohne_konto",
    "k_ankuenfte",
}
# Die 21 Basisfunktionen (Liste Sebastian/Jura 27.11.) und abzeichen_sichtbar sowie
# die frueheren Teile der Pakete: kein Schalter mehr.
BASISFUNKTIONEN = {
    "saison_ziel",
    "gartenansicht",
    "kopiert_erfolg",
    "konter_probe",
    "luecke_zu_gross",
    "einwilligung_im_gewinn",
    "naechster_schritt",
    "null_treffer_anzahl",
    "gepostet",
    "gepostet_ohne_konto",
    "herkunft_pruefen",
    "abkuerzungen",
    "antworten_hinweis",
    "sharepic",
    "meldeweg_sichtbar",
    "bestandszahl_zuwachs",
    "feedback_gestoert",
    "dse_kurzfassung",
    "stimmen_text_verfall",
    "vertrauenszeile",
    "hinweiszeile_kurz",
}
ENTFALLEN = BASISFUNKTIONEN | {
    "abzeichen_sichtbar",
    "punkte",
    "rangliste",
    "team_fortschritt",
    "teamlink_vertrauenssatz",
    "danke_knopf",
    "saal_spruch",
}


class Uhr:
    def __init__(self):
        self.jetzt = 0.0

    def __call__(self):
        return self.jetzt


def _dienst(werte=None, uhr=None, lesen=None):
    werte = {} if werte is None else werte
    gesetzt = []

    def setzen(name, an, admin):
        werte[name] = an
        gesetzt.append((name, an, admin))

    dienst = SchalterService(
        admin_werte_lesen=lesen or (lambda: dict(werte)),
        admin_wert_setzen=setzen,
        uhr=uhr or Uhr(),
    )
    return dienst, werte, gesetzt


ALLE_OBERGRENZEN = Settings(**{art.feld: True for art in SCHALTER.values()})


# --- Bestand nach dem Umbau ----------------------------------------------------


def test_genau_vier_pakete_und_acht_einzelschalter():
    assert len(BASISFUNKTIONEN) == 21
    assert {n for n, a in SCHALTER.items() if a.gruppe == PAKETE} == PAKET_NAMEN
    assert {n for n, a in SCHALTER.items() if a.gruppe == EINZELSCHALTER} == (
        EINZEL_NAMEN
    )
    assert GRUPPEN == (PAKETE, EINZELSCHALTER)


@pytest.mark.parametrize("name", sorted(ENTFALLEN))
def test_entfallene_schalter_gibt_es_nicht_mehr(name):
    """Kein Eintrag, kein Feld in Settings, Setzen und Fragen wie unbekannt."""
    dienst, _, _ = _dienst()

    assert name not in SCHALTER
    with pytest.raises(UnbekannterSchalter):
        dienst.wirksam(name, Settings())
    with pytest.raises(UnbekannterSchalter):
        dienst.setzen(name, True, "admin-1", Settings())
    if name not in NOTAUS:
        assert f"{name}_aktiv" not in Settings.model_fields


def test_pakete_behalten_name_feld_und_umgebungsvariable_des_hauptschalters():
    teile = {n: SCHALTER[n].teile for n in PAKET_NAMEN}
    assert teile == {
        "teams": ("teams", "team_fortschritt", "teamlink_vertrauenssatz"),
        "spielgefuehl_buehne": ("punkte", "spielgefuehl_buehne", "rangliste"),
        "wirkungs_echo": ("wirkungs_echo", "danke_knopf"),
        "k_begruessung": ("k_begruessung", "saal_spruch"),
    }
    for name in PAKET_NAMEN:
        art = SCHALTER[name]
        assert art.feld == f"{name}_aktiv"
        assert art.umgebungsvariable == f"SEMANTIC_SEARCH_{name.upper()}_AKTIV"
        assert name in art.teile


@pytest.mark.parametrize("name", sorted(PAKET_NAMEN | EINZEL_NAMEN))
def test_obergrenze_von_haus_aus_aus(name):
    assert Settings.model_fields[SCHALTER[name].feld].default is False


def test_rechtlich_freigegeben_und_wartet_auf_recht():
    """Go 27.11.: freigegeben sind Pakete, team_quests und muster_stimmen, seit der
    Jura-Akte 28.11. auch team_live; nur die fuenf heiklen warten auf Recht."""
    dienst, _, _ = _dienst()
    stand = {s.name: s for s in dienst.stand(Settings())}

    freigegeben = {n for n, a in SCHALTER.items() if a.rechtlich_freigegeben}
    assert freigegeben == PAKET_NAMEN | {"team_quests", "muster_stimmen", "team_live"}
    assert {n for n, s in stand.items() if s.wartet_auf_recht} == HEIKEL
    for name in HEIKEL:
        assert stand[name].dsfa_hinweis


@pytest.mark.parametrize(
    "name", ["teams_oeffentlich", "merkliste", "aufrufe_zaehlen", "k_ankuenfte"]
)
def test_aus_lassen_laut_jura_26_11(name):
    hinweis = SCHALTER[name].einschalt_hinweis
    assert hinweis.startswith("Aus lassen (Jura 26.11.): ")
    assert len(hinweis) > len("Aus lassen (Jura 26.11.): ") + 10


def test_danke_ohne_konto_nicht_einschalten():
    hinweis = SCHALTER["danke_ohne_konto"].einschalt_hinweis
    assert hinweis.startswith("Nicht einschalten (Jura 26.11.): ")
    assert "Variante B" in hinweis


def test_oeffentlich_alle_ausser_aufrufe_zaehlen():
    assert set(oeffentliche_schalter()) == (PAKET_NAMEN | EINZEL_NAMEN) - {
        "aufrufe_zaehlen"
    }


# --- Wirksam ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "obergrenze, admin, erwartet",
    [
        (False, None, False),
        (True, None, False),
        (False, True, False),
        (True, False, False),
        (True, True, True),
    ],
)
@pytest.mark.parametrize("paket", sorted(PAKET_NAMEN))
def test_paket_wirksam_nur_mit_obergrenze_und_admin_wert(
    paket, obergrenze, admin, erwartet
):
    werte = {} if admin is None else {paket: admin}
    dienst, _, _ = _dienst(werte)

    assert dienst.wirksam(paket, Settings(**{f"{paket}_aktiv": obergrenze})) is erwartet


def test_admin_werte_frueherer_teile_werden_ignoriert():
    """Nur der Admin-Wert des Paketnamens zaehlt; alte Zeilen bleiben stehen."""
    alte_teile = {
        "punkte": True,
        "rangliste": True,
        "team_fortschritt": True,
        "teamlink_vertrauenssatz": True,
        "danke_knopf": True,
        "saal_spruch": True,
        "sharepic": True,
        "abzeichen_sichtbar": True,
    }
    dienst, werte, _ = _dienst(dict(alte_teile))

    for paket in PAKET_NAMEN:
        assert dienst.wirksam(paket, ALLE_OBERGRENZEN) is False
    stand = dienst.stand(ALLE_OBERGRENZEN)
    assert {s.name for s in stand} == PAKET_NAMEN | EINZEL_NAMEN
    # Nichts geloescht
    assert werte == alte_teile


@pytest.mark.parametrize(
    "schalter, paket",
    [
        ("team_quests", "teams"),
        ("team_live", "teams"),
        ("teams_oeffentlich", "teams"),
        ("muster_stimmen", "spielgefuehl_buehne"),
        ("danke_ohne_konto", "wirkungs_echo"),
    ],
)
def test_einzelschalter_nur_mit_seinem_paket(schalter, paket):
    werte = {name: True for name in SCHALTER}
    dienst, _, _ = _dienst(werte)
    assert dienst.wirksam(schalter, ALLE_OBERGRENZEN) is True

    dienst, _, _ = _dienst({**werte, paket: False})
    assert dienst.wirksam(schalter, ALLE_OBERGRENZEN) is False
    stand = {s.name: s for s in dienst.stand(ALLE_OBERGRENZEN)}
    assert stand[schalter].admin_wert is True
    assert stand[schalter].wirksam is False

    ohne_paket_obergrenze = Settings(
        **{art.feld: art.name != paket for art in SCHALTER.values()}
    )
    dienst, _, _ = _dienst(werte)
    assert dienst.wirksam(schalter, ohne_paket_obergrenze) is False


@pytest.mark.parametrize("schalter", ["merkliste", "aufrufe_zaehlen", "k_ankuenfte"])
def test_einzelschalter_ohne_paket(schalter):
    dienst, _, _ = _dienst({schalter: True})
    assert dienst.wirksam(schalter, Settings(**{f"{schalter}_aktiv": True})) is True


@pytest.mark.parametrize("paket", sorted(PAKET_NAMEN))
def test_pakete_haengen_an_keinem_anderen_schalter(paket):
    dienst, _, _ = _dienst({paket: True})
    assert dienst.wirksam(paket, Settings(**{f"{paket}_aktiv": True})) is True


def test_einschalten_ueber_die_obergrenze_abgelehnt_ausschalten_geht():
    dienst, _, gesetzt = _dienst()

    with pytest.raises(ObergrenzeAus):
        dienst.setzen("spielgefuehl_buehne", True, "admin-1", Settings())
    dienst.setzen("spielgefuehl_buehne", False, "admin-1", Settings())

    assert gesetzt == [("spielgefuehl_buehne", False, "admin-1")]


def test_unbekannter_schalter():
    dienst, _, _ = _dienst()

    with pytest.raises(UnbekannterSchalter):
        dienst.setzen("gibtsnicht", False, "admin-1", Settings())
    with pytest.raises(UnbekannterSchalter):
        dienst.wirksam("gibtsnicht", Settings())


def test_cache_liest_hoechstens_je_cache_dauer_setzen_gilt_sofort():
    uhr = Uhr()
    gelesen = []
    werte = {"teams": False}

    def lesen():
        gelesen.append(1)
        return dict(werte)

    dienst, _, _ = _dienst(werte, uhr=uhr, lesen=lesen)
    settings = Settings(teams_aktiv=True)

    assert dienst.wirksam("teams", settings) is False
    werte["teams"] = True  # anderer Prozess schaltet ein
    assert dienst.wirksam("teams", settings) is False
    assert len(gelesen) == 1
    uhr.jetzt = 46
    assert dienst.wirksam("teams", settings) is True
    assert len(gelesen) == 2

    dienst.setzen("teams", False, "admin-1", settings)
    assert dienst.wirksam("teams", settings) is False


def test_stand_frisch_liest_am_cache_vorbei():
    uhr = Uhr()
    werte = {"teams": False}
    dienst, _, _ = _dienst(werte, uhr=uhr)
    settings = Settings(teams_aktiv=True)
    assert dienst.wirksam("teams", settings) is False

    werte["teams"] = True  # andere Replika schaltet ein
    stand = {s.name: s for s in dienst.stand(settings, frisch=True)}

    assert stand["teams"].admin_wert is True
    assert stand["teams"].wirksam is True
    assert dienst.wirksam("teams", settings) is True


def test_ohne_obergrenze_liest_wirksam_die_datenbank_nicht():
    gelesen = []

    def lesen():
        gelesen.append(1)
        return {"spielgefuehl_buehne": True}

    dienst, _, _ = _dienst(lesen=lesen)

    assert dienst.wirksam("spielgefuehl_buehne", Settings()) is False
    assert gelesen == []


def test_datenbank_nicht_erreichbar_gilt_aus():
    def kaputt():
        raise RuntimeError("weg")

    dienst, _, _ = _dienst(lesen=kaputt)

    assert dienst.wirksam("teams", Settings(teams_aktiv=True)) is False


def test_stand_nach_gruppen_geordnet():
    dienst, _, _ = _dienst()
    stand = dienst.stand(Settings())

    assert {s.name for s in stand} == set(SCHALTER)
    reihenfolge = [GRUPPEN.index(s.gruppe) for s in stand]
    assert reihenfolge == sorted(reihenfolge)
    assert all(s.erklaerung for s in stand)


def test_schalter_wirksam_nimmt_den_globalen_dienst():
    dienst, _, _ = _dienst()
    schalter_service_setzen(dienst)

    assert schalter_wirksam("teams", Settings(teams_aktiv=True)) is False


# --- Not-Aus -----------------------------------------------------------------------


def test_notaus_genau_diese_vier():
    assert set(NOTAUS) == {
        "feedback_gestoert",
        "gepostet_ohne_konto",
        "null_treffer_anzahl",
        "herkunft_pruefen",
    }


@pytest.mark.parametrize("name", sorted(NOTAUS))
def test_notaus_standard_an_false_schaltet_ab_ohne_admin_wert(name, monkeypatch):
    feld = NOTAUS[name]
    assert Settings.model_fields[feld].default is True
    assert notaus_wirksam(name, Settings()) is True
    assert notaus_wirksam(name, Settings(**{feld: False})) is False
    # Aus der Umgebung, wie Salt es setzt
    monkeypatch.setenv(f"SEMANTIC_SEARCH_{name.upper()}_AKTIV", "false")
    assert notaus_wirksam(name, Settings()) is False
    # Kein Admin-Knopf
    assert name not in SCHALTER


def test_notaus_unbekannt():
    with pytest.raises(UnbekannterSchalter):
        notaus_wirksam("sharepic", Settings())


@pytest.mark.parametrize(
    "heute, erwartet",
    [
        (date(2026, 12, 30), True),
        (date(2026, 12, 31), False),
        (date(2027, 1, 5), False),
    ],
)
def test_gestoert_knopf_endet_am_stichtag_ohne_schalter(heute, erwartet):
    from services.feedback_service import gestoert_knopf_an

    assert gestoert_knopf_an(Settings(), heute=heute) is erwartet
    assert (
        gestoert_knopf_an(Settings(feedback_gestoert_aktiv=False), heute=heute) is False
    )


# --- Datenschutzerklaerung -------------------------------------------------------

# Schalter, an denen die Datenschutzerklaerung einen Absatz oder Satz haengt, gelesen
# aus datenschutz.component.ts (jedes ``.an('<name>')``). Grundsatz Jura 26.11.: kein
# Schalter ohne seinen Absatz. Das Frontend kennt nur, was GET /api/v1/funktionen
# meldet; ein nicht gemeldeter Name liesse den Absatz auch eingeschaltet weg.
_DSE_KOMPONENTE = (
    Path(__file__).resolve().parents[6]
    / "frontend/gutgesagt-frontend/src/app/datenschutz/datenschutz.component.ts"
)
DSE_SCHALTER = tuple(
    sorted(set(re.findall(r"\.an\('([a-z_]+)'\)", _DSE_KOMPONENTE.read_text())))
)


def test_dse_schalter_aus_der_komponente_gelesen():
    # Faellt das Lesen still aus, waere der Test darunter leer
    assert {"spielgefuehl_buehne", "wirkungs_echo", "teams"} <= set(DSE_SCHALTER)


@pytest.mark.parametrize("name", DSE_SCHALTER)
def test_schalter_der_datenschutzerklaerung_meldet_funktionen(name):
    from api.v1.funktionen import NOTAUS_OEFFENTLICH

    gemeldet = set(oeffentliche_schalter()) | set(NOTAUS_OEFFENTLICH)
    gemeldet.add("feedback_gestoert")
    assert name in gemeldet
