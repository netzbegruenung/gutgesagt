"""
Herkunft pruefen (#759, GLOSSARY.md "Herkunft pruefen"): nachts die Links aller
sichtbaren Herkuenfte abrufen und tote oder umgezogene fuer Admins auflisten.

- Nur mit dem Schalter ``herkunft_pruefen`` (services/schalter_service.py). Ist er aus,
  laeuft kein Lauf, nichts wird abgerufen oder gespeichert; die Admin-Liste ist leer.
  Wird er waehrend eines Laufs ausgeschaltet, hoert der Lauf nach dem aktuellen Link auf.
- Der Abruf selbst steht in utils/sicherer_abruf.py (nur http/https, IP-Pruefung beim
  Verbinden, Zeitgrenzen). Hier: welche Links, in welchem Abstand, was gespeichert wird.
- Hoeflich: ein Link nach dem anderen, mindestens ``ABSTAND_SEKUNDEN`` dazwischen,
  hoechstens ``HERKUENFTE_HOECHSTENS`` je Lauf; eine Adresse, die mehrere Herkuenfte
  teilen, nur einmal.
- Am Beitrag aendert sich nichts. Gespeichert wird je Herkunft nur Adresse, Ergebnis,
  Status, Weiterleitungsziel und Zeitpunkte (Tabelle ``herkunft_pruefung``).
- Takt: stuendlich nachsehen; faellig ist ein Lauf einmal je UTC-Tag ab
  ``NACHT_STUNDE`` Uhr. Ein Admin kann einen Lauf auch sofort anstossen.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, List, Optional

from core.logging import get_logger
from repositories.herkunft_pruefung_repository import (
    HerkunftPruefungRepository,
    HerkunftPruefungStand,
)
from utils import sicherer_abruf
from utils.sicherer_abruf import Abrufergebnis

logger = get_logger(__name__)

SCHALTER = "herkunft_pruefen"
ABSTAND_SEKUNDEN = 1.0
HERKUENFTE_HOECHSTENS = 2000
AUFFAELLIGE_HOECHSTENS = 200
NACHT_STUNDE = 2
TAKT_SEKUNDEN = 60 * 60


@dataclass(frozen=True)
class HerkunftLink:
    id: uuid.UUID
    adresse: str


def ist_link(adresse: Optional[str]) -> bool:
    """Nur Herkuenfte mit http- oder https-Adresse; eine Rede oder ein Buch nicht."""
    if not adresse:
        return False
    klein = adresse.strip().lower()
    return klein.startswith("http://") or klein.startswith("https://")


class HerkunftPruefenService:
    def __init__(
        self,
        repository: HerkunftPruefungRepository,
        herkuenfte_laden: Callable[[], Awaitable[List[HerkunftLink]]],
        wirksam: Callable[[], bool],
        pruefen: Optional[Callable[[str], Awaitable[Abrufergebnis]]] = None,
        abstand_sekunden: float = ABSTAND_SEKUNDEN,
        uhr: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._repository = repository
        self._laden = herkuenfte_laden
        self._wirksam = wirksam
        self._pruefen = pruefen
        self._abstand = abstand_sekunden
        self._uhr = uhr
        self._lauf: Optional[asyncio.Task] = None

    @property
    def laeuft(self) -> bool:
        return self._lauf is not None and not self._lauf.done()

    def wirksam(self) -> bool:
        return self._wirksam()

    async def stand(self) -> HerkunftPruefungStand:
        return await asyncio.to_thread(
            self._repository.stand, sicherer_abruf.OK, AUFFAELLIGE_HOECHSTENS
        )

    def anstossen(self) -> bool:
        """Einen Lauf im Hintergrund starten; False, wenn schon einer laeuft."""
        if self.laeuft:
            return False
        self._lauf = asyncio.create_task(self.lauf())
        return True

    async def faellig(self) -> bool:
        jetzt = self._uhr()
        if jetzt.hour < NACHT_STUNDE:
            return False
        letzter = await asyncio.to_thread(self._repository.letzter_lauf)
        return letzter is None or letzter.astimezone(timezone.utc).date() < jetzt.date()

    async def lauf(self) -> int:
        """Alle Links pruefen; gibt zurueck, wie viele Adressen abgerufen wurden."""
        if not self._wirksam():
            return 0
        herkuenfte = [h for h in await self._laden() if ist_link(h.adresse)]
        herkuenfte = herkuenfte[:HERKUENFTE_HOECHSTENS]
        pool = None
        if self._pruefen is None:
            pool = sicherer_abruf.neuer_pool()

            async def pruefen(adresse: str) -> Abrufergebnis:
                return await sicherer_abruf.link_pruefen(pool, adresse)

        else:
            pruefen = self._pruefen
        schon: dict = {}
        abgerufen = 0
        try:
            for herkunft in herkuenfte:
                if not self._wirksam():
                    logger.info("Herkunft pruefen: Schalter aus, Lauf beendet")
                    return abgerufen
                adresse = herkunft.adresse.strip()
                ergebnis = schon.get(adresse)
                if ergebnis is None:
                    if abgerufen:
                        await asyncio.sleep(self._abstand)
                    ergebnis = await pruefen(adresse)
                    schon[adresse] = ergebnis
                    abgerufen += 1
                await asyncio.to_thread(
                    self._repository.speichern,
                    herkunft.id,
                    adresse[:2048],
                    ergebnis.ergebnis,
                    ergebnis.http_status,
                    (ergebnis.ziel or None) and ergebnis.ziel[:2048],
                    self._uhr(),
                    ergebnis.ergebnis != sicherer_abruf.OK,
                )
            entfernt = await asyncio.to_thread(
                self._repository.uebrige_loeschen, [h.id for h in herkuenfte]
            )
        finally:
            if pool is not None:
                await pool.aclose()
        auffaellig = sum(1 for e in schon.values() if e.ergebnis != sicherer_abruf.OK)
        # Keine Adressen ins Log: Sie stehen in der Admin-Liste.
        logger.info(
            f"Herkunft pruefen: {abgerufen} Adressen geprueft, {auffaellig} auffaellig, "
            f"{entfernt} alte Eintraege entfernt"
        )
        return abgerufen


async def pruefen_im_takt(
    service: HerkunftPruefenService, takt_sekunden: float = TAKT_SEKUNDEN
) -> None:
    """
    Hintergrund-Task aus main.py: stuendlich nachsehen, ob ein Lauf faellig ist. Bei
    ausgeschaltetem Schalter fragt er weder die Herkuenfte noch die Tabelle ab.
    """
    while True:
        try:
            if service.wirksam() and not service.laeuft and await service.faellig():
                service.anstossen()
        except Exception as e:
            logger.error(f"Herkunft pruefen: {type(e).__name__}", exc_info=True)
        await asyncio.sleep(takt_sekunden)


def herkuenfte_aus_index(
    reference_service,
) -> Callable[[], Awaitable[List[HerkunftLink]]]:
    """Die sichtbaren Herkuenfte aus dem Suchindex (ohne gesperrte und geloeschte)."""

    async def laden() -> List[HerkunftLink]:
        eintraege = await reference_service.get_all(
            limit=HERKUENFTE_HOECHSTENS, offset=0
        )
        return [
            HerkunftLink(id=e.id, adresse=e.reference_string)
            for e in eintraege
            if ist_link(getattr(e, "reference_string", None))
        ]

    return laden


_service: Optional[HerkunftPruefenService] = None


def herkunft_pruefen_bauen() -> HerkunftPruefenService:
    """Der Dienst aus den globalen Teilen; beim Start aus main.py, merkt ihn sich."""
    from dependencies import get_reference_service
    from repositories.herkunft_pruefung_repository import (
        get_herkunft_pruefung_repository,
    )
    from services.schalter_service import schalter_wirksam

    service = HerkunftPruefenService(
        get_herkunft_pruefung_repository(),
        herkuenfte_aus_index(get_reference_service()),
        lambda: schalter_wirksam(SCHALTER),
    )
    herkunft_pruefen_service_setzen(service)
    return service


def herkunft_pruefen_service_setzen(service: Optional[HerkunftPruefenService]) -> None:
    """Beim Start aus main.py (und in Tests)."""
    global _service
    _service = service


def get_herkunft_pruefen_service() -> Optional[HerkunftPruefenService]:
    return _service
