"""
Admin-Einstellungen mit Textwert (Seite "Schalter"), neben den Schaltern
(services/schalter_service.py). Bisher eine: ``aktuelle_saison``, die Saison der
Teams, die am Namen erscheinen (services/team_service.py). Standard ist das laufende
Jahr (UTC), solange kein Admin etwas anderes setzt.

Gelesen wird mit kurzem Cache wie bei den Schaltern; ist die Datenbank nicht
erreichbar, gilt der Standard.
"""

import re
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from core.logging import get_logger
from domain.teams import SAISON_MAX
from utils.utc_tag import heute_utc

logger = get_logger(__name__)

CACHE_SEKUNDEN = 45.0

AKTUELLE_SAISON = "aktuelle_saison"

_STEUERZEICHEN = re.compile(r"[\x00-\x1f\x7f]")


class UnbekannteEinstellung(KeyError):
    pass


class UngueltigerWert(ValueError):
    pass


@dataclass(frozen=True)
class Einstellungsart:
    name: str
    erklaerung: str
    max_laenge: int
    standard: Callable[[], str]


EINSTELLUNGEN: Dict[str, Einstellungsart] = {
    e.name: e
    for e in (
        Einstellungsart(
            name=AKTUELLE_SAISON,
            erklaerung=(
                "Saison der Teams, die am Namen erscheinen; auf dem Profil stehen alle "
                "Saisons. Neue Teamlinks bekommen sie als Vorschlag."
            ),
            max_laenge=SAISON_MAX,
            standard=lambda: str(heute_utc().year),
        ),
    )
}


@dataclass(frozen=True)
class Einstellungsstand:
    name: str
    erklaerung: str
    wert: str
    standard: str
    max_laenge: int


def wert_bereinigen(name: str, wert: str) -> str:
    """Leerraum zusammenfassen; leer, zu lang oder mit Steuerzeichen: UngueltigerWert."""
    art = _art(name)
    if _STEUERZEICHEN.search(wert.replace(" ", "")):
        raise UngueltigerWert(name)
    wert = " ".join(wert.split())
    if not wert or len(wert) > art.max_laenge:
        raise UngueltigerWert(name)
    return wert


class EinstellungenService:
    def __init__(
        self,
        lesen: Callable[[], Dict[str, str]],
        setzen: Callable[[str, str, str], None],
        cache_sekunden: float = CACHE_SEKUNDEN,
        uhr: Callable[[], float] = time.monotonic,
    ):
        self._lesen = lesen
        self._setzen = setzen
        self._cache_sekunden = cache_sekunden
        self._uhr = uhr
        self._werte: Optional[Dict[str, str]] = None
        self._gelesen_um = 0.0
        self._sperre = threading.Lock()

    def _gespeichert(self, frisch: bool = False) -> Dict[str, str]:
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
                    f"Einstellungen nicht gelesen, Standard gilt: {type(e).__name__}"
                )
                self._werte = {}
            self._gelesen_um = self._uhr()
            return self._werte

    def wert(self, name: str, frisch: bool = False) -> str:
        art = _art(name)
        return self._gespeichert(frisch).get(name) or art.standard()

    def stand(self, frisch: bool = False) -> List[Einstellungsstand]:
        werte = self._gespeichert(frisch)
        return [
            Einstellungsstand(
                name=art.name,
                erklaerung=art.erklaerung,
                wert=werte.get(art.name) or art.standard(),
                standard=art.standard(),
                max_laenge=art.max_laenge,
            )
            for art in EINSTELLUNGEN.values()
        ]

    def setzen(self, name: str, wert: str, admin: str) -> str:
        wert = wert_bereinigen(name, wert)
        self._setzen(name, wert, admin)
        with self._sperre:
            self._werte = None
        return wert


def _art(name: str) -> Einstellungsart:
    try:
        return EINSTELLUNGEN[name]
    except KeyError:
        raise UnbekannteEinstellung(name)


_service: Optional[EinstellungenService] = None


def get_einstellungen_service() -> EinstellungenService:
    global _service
    if _service is None:
        from repositories.einstellung_repository import get_einstellung_repository

        _service = EinstellungenService(
            lesen=lambda: get_einstellung_repository().alle(),
            setzen=lambda n, w, a: get_einstellung_repository().setzen(n, w, a),
        )
    return _service


def einstellungen_service_setzen(service: Optional[EinstellungenService]) -> None:
    """Fuer Tests: einen eigenen Dienst einsetzen (None: wieder aus der Datenbank)."""
    global _service
    _service = service


def aktuelle_saison() -> str:
    return get_einstellungen_service().wert(AKTUELLE_SAISON)
