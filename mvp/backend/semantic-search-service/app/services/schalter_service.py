"""
Schalter mit Obergrenze und Admin-Wert (#708, GLOSSARY.md "Schalter").

Die Umgebungsvariable (``SEMANTIC_SEARCH_PUNKTE_AKTIV`` usw., ``core/config.py``) ist
die Obergrenze, der Admin-Wert liegt in der Tabelle ``schalter``. Wirksam ist ein
Schalter nur, wenn beide an sind; ohne Admin-Wert gilt aus. So kann auf Prod nichts
angehen, was der Server nicht erlaubt (etwa Punkte ohne beschlossene DSFA), und ein
Admin kann ohne Rollout ein- und ausschalten.

Alle Stellen im Code fragen ``schalter_wirksam``, nicht die Settings direkt. Die
Admin-Werte liest der Dienst mit kurzem Cache (``CACHE_SEKUNDEN``); eine Aenderung
ueber ``setzen`` gilt in diesem Prozess sofort, in anderen nach dem Cache. Ist die
Datenbank nicht erreichbar, gilt aus (wie ohne Eintrag), bis der naechste Versuch
gelingt.

Seit dem Schalter-Umbau (27.11.2026, docs/ARCHITECTURE.md "Schalter nach dem Umbau")
gibt es nur noch vier Pakete (PAKET_SCHALTER) und sieben Einzelschalter
(EINZEL_SCHALTER). Die frueheren Schalter der Basisfunktionen sind weg, der Code laeuft
wie "an"; vier davon behalten als Not-Aus nur ihre Umgebungsvariable (NOTAUS,
``notaus_wirksam``, ohne Admin-Wert).
"""

import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from core.config import Settings, settings as globale_settings
from core.logging import get_logger

logger = get_logger(__name__)

CACHE_SEKUNDEN = 45.0

DSFA_HINWEIS = (
    "Vor dem Einschalten auf Prod: DSFA beschlossen (docs/DSFA.md Abschnitt 7)"
)

# Go des Vorstands und AV-Vertrag seit 27.11.2026 (Schalter-Umbau): Pakete und die
# Einzelschalter, die danach freigegeben sind, tragen rechtlich_freigegeben. Ihr Hinweis
# sagt nur noch, welche Schutzgrenze weiter gilt.
GO_27_11 = "Go des Vorstands angenommen (Sebastian, 27.11.)"

# Abschnitte der Admin-Seite "Schalter", in dieser Reihenfolge (Schalter-Umbau 27.11.:
# vier Pakete, daneben die Einzelschalter). Die Seite zeigt je Gruppe einen Abschnitt.
PAKETE = "Pakete"
EINZELSCHALTER = "Einzelschalter"
GRUPPEN = (PAKETE, EINZELSCHALTER)


@dataclass(frozen=True)
class Schalterart:
    name: str
    # Feld in Settings, das die Obergrenze traegt
    feld: str
    umgebungsvariable: str
    erklaerung: str
    dsfa_hinweis: bool = False
    # Ob GET /api/v1/funktionen den wirksamen Wert ohne Anmeldung meldet (api/v1/
    # funktionen.py): fuer Funktionen, die nur im Browser laufen oder die die App ohne
    # eigenen Abruf ausblendet, und fuer Absaetze der Datenschutzerklaerung.
    oeffentlich: bool = False
    # Eigene Bedingung fuers Einschalten auf Prod, die die Admin-Seite statt des
    # allgemeinen DSFA-Hinweises zeigt (etwa ein DSFA-Nachtrag oder ein Jura-OK).
    einschalt_hinweis: Optional[str] = None
    # Abschnitt auf der Admin-Seite, einer aus GRUPPEN
    gruppe: str = EINZELSCHALTER
    # Rechtlich freigegeben, obwohl ein Hinweis steht (der Hinweis sagt dann, was
    # weiter gilt): Die Admin-Seite zeigt den Schalter nicht als "wartet auf Recht".
    rechtlich_freigegeben: bool = False
    # Nur bei Paketen: die frueheren Schalter, die das Paket ersetzt (Doku, Tests).
    # Im Code fragt man den Paketnamen, nie einen Teil.
    teile: Tuple[str, ...] = ()

    def __post_init__(self):
        # Beim Import auffallen statt mit 500 auf der Admin-Seite
        if self.gruppe not in GRUPPEN:
            raise ValueError(f"Unbekannte Gruppe {self.gruppe!r} fuer {self.name}")
        if self.teile and self.gruppe != PAKETE:
            raise ValueError(f"Nur Pakete haben Teile: {self.name}")


# Pakete (Schalter-Umbau 27.11., GLOSSARY.md "Paket"): je Paket ein Schalter, der die
# frueheren Teil-Schalter ersetzt. Name, Feld und Umgebungsvariable sind die des
# bisherigen Hauptschalters, damit in der Konfiguration nur Zeilen wegfallen. Der
# Admin-Wert gilt unter dem Paketnamen; die Admin-Werte der frueheren Teile werden
# ignoriert (nicht geloescht).
PAKET_SCHALTER = (
    Schalterart(
        name="teams",
        gruppe=PAKETE,
        teile=("teams", "team_fortschritt", "teamlink_vertrauenssatz"),
        rechtlich_freigegeben=True,
        feld="teams_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_TEAMS_AKTIV",
        erklaerung=(
            "Paket Teams: Teams über Einladungen (Teamfelder an der Einladung, Beitreten "
            "mit eigener Einwilligung, „Meine Teams“), der Team-Fortschritt der letzten "
            "Woche und der Vertrauenssatz beim Teambeitritt. Aus: Einladungen wie "
            "bisher, Teamfelder werden ignoriert."
        ),
        einschalt_hinweis=(
            f"{GO_27_11}; Team-Summe erst ab 5 Mitgliedern mit Einwilligung. Die "
            "Anzeige am Namen (teams_oeffentlich) bleibt ein eigener Schalter."
        ),
        oeffentlich=True,
    ),
    Schalterart(
        name="spielgefuehl_buehne",
        gruppe=PAKETE,
        teile=("punkte", "spielgefuehl_buehne", "rangliste"),
        rechtlich_freigegeben=True,
        feld="spielgefuehl_buehne_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_SPIELGEFUEHL_BUEHNE_AKTIV",
        erklaerung=(
            "Paket Spielgefühl: Punkte und Meilensteine, das Spielgefühl als eine Frage "
            "(Aus, Nur für mich, in der Saison-Rangliste mitspielen) und die Rangliste "
            "je Saison; Abzeichen gibt es nur in der Rangliste. Dazu die "
            "Muster-Hinweise für Admins."
        ),
        einschalt_hinweis=f"{GO_27_11}; Rangliste sichtbar erst ab 10 Teilnehmenden",
        oeffentlich=True,
    ),
    Schalterart(
        name="wirkungs_echo",
        gruppe=PAKETE,
        teile=("wirkungs_echo", "danke_knopf"),
        rechtlich_freigegeben=True,
        feld="wirkungs_echo_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_WIRKUNGS_ECHO_AKTIV",
        erklaerung=(
            "Paket Wirkungs-Echo: Wer schreibt, sieht je Beitrag, wie oft er öffentlich "
            "gepostet wurde und wie oft jemand Danke gesagt hat, nur als Summe und nie, "
            "von wem; dazu der Knopf „Danke an die Autorin“ nach dem Kopieren für "
            "Angemeldete. Bringt keine Punkte."
        ),
        einschalt_hinweis=f"{GO_27_11}; der DSE-Absatz nennt beide Summen",
        oeffentlich=True,
    ),
    Schalterart(
        name="k_begruessung",
        gruppe=PAKETE,
        teile=("k_begruessung", "saal_spruch"),
        rechtlich_freigegeben=True,
        feld="k_begruessung_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_K_BEGRUESSUNG_AKTIV",
        erklaerung=(
            "Paket BDK-Begrüßung: Wer über ?k=sticker oder ?k=bdk kommt, liest eine "
            "passende Begrüßung (mit ?k=bdk beim Anmelden dazu den Hinweis zum "
            "Teamlink), und oben auf der Startseite steht die Karte „Heute im Netz zur "
            "BDK:“ mit dem Saal-Spruch des Tages. Nur Anzeige, speichert nichts zur "
            "Person."
        ),
        einschalt_hinweis=f"{GO_27_11} (nur Anzeige, nichts gespeichert)",
        oeffentlich=True,
    ),
)


# Einzelschalter, von Haus aus aus. Die fuenf heiklen (teams_oeffentlich, merkliste,
# aufrufe_zaehlen, danke_ohne_konto, k_ankuenfte) warten auf Recht; ihr Hinweis sagt,
# was fehlt.
EINZEL_SCHALTER = (
    Schalterart(
        name="team_quests",
        rechtlich_freigegeben=True,
        feld="team_quests_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_TEAM_QUESTS_AKTIV",
        erklaerung=(
            "Team-Quests: ein gemeinsames Wochenziel je Team aus dem Bedarf; "
            "Quest-Punkte für Mitglieder, die beigetragen haben, nur mit dem Paket "
            "Spielgefühl. Wirkt nur zusammen mit dem Paket Teams."
        ),
        dsfa_hinweis=True,
        einschalt_hinweis=(
            f"{GO_27_11}; Quest-Punkte nur mit Wortlaut -28 (spielgefuehl-2026-11-28) "
            "und dem Paket Spielgefühl; an nur mit dem Paket Teams"
        ),
        # Die Datenschutzerklaerung blendet ihren Absatz danach ein
        oeffentlich=True,
    ),
    Schalterart(
        name="muster_stimmen",
        rechtlich_freigegeben=True,
        feld="muster_stimmen_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_MUSTER_STIMMEN_AKTIV",
        erklaerung=(
            "Muster-Hinweise auch, wenn zwei Konten einander innerhalb von sieben Tagen "
            "zustimmen, nur bei Konten, die beide einem Wortlaut des Spielgefühls mit "
            "Zustimmungen zugestimmt haben (die Frage zeigt ihn immer). "
            "Nur ein Hinweis für Admins, keine Wirkung auf Punkte oder Rangliste; wirkt "
            "nur zusammen mit dem Paket Spielgefühl."
        ),
        einschalt_hinweis=f"{GO_27_11}; Wortlaut spielgefuehl-2026-11-28, DSE-Satz drin",
        # Die Datenschutzerklaerung zeigt ihren Satz danach
        oeffentlich=True,
    ),
    Schalterart(
        name="teams_oeffentlich",
        feld="teams_oeffentlich_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_TEAMS_OEFFENTLICH_AKTIV",
        erklaerung=(
            "Teams der aktuellen Saison am Anzeigenamen, die andere Angemeldete "
            "sehen, nur mit eigener Einwilligung; wirkt nur zusammen mit dem Paket "
            "Teams. Aus, bis die Datenschutzbeauftragte geraten hat."
        ),
        dsfa_hinweis=True,
        einschalt_hinweis=(
            "Aus lassen (Jura 26.11.): Art. 9, Wortlaut ungeprüft, Rat der "
            "Datenschutzbeauftragten offen; kein DSE-Absatz. Die Vertrauenszeile vor "
            "dem Anmelden stimmt nur, solange dieser Schalter aus ist"
        ),
        oeffentlich=True,
    ),
    Schalterart(
        name="merkliste",
        feld="merkliste_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_MERKLISTE_AKTIV",
        erklaerung=(
            "Merken an der Beitragskarte und der Reiter „Gemerkt“ in Meine "
            "Beiträge, nur mit Art.-9-Einwilligung; der Widerruf löscht die "
            "Merkliste. Nur die Person selbst sieht sie."
        ),
        einschalt_hinweis=(
            "Aus lassen (Jura 26.11.): Zweck steht nicht im Wortlaut der "
            "Einwilligung; braucht neuen Einwilligungswortlaut + DSFA-Abschnitt + "
            "DSE-Absatz (neuer Zweck, politisches Interesse)"
        ),
        oeffentlich=True,
    ),
    Schalterart(
        name="aufrufe_zaehlen",
        feld="aufrufe_zaehlen_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_AUFRUFE_ZAEHLEN_AKTIV",
        erklaerung=(
            "Zählt Aufrufe und Besucher je Tag am Server aus den Abrufen von "
            "Startseite, Suche, Thema und Beitrag, ohne eigene Anfrage aus dem "
            "Browser und ohne Cookie; die IP-Adresse wird nicht gespeichert. "
            "Zeigt sie unter Kennzahlen."
        ),
        dsfa_hinweis=True,
        einschalt_hinweis=(
            "Aus lassen (Jura 26.11.): erst nach DSB-Antwort (§ 25 TDDDG, #495) "
            "und DSFA-Zeile V-Messung; kein DSE-Absatz"
        ),
    ),
    Schalterart(
        name="danke_ohne_konto",
        feld="danke_ohne_konto_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_DANKE_OHNE_KONTO_AKTIV",
        erklaerung=(
            "Danke-Knopf auch ohne Konto, entdoppelt über das Besuchermerkmal; wirkt "
            "nur zusammen mit dem Paket Wirkungs-Echo."
        ),
        einschalt_hinweis=(
            "Nicht einschalten (Jura 26.11.): erfüllt Variante B nicht, ohne Konto "
            "entdoppelt über einen Tages-Prüfwert aus dem Besuchermerkmal, Pfad nennt "
            "Beitrag und „danke“, Summe nicht getrennt ausgewiesen; kein DSE-Absatz"
        ),
        oeffentlich=True,
    ),
    Schalterart(
        name="k_ankuenfte",
        feld="k_ankuenfte_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_K_ANKUENFTE_AKTIV",
        erklaerung=(
            "Zählt, wie oft die App mit ?k=<Wort> geöffnet wurde, je Wort aus der "
            "Positivliste und Tag; ohne Kennung, Konto, Adresse oder Beitrag. Die "
            "Zahlen stehen in der Übersicht."
        ),
        einschalt_hinweis=(
            "Aus lassen (Jura 26.11.): zusätzliche Anfrage aus dem Browser, § 25 "
            "TDDDG offen; kein DSE-Absatz"
        ),
        oeffentlich=True,
    ),
)


SCHALTER: Dict[str, Schalterart] = {
    s.name: s for s in (*PAKET_SCHALTER, *EINZEL_SCHALTER)
}


# Not-Aus (Entscheidung Maintainer 27.11.): Basisfunktionen ohne Admin-Wert, die nur die
# Umgebungsvariable SEMANTIC_SEARCH_<NAME>_AKTIV noch abschalten kann. Standard an;
# "=false" schaltet ab. Keine Zeile auf der Admin-Seite. Name -> Feld in Settings.
NOTAUS: Dict[str, str] = {
    "feedback_gestoert": "feedback_gestoert_aktiv",
    "gepostet_ohne_konto": "gepostet_ohne_konto_aktiv",
    "null_treffer_anzahl": "null_treffer_anzahl_aktiv",
    "herkunft_pruefen": "herkunft_pruefen_aktiv",
}


class UnbekannterSchalter(KeyError):
    pass


class ObergrenzeAus(RuntimeError):
    """Einschalten ueber die Obergrenze hinaus: der Server erlaubt es nicht."""


@dataclass(frozen=True)
class Schalterstand:
    name: str
    erklaerung: str
    umgebungsvariable: str
    obergrenze: bool
    admin_wert: bool
    wirksam: bool
    dsfa_hinweis: Optional[str]
    gruppe: str
    # Ein Hinweis steht und der Schalter ist nicht rechtlich freigegeben
    wartet_auf_recht: bool


class SchalterService:
    def __init__(
        self,
        admin_werte_lesen: Callable[[], Dict[str, bool]],
        admin_wert_setzen: Callable[[str, bool, str], None],
        cache_sekunden: float = CACHE_SEKUNDEN,
        uhr: Callable[[], float] = time.monotonic,
    ):
        self._lesen = admin_werte_lesen
        self._setzen = admin_wert_setzen
        self._cache_sekunden = cache_sekunden
        self._uhr = uhr
        self._werte: Optional[Dict[str, bool]] = None
        self._gelesen_um = 0.0
        self._sperre = threading.Lock()

    def admin_werte(self, frisch: bool = False) -> Dict[str, bool]:
        """Admin-Werte mit Cache; synchron (kurze Abfrage hoechstens je Cache-Dauer).

        ``frisch``: am Cache vorbei lesen (Admin-Seite, mehrere Replikas) und den
        Cache dabei erneuern.
        """
        with self._sperre:
            if (
                not frisch
                and self._werte is not None
                and self._uhr() - self._gelesen_um < self._cache_sekunden
            ):
                return self._werte
            try:
                self._werte = dict(self._lesen())
            except Exception as e:
                logger.error(
                    f"Schalter nicht gelesen, gelten als aus: {type(e).__name__}",
                    exc_info=True,
                )
                self._werte = {}
            self._gelesen_um = self._uhr()
            return self._werte

    def admin_werte_streng(self) -> Dict[str, bool]:
        """
        Admin-Werte frisch aus der Datenbank, ohne Rueckfall auf "alle aus": Ein
        Lesefehler wirft. Fuer Laeufe, die nach dem Stand Daten loeschen (Abgleich der
        Muster-Hinweise); erneuert den Cache, damit die folgenden Fragen denselben
        Stand sehen.
        """
        werte = dict(self._lesen())
        with self._sperre:
            self._werte = werte
            self._gelesen_um = self._uhr()
        return werte

    def admin_wert(self, name: str) -> bool:
        return bool(self.admin_werte().get(name, False))

    def wirksam(self, name: str, einstellungen: Settings) -> bool:
        # Ohne Obergrenze gar nicht erst lesen: Auf Prod fragt der Dienst die
        # Datenbank dann nicht.
        if not getattr(einstellungen, _art(name).feld):
            return False
        return _wirksam(name, einstellungen, self.admin_werte())

    def stand(
        self, einstellungen: Settings, frisch: bool = False
    ) -> List[Schalterstand]:
        """Stand aller Schalter nach Gruppen (GRUPPEN); ``frisch`` liest die
        Admin-Werte am Cache vorbei."""
        werte = self.admin_werte(frisch=frisch)
        return [
            _stand(art, einstellungen, werte)
            for art in sorted(SCHALTER.values(), key=lambda a: GRUPPEN.index(a.gruppe))
        ]

    def setzen(self, name: str, an: bool, admin: str, einstellungen: Settings) -> None:
        """Admin-Wert setzen. Ausschalten geht immer, Einschalten nur unter der Obergrenze."""
        art = _art(name)
        if an and not getattr(einstellungen, art.feld):
            raise ObergrenzeAus(name)
        self._setzen(name, an, admin)
        with self._sperre:
            self._werte = None


def _stand(
    art: Schalterart, einstellungen: Settings, werte: Dict[str, bool]
) -> Schalterstand:
    hinweis = art.einschalt_hinweis or (DSFA_HINWEIS if art.dsfa_hinweis else None)
    return Schalterstand(
        name=art.name,
        erklaerung=art.erklaerung,
        umgebungsvariable=art.umgebungsvariable,
        obergrenze=bool(getattr(einstellungen, art.feld)),
        admin_wert=bool(werte.get(art.name, False)),
        wirksam=_wirksam(art.name, einstellungen, werte),
        dsfa_hinweis=hinweis,
        gruppe=art.gruppe,
        wartet_auf_recht=bool(hinweis) and not art.rechtlich_freigegeben,
    )


def _an(name: str, einstellungen: Settings, werte: Dict[str, bool]) -> bool:
    """Obergrenze und Admin-Wert, ohne Kopplungen an andere Schalter."""
    art = _art(name)
    return bool(getattr(einstellungen, art.feld)) and bool(werte.get(name, False))


# Einzelschalter, die nur zusammen mit einem Paket wirken: Name -> Paket.
VORAUSSETZUNG: Dict[str, str] = {
    # Der Zweck Zustimmungen steht im Wortlaut des Spielgefuehls (domain/spielgefuehl.py)
    "muster_stimmen": "spielgefuehl_buehne",
    # Ohne Teams keine Teams am Namen und keine Quests
    "teams_oeffentlich": "teams",
    "team_quests": "teams",
    # Ohne Danke-Knopf (Paket Wirkungs-Echo) kein Danke ohne Konto
    "danke_ohne_konto": "wirkungs_echo",
}


def _wirksam(name: str, einstellungen: Settings, werte: Dict[str, bool]) -> bool:
    an = _an(name, einstellungen, werte)
    paket = VORAUSSETZUNG.get(name)
    if paket is None:
        return an
    return an and _wirksam(paket, einstellungen, werte)


def oeffentliche_schalter() -> List[str]:
    """Namen der Schalter, deren wirksamen Wert GET /api/v1/funktionen meldet."""
    return [art.name for art in SCHALTER.values() if art.oeffentlich]


def notaus_wirksam(name: str, einstellungen: Optional[Settings] = None) -> bool:
    """
    Ob eine Basisfunktion mit Not-Aus (NOTAUS) laeuft: an, solange ihre
    Umgebungsvariable nicht auf false steht. Kein Admin-Wert, keine Datenbank.
    """
    try:
        feld = NOTAUS[name]
    except KeyError:
        raise UnbekannterSchalter(name)
    e = einstellungen if einstellungen is not None else globale_settings
    return bool(getattr(e, feld))


def _art(name: str) -> Schalterart:
    try:
        return SCHALTER[name]
    except KeyError:
        raise UnbekannterSchalter(name)


def _aus_datenbank() -> SchalterService:
    from repositories.schalter_repository import get_schalter_repository

    return SchalterService(
        admin_werte_lesen=lambda: get_schalter_repository().admin_werte(),
        admin_wert_setzen=lambda n, a, w: get_schalter_repository().setzen(n, a, w),
    )


_service: Optional[SchalterService] = None


def get_schalter_service() -> SchalterService:
    global _service
    if _service is None:
        _service = _aus_datenbank()
    return _service


def schalter_service_setzen(service: Optional[SchalterService]) -> None:
    """Fuer Tests: einen eigenen Dienst einsetzen (None: wieder aus der Datenbank)."""
    global _service
    _service = service


def schalter_wirksam(name: str, einstellungen: Optional[Settings] = None) -> bool:
    """Ob der Schalter wirkt: Obergrenze aus ``einstellungen`` (sonst global) und Admin-Wert."""
    return get_schalter_service().wirksam(
        name, einstellungen if einstellungen is not None else globale_settings
    )
