"""
Schalter mit Obergrenze und Admin-Wert (#708): wirksam nur, wenn beide an sind; ohne
Admin-Wert aus; Einschalten ueber die Obergrenze hinaus abgelehnt; kurzer Cache.
"""

import pytest

from core.config import Settings
from services.schalter_service import (
    ObergrenzeAus,
    SchalterService,
    UnbekannterSchalter,
    schalter_service_setzen,
    schalter_wirksam,
)


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
def test_wirksam_nur_mit_obergrenze_und_admin_wert(obergrenze, admin, erwartet):
    werte = {} if admin is None else {"gepostet": admin}
    dienst, _, _ = _dienst(werte)

    assert dienst.wirksam("gepostet", Settings(gepostet_aktiv=obergrenze)) is erwartet


def test_abzeichen_nur_mit_wirksamen_punkten():
    settings = Settings(punkte_aktiv=True, abzeichen_sichtbar_aktiv=True)
    dienst, _, _ = _dienst({"abzeichen_sichtbar": True, "punkte": False})

    assert dienst.wirksam("abzeichen_sichtbar", settings) is False

    dienst, _, _ = _dienst({"abzeichen_sichtbar": True, "punkte": True})
    assert dienst.wirksam("abzeichen_sichtbar", settings) is True


def test_einschalten_ueber_die_obergrenze_abgelehnt_ausschalten_geht():
    dienst, werte, gesetzt = _dienst()

    with pytest.raises(ObergrenzeAus):
        dienst.setzen("punkte", True, "admin-1", Settings(punkte_aktiv=False))
    dienst.setzen("punkte", False, "admin-1", Settings(punkte_aktiv=False))

    assert gesetzt == [("punkte", False, "admin-1")]


def test_unbekannter_schalter():
    dienst, _, _ = _dienst()

    with pytest.raises(UnbekannterSchalter):
        dienst.setzen("gibtsnicht", False, "admin-1", Settings())
    with pytest.raises(UnbekannterSchalter):
        dienst.wirksam("gibtsnicht", Settings())


def test_cache_liest_hoechstens_je_cache_dauer_setzen_gilt_sofort():
    uhr = Uhr()
    gelesen = []
    werte = {"gepostet": False}

    def lesen():
        gelesen.append(1)
        return dict(werte)

    dienst, _, _ = _dienst(werte, uhr=uhr, lesen=lesen)
    settings = Settings(gepostet_aktiv=True)

    assert dienst.wirksam("gepostet", settings) is False
    werte["gepostet"] = True  # anderer Prozess schaltet ein
    assert dienst.wirksam("gepostet", settings) is False
    assert len(gelesen) == 1
    uhr.jetzt = 46
    assert dienst.wirksam("gepostet", settings) is True
    assert len(gelesen) == 2

    dienst.setzen("gepostet", False, "admin-1", settings)
    assert dienst.wirksam("gepostet", settings) is False


def test_stand_frisch_liest_am_cache_vorbei():
    uhr = Uhr()
    werte = {"gepostet": False}
    dienst, _, _ = _dienst(werte, uhr=uhr)
    settings = Settings(gepostet_aktiv=True)
    assert dienst.wirksam("gepostet", settings) is False

    werte["gepostet"] = True  # andere Replika schaltet ein
    stand = {s.name: s for s in dienst.stand(settings, frisch=True)}

    assert stand["gepostet"].admin_wert is True
    assert stand["gepostet"].wirksam is True
    # Der frische Wert erneuert auch den Cache
    assert dienst.wirksam("gepostet", settings) is True


def test_ohne_obergrenze_liest_wirksam_die_datenbank_nicht():
    gelesen = []

    def lesen():
        gelesen.append(1)
        return {"punkte": True}

    dienst, _, _ = _dienst(lesen=lesen)

    assert dienst.wirksam("punkte", Settings(punkte_aktiv=False)) is False
    assert gelesen == []


def test_datenbank_nicht_erreichbar_gilt_aus():
    def kaputt():
        raise RuntimeError("weg")

    dienst, _, _ = _dienst(lesen=kaputt)

    assert dienst.wirksam("punkte", Settings(punkte_aktiv=True)) is False


def test_stand_nennt_obergrenze_admin_wert_wirksam_und_dsfa_hinweis():
    dienst, _, _ = _dienst({"punkte": True})
    stand = {s.name: s for s in dienst.stand(Settings(punkte_aktiv=True))}

    # Mindestens diese; weitere Schalter pruefen ihre eigenen Tests
    assert set(stand) >= {"punkte", "abzeichen_sichtbar", "gepostet"}
    assert (
        stand["punkte"].obergrenze,
        stand["punkte"].admin_wert,
        stand["punkte"].wirksam,
    ) == (True, True, True)
    assert stand["gepostet"].admin_wert is False
    assert "DSFA" in stand["punkte"].dsfa_hinweis
    assert "DSFA" in stand["abzeichen_sichtbar"].dsfa_hinweis
    assert stand["gepostet"].dsfa_hinweis is None
    assert stand["merkliste"].wartet_auf_recht is True
    assert stand["abkuerzungen"].dsfa_hinweis is None
    assert stand["sharepic"].dsfa_hinweis is None
    assert all(s.erklaerung for s in stand.values())


def test_herkunft_pruefen_obergrenze_an_admin_wert_aus():
    """#759: Der Server erlaubt ihn von sich aus; wirksam erst mit dem Admin-Wert."""
    dienst, _, _ = _dienst()
    stand = {s.name: s for s in dienst.stand(Settings())}["herkunft_pruefen"]

    assert (stand.obergrenze, stand.admin_wert, stand.wirksam) == (True, False, False)
    assert stand.dsfa_hinweis is None
    assert dienst.wirksam("herkunft_pruefen", Settings()) is False


def test_antworten_hinweis_obergrenze_aus_admin_wert_aus():
    """#760: Standard aus, bis die Datenschutzerklaerung den Satz hat."""
    dienst, _, _ = _dienst()
    stand = {s.name: s for s in dienst.stand(Settings())}["antworten_hinweis"]

    assert (stand.obergrenze, stand.admin_wert, stand.wirksam) == (False, False, False)
    assert stand.dsfa_hinweis is None


def test_sharepic_standard_aus_ohne_admin_wert():
    """Obergrenze standardmaessig an, ohne Admin-Wert trotzdem aus (#756)."""
    dienst, _, _ = _dienst()

    assert dienst.wirksam("sharepic", Settings()) is False
    dienst, _, _ = _dienst({"sharepic": True})
    assert dienst.wirksam("sharepic", Settings()) is True


def test_schalter_wirksam_nimmt_den_globalen_dienst():
    dienst, _, _ = _dienst()
    schalter_service_setzen(dienst)

    assert schalter_wirksam("punkte", Settings(punkte_aktiv=True)) is False


def test_stand_nach_gruppen_geordnet_jeder_schalter_in_einer_gruppe():
    from services.schalter_service import GRUPPEN, SCHALTER

    dienst, _, _ = _dienst()
    stand = dienst.stand(Settings())

    assert {s.name for s in stand} == set(SCHALTER)
    assert all(s.gruppe in GRUPPEN for s in stand)
    reihenfolge = [GRUPPEN.index(s.gruppe) for s in stand]
    assert reihenfolge == sorted(reihenfolge)
    gruppe = {s.name: s.gruppe for s in stand}
    assert gruppe["sharepic"] == "Grundfunktionen"
    # Unterschalter bei seiner Voraussetzung "gepostet"
    assert gruppe["gepostet_ohne_konto"] == gruppe["gepostet"] == "Grundfunktionen"
    assert gruppe["team_quests"] == "Teams"
    assert gruppe["naechster_schritt"] == "Spielgefühl"
    assert gruppe["rangliste"] == "Punkte & Anerkennung"


def test_wartet_auf_recht_nur_mit_hinweis_und_ohne_freigabe():
    dienst, _, _ = _dienst()
    stand = {s.name: s for s in dienst.stand(Settings())}

    assert stand["punkte"].wartet_auf_recht is True
    assert stand["teams_oeffentlich"].wartet_auf_recht is True
    # Teams: Hinweis steht, aber rechtlich freigegeben (25.11.)
    assert stand["teams"].dsfa_hinweis
    assert stand["teams"].wartet_auf_recht is False
    assert stand["sharepic"].wartet_auf_recht is False
