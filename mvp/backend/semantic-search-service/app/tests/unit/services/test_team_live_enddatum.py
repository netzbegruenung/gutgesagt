"""
Enddatum des Schalters team_live (Jura-Pruefpunkt 4, 28.11.2026): Standard aus, und nach
dem Tag in der Admin-Einstellung ``team_live_bis`` (Standard 2026-12-06, BDK-Ende,
deutsche Zeit) wirkt er nicht mehr, auch wenn Obergrenze und Admin-Wert an sind. Die
Admin-Seite zeigt das am Schalter an.
"""

from datetime import date
import pytest

from core.config import Settings
from services.einstellungen_service import (
    EINSTELLUNGEN,
    TEAM_LIVE_BIS,
    EinstellungenService,
    UngueltigerWert,
    datum_lesen,
    einstellungen_service_setzen,
    wert_bereinigen,
)
from services.schalter_service import (
    ENDDATUM,
    SCHALTER,
    SchalterService,
    _enddatum_aus_einstellungen,
)

pytestmark = pytest.mark.unit

AN = Settings(teams_aktiv=True, team_live_aktiv=True)
ENDE = date(2026, 12, 6)


def _dienst(heute, enddatum=lambda name: ENDE):
    return SchalterService(
        admin_werte_lesen=lambda: {"teams": True, "team_live": True},
        admin_wert_setzen=lambda *a: None,
        enddatum=enddatum,
        heute=lambda: heute,
    )


def test_standard_aus_und_bdk_ende():
    assert Settings.model_fields["team_live_aktiv"].default is False
    assert ENDDATUM == {"team_live": TEAM_LIVE_BIS}
    assert EINSTELLUNGEN[TEAM_LIVE_BIS].standard() == "2026-12-06"
    assert "BDK-Ende" in EINSTELLUNGEN[TEAM_LIVE_BIS].erklaerung


@pytest.mark.parametrize(
    "heute, wirkt",
    [(date(2026, 12, 4), True), (ENDE, True), (date(2026, 12, 7), False)],
)
def test_wirkt_bis_einschliesslich_ende(heute, wirkt):
    assert _dienst(heute).wirksam("team_live", AN) is wirkt


def test_andere_schalter_haben_kein_ende():
    assert _dienst(date(2030, 1, 1)).wirksam("teams", AN) is True


def test_admin_seite_zeigt_das_ende():
    stand = {s.name: s for s in _dienst(date(2026, 12, 7)).stand(AN)}

    assert stand["team_live"].admin_wert is True
    assert stand["team_live"].wirksam is False
    assert "Abgelaufen" in stand["team_live"].erklaerung
    assert "06.12.2026" in stand["team_live"].erklaerung
    assert "team_live_bis" in stand["team_live"].erklaerung
    # Vor dem Ende steht, wann er endet
    vorher = {s.name: s for s in _dienst(ENDE).stand(AN)}
    assert vorher["team_live"].erklaerung == (
        SCHALTER["team_live"].erklaerung
        + " Endet nach dem 06.12.2026 (Einstellung team_live_bis)."
    )
    assert vorher["team_live"].wirksam is True
    # Ohne Enddatum (andere Schalter) kein Vermerk
    assert vorher["teams"].erklaerung == SCHALTER["teams"].erklaerung


def test_enddatum_nicht_lesbar_wirkt_nicht():
    def kaputt(name):
        raise RuntimeError("db weg")

    dienst = _dienst(date(2026, 12, 4), enddatum=kaputt)

    assert dienst.wirksam("team_live", AN) is False
    assert (
        "nicht lesbar" in {s.name: s for s in dienst.stand(AN)}["team_live"].erklaerung
    )


@pytest.mark.parametrize("wert", ["morgen", "06.12.2026", "2026-13-01", "2026-2-1"])
def test_einstellung_nur_als_datum(wert):
    with pytest.raises(UngueltigerWert):
        wert_bereinigen(TEAM_LIVE_BIS, wert)


def test_einstellung_gueltig():
    assert wert_bereinigen(TEAM_LIVE_BIS, " 2026-12-07 ") == "2026-12-07"
    assert datum_lesen("2026-12-07") == date(2026, 12, 7)


@pytest.mark.parametrize(
    "gespeichert, erwartet",
    [({}, ENDE), ({TEAM_LIVE_BIS: "2026-12-10"}, date(2026, 12, 10))],
)
def test_enddatum_aus_den_einstellungen(gespeichert, erwartet):
    einstellungen_service_setzen(
        EinstellungenService(lesen=lambda: gespeichert, setzen=lambda *a: None)
    )
    try:
        assert _enddatum_aus_einstellungen("team_live") == erwartet
    finally:
        einstellungen_service_setzen(None)


def test_unlesbarer_gespeicherter_wert_wirkt_nicht():
    einstellungen_service_setzen(
        EinstellungenService(
            lesen=lambda: {TEAM_LIVE_BIS: "kaputt"}, setzen=lambda *a: None
        )
    )
    try:
        assert _enddatum_aus_einstellungen("team_live") == date.min
    finally:
        einstellungen_service_setzen(None)


def test_funktionen_meldet_nach_dem_ende_aus():
    """Auch die Datenschutzerklaerung blendet die Saetze nach dem Ende wieder aus."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.v1.funktionen import router
    from dependencies import get_settings
    from services.schalter_service import schalter_service_setzen

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/funktionen")
    app.dependency_overrides[get_settings] = lambda: AN
    schalter_service_setzen(_dienst(date(2026, 12, 7)))
    try:
        antwort = TestClient(app).get("/api/v1/funktionen").json()["funktionen"]
    finally:
        schalter_service_setzen(None)

    assert antwort["teams"] is True
    assert antwort["team_live"] is False
