"""
Saal-Spruch (Schalter ``saal_spruch``, GLOSSARY.md "Saal-Spruch").

Ein Admin legt je Tag einen oeffentlichen Spruch fest, etwa an den Tagen der BDK jeden
Morgen den, der gerade unter BDK-Beitraegen im Netz kursiert; die Startseite zeigt ihn an
diesem Tag als Karte "Heute im Netz zur BDK:" mit dem Knopf "Antworten ansehen", der die
Suche mit dem Spruch startet. Der Tag gilt in Europe/Berlin, weil BDK und Publikum dort
sind: Um 00:30 Uhr am Samstag gilt der Spruch fuer
Samstag, nicht der des UTC-Freitags.

Gespeichert wird nur Datum und Text (Tabelle ``saal_sprueche``), nichts zur Person.
Gelesen wird der heutige Spruch mit kurzem Cache, weil die Startseite bei jedem Aufruf
fragt; ist die Datenbank nicht erreichbar, gibt es heute keinen Spruch.
"""

import re
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.fehler import Validierungsfehler
from core.logging import get_logger
from infrastructure.database.models import SAAL_SPRUCH_MAX

logger = get_logger(__name__)

CACHE_SEKUNDEN = 60.0

# ASCII-Steuerzeichen sowie Nullbreiten- und Bidi-Steuerzeichen: Der Text steht oeffentlich
# gross als Zitat, unsichtbare Zeichen koennten ihn verdrehen oder die Suche verfaelschen.
_STEUERZEICHEN = re.compile(
    r"[\x00-\x08\x0b-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]"
)


class SaalSpruchUngueltig(Validierungsfehler):
    """Leer, zu lang, mit Steuerzeichen oder fuer einen vergangenen Tag; der Text ist
    fuer den Admin formuliert (``antworttext``)."""


_TEXT_UNGUELTIG = (
    f"Bitte einen Spruch mit höchstens {SAAL_SPRUCH_MAX} Zeichen angeben, ohne "
    "Steuerzeichen."
)


def heute_im_saal(jetzt: Optional[datetime] = None) -> date:
    """Der heutige Tag in Europe/Berlin; ohne Zeitzonendaten der UTC-Tag."""
    jetzt = jetzt or datetime.now(timezone.utc)
    try:
        return jetzt.astimezone(ZoneInfo("Europe/Berlin")).date()
    except ZoneInfoNotFoundError:
        return jetzt.astimezone(timezone.utc).date()


def spruch_bereinigen(text: str) -> str:
    """Leerraum (auch Zeilenumbrueche) zu einem Leerzeichen; leer, zu lang oder mit
    Steuerzeichen: SaalSpruchUngueltig."""
    if _STEUERZEICHEN.search(text):
        raise SaalSpruchUngueltig(_TEXT_UNGUELTIG)
    text = " ".join(text.split())
    if not text:
        raise SaalSpruchUngueltig(_TEXT_UNGUELTIG)
    if len(text) > SAAL_SPRUCH_MAX:
        raise SaalSpruchUngueltig(_TEXT_UNGUELTIG)
    return text


@dataclass(frozen=True)
class SaalSpruch:
    datum: date
    text: str


class SaalSpruchService:
    def __init__(
        self,
        fuer_tag: Callable[[date], Optional[str]],
        ab: Callable[[date], Dict[date, str]],
        setzen: Callable[[date, str], None],
        loeschen: Callable[[date], None],
        heute: Callable[[], date] = heute_im_saal,
        cache_sekunden: float = CACHE_SEKUNDEN,
        uhr: Callable[[], float] = time.monotonic,
    ):
        self._fuer_tag = fuer_tag
        self._ab = ab
        self._setzen = setzen
        self._loeschen = loeschen
        self._heute = heute
        self._cache_sekunden = cache_sekunden
        self._uhr = uhr
        # (Tag, Spruch oder None, gelesen um)
        self._cache: Optional[Tuple[date, Optional[str], float]] = None
        self._sperre = threading.Lock()

    def heute(self) -> Optional[str]:
        """Der Spruch fuer heute oder None; Fehler beim Lesen gelten als kein Spruch."""
        tag = self._heute()
        with self._sperre:
            if (
                self._cache is not None
                and self._cache[0] == tag
                and self._uhr() - self._cache[2] < self._cache_sekunden
            ):
                return self._cache[1]
            try:
                text = self._fuer_tag(tag)
            except Exception as e:
                logger.error(
                    f"Saal-Spruch nicht gelesen, heute keiner: {type(e).__name__}"
                )
                text = None
            self._cache = (tag, text, self._uhr())
            return text

    def heutiger_tag(self) -> date:
        return self._heute()

    def kommende(self) -> List[SaalSpruch]:
        """Sprueche ab heute, nach Datum (Admin-Seite)."""
        return [SaalSpruch(d, t) for d, t in self._ab(self._heute()).items()]

    def setzen(self, tag: date, text: str) -> str:
        """Spruch fuer den Tag festlegen; vergangene Tage: SaalSpruchUngueltig."""
        if tag < self._heute():
            raise SaalSpruchUngueltig(
                "Für vergangene Tage lässt sich kein Spruch mehr festlegen."
            )
        text = spruch_bereinigen(text)
        self._setzen(tag, text)
        self._vergessen()
        return text

    def loeschen(self, tag: date) -> None:
        self._loeschen(tag)
        self._vergessen()

    def _vergessen(self) -> None:
        with self._sperre:
            self._cache = None


_service: Optional[SaalSpruchService] = None


def get_saal_spruch_service() -> SaalSpruchService:
    global _service
    if _service is None:
        from repositories.saal_spruch_repository import get_saal_spruch_repository

        _service = SaalSpruchService(
            fuer_tag=lambda t: get_saal_spruch_repository().fuer_tag(t),
            ab=lambda t: get_saal_spruch_repository().ab(t),
            setzen=lambda t, s: get_saal_spruch_repository().setzen(t, s),
            loeschen=lambda t: get_saal_spruch_repository().loeschen(t),
        )
    return _service


def saal_spruch_service_setzen(service: Optional[SaalSpruchService]) -> None:
    """Fuer Tests: einen eigenen Dienst einsetzen (None: wieder aus der Datenbank)."""
    global _service
    _service = service
