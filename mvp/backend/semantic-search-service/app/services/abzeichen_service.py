"""
Meilenstein-Abzeichen am Anzeigenamen, die andere Angemeldete sehen (#351,
GLOSSARY.md "Meilenstein" und "Zustimmung zur Sichtbarkeit").

Das Abzeichen ist die Zahl der erreichten Meilensteine ohne Wegmarken. Es steht nur an Personen,
die der Sichtbarkeit zugestimmt haben, nur fuer Angemeldete
(services/beitrag_fuer_aufrufer.py) und nur mit beiden Schaltern wirksam
(Obergrenze und Admin-Wert, services/schalter_service.py). Startkonten und Personen ohne Art.-9-Einwilligung
haben keine Meilensteine und damit kein Abzeichen (services/meilensteine_service.py).

Die Zahlen liegen nur im Arbeitsspeicher: Antworten mit Anzeigenamen entstehen bei
jeder Suche, und die Meilensteine je Autorin dort zu berechnen, hiesse je Treffer
Qdrant und PostgreSQL zu fragen. Stattdessen rechnet ``im_takt`` die Abzeichen aller
Zustimmenden alle 15 Minuten neu, eine Antwort auf die Frage sofort. Ein Nein und ein
Widerruf der Art.-9-Einwilligung nehmen das Abzeichen sofort weg (``vergessen``).
Nach einem Neustart fehlen die Abzeichen bis zum ersten Lauf, der beim Start beginnt.

Mit Schalter ``spielgefuehl_buehne`` (domain/spielgefuehl.py) gibt es keine Abzeichen am
Anzeigenamen (``abzeichen`` bleibt leer): Gerechnet wird dann fuer alle, die in der
Rangliste mitspielen, und die Zahl erscheint nur dort (``in_rangliste``), solange der
Schalter ``rangliste`` wirkt. Ein Herabstufen nimmt sie sofort weg (``vergessen``).
"""

import asyncio
import logging
from typing import Awaitable, Callable, Dict, Iterable, List, Optional

from core.config import Settings
from core.logging import log_pseudonym
from services.schalter_service import schalter_wirksam
from domain.abzeichen_sichtbarkeit import WORTLAUTE, UnbekannterWortlaut
from domain.meilensteine import Meilenstein
from repositories.abzeichen_sichtbarkeit_repository import (
    AbzeichenSichtbarkeitRepository,
    Sichtbarkeit,
)

logger = logging.getLogger(__name__)

TAKT_SEKUNDEN = 15 * 60

Meilensteine = Callable[[str], Awaitable[List[Meilenstein]]]


class AbzeichenService:
    def __init__(
        self,
        repository: AbzeichenSichtbarkeitRepository,
        meilensteine: Meilensteine,
        settings: Settings,
        buehne_aktiv: Callable[[], bool] = lambda: False,
        mitspielende: Callable[[], Iterable[str]] = lambda: [],
        spielt_mit: Callable[[str], bool] = lambda user_id: False,
    ):
        """
        ``buehne_aktiv``: ob das Spielgefuehl-Modell gilt; ``mitspielende``: wer dann
        in der Rangliste mitspielt; ``spielt_mit(kennung)``: ob eine Person das gerade
        tut. Alle synchron; ohne Angabe gilt immer das bisherige Modell.
        """
        self._repository = repository
        self._meilensteine = meilensteine
        self._settings = settings
        self._buehne_aktiv = buehne_aktiv
        self._mitspielende = mitspielende
        self._spielt_mit = spielt_mit
        self._abzeichen: Dict[str, int] = {}
        # Unter welchem Modell die Zahlen gerechnet sind (True: Spielgefuehl); nach
        # einem Wechsel gilt keine, bis der naechste Lauf neu gerechnet hat.
        self._modus: Optional[bool] = None
        # Zaehlt je Kennung jedes Vergessen; eine Rechnung, die vorher begann,
        # schreibt dann nichts mehr (siehe _neu_berechnen).
        self._vergessen: Dict[str, int] = {}

    def abzeichen(self, kennungen: Iterable[Optional[str]]) -> Dict[str, int]:
        """
        Die Abzeichen am Anzeigenamen fuer diese Kennungen, nur die vorhandenen; ohne
        Schalter leer, im Spielgefuehl-Modell immer leer.
        """
        if self._buehne_aktiv() or not self._wirksam() or self._modus is True:
            return {}
        return {k: self._abzeichen[k] for k in kennungen if k in self._abzeichen}

    def in_rangliste(self, kennungen: Iterable[str]) -> Dict[str, int]:
        """
        Die Abzeichen fuer die Rangliste: nur im Spielgefuehl-Modell und mit Schalter
        ``rangliste``, sonst leer.
        """
        if not self._buehne_aktiv() or not self._rangliste_wirksam():
            return {}
        if self._modus is not True:
            return {}
        return {k: self._abzeichen[k] for k in kennungen if k in self._abzeichen}

    def sichtbarkeit(self, user_id: str) -> Optional[Sichtbarkeit]:
        """Die juengste Antwort der Person; synchron, im Thread aufrufen."""
        return self._repository.lesen(user_id)

    async def antworten(self, user_id: str, zeigen: bool, wortlaut: str) -> None:
        """Die Antwort speichern; ein Ja zeigt das Abzeichen sofort, ein Nein nimmt es weg."""
        if wortlaut not in WORTLAUTE:
            raise UnbekannterWortlaut(wortlaut)
        if not zeigen:
            self.vergessen(user_id)
        await asyncio.to_thread(self._repository.antworten, user_id, zeigen, wortlaut)
        if zeigen:
            await self._neu_berechnen(user_id)
        else:
            # Noch einmal nach dem Speichern: Eine Rechnung im Takt, die vor dem
            # Speichern das alte Ja gelesen hat, schreibt dann nichts mehr.
            self.vergessen(user_id)

    def zuruecknehmen(self, user_id: str) -> None:
        """
        Beim Widerruf der Art.-9-Einwilligung: Abzeichen sofort weg und ein frueheres Ja
        als Nein festhalten. Sonst erschiene das Abzeichen nach einer neuen
        Art.-9-Einwilligung ohne neue Frage wieder. Synchron (Endpunkt im Threadpool);
        wer nie zugestimmt hat, bekommt keine Zeile.
        """
        self.vergessen(user_id)
        antwort = self._repository.lesen(user_id)
        if antwort is not None and antwort.zeigen:
            self._repository.antworten(user_id, False, antwort.wortlaut)
        self.vergessen(user_id)

    def vergessen(self, user_id: str) -> None:
        """Das Abzeichen sofort wegnehmen (Nein, Widerruf der Art.-9-Einwilligung)."""
        self._abzeichen.pop(user_id, None)
        self._vergessen[user_id] = self._vergessen.get(user_id, 0) + 1

    async def alle_aktualisieren(self) -> None:
        """Die Abzeichen aller Zustimmenden neu berechnen; alle anderen vergessen."""
        buehne = await asyncio.to_thread(self._buehne_aktiv)
        if buehne != self._modus:
            # Modellwechsel: nichts aus dem anderen Modell zeigen.
            for kennung in list(self._abzeichen):
                self.vergessen(kennung)
            self._modus = buehne
        if not await asyncio.to_thread(self._rechnen_wirksam, buehne):
            self._abzeichen.clear()
            return
        zeigende = list(
            await asyncio.to_thread(
                self._mitspielende if buehne else self._repository.zeigende
            )
        )
        for kennung in set(self._abzeichen) - set(zeigende):
            self.vergessen(kennung)
        for kennung in zeigende:
            await self._neu_berechnen(kennung)

    def _wirksam(self) -> bool:
        """Beide Schalter wirksam (Obergrenze und Admin-Wert, #708)."""
        return schalter_wirksam("abzeichen_sichtbar", self._settings)

    def _rangliste_wirksam(self) -> bool:
        return schalter_wirksam("rangliste", self._settings)

    def _rechnen_wirksam(self, buehne: bool) -> bool:
        """Ob gerechnet wird: fuer den Namen (bisher) oder fuer die Rangliste (Spielgefuehl)."""
        return self._rangliste_wirksam() if buehne else self._wirksam()

    def _zeigt(self, user_id: str, buehne: bool) -> bool:
        if buehne:
            return self._spielt_mit(user_id)
        antwort = self._repository.lesen(user_id)
        return antwort is not None and antwort.zeigen

    async def _neu_berechnen(self, user_id: str) -> None:
        buehne = await asyncio.to_thread(self._buehne_aktiv)
        if self._modus is None:
            self._modus = buehne
        if buehne != self._modus or not await asyncio.to_thread(
            self._rechnen_wirksam, buehne
        ):
            return
        stand = self._vergessen.get(user_id, 0)
        try:
            # Wegmarken (eigenes Tun) zaehlen nicht: Die Zahl zeigt Anerkennung
            # durch andere (domain/meilensteine.py, docs/DSFA.md V22).
            erreicht = sum(
                1
                for m in await self._meilensteine(user_id)
                if m.erreicht and m.zaehlt_fuers_abzeichen
            )
            # Erst nach der Rechnung nachsehen: Ein Nein waehrend der Rechnung
            # (im Takt laufen viele nacheinander) darf kein Abzeichen zuruecklassen.
            if not await asyncio.to_thread(self._zeigt, user_id, buehne):
                erreicht = 0
        except Exception as e:
            # Lieber ein fehlendes Abzeichen als eine fehlgeschlagene Antwort.
            logger.error(
                f"Abzeichen fuer {log_pseudonym(user_id)} nicht berechnet: {type(e).__name__}",
                exc_info=True,
            )
            return
        if self._vergessen.get(user_id, 0) != stand:
            # Waehrend der Rechnung vergessen (Nein, Widerruf): nichts schreiben.
            return
        if erreicht:
            self._abzeichen[user_id] = erreicht
        else:
            self._abzeichen.pop(user_id, None)


async def abzeichen_im_takt(
    service: AbzeichenService, takt_sekunden: float = TAKT_SEKUNDEN
) -> None:
    """Hintergrund-Task aus main.py: rechnet die Abzeichen sofort und dann im Takt neu."""
    while True:
        try:
            await service.alle_aktualisieren()
        except Exception as e:
            logger.error(
                f"Error refreshing milestone badges: {type(e).__name__}", exc_info=True
            )
        await asyncio.sleep(takt_sekunden)


_service: Optional[AbzeichenService] = None


def abzeichen_service_setzen(service: Optional[AbzeichenService]) -> None:
    """Beim Start aus main.py (und in Tests); ohne Dienst gibt es keine Abzeichen."""
    global _service
    _service = service


def get_abzeichen_service() -> Optional[AbzeichenService]:
    return _service
