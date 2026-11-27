"""
Ankuenfte je Kampagnenwort und Tag (GLOSSARY.md "Ankunft", "Kampagnenwort").

Wer die App mit ``?k=<wort>`` oeffnet (QR-Code am Sticker, Link fuer eine Gruppe), zaehlt
einmal je geoeffneter Seite auf die Zahl dieses Worts und UTC-Tags. Bedingungen der
vorlaeufigen Jura-Einschaetzung (26.11.2026), hier oder am Endpunkt (api/v1/ankunft.py):

- Nur die Zahl je Wort und Tag: keine Kennung, kein Konto, keine Adresse, kein Beitrag,
  kein Pruefwert. Keine Verknuepfung mit einem Konto oder Beitrag (sonst Art. 9 DSGVO).
- Nur Woerter aus der Positivliste ``Settings.k_woerter``; jedes andere Wort zaehlt nicht
  und wird nirgends abgelegt, auch nicht im Log.
- Gegen Missbrauch nur eine Drosselung im Arbeitsspeicher im Sekundenfenster
  (dependencies.get_ankunft_rate_limiter).
- Frist: ANKUNFT_TAGE nach dem Tag (docs/LOESCHKONZEPT.md), angewendet vom Task der
  Loeschfristen (services/loeschfristen_service.py).

Schalter ``k_ankuenfte``.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from repositories.ankunft_repository import AnkunftRepository
from utils.utc_tag import heute_utc

# Zwoelf Monate: lang genug, um eine Saison und die BDK des Folgejahres zu vergleichen.
ANKUNFT_TAGE = 365
# So viele Tage zeigt die Admin-Uebersicht.
ANZEIGE_TAGE = 30


@dataclass(frozen=True)
class AnkuenfteAmTag:
    tag: date
    k: str
    anzahl: int


class AnkunftService:
    def __init__(self, repository: AnkunftRepository):
        self._repository = repository

    def zaehlen(self, k: str, heute: Optional[date] = None) -> None:
        """Eine Ankunft fuer ``k`` heute; synchron, im Thread aufrufen. ``k`` ist geprueft."""
        self._repository.zaehlen(k, heute or heute_utc())

    def letzte_tage(
        self, tage: int = ANZEIGE_TAGE, heute: Optional[date] = None
    ) -> List[AnkuenfteAmTag]:
        """Zeilen der letzten ``tage`` Tage (heute eingeschlossen), neueste zuerst."""
        von = (heute or heute_utc()) - timedelta(days=tage - 1)
        return [
            AnkuenfteAmTag(tag=t, k=k, anzahl=n)
            for t, k, n in self._repository.tage(von)
        ]


def kampagnenwort_pruefen(wort: Optional[str], erlaubt: frozenset) -> Optional[str]:
    """Das Wort klein geschrieben, wenn es auf der Positivliste steht; sonst None."""
    if not wort:
        return None
    klein = wort.strip().lower()
    return klein if klein in erlaubt else None


_service: Optional[AnkunftService] = None


def get_ankunft_service() -> AnkunftService:
    global _service
    if _service is None:
        from repositories.ankunft_repository import get_ankunft_repository

        _service = AnkunftService(get_ankunft_repository())
    return _service
