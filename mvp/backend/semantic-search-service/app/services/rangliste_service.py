"""
Rangliste je Saison mit eigener Einwilligung (#793, Schalter ``rangliste``; Regeln in
domain/rangliste.py).

Wer in der Rangliste steht, wird bei jedem Abruf neu bestimmt: Die juengste Antwort
ist "teilnehmen", und beide Voraussetzungen gelten noch, die Art.-9-Einwilligung zur
Mitwirkung und die Einwilligung "Punkte und Meilensteine". Startkonten stehen nie
darin, weil sie keine Punkte sammeln. Faellt eine Voraussetzung weg oder widerruft
die Person, ist sie beim naechsten Abruf draussen, und die anderen ruecken nach.

Sehen kann die Rangliste nur, wer selbst darin steht. Bezugsgroesse sind die Punkte
nach ADR 0004 in den Tagen der laufenden Saison (services/punkte_service.py,
``zeitraum``). Nur diese Saisonpunkte liegen kurz im Arbeitsspeicher
(``CACHE_SEKUNDEN``), damit nicht jeder Abruf die Punkte aller Teilnehmenden neu
rechnet; gespeichert werden weder Punkte noch Plaetze.

Vergangene Saisons gibt es nur als Summe: die eigenen Punkte der Saison, keine Liste
mit Namen. Weil die Nutzung je Tag nur fuer die Frist der usage_events vorliegt,
erscheinen nur vergangene Saisons, die ganz in dieser Frist liegen
(``NUTZUNG_FRIST_TAGE``); aeltere wuerden sonst mit der Zeit schrumpfen.
"""

import asyncio
import threading
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import (
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
)

from core.logging import get_logger, log_pseudonym
from domain.punkte import Punktestand
from domain.rangliste import (
    AKTUELLER_WORTLAUT,
    WORTLAUTE,
    Rangliste,
    UnbekannterWortlaut,
    rangliste_bilden,
    ranglistenname,
)
from domain.saisons import Saison, SaisonZustand, laufende_saison
from repositories.rangliste_einwilligung_repository import (
    RanglisteAntwort,
    RanglisteEinwilligungRepository,
)
from utils.utc_tag import heute_utc

logger = get_logger(__name__)

CACHE_SEKUNDEN = 120.0
# Frist der usage_events (UsageTrackingRepository.cleanup_old_events)
NUTZUNG_FRIST_TAGE = 90
# Hoechstens so viele vergangene Saisons als Summe
VERGANGENE_MAX = 3

SaisonPunkte = Callable[[str, Tuple[date, date]], Awaitable[Punktestand]]


@dataclass(frozen=True)
class VergangeneSaison:
    name: str
    # Die eigenen Punkte der Saison
    punkte: int


@dataclass(frozen=True)
class RanglisteStand:
    """Was die Person in „Meine Beiträge“ sieht."""

    antwort: Optional[RanglisteAntwort]
    # Art.-9-Einwilligung und "Punkte und Meilensteine" gelten, kein Startkonto
    voraussetzungen: bool
    ranglistenname: str
    anzeigename: Optional[str]
    saison: Optional[Saison]
    # Nur fuer Teilnehmende: eigene Punkte der laufenden Saison
    eigene_punkte: Optional[int]
    # Nur fuer Teilnehmende und ab MIN_TEILNEHMENDE
    rangliste: Optional[Rangliste]
    vergangene: List[VergangeneSaison]

    @property
    def teilnehmend(self) -> bool:
        return (
            self.antwort is not None
            and self.antwort.teilnehmen
            and self.voraussetzungen
        )


class RanglisteService:
    def __init__(
        self,
        repository: RanglisteEinwilligungRepository,
        saisons: Callable[[], List[Saison]],
        saisonpunkte: SaisonPunkte,
        voraussetzungen: Callable[[str], bool],
        anzeigenamen: Callable[[Iterable[str]], Dict[str, str]],
        heute: Callable[[], date] = heute_utc,
        cache_sekunden: float = CACHE_SEKUNDEN,
        uhr: Callable[[], float] = time.monotonic,
    ):
        """
        ``saisons``: alle Saisons (SaisonService.alle); ``saisonpunkte(kennung,
        (erster, letzter))``: der Punktestand in diesen Tagen (PunkteService.punkte);
        ``voraussetzungen(kennung)``: beide Einwilligungen gelten und kein Startkonto,
        synchron; ``anzeigenamen``: AnzeigenameService.namen.
        """
        self._repository = repository
        self._saisons = saisons
        self._saisonpunkte = saisonpunkte
        self._voraussetzungen = voraussetzungen
        self._anzeigenamen = anzeigenamen
        self._heute = heute
        self._cache_sekunden = cache_sekunden
        self._uhr = uhr
        self._sperre = threading.Lock()
        self._punkte: Dict[Tuple[str, str, date], Tuple[float, int]] = {}

    # --- Einwilligung ---------------------------------------------------------

    def antwort(self, user_id: str) -> Optional[RanglisteAntwort]:
        """Die juengste Antwort; synchron, im Thread aufrufen."""
        return self._repository.lesen(user_id)

    def antworten(
        self, user_id: str, teilnehmen: bool, mit_anzeigename: bool, wortlaut: str
    ) -> None:
        """
        Ja oder Nein, jederzeit aenderbar; synchron. Ein Ja nur zum aktuellen
        Wortlaut. Ein Nein nimmt auch die Wahl des Anzeigenamens zurueck.
        """
        if wortlaut not in WORTLAUTE or (teilnehmen and wortlaut != AKTUELLER_WORTLAUT):
            raise UnbekannterWortlaut(wortlaut)
        self._repository.antworten(
            user_id, teilnehmen, mit_anzeigename and teilnehmen, wortlaut
        )

    # --- Stand ----------------------------------------------------------------

    async def stand(self, user_id: str) -> RanglisteStand:
        heute = self._heute()
        antwort, voraussetzungen, saisons, namen = await asyncio.gather(
            asyncio.to_thread(self._repository.lesen, user_id),
            asyncio.to_thread(self._voraussetzungen, user_id),
            asyncio.to_thread(self._saisons),
            asyncio.to_thread(self._anzeigenamen, [user_id]),
        )
        saison = laufende_saison(saisons, heute)
        teilnehmend = antwort is not None and antwort.teilnehmen and voraussetzungen
        eigene_punkte: Optional[int] = None
        rangliste: Optional[Rangliste] = None
        vergangene: List[VergangeneSaison] = []
        if teilnehmend:
            if saison is not None:
                rangliste, eigene_punkte = await self._rangliste(saison, user_id, heute)
            vergangene = await self._vergangene(saisons, user_id, heute)
        return RanglisteStand(
            antwort=antwort,
            voraussetzungen=voraussetzungen,
            ranglistenname=ranglistenname(user_id),
            anzeigename=namen.get(user_id),
            saison=saison,
            eigene_punkte=eigene_punkte,
            rangliste=rangliste,
            vergangene=vergangene,
        )

    async def _rangliste(
        self, saison: Saison, user_id: str, heute: date
    ) -> Tuple[Optional[Rangliste], int]:
        teilnehmende = await asyncio.to_thread(self._repository.teilnehmende)
        # Je Abruf: Wer eine Voraussetzung verloren hat, faellt sofort heraus.
        gueltig: Dict[str, bool] = {}
        for kennung, mit_anzeigename in teilnehmende.items():
            if kennung == user_id or await asyncio.to_thread(
                self._voraussetzungen, kennung
            ):
                gueltig[kennung] = mit_anzeigename
        gueltig.setdefault(user_id, False)
        punkte: Dict[str, int] = {}
        for kennung in gueltig:
            stand = await self._punkte_in(saison, kennung, heute)
            if stand is not None:
                punkte[kennung] = stand
        eigene = punkte.get(user_id, 0)
        mit_namen = [k for k, mit in gueltig.items() if mit and k in punkte]
        namen = (
            await asyncio.to_thread(self._anzeigenamen, mit_namen) if mit_namen else {}
        )
        return rangliste_bilden(punkte, namen, user_id), eigene

    async def _vergangene(
        self, saisons: List[Saison], user_id: str, heute: date
    ) -> List[VergangeneSaison]:
        frist = heute - timedelta(days=NUTZUNG_FRIST_TAGE)
        vorbei = sorted(
            (
                s
                for s in saisons
                if s.zustand(heute) is SaisonZustand.VORBEI and s.beginn >= frist
            ),
            key=lambda s: s.beginn,
            reverse=True,
        )[:VERGANGENE_MAX]
        ergebnis: List[VergangeneSaison] = []
        for saison in vorbei:
            punkte = await self._punkte_in(saison, user_id, heute)
            if punkte is not None:
                ergebnis.append(VergangeneSaison(name=saison.name, punkte=punkte))
        return ergebnis

    async def _punkte_in(
        self, saison: Saison, kennung: str, heute: date
    ) -> Optional[int]:
        """Saisonpunkte mit kurzem Cache; None, wenn die Kennung keine sammelt."""
        schluessel = (kennung, str(saison.id), heute)
        jetzt = self._uhr()
        with self._sperre:
            treffer = self._punkte.get(schluessel)
            if treffer is not None and jetzt - treffer[0] < self._cache_sekunden:
                return treffer[1]
        try:
            stand = await self._saisonpunkte(kennung, (saison.beginn, saison.ende))
        except Exception as e:
            # Lieber ohne diese Person als eine fehlgeschlagene Rangliste.
            logger.error(
                f"Saisonpunkte fuer {log_pseudonym(kennung)} nicht berechnet: {type(e).__name__}",
                exc_info=True,
            )
            return None
        if not stand.sammelt:
            return None
        with self._sperre:
            # Abgelaufene Eintraege mitnehmen, damit der Cache nicht waechst.
            self._punkte = {
                k: v
                for k, v in self._punkte.items()
                if jetzt - v[0] < self._cache_sekunden
            }
            self._punkte[schluessel] = (jetzt, stand.gesamt)
        return stand.gesamt


def zuruecknehmen(
    user_id: str, repository: Optional[RanglisteEinwilligungRepository] = None
) -> None:
    """
    Beim Widerruf der Art.-9-Einwilligung (api/v1/art9_einwilligung.py): ein
    frueheres Ja als Nein festhalten, auch bei ausgeschaltetem Schalter. Draussen ist
    die Person schon durch die fehlende Voraussetzung; ohne diese Zeile stuende sie
    nach einer neuen Art.-9-Einwilligung ohne neue Frage wieder in der Rangliste.
    Wer nie zugestimmt hat, bekommt keine Zeile. Synchron.
    """
    from repositories.rangliste_einwilligung_repository import (
        get_rangliste_einwilligung_repository,
    )

    repository = repository or get_rangliste_einwilligung_repository()
    antwort = repository.lesen(user_id)
    if antwort is not None and antwort.teilnehmen:
        repository.antworten(user_id, False, False, antwort.wortlaut)


_service: Optional[RanglisteService] = None


def _voraussetzungen(user_id: str) -> bool:
    from core.config import settings
    from repositories.punkte_einwilligung_repository import (
        get_punkte_einwilligung_repository,
    )
    from services.art9_einwilligung_service import get_art9_einwilligung_service

    if settings.ist_startkonto(user_id):
        return False
    return get_art9_einwilligung_service().eingewilligt(
        user_id
    ) and get_punkte_einwilligung_repository().eingewilligt(user_id)


def get_rangliste_service() -> RanglisteService:
    global _service
    if _service is None:
        from core.config import settings
        from dependencies import get_punkte_service
        from repositories.rangliste_einwilligung_repository import (
            get_rangliste_einwilligung_repository,
        )
        from services.anzeigename_service import get_anzeigename_service
        from services.saison_service import get_saison_service

        def saisonpunkte(kennung: str, zeitraum: Tuple[date, date]):
            # Erst beim ersten Rechnen gebaut: Wer nicht teilnimmt, braucht ihn nie.
            return get_punkte_service(settings).punkte(kennung, zeitraum)

        _service = RanglisteService(
            get_rangliste_einwilligung_repository(),
            lambda: get_saison_service().alle(),
            saisonpunkte,
            _voraussetzungen,
            lambda kennungen: get_anzeigename_service().namen(kennungen),
        )
    return _service


def rangliste_service_setzen(service: Optional[RanglisteService]) -> None:
    """Fuer Tests: einen eigenen Dienst einsetzen (None: beim naechsten Abruf neu)."""
    global _service
    _service = service
