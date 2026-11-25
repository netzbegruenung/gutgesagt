"""
SaisonService (#782): laufende Saison als aktuelle Saison der Teams auch ohne Schalter,
Vorschlag fuer Teamlinks (laufende oder naechste geplante),
Balken erst ab der Schwelle und nur mit Summen abgeschlossener Wochen, Stand fuer
Admins, Cache wird nach dem Schreiben verworfen. Repository als Attrappe.
"""

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from core.config import Settings
from domain.saisons import Saison, SaisonGesperrt, SaisonZustand
from services.einstellungen_service import aktuelle_saison, saison_vorschlag
from services.saison_service import SaisonService, saison_service_setzen
from utils.utc_tag import heute_utc

pytestmark = pytest.mark.unit

MO = date(2026, 11, 30)
HEUTE = MO + timedelta(weeks=3, days=2)  # Mittwoch der vierten Saisonwoche
SAISON = Saison(uuid.uuid4(), "Winter 26", MO, MO + timedelta(weeks=8), 1000)
STARK = {MO - timedelta(weeks=i): 30 for i in range(1, 4)}


def _service(saisons=(SAISON,), zahlen=None, wirksam=True, **settings):
    repository = MagicMock()
    repository.alle.return_value = list(saisons)
    gefragt = []

    def wochen(von, laufende):
        gefragt.append((von, laufende))
        return dict(zahlen or {})

    service = SaisonService(
        repository,
        wochen,
        einstellungen=Settings(**settings),
        wirksam=lambda _s: wirksam,
    )
    return service, repository, gefragt


class TestFuerTeams:
    def test_laufende_saison_bei_schalter_an(self):
        service, _, _ = _service()
        assert service.saison_fuer_teams(HEUTE) == "Winter 26"

    def test_schalter_aus_gilt_trotzdem(self):
        # Der Schalter steuert nur den Balken: Sonst kippten die Teams der laufenden
        # Saison beim Ausschalten unter "Vergangene Saisons"
        service, _, _ = _service(wirksam=False)
        assert service.saison_fuer_teams(HEUTE) == "Winter 26"

    def test_vor_der_ersten_saison(self):
        service, _, _ = _service()
        assert service.saison_fuer_teams(MO - timedelta(days=1)) is None

    def test_luecke_behaelt_die_beendete_saison(self):
        # Einstellung "2026" und alte Teams duerfen in der Luecke nicht zurueckkommen
        naechste = Saison(
            uuid.uuid4(),
            "Frühjahr 27",
            SAISON.ende + timedelta(days=15),
            SAISON.ende + timedelta(days=90),
            10,
        )
        service, _, _ = _service(saisons=(naechste, SAISON))
        assert service.saison_fuer_teams(SAISON.ende + timedelta(days=1)) == "Winter 26"
        assert service.saison_fuer_teams(naechste.beginn) == "Frühjahr 27"

    def test_hinweis_auch_in_der_luecke(self, einstellungen_ohne_datenbank):
        from api.v1.schalter import _hinweis

        heute = heute_utc()
        vorbei = Saison(
            uuid.uuid4(),
            "Winter 26",
            heute - timedelta(days=30),
            heute - timedelta(days=2),
            5,
        )
        saison_service_setzen(_service(saisons=(vorbei,))[0])
        assert "„Winter 26“" in _hinweis("aktuelle_saison")
        assert _hinweis("teams") is None
        saison_service_setzen(_service(saisons=(vorbei,), wirksam=False)[0])
        assert "„Winter 26“" in _hinweis("aktuelle_saison")
        saison_service_setzen(_service(saisons=())[0])
        assert _hinweis("aktuelle_saison") is None

    def test_hinweis_vor_der_ersten_saison(self, einstellungen_ohne_datenbank):
        from api.v1.schalter import _hinweis

        heute = heute_utc()
        geplant = Saison(
            uuid.uuid4(),
            "Winter 26/27",
            heute + timedelta(days=5),
            heute + timedelta(days=95),
            5,
        )
        saison_service_setzen(_service(saisons=(geplant,))[0])
        hinweis = _hinweis("aktuelle_saison")
        assert "Gilt bis zum Beginn der Saison „Winter 26/27“" in hinweis
        assert "Vorschlag" in hinweis

    def test_datenbank_weg_heisst_einstellung(self):
        service, repository, _ = _service()
        repository.alle.side_effect = RuntimeError("weg")
        assert service.saison_fuer_teams(HEUTE) is None

    def test_aktuelle_saison_der_teams(self, einstellungen_ohne_datenbank):
        einstellungen_ohne_datenbank["aktuelle_saison"] = "2026"
        heute = heute_utc()
        jetzt = Saison(uuid.uuid4(), "Winter 26", heute, heute + timedelta(days=9), 5)
        service, _, _ = _service(saisons=(jetzt,))
        saison_service_setzen(service)
        assert aktuelle_saison() == "Winter 26"
        saison_service_setzen(_service(saisons=(jetzt,), wirksam=False)[0])
        assert aktuelle_saison() == "Winter 26"
        saison_service_setzen(_service(saisons=())[0])
        assert aktuelle_saison() == "2026"


class TestVorschlag:
    WINTER = Saison(uuid.uuid4(), "Winter 26/27", MO, MO + timedelta(days=90), 1000)
    FRUEHJAHR = Saison(
        uuid.uuid4(),
        "Frühjahr 27",
        MO + timedelta(days=91),
        MO + timedelta(days=182),
        1000,
    )

    def test_laufende(self):
        service, _, _ = _service(saisons=(self.FRUEHJAHR, self.WINTER))
        assert service.vorschlag(MO + timedelta(days=10)) == "Winter 26/27"

    def test_vor_dem_beginn_die_naechste(self):
        # BDK-Teamlink vor dem 30.11.: schon der Name der Saison, in die das Team faellt
        service, _, _ = _service(saisons=(self.FRUEHJAHR, self.WINTER))
        assert service.vorschlag(MO - timedelta(days=5)) == "Winter 26/27"

    def test_schalter_aus_gilt_trotzdem(self):
        service, _, _ = _service(saisons=(self.WINTER,), wirksam=False)
        assert service.vorschlag(MO - timedelta(days=5)) == "Winter 26/27"

    def test_ohne_laufende_und_geplante_keiner(self):
        service, _, _ = _service(saisons=(self.WINTER,))
        assert service.vorschlag(self.WINTER.ende + timedelta(days=1)) is None

    def test_datenbank_weg_keiner(self):
        service, repository, _ = _service()
        repository.alle.side_effect = RuntimeError("weg")
        assert service.vorschlag(HEUTE) is None

    def test_saison_vorschlag_mit_ersatz(self, einstellungen_ohne_datenbank):
        einstellungen_ohne_datenbank["aktuelle_saison"] = "2026"
        heute = heute_utc()
        geplant = Saison(
            uuid.uuid4(),
            "Winter 26/27",
            heute + timedelta(days=5),
            heute + timedelta(days=95),
            5,
        )
        saison_service_setzen(_service(saisons=(geplant,))[0])
        # Vor dem Beginn: Vorschlag schon die Saison, aktuell noch die Einstellung
        assert saison_vorschlag() == "Winter 26/27"
        assert aktuelle_saison() == "2026"
        saison_service_setzen(_service(saisons=())[0])
        assert saison_vorschlag() == "2026"


class TestBalken:
    def test_unter_der_schwelle_kein_balken(self):
        service, _, _ = _service(zahlen={MO: 30, MO + timedelta(weeks=1): 24})
        assert service.balken(HEUTE) is None

    def test_ab_der_schwelle_summe_abgeschlossener_wochen(self):
        zahlen = {
            **STARK,
            MO: 30,
            MO + timedelta(weeks=1): 40,
            MO + timedelta(weeks=2): 50,
            MO + timedelta(weeks=3): 9,  # laufend
        }
        service, _, _ = _service(zahlen=zahlen)
        balken = service.balken(HEUTE)
        assert balken is not None
        assert (balken.name, balken.ziel, balken.erreicht) == ("Winter 26", 1000, 120)

    def test_schwelle_konfigurierbar(self):
        service, _, _ = _service(
            zahlen={MO: 3},
            saison_ziel_schwelle_menschen=2,
            saison_ziel_schwelle_wochen=1,
        )
        assert service.balken(HEUTE).erreicht == 3

    def test_ohne_laufende_saison_kein_balken(self):
        service, _, _ = _service(saisons=(), zahlen=STARK)
        assert service.balken(HEUTE) is None

    def test_cache_fragt_nicht_bei_jedem_aufruf(self):
        service, repository, gefragt = _service(zahlen=STARK)
        service.balken(HEUTE)
        service.balken(HEUTE)
        assert len(gefragt) == 1
        assert repository.alle.call_count == 1


class TestAdmin:
    def test_stand(self):
        alt = Saison(
            uuid.uuid4(),
            "Herbst 26",
            MO - timedelta(weeks=8),
            MO - timedelta(days=1),
            50,
        )
        zahlen = {**STARK, MO: 10, MO + timedelta(weeks=3): 4}
        service, _, _ = _service(saisons=(SAISON, alt), zahlen=zahlen)
        stand = service.admin_stand(HEUTE)
        laufend, vorbei = stand.saisons
        assert laufend.zustand is SaisonZustand.LAUFEND
        assert (laufend.erreicht, laufend.laufende_woche) == (10, 4)
        assert vorbei.zustand is SaisonZustand.VORBEI
        assert (vorbei.erreicht, vorbei.laufende_woche) == (90, None)
        assert stand.schwelle_erreicht
        assert (stand.schwelle_menschen, stand.schwelle_wochen) == (25, 3)

    def test_schreiben_verwirft_cache(self):
        service, repository, _ = _service()
        assert service.laufende(HEUTE) == SAISON
        repository.alle.return_value = []
        service.anlegen(
            "Frühjahr 27",
            HEUTE + timedelta(weeks=9),
            HEUTE + timedelta(weeks=20),
            500,
            heute=HEUTE,
        )
        assert service.laufende(HEUTE) is None

    def test_anlegen_rueckwirkend_gesperrt(self):
        service, repository, _ = _service()
        with pytest.raises(SaisonGesperrt):
            service.anlegen("Alt", HEUTE - timedelta(days=1), HEUTE, 5, heute=HEUTE)
        repository.anlegen.assert_not_called()

    def test_aendern_prueft_unter_der_sperre(self):
        service, repository, _ = _service()

        def aendern(saison_id, eingabe, pruefen):
            pruefen(SAISON)
            return SAISON

        repository.aendern.side_effect = aendern
        with pytest.raises(SaisonGesperrt):
            service.aendern(
                SAISON.id, "Anders", SAISON.beginn, SAISON.ende, 5, heute=HEUTE
            )
