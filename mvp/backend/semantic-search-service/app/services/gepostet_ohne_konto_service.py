"""
Meldungen ohne Konto (#799, GLOSSARY.md "Meldung ohne Konto"): "Ja, gepostet" auch
ohne Anmeldung, als reiner Wochenzaehler.

Bedingungen (Jura, 25.11.2026), hier oder am Endpunkt (api/v1/ereignis.py):

- Je Klick +1 auf die Zahl der Kalenderwoche (UTC, ab Montag), getrennt von der Zahl
  verschiedener Menschen mit Konto (``gepostet_wochen``, services/gepostet_service.py).
- Kein Pruefwert: weder aus der Adresse noch aus einem Besuchermerkmal noch aus dem
  Tages-Pruefwert vom Kopieren; kein Beitrag. Entdoppelt wird nur auf der offenen
  Seite (der Knopf ist nach dem Klick weg), im Browser wird nichts gespeichert.
- Gegen Missbrauch nur eine Drosselung im Arbeitsspeicher im Sekundenfenster
  (dependencies.get_ereignis_rate_limiter), ohne Wochenbezug.
- "Menschen" zaehlen nur mit Konto: Nordstern, Saison-Ziel und dessen Schwelle lesen
  diese Zahl nie mit; sie wird daneben ausgewiesen.

Schalter ``gepostet_ohne_konto``, wirkt nur zusammen mit ``gepostet``.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional

from repositories.gepostet_ohne_konto_repository import GepostetOhneKontoRepository
from utils.utc_tag import heute_utc, wochenbeginn


@dataclass(frozen=True)
class OhneKontoWoche:
    woche: date
    meldungen: int


class GepostetOhneKontoService:
    def __init__(self, repository: GepostetOhneKontoRepository):
        self._repository = repository

    def melden(self, heute: Optional[date] = None) -> None:
        """Eine Meldung ohne Konto fuer diese Woche; synchron, im Thread aufrufen."""
        self._repository.zaehlen(wochenbeginn(heute or heute_utc()))

    def wochenzahlen(self, von: date, laufende: date) -> Dict[date, int]:
        """Meldungen je Woche von ``von`` bis zur laufenden Woche, nur Wochen mit Meldungen."""
        return self._repository.wochen(von, laufende)

    def wochen(self, anzahl: int, heute: Optional[date] = None) -> List[OhneKontoWoche]:
        """Die letzten ``anzahl`` Kalenderwochen, die laufende zuletzt; ohne Meldung 0."""
        laufende = wochenbeginn(heute or heute_utc())
        von = laufende - timedelta(weeks=anzahl - 1)
        zahlen = self._repository.wochen(von, laufende)
        return [
            OhneKontoWoche(woche=w, meldungen=zahlen.get(w, 0))
            for w in (von + timedelta(weeks=i) for i in range(anzahl))
        ]


_service: Optional[GepostetOhneKontoService] = None


def get_gepostet_ohne_konto_service() -> GepostetOhneKontoService:
    global _service
    if _service is None:
        from repositories.gepostet_ohne_konto_repository import (
            get_gepostet_ohne_konto_repository,
        )

        _service = GepostetOhneKontoService(get_gepostet_ohne_konto_repository())
    return _service
