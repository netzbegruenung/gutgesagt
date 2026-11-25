"""
Was bei der Autorin ankommt (#790, #791): je Beitrag nur Summen, nie wer.

- **Wirkungs-Echo** (Schalter ``wirkungs_echo``): Meldet jemand nach dem Kopieren
  "Ja, gepostet" und nennt dabei den Beitrag, zaehlt dessen Summe "oeffentlich
  gepostet" eins hoch. Die Wochenzahl "Ja, gepostet" (services/gepostet_service.py)
  bleibt davon getrennt und kennt weiter keinen Beitrag. Am Zaehler steht nur der
  Beitrag und die Summe, keine Kennung und kein Zeitpunkt. Entdoppelt wird nur im
  Arbeitsspeicher (``EchoMerker``): hoechstens einmal je Person, Beitrag und UTC-Tag,
  ueber einen HMAC mit einem Tagesschluessel, der nirgends gespeichert wird. Preis:
  Nach einem Neustart zaehlt eine zweite Meldung am selben Tag noch einmal.
- **Danke** (Schalter ``danke_knopf``, ohne Konto zusaetzlich ``danke_ohne_konto``):
  hoechstens ein Danke je Person (Besucher: Besuchermerkmal), Beitrag und Tag,
  entdoppelt wie die Nutzung ueber einen Tages-Pruefwert in ``nutzung_heute``
  (services/entdoppelung.py). Keine Punkte.

Eigene Beitraege und Startkonten zaehlen bei beidem nicht; das prueft der Endpunkt
(api/v1/usage.py), weil nur er Aufrufer und Beitrag kennt.
"""

import hashlib
import hmac
import threading
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Set

from repositories.wirkung_repository import WirkungRepository
from services.entdoppelung import danke_pruefwert
from utils.besucher_pseudonym import Tagesschluessel


class EchoMerker:
    """
    Wer heute welchen Beitrag schon als gepostet gemeldet hat, nur als HMAC im
    Prozessspeicher. Mit dem Tag wechseln Schluessel und Menge; ``hoechstens``
    begrenzt den Speicher, danach beginnt die Menge neu (dann zaehlt eine Meldung
    am selben Tag ein zweites Mal, die sichere Richtung fuer den Speicher).
    """

    def __init__(self, hoechstens: int = 100_000):
        self._schluessel = Tagesschluessel()
        self._tag: Optional[date] = None
        self._gesehen: Set[str] = set()
        self._hoechstens = hoechstens
        self._lock = threading.Lock()

    def erstmals(self, kennung: str, content_id: uuid.UUID, tag: date) -> bool:
        """True, wenn diese Person diesen Beitrag heute zum ersten Mal meldet."""
        wert = hmac.new(
            self._schluessel.fuer(tag),
            f"echo|{kennung}|{content_id}|{tag.isoformat()}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        with self._lock:
            if self._tag != tag or len(self._gesehen) >= self._hoechstens:
                self._tag = tag
                self._gesehen = set()
            if wert in self._gesehen:
                return False
            self._gesehen.add(wert)
            return True


class WirkungService:
    def __init__(
        self, repository: WirkungRepository, merker: Optional[EchoMerker] = None
    ):
        self._repository = repository
        self._merker = merker or EchoMerker()

    def gepostet_melden(
        self, kennung: str, content_id: uuid.UUID, moment: Optional[datetime] = None
    ) -> bool:
        """Synchron. Zaehlt "oeffentlich gepostet", wenn heute neu; True, wenn gezaehlt."""
        tag = (moment or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
        if not self._merker.erstmals(kennung, content_id, tag):
            return False
        self._repository.gepostet_zaehlen(content_id)
        return True

    def danke_sagen(
        self,
        kennung: Optional[str],
        besucher_merkmal: Optional[str],
        content_id: uuid.UUID,
        moment: Optional[datetime] = None,
    ) -> bool:
        """Synchron. Zaehlt das Danke, wenn heute neu; True, wenn gezaehlt."""
        jetzt = moment or datetime.now(timezone.utc)
        wert = danke_pruefwert(kennung, besucher_merkmal, content_id, jetzt)
        if wert is None:
            return False
        return self._repository.danke_zaehlen(
            content_id, wert, jetzt.astimezone(timezone.utc).date()
        )

    def nachtragen(
        self,
        eintraege: List[Dict[str, Any]],
        mit_gepostet: bool,
        mit_danke: bool,
    ) -> List[Dict[str, Any]]:
        """
        Traegt fuer "Meine Beitraege" ``oeffentlich_gepostet`` und ``danke`` nach,
        jeweils nur mit eingeschaltetem Schalter; sonst bleibt das Feld None und die
        Karte zeigt nichts.
        """
        if not (mit_gepostet or mit_danke):
            return eintraege
        ids = []
        for eintrag in eintraege:
            try:
                ids.append(uuid.UUID(str(eintrag["id"])))
            except (KeyError, ValueError, TypeError):
                continue
        summen = self._repository.je_beitrag(ids)
        for eintrag in eintraege:
            gepostet, danke = summen.get(str(eintrag.get("id")), (0, 0))
            if mit_gepostet:
                eintrag["oeffentlich_gepostet"] = gepostet
            if mit_danke:
                eintrag["danke"] = danke
        return eintraege

    def gepostet_summe(self, content_ids: List[uuid.UUID]) -> int:
        """Wie oft die Beitraege zusammen als oeffentlich gepostet gemeldet wurden."""
        return sum(g for g, _ in self._repository.je_beitrag(content_ids).values())


_service: Optional[WirkungService] = None


def get_wirkung_service() -> WirkungService:
    global _service
    if _service is None:
        from repositories.wirkung_repository import get_wirkung_repository

        _service = WirkungService(get_wirkung_repository())
    return _service
