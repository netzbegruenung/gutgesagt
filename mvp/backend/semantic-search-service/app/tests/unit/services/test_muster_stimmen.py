"""
Gegenseitige Zustimmungen in den Muster-Hinweisen (Schalter ``muster_stimmen``,
Entscheidung Maintainer 27.11., Wortlaut spielgefuehl-2026-11-27, seit der juristischen
Vorgabe vom 27.11. in der Fassung spielgefuehl-2026-11-28).

Geprueft: die Wortlaute und wann sie gelten, wer neu gefragt wird, dass Zustimmungen
nur bei Paaren mit beiderseitiger Einwilligung zu -27 oder -28 gemeldet und gezeigt
werden, dass Ablehnungen nicht zaehlen, der Schalter und der Widerruf. Das Erkennen
im Fenster (Schwelle) pruefen tests/integration/test_muster_hinweise.py gegen
PostgreSQL.
"""

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.v1.voting as voting_module
from api.v1.funktionen import router as funktionen_router
from api.v1.metrics import router as metrics_router
from api.v1.spielgefuehl import router as spielgefuehl_router
from core.config import Settings
from dependencies import (
    get_beitrag_laden,
    get_muster_hinweise_service,
    get_settings,
    get_voting_service,
)
from domain.models.vote import VoteResponse
from domain.spielgefuehl import (
    AKTUELLER_WORTLAUT,
    GELTENDE_WORTLAUTE,
    STIMMEN_WORTLAUTE,
    WORTLAUTE,
    Stufe,
    UnbekannterWortlaut,
    neu_fragen,
    stimmen_eingewilligt,
)
from repositories.muster_hinweis_repository import NUTZUNG, ZUSTIMMUNG, MusterHinweis
from repositories.spielgefuehl_repository import SpielgefuehlAntwort
from services.muster_hinweise_service import MusterHinweiseService
from services.schalter_service import SchalterService, schalter_service_setzen
from services.spielgefuehl_service import (
    KeinWiderruf,
    SpielgefuehlService,
    spielgefuehl_service_setzen,
)

pytestmark = pytest.mark.unit

ALT = "spielgefuehl-2026-11-26"
NEU = "spielgefuehl-2026-11-27"
AKTUELL = AKTUELLER_WORTLAUT
TAG = date(2026, 11, 27)
ADMIN = {"X-User": "admin-1", "X-Is-Admin": "true"}

# Alle Obergrenzen, die muster_stimmen braucht (die Admin-Werte setzt das Autouse-
# Fixture schalter_admin_alle_an auf an)
STIMMEN_AN = dict(
    punkte_aktiv=True, spielgefuehl_buehne_aktiv=True, muster_stimmen_aktiv=True
)


def _antwort(stufe: Stufe, wortlaut: str) -> SpielgefuehlAntwort:
    return SpielgefuehlAntwort(stufe, False, wortlaut, datetime.now(timezone.utc))


class TestWortlaut:
    def test_kennungen(self):
        assert AKTUELL == "spielgefuehl-2026-11-28"
        assert STIMMEN_WORTLAUTE == {NEU, AKTUELL}

    def test_in_minus_27_aendert_sich_nur_der_absatz_zu_absprachen(self):
        alt, neu = WORTLAUTE[ALT], WORTLAUTE[NEU]
        assert neu.stufen == alt.stufen
        assert neu.einleitung == alt.einleitung
        assert neu.fuss == alt.fuss
        assert neu.absprachen == (
            "Für ‚Nur für mich‘ und ‚In der Saison-Rangliste mitspielen‘ willige ich "
            "außerdem ein: Damit Punkte nicht durch Absprachen entstehen, prüft Gut "
            "gesagt, ob sich zwei Konten auffällig oft gegenseitig nutzen oder einander "
            "zustimmen. Fällt das auf, sehen die Administratorinnen und Administratoren "
            "einen Hinweis mit den Kennungen beider Konten; an Punkten und Rangliste "
            "ändert das nichts."
        )

    def test_der_alte_wortlaut_bleibt_wortgleich(self):
        assert "einander zustimmen" not in WORTLAUTE[ALT].absprachen

    def test_alle_drei_gelten_fuer_das_was_sie_nennen(self):
        assert GELTENDE_WORTLAUTE == {ALT, NEU, AKTUELL}

    @pytest.mark.parametrize(
        "wortlaut, stufe, erwartet",
        [
            (ALT, Stufe.FUER_MICH, True),
            (ALT, Stufe.RANGLISTE, True),
            (NEU, Stufe.FUER_MICH, True),
            (NEU, Stufe.RANGLISTE, True),
            (ALT, Stufe.AUS, False),
            (NEU, Stufe.AUS, False),
            (AKTUELL, Stufe.FUER_MICH, False),
            (AKTUELL, Stufe.RANGLISTE, False),
        ],
    )
    def test_neu_fragen_unabhaengig_vom_schalter(self, wortlaut, stufe, erwartet):
        assert neu_fragen(wortlaut, stufe) is erwartet

    @pytest.mark.parametrize(
        "wortlaut, stufe, erwartet",
        [
            (NEU, Stufe.FUER_MICH, True),
            (NEU, Stufe.RANGLISTE, True),
            (AKTUELL, Stufe.FUER_MICH, True),
            (AKTUELL, Stufe.RANGLISTE, True),
            (NEU, Stufe.AUS, False),
            (AKTUELL, Stufe.AUS, False),
            # Einwilligungen unter -26 reichen nicht
            (ALT, Stufe.RANGLISTE, False),
            (ALT, Stufe.FUER_MICH, False),
            (AKTUELL, None, False),
        ],
    )
    def test_stimmen_eingewilligt(self, wortlaut, stufe, erwartet):
        assert stimmen_eingewilligt(wortlaut, stufe) is erwartet


class TestSpielgefuehlService:
    def _dienst(self, antwort, **weitere):
        repository = MagicMock()
        repository.lesen.return_value = antwort
        dienst = SpielgefuehlService(
            repository,
            lambda: set(),
            lambda user_id: False,
            **weitere,
        )
        return dienst, repository

    @pytest.mark.parametrize("wortlaut", [ALT, NEU])
    @pytest.mark.parametrize("stufe", [Stufe.FUER_MICH, Stufe.RANGLISTE])
    def test_minus_26_und_27_werden_neu_gefragt(self, wortlaut, stufe):
        dienst, _ = self._dienst(_antwort(stufe, wortlaut))

        assert dienst.stand("kim-1").stufe is None

    def test_aktueller_wortlaut_bleibt(self):
        dienst, _ = self._dienst(_antwort(Stufe.RANGLISTE, AKTUELL))

        assert dienst.stand("kim-1").stufe is Stufe.RANGLISTE

    @pytest.mark.parametrize("wortlaut", [ALT, NEU])
    def test_aus_wird_nicht_neu_gefragt(self, wortlaut):
        dienst, _ = self._dienst(_antwort(Stufe.AUS, wortlaut))

        assert dienst.stand("kim-1").stufe is Stufe.AUS

    @pytest.mark.parametrize("wortlaut", [ALT, NEU])
    def test_nur_der_aktuelle_wortlaut(self, wortlaut):
        dienst, repository = self._dienst(None)

        with pytest.raises(UnbekannterWortlaut):
            dienst.antworten("kim-1", Stufe.FUER_MICH, None, wortlaut)
        dienst.antworten("kim-1", Stufe.FUER_MICH, None, AKTUELL)

        repository.antworten.assert_called_once_with(
            "kim-1", Stufe.FUER_MICH, False, AKTUELL, None
        )

    def test_aus_geht_zu_jedem_wortlaut(self):
        dienst, _ = self._dienst(None)

        dienst.antworten("kim-1", Stufe.AUS, None, ALT)

    def test_aus_loescht_alle_hinweise(self):
        alle = Mock()
        dienst, _ = self._dienst(
            _antwort(Stufe.FUER_MICH, NEU), hinweise_vergessen=alle
        )

        dienst.antworten("kim-1", Stufe.AUS, None, AKTUELL)

        alle.assert_called_once_with("kim-1")

    @pytest.mark.parametrize("wortlaut", [ALT, NEU])
    def test_widerruf_ohne_schalter_behaelt_den_alten_wortlaut(self, wortlaut):
        """Ohne Schalter sieht die Person -28 nicht: keine Einwilligung zu -28."""
        dienst, repository = self._dienst(_antwort(Stufe.RANGLISTE, wortlaut))

        dienst.antworten("kim-1", Stufe.FUER_MICH, None, AKTUELL, widerruf=True)

        repository.antworten.assert_called_once_with(
            "kim-1", Stufe.FUER_MICH, False, wortlaut, None
        )

    @pytest.mark.parametrize(
        "vorher", [None, _antwort(Stufe.FUER_MICH, ALT), _antwort(Stufe.AUS, ALT)]
    )
    def test_widerruf_ohne_schalter_nie_gleich_oder_hoeher(self, vorher):
        dienst, repository = self._dienst(vorher)

        with pytest.raises(KeinWiderruf):
            dienst.antworten("kim-1", Stufe.FUER_MICH, None, AKTUELL, widerruf=True)
        repository.antworten.assert_not_called()

    def test_widerruf_aus_mit_jedem_wortlaut(self):
        dienst, repository = self._dienst(_antwort(Stufe.RANGLISTE, ALT))

        dienst.antworten("kim-1", Stufe.AUS, None, AKTUELL, widerruf=True)

        repository.antworten.assert_called_once_with(
            "kim-1", Stufe.AUS, False, AKTUELL, None
        )

    def test_herabstufen_behaelt_die_hinweise(self):
        alle = Mock()
        dienst, _ = self._dienst(
            _antwort(Stufe.RANGLISTE, AKTUELL), hinweise_vergessen=alle
        )

        dienst.antworten("kim-1", Stufe.FUER_MICH, None, AKTUELL)

        alle.assert_not_called()


def _hinweis(a: str, b: str, art: str = NUTZUNG) -> MusterHinweis:
    return MusterHinweis(a, b, 1, TAG, TAG, art)


class TestMusterHinweiseService:
    def test_zustimmung_melden_mit_eigener_art_und_eigenem_pruefwert(self):
        repository = Mock()
        dienst = MusterHinweiseService(repository)
        moment = datetime(2026, 11, 27, 12, tzinfo=timezone.utc)

        dienst.zustimmung_melden("kim-1", "bo-2", moment)
        dienst.nutzung_melden("kim-1", "bo-2", moment)

        zustimmung, nutzung = repository.nutzung_merken.call_args_list
        assert zustimmung.kwargs["art"] == ZUSTIMMUNG
        assert nutzung.kwargs["art"] == NUTZUNG
        # Gleiches Fenster, aber nie derselbe Pruefwert: Eine Nutzung trifft nie auf
        # eine Zustimmung der Gegenrichtung.
        assert zustimmung.kwargs["fenster_ab"] == nutzung.kwargs["fenster_ab"]
        assert zustimmung.args[0] != nutzung.args[0]
        assert not set(zustimmung.args[1]) & set(nutzung.args[1])

    @pytest.mark.parametrize(
        "von, an", [("kim-1", "kim-1"), (None, "bo-2"), ("kim-1", None)]
    )
    def test_zustimmung_ohne_paar_meldet_nichts(self, von, an):
        repository = Mock()

        MusterHinweiseService(repository).zustimmung_melden(von, an)

        repository.nutzung_merken.assert_not_called()

    def test_hinweise_aus_zustimmungen_nur_mit_beiden_im_neuen_wortlaut(self):
        repository = Mock()
        repository.hinweise.return_value = [
            _hinweis("bo-2", "kim-1", ZUSTIMMUNG),
            _hinweis("ali-3", "kim-1", ZUSTIMMUNG),
            _hinweis("ali-3", "kim-1", NUTZUNG),
        ]
        alle = {"bo-2", "kim-1", "ali-3"}

        hinweise = MusterHinweiseService(repository).hinweise(
            lambda ks: alle, lambda ks: {"bo-2", "kim-1"}
        )

        assert hinweise == [
            _hinweis("bo-2", "kim-1", ZUSTIMMUNG),
            _hinweis("ali-3", "kim-1", NUTZUNG),
        ]

    def test_ohne_filter_fuer_zustimmungen_keine_zustimmungen(self):
        repository = Mock()
        repository.hinweise.return_value = [
            _hinweis("bo-2", "kim-1", ZUSTIMMUNG),
            _hinweis("bo-2", "kim-1", NUTZUNG),
        ]

        hinweise = MusterHinweiseService(repository).hinweise(lambda ks: set(ks))

        assert hinweise == [_hinweis("bo-2", "kim-1", NUTZUNG)]

    def test_zustimmungen_brauchen_auch_die_punkte_einwilligung(self):
        repository = Mock()
        repository.hinweise.return_value = [_hinweis("bo-2", "kim-1", ZUSTIMMUNG)]

        hinweise = MusterHinweiseService(repository).hinweise(
            lambda ks: {"bo-2"}, lambda ks: {"bo-2", "kim-1"}
        )

        assert hinweise == []

    def test_vergessen_nur_zustimmungen(self):
        repository = Mock()

        MusterHinweiseService(repository).vergessen("kim-1", art=ZUSTIMMUNG)

        repository.vergessen.assert_called_once_with("kim-1", art=ZUSTIMMUNG)


class TestAbgleichImLoeschlauf:
    """
    Bedingung Jura zu #863 (Art. 17): Der Loeschlauf loescht alle Hinweise, bei denen
    nicht mehr beide Konten wirksam eingewilligt haben, auch einen, der waehrend
    eines Widerrufs entstand.
    """

    PAARE = [
        ("bo-2", "kim-1", NUTZUNG),
        ("ali-3", "kim-1", NUTZUNG),
        ("bo-2", "kim-1", ZUSTIMMUNG),
        ("ali-3", "bo-2", ZUSTIMMUNG),
    ]

    def _dienst(self, punkte, stimmen, stand_sichern=lambda: None):
        repository = Mock()
        repository.paare.return_value = list(self.PAARE)
        repository.paare_verwerfen_vor.return_value = 0
        repository.loeschen_vor.return_value = 0
        repository.loeschen_paare.side_effect = lambda paare: len(paare)
        dienst = MusterHinweiseService(
            repository,
            eingewilligte=(
                punkte if callable(punkte) else (lambda ks: set(ks) & punkte)
            ),
            stimmen_eingewilligte=lambda ks: set(ks) & stimmen,
            stand_sichern=stand_sichern,
        )
        return dienst, repository

    def _geloescht(self, repository):
        return [p for c in repository.loeschen_paare.call_args_list for p in c.args[0]]

    def test_je_art_die_eigene_bedingung(self):
        # ali-3: Punkte ja, aber nicht -27; kim-1 nach einem Widerruf ohne -27
        dienst, repository = self._dienst(
            punkte={"bo-2", "kim-1"}, stimmen={"bo-2", "ali-3"}
        )

        assert dienst.ohne_einwilligung_loeschen() == 2

        assert self._geloescht(repository) == [
            ("ali-3", "kim-1", NUTZUNG),
            ("bo-2", "kim-1", ZUSTIMMUNG),
        ]

    def test_schalter_nicht_lesbar_nichts_geloescht(self):
        """Ein Lesefehler gaelte sonst als "alle aus" (bisheriges Modell)."""
        dienst, repository = self._dienst(
            punkte=set(), stimmen=set(), stand_sichern=Mock(side_effect=OSError("weg"))
        )

        dienst.fristen_anwenden(TAG)

        repository.loeschen_paare.assert_not_called()
        repository.loeschen_vor.assert_called_once()

    def test_scheitert_eine_bedingung_gilt_die_andere(self):
        dienst, repository = self._dienst(
            punkte=Mock(side_effect=RuntimeError("weg")), stimmen=set()
        )

        assert dienst.ohne_einwilligung_loeschen() == 2
        assert {p[2] for p in self._geloescht(repository)} == {ZUSTIMMUNG}

    def test_alle_eingewilligt_nichts_geloescht(self):
        alle = {"bo-2", "kim-1", "ali-3"}
        dienst, repository = self._dienst(punkte=alle, stimmen=alle)

        assert dienst.ohne_einwilligung_loeschen() == 0
        repository.loeschen_paare.assert_not_called()

    def test_ohne_bedingungen_kein_abgleich(self):
        repository = Mock()

        assert MusterHinweiseService(repository).ohne_einwilligung_loeschen() == 0
        repository.paare.assert_not_called()

    def test_der_taegliche_lauf_gleicht_ab(self):
        dienst, repository = self._dienst(punkte=set(), stimmen=set())

        dienst.fristen_anwenden(TAG)

        assert len(self._geloescht(repository)) == 4
        repository.loeschen_vor.assert_called_once()

    def test_fehler_im_abgleich_kostet_die_fristen_nicht(self):
        dienst, repository = self._dienst(punkte=set(), stimmen=set())
        repository.paare.side_effect = RuntimeError("weg")

        dienst.fristen_anwenden(TAG)

        repository.loeschen_vor.assert_called_once()
        repository.paare_verwerfen_vor.assert_called_once()

    def test_dashboard_raeumt_nebenbei_auf(self):
        repository = Mock()
        repository.hinweise.return_value = [
            _hinweis(a, b, art) for a, b, art in self.PAARE
        ]
        alle = {"bo-2", "kim-1", "ali-3"}

        hinweise = MusterHinweiseService(repository).hinweise(
            lambda ks: set(ks) & {"bo-2", "kim-1"}, lambda ks: set(ks) & alle
        )

        assert hinweise == [
            _hinweis("bo-2", "kim-1", NUTZUNG),
            _hinweis("bo-2", "kim-1", ZUSTIMMUNG),
        ]
        # Geloescht nur, was die eigene Bedingung verfehlt: die Nutzung mit ali-3.
        # Die Zustimmung ali-3/bo-2 bleibt (ihre Bedingung gilt), wird aber nicht
        # gezeigt, weil ali-3 die Punkte-Einwilligung fehlt.
        repository.loeschen_paare.assert_called_once_with([("ali-3", "kim-1", NUTZUNG)])

    def test_dashboard_ohne_schalter_loescht_keine_zustimmungen(self):
        repository = Mock()
        repository.hinweise.return_value = [_hinweis("bo-2", "kim-1", ZUSTIMMUNG)]

        MusterHinweiseService(repository).hinweise(lambda ks: set(ks))

        repository.loeschen_paare.assert_not_called()

    def test_fehler_beim_aufraeumen_kostet_das_dashboard_nicht(self):
        repository = Mock()
        repository.hinweise.return_value = [_hinweis("bo-2", "kim-1")]
        repository.loeschen_paare.side_effect = RuntimeError("weg")

        assert MusterHinweiseService(repository).hinweise(lambda ks: set()) == []

    def test_produktion_hat_beide_bedingungen(self):
        from dependencies import get_muster_hinweise_service

        dienst = get_muster_hinweise_service()

        assert dienst._eingewilligte is not None
        assert dienst._stimmen_eingewilligte is not None


def test_strenges_lesen_wirft_statt_alle_aus():
    """Fuer den Abgleich: ein Lesefehler darf nicht als "alle Schalter aus" gelten."""
    dienst = SchalterService(Mock(side_effect=OSError("weg")), Mock())

    with pytest.raises(OSError):
        dienst.admin_werte_streng()
    # Das tolerante Lesen bleibt, wie es war
    assert dienst.admin_werte() == {}


def test_strenges_lesen_erneuert_den_cache():
    werte = {"punkte": True}
    lesen = Mock(side_effect=lambda: dict(werte))
    dienst = SchalterService(lesen, Mock())
    dienst.admin_werte()
    werte["punkte"] = False

    assert dienst.admin_werte_streng() == {"punkte": False}
    assert dienst.admin_werte() == {"punkte": False}
    assert lesen.call_count == 2


# --- Abstimmen (api/v1/voting.py) ---------------------------------------------------

BEITRAG = uuid.uuid4()


@pytest.fixture
def muster():
    return Mock()


@pytest.fixture
def abstimmen(muster, spielgefuehl_ohne_datenbank):
    """Abstimmen mit gemocktem Dienst; ``einstellungen`` aendert der Test."""
    einstellungen = {"settings": Settings(**STIMMEN_AN)}
    dienst = MagicMock()
    for methode in ("set_like", "set_dislike"):
        getattr(dienst, methode).return_value = VoteResponse(
            content_id=BEITRAG, vote_type=None, message="ok"
        )

    async def laden(content_id):
        return SimpleNamespace(id=content_id, original_author="bo-2")

    app = FastAPI()
    app.include_router(voting_module.router, prefix="/api/v1/voting")
    app.dependency_overrides[get_beitrag_laden] = lambda: laden
    app.dependency_overrides[get_voting_service] = lambda: dienst
    app.dependency_overrides[get_settings] = lambda: einstellungen["settings"]
    spielgefuehl_ohne_datenbank.stimmen_eingewilligte.side_effect = lambda ks: set(
        ks
    ) & {"kim-1", "bo-2"}
    with patch.object(
        voting_module, "get_muster_hinweise_service", return_value=muster
    ):
        yield SimpleNamespace(
            client=TestClient(app),
            einstellungen=einstellungen,
            einwilligung=spielgefuehl_ohne_datenbank,
        )


def _stimme(abstimmen, art="like", wer="kim-1"):
    return abstimmen.client.put(
        f"/api/v1/voting/content/{BEITRAG}/{art}", headers={"X-User": wer}
    )


class TestAbstimmen:
    def test_zustimmung_beider_mit_neuem_wortlaut_wird_gemeldet(
        self, abstimmen, muster
    ):
        assert _stimme(abstimmen).status_code == 200

        muster.zustimmung_melden.assert_called_once_with("kim-1", "bo-2")
        # Beide Konten beim Erzeugen geprueft, in einer Abfrage
        abstimmen.einwilligung.stimmen_eingewilligte.assert_called_once()
        assert set(abstimmen.einwilligung.stimmen_eingewilligte.call_args.args[0]) == {
            "kim-1",
            "bo-2",
        }

    def test_ablehnung_zaehlt_nicht(self, abstimmen, muster):
        assert _stimme(abstimmen, "dislike").status_code == 200

        muster.zustimmung_melden.assert_not_called()

    def test_nur_einer_mit_neuem_wortlaut_meldet_nichts(self, abstimmen, muster):
        """Das andere Konto hat nur -26 (oder gar nicht) eingewilligt."""
        abstimmen.einwilligung.stimmen_eingewilligte.side_effect = lambda ks: {"kim-1"}

        assert _stimme(abstimmen).status_code == 200

        muster.zustimmung_melden.assert_not_called()

    @pytest.mark.parametrize(
        "ohne", ["muster_stimmen_aktiv", "spielgefuehl_buehne_aktiv", "punkte_aktiv"]
    )
    def test_ohne_schalter_nichts_und_keine_abfrage(self, abstimmen, muster, ohne):
        abstimmen.einstellungen["settings"] = Settings(**{**STIMMEN_AN, ohne: False})

        assert _stimme(abstimmen).status_code == 200

        muster.zustimmung_melden.assert_not_called()
        abstimmen.einwilligung.stimmen_eingewilligte.assert_not_called()

    def test_admin_wert_aus_meldet_nichts(self, abstimmen, muster):
        werte = {"punkte": True, "spielgefuehl_buehne": True, "muster_stimmen": False}
        schalter_service_setzen(SchalterService(lambda: werte, Mock()))

        assert _stimme(abstimmen).status_code == 200

        muster.zustimmung_melden.assert_not_called()

    def test_startkonto_meldet_nichts(self, abstimmen, muster):
        abstimmen.einstellungen["settings"] = Settings(
            **STIMMEN_AN, startkonten="kim-1"
        )

        assert _stimme(abstimmen).status_code == 200

        muster.zustimmung_melden.assert_not_called()

    def test_fehler_kostet_die_stimme_nicht(self, abstimmen, muster):
        muster.zustimmung_melden.side_effect = RuntimeError("weg")

        assert _stimme(abstimmen).status_code == 200

    def test_ohne_art9_einwilligung_der_autorin_nichts(
        self, abstimmen, muster, art9_einwilligung_ohne_datenbank
    ):
        """
        Nach einem Art.-9-Widerruf (Stimmen geloescht, Spielgefuehl bleibt auf
        fuer_mich) darf ein alter Paar-Pruefwert keinen neuen Hinweis ergeben.
        """
        art9_einwilligung_ohne_datenbank.zaehlende.side_effect = lambda ks: set(ks) - {
            "bo-2"
        }

        assert _stimme(abstimmen).status_code == 200

        muster.zustimmung_melden.assert_not_called()


# --- Admin-Dashboard (api/v1/metrics.py) --------------------------------------------


def _admin(settings: Settings, hinweise) -> list:
    repository = Mock()
    repository.hinweise.return_value = list(hinweise)
    app = FastAPI()
    app.include_router(metrics_router, prefix="/api/v1/metrics")
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_muster_hinweise_service] = (
        lambda: MusterHinweiseService(repository)
    )
    antwort = TestClient(app).get("/api/v1/metrics/muster-hinweise", headers=ADMIN)
    assert antwort.status_code == 200
    return [(h["konto_a"], h["konto_b"], h["art"]) for h in antwort.json()["hinweise"]]


class TestAdmin:
    HINWEISE = (_hinweis("bo-2", "kim-1", ZUSTIMMUNG), _hinweis("bo-2", "kim-1"))

    @pytest.fixture(autouse=True)
    def eingewilligt(self, spielgefuehl_ohne_datenbank):
        spielgefuehl_ohne_datenbank.wirksame_stufen.return_value = {
            "bo-2": Stufe.FUER_MICH,
            "kim-1": Stufe.RANGLISTE,
        }
        spielgefuehl_ohne_datenbank.stimmen_eingewilligte.side_effect = set
        return spielgefuehl_ohne_datenbank

    def test_mit_schalter_und_einwilligung_beider(self):
        assert _admin(Settings(**STIMMEN_AN), self.HINWEISE) == [
            ("bo-2", "kim-1", ZUSTIMMUNG),
            ("bo-2", "kim-1", NUTZUNG),
        ]

    def test_ohne_schalter_nur_nutzung(self):
        settings = Settings(**{**STIMMEN_AN, "muster_stimmen_aktiv": False})

        assert _admin(settings, self.HINWEISE) == [("bo-2", "kim-1", NUTZUNG)]

    def test_ohne_art9_einwilligung_keine_zustimmungen(
        self, art9_einwilligung_ohne_datenbank
    ):
        art9_einwilligung_ohne_datenbank.zaehlende.side_effect = lambda ks: set(ks) - {
            "kim-1"
        }

        assert ("bo-2", "kim-1", ZUSTIMMUNG) not in _admin(
            Settings(**STIMMEN_AN), self.HINWEISE
        )

    def test_widerruf_des_neuen_wortlauts_versteckt_sofort(self, eingewilligt):
        eingewilligt.stimmen_eingewilligte.side_effect = lambda ks: {"bo-2"}

        assert _admin(Settings(**STIMMEN_AN), self.HINWEISE) == [
            ("bo-2", "kim-1", NUTZUNG)
        ]


# --- Frage und Einschalttag ----------------------------------------------------------


def _spielgefuehl(settings: Settings) -> dict:
    app = FastAPI()
    app.include_router(spielgefuehl_router, prefix="/api/v1/usage")
    app.dependency_overrides[get_settings] = lambda: settings
    antwort = TestClient(app).get(
        "/api/v1/usage/users/me/spielgefuehl", headers={"X-User": "kim-1"}
    )
    assert antwort.status_code == 200
    return antwort.json()


class TestFrage:
    @pytest.fixture(autouse=True)
    def ohne_datenbank(self, anzeigenamen_ohne_datenbank, spielgefuehl_ohne_datenbank):
        anzeigenamen_ohne_datenbank.anzeigenamen.return_value = {}
        # Der echte Dienst ueber dem Repository-Ersatz, ohne Abzeichen-Tabelle
        spielgefuehl_service_setzen(
            SpielgefuehlService(
                spielgefuehl_ohne_datenbank, lambda: set(), lambda user_id: False
            )
        )

    @pytest.mark.parametrize(
        "einstellungen",
        [STIMMEN_AN, {**STIMMEN_AN, "muster_stimmen_aktiv": False}],
        ids=["mit_schalter", "ohne_schalter"],
    )
    @pytest.mark.parametrize("wortlaut", [ALT, NEU])
    def test_frage_zeigt_immer_minus_28_und_fragt_neu(
        self, spielgefuehl_ohne_datenbank, einstellungen, wortlaut
    ):
        spielgefuehl_ohne_datenbank.lesen.return_value = _antwort(
            Stufe.FUER_MICH, wortlaut
        )

        stand = _spielgefuehl(Settings(**einstellungen))

        assert stand["aktueller_wortlaut"]["kennung"] == AKTUELL
        assert (
            stand["aktueller_wortlaut"]["absprachen"] == WORTLAUTE[AKTUELL].absprachen
        )
        assert stand["stufe"] is None


def _seit(settings: Settings, name: str = "muster_stimmen"):
    app = FastAPI()
    app.include_router(funktionen_router, prefix="/api/v1/funktionen")
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app).get(f"/api/v1/funktionen/{name}/seit")


class TestEinschalttag:
    def test_ohne_schalter_null_ohne_datenbank(self):
        with patch(
            "repositories.schalter_repository.get_schalter_repository"
        ) as repository:
            antwort = _seit(Settings())

        assert antwort.status_code == 200
        assert antwort.json() == {"seit": None}
        repository.assert_not_called()

    def test_mit_schalter_der_tag_in_deutscher_zeit(self):
        # 23:30 UTC ist in Berlin schon der naechste Tag
        zeitpunkt = datetime(2026, 11, 27, 23, 30, tzinfo=timezone.utc)
        with patch(
            "repositories.schalter_repository.get_schalter_repository",
            return_value=Mock(**{"eingeschaltet_am.return_value": zeitpunkt}),
        ):
            antwort = _seit(Settings(**STIMMEN_AN))

        assert antwort.json() == {"seit": "2026-11-28"}

    def test_fehler_gibt_null(self):
        with patch(
            "repositories.schalter_repository.get_schalter_repository",
            return_value=Mock(**{"eingeschaltet_am.side_effect": RuntimeError("weg")}),
        ):
            antwort = _seit(Settings(**STIMMEN_AN))

        assert antwort.status_code == 200
        assert antwort.json() == {"seit": None}

    def test_andere_schalter_nicht(self):
        assert _seit(Settings(punkte_aktiv=True), "punkte").status_code == 404
