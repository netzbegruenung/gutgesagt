"""
Teams ueber Einladungen: TeamService und die Teamwege im EinladungService, mit
gemocktem Repository. Geprueft wird, dass nichts ohne Schalter und ohne Einwilligung
gespeichert wird, dass ein vorhandenes Konto beim Einloesen kein Team bekommt und
dass Teams am Namen nur mit eigenem Schalter und eigener Einwilligung erscheinen.
"""

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.config import Settings
from domain.interfaces.konten_im_realm import KontoErgebnis
from domain.teams import (
    EINWILLIGUNG_KENNUNG,
    EINWILLIGUNG_WORTLAUTE,
    OEFFENTLICH_KENNUNG,
    UnbekannterWortlaut,
)
from repositories.team_repository import Mitgliedschaft, NichtEinloesbar
from services.einladung_service import (
    EinladungOhneTeam,
    EinladungService,
    EinladungUngueltig,
)
from services.einstellungen_service import (
    EinstellungenService,
    UngueltigerWert,
    wert_bereinigen,
)
from services.team_service import (
    OeffentlichAus,
    SaisonUnbekannt,
    Team,
    TeamService,
    TeamsAus,
)
from utils.utc_tag import heute_utc

pytestmark = pytest.mark.unit

HEUTE = date(2026, 11, 25)
JETZT = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
CODE = "Ab3dEf6hIj9kLm2n"
TEAM = Team("BDK 26 Berlin", "vogel", "2026")
AN = Settings(teams_aktiv=True, teams_oeffentlich_aktiv=True)
NUR_TEAMS = Settings(teams_aktiv=True, teams_oeffentlich_aktiv=False)
AUS = Settings(teams_aktiv=False, teams_oeffentlich_aktiv=True)


def _mitgliedschaft(nummer=37):
    return Mitgliedschaft(
        id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
        team_name=TEAM.name,
        team_motiv=TEAM.motiv,
        saison=TEAM.saison,
        nummer=nummer,
        eingetreten_am=HEUTE,
    )


def _zeile(**werte):
    standard = dict(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        code=CODE,
        notiz="Teamlink",
        erlaubte_einloesungen=50,
        einloesungen=3,
        gueltig_bis=date(2026, 12, 31),
        abgeschaltet=False,
        angelegt_am=HEUTE,
        team_name=TEAM.name,
        team_motiv=TEAM.motiv,
        team_saison=TEAM.saison,
    )
    standard.update(werte)
    return SimpleNamespace(**standard)


@pytest.fixture
def team_repo():
    repo = Mock()
    repo.beitreten.return_value = (_mitgliedschaft(), True)
    repo.mitglieder_je_team.return_value = {(TEAM.name, TEAM.saison): 36}
    repo.letzte_nummer.return_value = 36
    repo.mitgliedschaft.return_value = None
    repo.oeffentliche_teams.return_value = {}
    return repo


def _teams(repo, settings=AN):
    return TeamService(repo, settings, saison=lambda: "2026", uhr=lambda: JETZT)


@pytest.fixture
def einladung_repo():
    repo = Mock()
    repo.einloesung_zaehlen.return_value = True
    repo.nach_code.return_value = _zeile()
    repo.anlegen.side_effect = lambda **w: _zeile(**w)
    return repo


@pytest.fixture
def konten():
    konten = Mock()
    konten.konto_anlegen.return_value = KontoErgebnis.ANGELEGT
    return konten


class TestSchalter:
    def test_teams_oeffentlich_wirkt_nur_mit_teams(self, team_repo):
        assert _teams(team_repo, AN).oeffentlich_wirksam() is True
        assert _teams(team_repo, AUS).oeffentlich_wirksam() is False
        assert _teams(team_repo, NUR_TEAMS).oeffentlich_wirksam() is False

    def test_ohne_schalter_kein_beitritt(self, team_repo):
        service = _teams(team_repo, AUS)
        with pytest.raises(TeamsAus):
            service.beitreten("konto-1", TEAM)
        team_repo.beitreten.assert_not_called()

    def test_eigene_teams_auch_ohne_schalter(self, team_repo):
        # Zum Verlassen (Widerruf) bleiben sie sichtbar.
        team_repo.meine.return_value = ["eine"]

        assert _teams(team_repo, AUS).meine("konto-1") == ["eine"]

    def test_verlassen_geht_auch_ohne_schalter(self, team_repo):
        team_repo.verlassen.return_value = True
        mid = uuid.uuid4()

        assert _teams(team_repo, AUS).verlassen("konto-1", mid) is True
        team_repo.verlassen.assert_called_once_with("konto-1", mid)


class TestBeitreten:
    def test_speichert_kennung_des_wortlauts_und_zeitpunkt(self, team_repo):
        mitgliedschaft, neu = _teams(team_repo).beitreten(
            "konto-1", TEAM, code=CODE, heute=HEUTE
        )

        assert neu is True and mitgliedschaft.nummer == 37
        team_repo.beitreten.assert_called_once_with(
            konto="konto-1",
            team_name=TEAM.name,
            team_motiv=TEAM.motiv,
            saison=TEAM.saison,
            einwilligung_kennung=EINWILLIGUNG_KENNUNG,
            zeitpunkt=JETZT,
            heute=HEUTE,
            code=CODE,
        )

    def test_speichert_die_gezeigte_kennung(self, team_repo):
        _teams(team_repo).beitreten(
            "konto-1", TEAM, einwilligung_kennung="team-2026-11-26"
        )

        kw = team_repo.beitreten.call_args.kwargs
        assert kw["einwilligung_kennung"] == "team-2026-11-26"

    def test_fruehere_kennung_gilt_nicht_fuer_neue_einwilligungen(self, team_repo):
        # Neuer Wortlaut, alte Seite noch offen: Die fruehere Kennung steht noch in
        # EINWILLIGUNG_WORTLAUTE (vorhandene Nachweise), traegt aber keine neue
        # Einwilligung; die Person sieht beim naechsten Versuch den neuen Wortlaut.
        assert "team-2026-11-25" in EINWILLIGUNG_WORTLAUTE
        with pytest.raises(UnbekannterWortlaut):
            _teams(team_repo).beitreten(
                "konto-1", TEAM, einwilligung_kennung="team-2026-11-25"
            )
        team_repo.beitreten.assert_not_called()

    def test_unbekannte_kennung_speichert_nichts(self, team_repo):
        with pytest.raises(UnbekannterWortlaut):
            _teams(team_repo).beitreten(
                "konto-1", TEAM, einwilligung_kennung="erfunden"
            )
        team_repo.beitreten.assert_not_called()

    def test_info_zeigt_mitglieder_und_naechste_nummer(self, team_repo):
        info = _teams(team_repo).info(TEAM)

        assert info.mitglieder == 36
        assert info.naechste_nummer == 37
        assert info.eigene_nummer is None
        team_repo.mitgliedschaft.assert_not_called()

    def test_info_kennt_die_eigene_nummer(self, team_repo):
        team_repo.mitgliedschaft.return_value = _mitgliedschaft(12)

        assert _teams(team_repo).info(TEAM, "konto-1").eigene_nummer == 12

    def test_nach_kontoanlage_scheitert_still(self, team_repo):
        team_repo.beitreten.side_effect = RuntimeError("Datenbank weg")

        _teams(team_repo).nach_kontoanlage("konto-1", TEAM)  # kein Fehler

    def test_nach_kontoanlage_mit_oeffentlich(self, team_repo):
        _teams(team_repo).nach_kontoanlage("konto-1", TEAM, oeffentlich=True)

        team_repo.oeffentlich_setzen.assert_called_once_with(
            "konto-1", True, OEFFENTLICH_KENNUNG, JETZT
        )

    def test_nach_kontoanlage_oeffentlich_ohne_schalter_nicht(self, team_repo):
        _teams(team_repo, NUR_TEAMS).nach_kontoanlage("konto-1", TEAM, oeffentlich=True)

        team_repo.beitreten.assert_called_once()
        team_repo.oeffentlich_setzen.assert_not_called()


class TestOeffentlich:
    def test_ja_nur_mit_schalter(self, team_repo):
        with pytest.raises(OeffentlichAus):
            _teams(team_repo, NUR_TEAMS).oeffentlich_antworten(
                "konto-1", True, OEFFENTLICH_KENNUNG
            )
        team_repo.oeffentlich_setzen.assert_not_called()

    def test_nein_geht_immer(self, team_repo):
        _teams(team_repo, AUS).oeffentlich_antworten(
            "konto-1", False, OEFFENTLICH_KENNUNG
        )

        team_repo.oeffentlich_setzen.assert_called_once_with(
            "konto-1", False, OEFFENTLICH_KENNUNG, JETZT
        )

    def test_unbekannter_wortlaut(self, team_repo):
        with pytest.raises(UnbekannterWortlaut):
            _teams(team_repo).oeffentlich_antworten("konto-1", True, "erfunden")

    def test_pillen_ohne_schalter_fragen_die_datenbank_nicht(self, team_repo):
        assert _teams(team_repo, NUR_TEAMS).pillen(["konto-1"]) == {}
        team_repo.oeffentliche_teams.assert_not_called()

    def test_pillen_nur_aktuelle_saison(self, team_repo):
        team_repo.oeffentliche_teams.return_value = {"konto-1": [(TEAM.name, "vogel")]}

        pillen = _teams(team_repo).pillen(["konto-1", None, "konto-1"])

        assert pillen == {"konto-1": [(TEAM.name, "vogel")]}
        team_repo.oeffentliche_teams.assert_called_once_with(["konto-1"], "2026")

    def test_pillen_bei_fehler_leer(self, team_repo):
        team_repo.oeffentliche_teams.side_effect = RuntimeError("weg")

        assert _teams(team_repo).pillen(["konto-1"]) == {}


class TestEinladungMitTeam:
    def test_anlegen_ohne_schalter_ignoriert_das_team(self, einladung_repo, team_repo):
        service = EinladungService(einladung_repo, None, _teams(team_repo, AUS))

        service.anlegen("Teamlink", 5, date(2026, 12, 31), heute=HEUTE, team=TEAM)

        werte = einladung_repo.anlegen.call_args.kwargs
        assert werte["team_name"] is None and werte["team_saison"] is None

    def test_anlegen_mit_schalter_speichert_das_team(self, einladung_repo, team_repo):
        service = EinladungService(einladung_repo, None, _teams(team_repo))

        einladung = service.anlegen(
            "Teamlink", 5, date(2026, 12, 31), heute=HEUTE, team=TEAM
        )

        assert einladung.team == TEAM

    def test_einloesen_ohne_einwilligung_keine_mitgliedschaft(
        self, einladung_repo, team_repo, konten
    ):
        service = EinladungService(einladung_repo, konten, _teams(team_repo))

        service.einloesen(CODE, "neu@example.org", heute=HEUTE)

        konten.konto_anlegen.assert_called_once_with("neu@example.org", None, None)
        team_repo.beitreten.assert_not_called()

    def test_einloesen_mit_einwilligung_tritt_beim_anlegen_bei(
        self, einladung_repo, team_repo, konten
    ):
        def anlegen(email, vorname, nachname, bei_angelegt=None):
            bei_angelegt("neues-konto")
            return KontoErgebnis.ANGELEGT

        konten.konto_anlegen.side_effect = anlegen
        service = EinladungService(einladung_repo, konten, _teams(team_repo))

        service.einloesen(CODE, "neu@example.org", heute=HEUTE, team_einwilligung=True)

        kw = team_repo.beitreten.call_args.kwargs
        assert kw["konto"] == "neues-konto"
        assert kw["team_name"] == TEAM.name and kw["saison"] == TEAM.saison
        # Gezaehlt ist schon beim Einloesen, nicht noch einmal
        assert kw["code"] is None
        assert kw["einwilligung_kennung"] == EINWILLIGUNG_KENNUNG

    def test_einloesen_vorhandenes_konto_bekommt_kein_team(
        self, einladung_repo, team_repo, konten
    ):
        # Keycloak ruft bei_angelegt fuer ein vorhandenes Konto nicht auf.
        konten.konto_anlegen.return_value = KontoErgebnis.VORHANDEN
        service = EinladungService(einladung_repo, konten, _teams(team_repo))

        service.einloesen(CODE, "alt@example.org", heute=HEUTE, team_einwilligung=True)

        assert "bei_angelegt" in konten.konto_anlegen.call_args.kwargs
        team_repo.beitreten.assert_not_called()

    def test_einloesen_ohne_schalter_wie_bisher(
        self, einladung_repo, team_repo, konten
    ):
        service = EinladungService(einladung_repo, konten, _teams(team_repo, AUS))

        service.einloesen(CODE, "neu@example.org", heute=HEUTE, team_einwilligung=True)

        konten.konto_anlegen.assert_called_once_with("neu@example.org", None, None)

    def test_beitreten(self, einladung_repo, team_repo):
        service = EinladungService(einladung_repo, None, _teams(team_repo))

        team, mitgliedschaft, neu = service.beitreten(CODE, "konto-1", heute=HEUTE)

        assert team == TEAM and neu is True and mitgliedschaft.nummer == 37
        assert team_repo.beitreten.call_args.kwargs["code"] == CODE

    def test_beitreten_einladung_zaehlt_nicht_mehr(self, einladung_repo, team_repo):
        team_repo.beitreten.side_effect = NichtEinloesbar()
        service = EinladungService(einladung_repo, None, _teams(team_repo))

        with pytest.raises(EinladungUngueltig):
            service.beitreten(CODE, "konto-1", heute=HEUTE)

    def test_beitreten_unbekannter_code(self, einladung_repo, team_repo):
        einladung_repo.nach_code.return_value = None
        service = EinladungService(einladung_repo, None, _teams(team_repo))

        with pytest.raises(EinladungUngueltig):
            service.beitreten("falsch", "konto-1")

    def test_beitreten_ohne_team(self, einladung_repo, team_repo):
        einladung_repo.nach_code.return_value = _zeile(
            team_name=None, team_motiv=None, team_saison=None
        )
        service = EinladungService(einladung_repo, None, _teams(team_repo))

        with pytest.raises(EinladungOhneTeam):
            service.beitreten(CODE, "konto-1")

    def test_beitreten_ohne_schalter(self, einladung_repo, team_repo):
        service = EinladungService(einladung_repo, None, _teams(team_repo, AUS))

        with pytest.raises(TeamsAus):
            service.beitreten(CODE, "konto-1")

    def test_team_info_nur_fuer_einloesbare(self, einladung_repo, team_repo):
        einladung_repo.nach_code.return_value = _zeile(abgeschaltet=True)
        service = EinladungService(einladung_repo, None, _teams(team_repo))

        assert service.team_info(CODE, heute=HEUTE) is None
        assert service.team_info(CODE, "konto-1", heute=HEUTE) is None

    def test_team_info_nicht_einloesbar_fuer_mitglied(self, einladung_repo, team_repo):
        # "Schon dabei" auch nach Ablauf, aber nur fuer ein Mitglied.
        einladung_repo.nach_code.return_value = _zeile(abgeschaltet=True)
        team_repo.mitgliedschaft.return_value = SimpleNamespace(nummer=12)
        service = EinladungService(einladung_repo, None, _teams(team_repo))

        assert service.team_info(CODE, "konto-1", heute=HEUTE).eigene_nummer == 12

    def test_team_info_ohne_schalter_leer(self, einladung_repo, team_repo):
        service = EinladungService(einladung_repo, None, _teams(team_repo, AUS))

        assert service.team_info(CODE, heute=HEUTE) is None


class TestEinstellungen:
    def test_standard_ist_das_laufende_jahr(self):
        service = EinstellungenService(lesen=lambda: {}, setzen=Mock())

        assert service.wert("aktuelle_saison") == str(heute_utc().year)

    def test_gesetzter_wert_gilt(self):
        werte = {}
        service = EinstellungenService(
            lesen=lambda: dict(werte),
            setzen=lambda n, w, a: werte.__setitem__(n, w),
        )

        assert service.setzen("aktuelle_saison", "  Saison  2027 ", "admin") == (
            "Saison 2027"
        )
        assert service.wert("aktuelle_saison") == "Saison 2027"

    @pytest.mark.parametrize(
        "wert", ["", "   ", "x" * 21, "20\x0026", "<b>26</b>", "A & B"]
    )
    def test_ungueltige_werte(self, wert):
        with pytest.raises(UngueltigerWert):
            wert_bereinigen("aktuelle_saison", wert)

    def test_schraegstrich_wie_bei_den_saisons(self):
        assert wert_bereinigen("aktuelle_saison", "Winter 26/27") == "Winter 26/27"

    def test_datenbank_weg_gilt_standard(self):
        def kaputt():
            raise RuntimeError("weg")

        service = EinstellungenService(lesen=kaputt, setzen=Mock())

        assert service.wert("aktuelle_saison")


class TestTeamFestlegen:
    """Befund 6: Ein Teamlink verweist auf die Saison per ID, wenn es sie gibt."""

    from domain.saisons import Saison as _Saison

    WINTER = _Saison(
        uuid.uuid4(), "Winter 26/27", date(2026, 11, 27), date(2027, 2, 24), 5
    )

    def _dienst(self, saisons):
        return TeamService(
            Mock(),
            saison=lambda: "2026",
            vorschlag=lambda: "Winter 26/27",
            saisons=lambda: saisons,
        )

    def test_vorhandene_saison_bekommt_ihre_id(self):
        team = self._dienst([self.WINTER]).team_festlegen(
            "BDK", "vogel", "Winter 26/27"
        )
        assert (team.saison, team.saison_id) == ("Winter 26/27", self.WINTER.id)

    def test_ohne_angabe_der_vorschlag_mit_id(self):
        team = self._dienst([self.WINTER]).team_festlegen("BDK", "vogel", None)
        assert team.saison_id == self.WINTER.id

    def test_unbekannte_saison_bei_vorhandenen_saisons(self):
        with pytest.raises(SaisonUnbekannt):
            self._dienst([self.WINTER]).team_festlegen("BDK", "vogel", "2026")

    def test_ohne_saisons_gilt_der_name_wie_bisher(self):
        team = self._dienst([]).team_festlegen("BDK", "vogel", "2026")
        assert (team.saison, team.saison_id) == ("2026", None)

    def test_id_zaehlt_nicht_zur_identitaet(self):
        mit = self._dienst([self.WINTER]).team_festlegen("BDK", "vogel", "Winter 26/27")
        assert mit == Team("BDK", "vogel", "Winter 26/27")
