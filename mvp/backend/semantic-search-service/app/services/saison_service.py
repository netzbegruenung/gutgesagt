"""
Saisons mit Gemeinschaftsziel (#782, Schalter ``saison_ziel``; Regeln in
domain/saisons.py).

Ein Admin legt Saisons an (Name, Beginn, Ende, Ziel in Widerspruchs-Wochen), im
Jahreszeiten-Takt (GLOSSARY.md "Saison"). Die laufende Saison ist die aktuelle Saison
der Teams (``saison_fuer_teams``, gelesen von services/einstellungen_service.py), in
einer Luecke zwischen zwei Saisons die zuletzt beendete; vor der ersten Saison gilt die
Einstellung auf der Seite Schalter. Das gilt unabhaengig vom Schalter: Er steuert nur
den Balken, sonst kippten die Teams einer laufenden Saison beim Ausschalten unter
"Vergangene Saisons". Neue Teamlinks bekommen die laufende oder die naechste geplante
Saison als Vorschlag (``vorschlag``).

Den Fortschrittsbalken sehen alle erst ab der Schwelle (Settings
``saison_ziel_schwelle_menschen`` und ``saison_ziel_schwelle_wochen``), vorher nur
Admins. Gezaehlt wird nur aus den vorhandenen Wochenzahlen von "Ja, gepostet"
(gepostet_wochen); gespeichert wird dafuer nichts Neues. Die Meldungen ohne Konto
(#799, gepostet_ohne_konto_wochen) sind keine Menschen: Sie zaehlen weder fuers Ziel
noch fuer die Schwelle, die Admin-Seite zeigt sie nur daneben.

Schnittstelle fuer spaetere Bausteine (Rangliste je Saison, Rueckblick): ``alle``,
``laufende`` und die Saison-Dataclass aus domain/saisons.py (id, name, beginn, ende).
"""

import threading
import time
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Callable, Dict, List, Optional

from core.config import Settings, settings as globale_settings
from core.logging import get_logger
from domain.saisons import (
    Saison,
    SaisonZustand,
    aenderung_pruefen,
    anlegen_pruefen,
    eingabe_pruefen,
    laufende_saison,
    loeschen_pruefen,
    saison_fuer_teams,
    saison_fuer_vorschlag,
    saisonzahl,
    schwelle_erreicht,
)
from repositories.saison_repository import SaisonRepository
from utils.utc_tag import heute_utc, wochenbeginn

logger = get_logger(__name__)

CACHE_SEKUNDEN = 45.0

# Ab hier zaehlen die Wochenzahlen fuer die Schwelle; "Ja, gepostet" gibt es seit #643.
_ERSTE_WOCHE = date(2026, 1, 5)

SCHALTER = "saison_ziel"


@dataclass(frozen=True)
class Balken:
    """Was alle sehen: nur Name, Ziel und die Summe abgeschlossener Wochen."""

    name: str
    ziel: int
    erreicht: int


@dataclass(frozen=True)
class SaisonStand:
    """Eine Saison fuer die Admin-Seite."""

    saison: Saison
    zustand: SaisonZustand
    # Widerspruchs-Wochen aus abgeschlossenen Wochen
    erreicht: int
    # Nur die laufende Saison: verschiedene Menschen der laufenden Woche bisher
    laufende_woche: Optional[int]
    # Meldungen ohne Konto (#799) aus abgeschlossenen Wochen der Saison, nur daneben:
    # nicht in ``erreicht``, nicht in der Schwelle
    meldungen_ohne_konto: int = 0
    # Nur die laufende Saison: Meldungen ohne Konto der laufenden Woche bisher
    laufende_woche_ohne_konto: Optional[int] = None


@dataclass(frozen=True)
class AdminStand:
    saisons: List[SaisonStand]
    schalter_wirksam: bool
    schwelle_erreicht: bool
    schwelle_menschen: int
    schwelle_wochen: int


def _wirksam(einstellungen: Settings) -> bool:
    # Basisfunktion seit dem Schalter-Umbau (27.11.): immer an. Fuer alle sichtbar ist
    # der Balken weiter erst ab der Schwelle (schwelle_erreicht).
    return True


class SaisonService:
    def __init__(
        self,
        repository: SaisonRepository,
        wochenzahlen: Callable[[date, date], Dict[date, int]],
        einstellungen: Optional[Settings] = None,
        ohne_konto_wochenzahlen: Optional[
            Callable[[date, date], Dict[date, int]]
        ] = None,
        wirksam: Callable[[Settings], bool] = _wirksam,
        cache_sekunden: float = CACHE_SEKUNDEN,
        uhr: Callable[[], float] = time.monotonic,
    ):
        """
        ``wochenzahlen(von, laufende)``: verschiedene Menschen je Woche von ``von`` bis
        zur laufenden Woche (GepostetRepository.wochen), nur Wochen mit Meldungen.
        ``ohne_konto_wochenzahlen(von, laufende)``: Meldungen ohne Konto je Woche
        (#799), nur fuer die Admin-Seite; ohne Angabe keine.
        """
        self._repository = repository
        self._wochenzahlen = wochenzahlen
        self._ohne_konto_wochenzahlen = ohne_konto_wochenzahlen or (lambda _v, _l: {})
        self._einstellungen = einstellungen
        self._wirksam_fn = wirksam
        self._cache_sekunden = cache_sekunden
        self._uhr = uhr
        self._sperre = threading.Lock()
        self._saisons: Optional[List[Saison]] = None
        self._gelesen_um = 0.0
        self._balken: Optional[tuple] = None

    @property
    def _settings(self) -> Settings:
        return self._einstellungen or globale_settings

    def wirksam(self) -> bool:
        return self._wirksam_fn(self._settings)

    # --- Lesen ---------------------------------------------------------------

    def _gecacht(self) -> List[Saison]:
        with self._sperre:
            if (
                self._saisons is not None
                and self._uhr() - self._gelesen_um < self._cache_sekunden
            ):
                return self._saisons
        saisons = self._repository.alle()
        with self._sperre:
            self._saisons = saisons
            self._gelesen_um = self._uhr()
        return saisons

    def _vergessen(self) -> None:
        with self._sperre:
            self._saisons = None
            self._balken = None

    def alle(self) -> List[Saison]:
        """Alle Saisons, die spaeteste zuerst (frisch aus der Datenbank)."""
        return self._repository.alle()

    def laufende(self, heute: Optional[date] = None) -> Optional[Saison]:
        """Die Saison, die heute laeuft (mit kurzem Cache), unabhaengig vom Schalter."""
        return laufende_saison(self._gecacht(), heute or heute_utc())

    def saison_fuer_teams(self, heute: Optional[date] = None) -> Optional[str]:
        """
        Name der Saison der Teams: die laufende, in einer Luecke zwischen zwei Saisons
        die zuletzt beendete (domain/saisons.py ``saison_fuer_teams``), unabhaengig vom
        Schalter. None ohne begonnene Saison oder wenn die Datenbank nicht erreichbar
        ist; dann gilt die Einstellung "aktuelle Saison".
        """
        return self._name(saison_fuer_teams, heute)

    def vorschlag(self, heute: Optional[date] = None) -> Optional[str]:
        """
        Name der Saison, die neue Teamlinks als Vorschlag bekommen: die laufende, sonst
        die naechste geplante (domain/saisons.py ``saison_fuer_vorschlag``). None ohne
        beides oder wenn die Datenbank nicht erreichbar ist.
        """
        return self._name(saison_fuer_vorschlag, heute)

    def _name(self, waehlen, heute: Optional[date]) -> Optional[str]:
        try:
            saison = waehlen(self._gecacht(), heute or heute_utc())
        except Exception as e:
            logger.error(f"Saisons nicht gelesen, Einstellung gilt: {type(e).__name__}")
            return None
        return saison.name if saison is not None else None

    def _zahlen(self, laufende: date) -> Dict[date, int]:
        return self._wochenzahlen(min(_ERSTE_WOCHE, laufende), laufende)

    def _schwelle(self, zahlen: Dict[date, int], laufende: date) -> bool:
        return schwelle_erreicht(
            zahlen,
            laufende,
            self._settings.saison_ziel_schwelle_menschen,
            self._settings.saison_ziel_schwelle_wochen,
        )

    def balken(self, heute: Optional[date] = None) -> Optional[Balken]:
        """
        Der oeffentliche Balken der laufenden Saison; None ohne laufende Saison oder
        solange die Schwelle nie erreicht war. Den Schalter prueft der Endpunkt.
        Mit kurzem Cache, weil die Startseite ihn fuer alle laedt.
        """
        heute = heute or heute_utc()
        with self._sperre:
            if (
                self._balken is not None
                and self._balken[0] == heute
                and self._uhr() - self._balken[1] < self._cache_sekunden
            ):
                return self._balken[2]
        saisons = self._gecacht()
        saison = laufende_saison(saisons, heute)
        ergebnis: Optional[Balken] = None
        if saison is not None:
            laufende = wochenbeginn(heute)
            zahlen = self._zahlen(laufende)
            if self._schwelle(zahlen, laufende):
                ergebnis = Balken(
                    name=saison.name,
                    ziel=saison.ziel,
                    erreicht=saisonzahl(saison, zahlen, laufende, saisons),
                )
        with self._sperre:
            self._balken = (heute, self._uhr(), ergebnis)
        return ergebnis

    def admin_stand(self, heute: Optional[date] = None) -> AdminStand:
        heute = heute or heute_utc()
        laufende = wochenbeginn(heute)
        saisons = self.alle()
        zahlen = self._zahlen(laufende)
        # Nur daneben (#799): nie in zahlen, damit Ziel und Schwelle Menschen bleiben.
        # Faellt die Abfrage aus, fehlen nur diese Zahlen, nicht die Saison-Seite.
        try:
            ohne_konto = self._ohne_konto_wochenzahlen(
                min(_ERSTE_WOCHE, laufende), laufende
            )
        except Exception as e:
            logger.error(f"Meldungen ohne Konto nicht gelesen: {type(e).__name__}")
            ohne_konto = {}
        return AdminStand(
            saisons=[
                SaisonStand(
                    saison=s,
                    zustand=s.zustand(heute),
                    erreicht=saisonzahl(s, zahlen, laufende, saisons),
                    laufende_woche=(
                        zahlen.get(laufende, 0) if s.laeuft(heute) else None
                    ),
                    meldungen_ohne_konto=saisonzahl(s, ohne_konto, laufende, saisons),
                    laufende_woche_ohne_konto=(
                        ohne_konto.get(laufende, 0) if s.laeuft(heute) else None
                    ),
                )
                for s in saisons
            ],
            schalter_wirksam=self.wirksam(),
            schwelle_erreicht=self._schwelle(zahlen, laufende),
            schwelle_menschen=self._settings.saison_ziel_schwelle_menschen,
            schwelle_wochen=self._settings.saison_ziel_schwelle_wochen,
        )

    # --- Schreiben (nur Admins) ----------------------------------------------

    def anlegen(
        self,
        name: str,
        beginn: date,
        ende: date,
        ziel: int,
        heute: Optional[date] = None,
    ) -> Saison:
        eingabe = eingabe_pruefen(name, beginn, ende, ziel)
        anlegen_pruefen(eingabe, heute or heute_utc())
        saison = self._repository.anlegen(eingabe)
        self._vergessen()
        return saison

    def aendern(
        self,
        saison_id: uuid.UUID,
        name: str,
        beginn: date,
        ende: date,
        ziel: int,
        heute: Optional[date] = None,
    ) -> Saison:
        heute = heute or heute_utc()
        eingabe = eingabe_pruefen(name, beginn, ende, ziel)
        saison = self._repository.aendern(
            saison_id, eingabe, lambda alt: aenderung_pruefen(alt, eingabe, heute)
        )
        self._vergessen()
        return saison

    def loeschen(self, saison_id: uuid.UUID, heute: Optional[date] = None) -> None:
        heute = heute or heute_utc()
        self._repository.loeschen(saison_id, lambda s: loeschen_pruefen(s, heute))
        self._vergessen()


_service: Optional[SaisonService] = None


def get_saison_service() -> SaisonService:
    global _service
    if _service is None:
        from repositories.gepostet_ohne_konto_repository import (
            get_gepostet_ohne_konto_repository,
        )
        from repositories.gepostet_repository import get_gepostet_repository
        from repositories.saison_repository import get_saison_repository

        _service = SaisonService(
            get_saison_repository(),
            lambda von, laufende: get_gepostet_repository().wochen(von, laufende),
            ohne_konto_wochenzahlen=lambda von, laufende: (
                get_gepostet_ohne_konto_repository().wochen(von, laufende)
            ),
        )
    return _service


def saison_service_setzen(service: Optional[SaisonService]) -> None:
    """Fuer Tests: einen eigenen Dienst einsetzen (None: wieder aus der Datenbank)."""
    global _service
    _service = service
