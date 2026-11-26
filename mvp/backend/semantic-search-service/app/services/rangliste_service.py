"""
Rangliste je Saison mit eigener Einwilligung (#793, Schalter ``rangliste``; Regeln in
domain/rangliste.py).

Wer in der Rangliste steht, wird bei jedem Abruf neu bestimmt: Die juengste Antwort
ist "teilnehmen", und beide Voraussetzungen gelten noch, die Art.-9-Einwilligung zur
Mitwirkung und die Einwilligung "Punkte und Meilensteine" (fuer alle Teilnehmenden in
je einer Abfrage). Startkonten stehen nie darin, weil sie keine Punkte sammeln. Faellt
eine Voraussetzung weg oder widerruft die Person, ist sie beim naechsten Abruf
draussen, und die anderen ruecken nach.

Sehen kann die Rangliste nur, wer selbst darin steht. Bezugsgroesse sind die Punkte
nach ADR 0004 in den Tagen der laufenden Saison (services/punkte_service.py,
``zeitraum``). Nur diese Saisonpunkte liegen kurz im Arbeitsspeicher
(``CACHE_SEKUNDEN``), einmal je Saison fuer alle Teilnehmenden: Laeuft der Cache ab,
rechnet ein Abruf neu (hoechstens ``PARALLEL`` Personen gleichzeitig), die anderen
warten auf sein Ergebnis. Gespeichert werden weder Punkte noch Plaetze.

Den zufaelligen Ranglistennamen wuerfelt das erste Ja (domain/rangliste.py,
``neuer_ranglistenname``); er steht in rangliste_einwilligung und bleibt der Person.

Vergangene Saisons gibt es nur als Summe: die eigenen Punkte der Saison, keine Liste
mit Namen. Weil die Nutzung je Tag nur fuer die Frist der usage_events vorliegt
(``usage_retention_days``, solange der Bereinigungsjob laeuft), erscheinen nur
vergangene Saisons, die ganz in dieser Frist liegen; aeltere wuerden sonst mit der
Zeit schrumpfen. Aus demselben Grund sollte eine Saison nicht laenger dauern als die
Frist, sonst faellt in ihren letzten Tagen die Nutzung vom Anfang heraus
(docs/ARCHITECTURE.md, Rangliste).
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
    Set,
    Tuple,
    Union,
)

from core.logging import get_logger, log_pseudonym
from domain.punkte import Punktestand
from domain.rangliste import (
    AKTUELLER_WORTLAUT,
    OHNE_NAMEN,
    WORTLAUTE,
    Rangliste,
    UnbekannterWortlaut,
    neuer_ranglistenname,
    rangliste_bilden,
)
from domain.saisons import Saison, SaisonZustand, laufende_saison
from repositories.rangliste_einwilligung_repository import (
    RanglisteAntwort,
    RanglisteEinwilligungRepository,
)
from utils.utc_tag import heute_utc

logger = get_logger(__name__)

CACHE_SEKUNDEN = 120.0
# Hoechstens so viele Saisonpunkte gleichzeitig berechnen
PARALLEL = 8
# Hoechstens so viele vergangene Saisons als Summe
VERGANGENE_MAX = 3

SaisonPunkte = Callable[[str, Tuple[date, date]], Awaitable[Punktestand]]

# Ergebnis einer Berechnung: Punkte, None (sammelt keine) oder _FEHLER
_FEHLER = object()


class EigenePunkteFehlen(RuntimeError):
    """Die Saisonpunkte der fragenden Person liessen sich nicht berechnen."""


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
    # Erst mit dem ersten Ja vergeben
    ranglistenname: Optional[str]
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
        voraussetzungen: Callable[[Iterable[str]], Set[str]],
        anzeigenamen: Callable[[Iterable[str]], Dict[str, str]],
        nutzung_frist_tage: Optional[int] = None,
        heute: Callable[[], date] = heute_utc,
        cache_sekunden: float = CACHE_SEKUNDEN,
        uhr: Callable[[], float] = time.monotonic,
        abzeichen: Optional[Callable[[Iterable[str]], Dict[str, int]]] = None,
    ):
        """
        ``saisons``: alle Saisons (SaisonService.alle); ``saisonpunkte(kennung,
        (erster, letzter))``: der Punktestand in diesen Tagen (PunkteService.punkte);
        ``voraussetzungen(kennungen)``: die Kennungen darunter, fuer die beide
        Einwilligungen gelten und die kein Startkonto sind, synchron;
        ``anzeigenamen``: AnzeigenameService.namen; ``nutzung_frist_tage``: Frist der
        usage_events, None ohne Bereinigungsjob (dann gilt keine Frist);
        ``abzeichen(kennungen)``: die Abzeichen in der Rangliste (nur im neuen Modell,
        AbzeichenService.in_rangliste), synchron; ohne Angabe keine.
        """
        self._repository = repository
        self._saisons = saisons
        self._saisonpunkte = saisonpunkte
        self._voraussetzungen = voraussetzungen
        self._anzeigenamen = anzeigenamen
        self._nutzung_frist_tage = nutzung_frist_tage
        self._heute = heute
        self._cache_sekunden = cache_sekunden
        self._uhr = uhr
        self._abzeichen = abzeichen or (lambda kennungen: {})
        self._sperre = threading.Lock()
        # Vergangene Saisons: je Person, Saison und Tag
        self._punkte: Dict[Tuple[str, str, date], Tuple[float, int]] = {}
        # Laufende Saison: alle Teilnehmenden zusammen, (Saison, Tag) -> (Zeit, Punkte)
        self._liste: Dict[Tuple[str, date], Tuple[float, Dict[str, Optional[int]]]] = {}
        self._listen_sperre: Optional[asyncio.Lock] = None
        self._listen_sperre_loop: Optional[asyncio.AbstractEventLoop] = None

    # --- Einwilligung ---------------------------------------------------------

    def antwort(self, user_id: str) -> Optional[RanglisteAntwort]:
        """Die juengste Antwort; synchron, im Thread aufrufen."""
        return self._repository.lesen(user_id)

    def antworten(
        self, user_id: str, teilnehmen: bool, mit_anzeigename: bool, wortlaut: str
    ) -> None:
        """
        Ja oder Nein, jederzeit aenderbar; synchron. Ein Ja nur zum aktuellen
        Wortlaut. Ein Nein nimmt auch die Wahl des Anzeigenamens zurueck. Das erste Ja
        wuerfelt den Ranglistennamen; danach behaelt die Person ihn.
        """
        if wortlaut not in WORTLAUTE or (teilnehmen and wortlaut != AKTUELLER_WORTLAUT):
            raise UnbekannterWortlaut(wortlaut)
        name: Optional[str] = None
        if teilnehmen:
            bisher = self._repository.lesen(user_id)
            if bisher is None or bisher.ranglistenname is None:
                name = neuer_ranglistenname(self._repository.vergebene_namen())
        self._repository.antworten(
            user_id, teilnehmen, mit_anzeigename and teilnehmen, wortlaut, name
        )

    # --- Stand ----------------------------------------------------------------

    async def stand(self, user_id: str) -> RanglisteStand:
        heute = self._heute()
        antwort, erfuellt, saisons, namen = await asyncio.gather(
            asyncio.to_thread(self._repository.lesen, user_id),
            asyncio.to_thread(self._voraussetzungen, [user_id]),
            asyncio.to_thread(self._saisons),
            asyncio.to_thread(self._anzeigenamen, [user_id]),
        )
        voraussetzungen = user_id in erfuellt
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
            ranglistenname=antwort.ranglistenname if antwort else None,
            anzeigename=namen.get(user_id),
            saison=saison,
            eigene_punkte=eigene_punkte,
            rangliste=rangliste,
            vergangene=vergangene,
        )

    async def _rangliste(
        self, saison: Saison, user_id: str, heute: date
    ) -> Tuple[Optional[Rangliste], Optional[int]]:
        teilnehmende = await asyncio.to_thread(self._repository.teilnehmende)
        # Je Abruf: Wer eine Voraussetzung verloren hat, faellt sofort heraus.
        andere = [k for k in teilnehmende if k != user_id]
        erfuellt = (
            await asyncio.to_thread(self._voraussetzungen, andere) if andere else set()
        )
        gueltig = [k for k in andere if k in erfuellt] + [user_id]
        alle = await self._saisonpunkte_aller(saison, gueltig, heute)
        if user_id not in alle:
            # Ohne die eigenen Punkte keine Liste: Sehen darf sie nur, wer darin steht.
            raise EigenePunkteFehlen(log_pseudonym(user_id))
        punkte = {k: p for k, p in alle.items() if p is not None}
        if user_id not in punkte:
            return None, None
        mit_namen = [
            k for k in punkte if k in teilnehmende and teilnehmende[k].mit_anzeigename
        ]
        anzeigenamen = (
            await asyncio.to_thread(self._anzeigenamen, mit_namen) if mit_namen else {}
        )
        namen: Dict[str, str] = {}
        for kennung in punkte:
            teilnahme = teilnehmende.get(kennung)
            namen[kennung] = (
                anzeigenamen.get(kennung)
                or (teilnahme.ranglistenname if teilnahme else None)
                or OHNE_NAMEN
            )
        abzeichen = await asyncio.to_thread(self._abzeichen, list(punkte))
        return rangliste_bilden(punkte, namen, user_id, abzeichen), punkte[user_id]

    def _sperre_fuer_liste(self) -> asyncio.Lock:
        # Eine asyncio-Sperre gehoert zu einer Ereignisschleife.
        loop = asyncio.get_running_loop()
        if self._listen_sperre is None or self._listen_sperre_loop is not loop:
            self._listen_sperre = asyncio.Lock()
            self._listen_sperre_loop = loop
        return self._listen_sperre

    async def _saisonpunkte_aller(
        self, saison: Saison, kennungen: List[str], heute: date
    ) -> Dict[str, Optional[int]]:
        """
        Saisonpunkte fuer alle ``kennungen`` (None: sammelt keine). Fehlt eine Kennung
        im Ergebnis, liess sich ihr Stand nicht berechnen; der naechste Abruf versucht
        es erneut. Ein Eintrag je Saison und Tag; nur ein Abruf rechnet, die anderen
        warten auf ihn und lesen dann den Cache.
        """
        schluessel = (str(saison.id), heute)
        async with self._sperre_fuer_liste():
            jetzt = self._uhr()
            eintrag = self._liste.get(schluessel)
            if eintrag is not None and jetzt - eintrag[0] >= self._cache_sekunden:
                eintrag = None
            bekannt: Dict[str, Optional[int]] = dict(eintrag[1]) if eintrag else {}
            fehlend = [k for k in kennungen if k not in bekannt]
            if fehlend:
                begrenzung = asyncio.Semaphore(PARALLEL)

                async def rechnen(kennung: str):
                    async with begrenzung:
                        return kennung, await self._saisonpunkte_eines(saison, kennung)

                for kennung, ergebnis in await asyncio.gather(
                    *(rechnen(k) for k in fehlend)
                ):
                    if ergebnis is not _FEHLER:
                        bekannt[kennung] = ergebnis
                # Nur der Eintrag dieser Saison und dieses Tages bleibt; neu
                # Hinzugekommene laufen mit ihm ab.
                self._liste = {schluessel: (eintrag[0] if eintrag else jetzt, bekannt)}
        return {k: bekannt[k] for k in kennungen if k in bekannt}

    async def _saisonpunkte_eines(
        self, saison: Saison, kennung: str
    ) -> Union[int, None, object]:
        """Punkte, None (sammelt keine) oder _FEHLER (nicht merken)."""
        try:
            stand = await self._saisonpunkte(kennung, (saison.beginn, saison.ende))
        except Exception as e:
            # Lieber ohne diese Person als eine fehlgeschlagene Rangliste.
            logger.error(
                f"Saisonpunkte fuer {log_pseudonym(kennung)} nicht berechnet: {type(e).__name__}",
                exc_info=True,
            )
            return _FEHLER
        if not stand.sammelt:
            return None
        # Ohne eine Quelle waere die Summe zu niedrig, und der Cache hielte den zu
        # tiefen Platz CACHE_SEKUNDEN lang: wie ein Fehler behandeln.
        if not stand.vollstaendig:
            return _FEHLER
        return stand.gesamt

    async def _vergangene(
        self, saisons: List[Saison], user_id: str, heute: date
    ) -> List[VergangeneSaison]:
        frist = (
            heute - timedelta(days=self._nutzung_frist_tage)
            if self._nutzung_frist_tage is not None
            else None
        )
        vorbei = sorted(
            (
                s
                for s in saisons
                if s.zustand(heute) is SaisonZustand.VORBEI
                and (frist is None or s.beginn >= frist)
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
        """Saisonpunkte einer Person mit kurzem Cache; None ohne Punkte oder bei Fehler."""
        schluessel = (kennung, str(saison.id), heute)
        jetzt = self._uhr()
        with self._sperre:
            treffer = self._punkte.get(schluessel)
            if treffer is not None and jetzt - treffer[0] < self._cache_sekunden:
                return treffer[1]
        ergebnis = await self._saisonpunkte_eines(saison, kennung)
        if not isinstance(ergebnis, int):
            return None
        with self._sperre:
            # Abgelaufene Eintraege mitnehmen, damit der Cache nicht waechst.
            self._punkte = {
                k: v
                for k, v in self._punkte.items()
                if jetzt - v[0] < self._cache_sekunden
            }
            self._punkte[schluessel] = (jetzt, ergebnis)
        return ergebnis


def zuruecknehmen(
    user_id: str, repository: Optional[RanglisteEinwilligungRepository] = None
) -> None:
    """
    Beim Widerruf der Art.-9-Einwilligung (api/v1/art9_einwilligung.py) und der
    Einwilligung "Punkte und Meilensteine" (api/v1/usage.py): ein frueheres Ja als Nein
    festhalten, auch bei ausgeschaltetem Schalter. Draussen ist die Person schon durch
    die fehlende Voraussetzung; ohne diese Zeile stuende sie nach einer neuen
    Einwilligung ohne neue Frage wieder in der Rangliste. Wer nie zugestimmt hat,
    bekommt keine Zeile. Synchron.
    """
    from repositories.rangliste_einwilligung_repository import (
        get_rangliste_einwilligung_repository,
    )

    repository = repository or get_rangliste_einwilligung_repository()
    antwort = repository.lesen(user_id)
    if antwort is not None and antwort.teilnehmen:
        repository.antworten(user_id, False, False, antwort.wortlaut)


_service: Optional[RanglisteService] = None


def _voraussetzungen(kennungen: Iterable[str]) -> Set[str]:
    """Wer von ``kennungen`` beide Einwilligungen hat und kein Startkonto ist."""
    from core.config import settings
    from services import spielgefuehl_service
    from services.art9_einwilligung_service import get_art9_einwilligung_service

    ohne_start = [k for k in kennungen if not settings.ist_startkonto(k)]
    if not ohne_start:
        return set()
    art9 = get_art9_einwilligung_service().eingewilligte(ohne_start)
    if not art9:
        return set()
    # Punkte: bisherige Einwilligung oder, mit Schalter spielgefuehl_buehne, Stufe
    # ab fuer_mich (services/spielgefuehl_service.py).
    return art9 & spielgefuehl_service.punkte_eingewilligte(art9)


def get_rangliste_service() -> RanglisteService:
    global _service
    if _service is None:
        from core.config import settings
        from dependencies import get_punkte_service
        from repositories.rangliste_einwilligung_repository import (
            get_rangliste_einwilligung_repository,
        )
        from repositories.spielgefuehl_repository import get_spielgefuehl_repository
        from services.abzeichen_service import get_abzeichen_service
        from services.anzeigename_service import get_anzeigename_service
        from services.saison_service import get_saison_service
        from services.spielgefuehl_service import RanglistenQuelle

        def saisonpunkte(kennung: str, zeitraum: Tuple[date, date]):
            # Erst beim ersten Rechnen gebaut: Wer nicht teilnimmt, braucht ihn nie.
            return get_punkte_service(settings).punkte(kennung, zeitraum)

        def abzeichen(kennungen: Iterable[str]) -> Dict[str, int]:
            # Nur im neuen Modell; der Dienst fragt seine Schalter selbst.
            dienst = get_abzeichen_service()
            return dienst.in_rangliste(kennungen) if dienst is not None else {}

        _service = RanglisteService(
            # Wer mitspielt: bisherige Einwilligung oder, mit Schalter
            # spielgefuehl_buehne, Stufe rangliste (services/spielgefuehl_service.py).
            RanglistenQuelle(
                get_rangliste_einwilligung_repository(), get_spielgefuehl_repository()
            ),
            lambda: get_saison_service().alle(),
            saisonpunkte,
            _voraussetzungen,
            lambda kennungen: get_anzeigename_service().namen(kennungen),
            # Ohne Bereinigungsjob bleiben die Nutzungsereignisse, eine Frist gilt nicht.
            (
                settings.usage_retention_days
                if settings.enable_bereinigungsjob
                else None
            ),
            abzeichen=abzeichen,
        )
    return _service


def rangliste_service_setzen(service: Optional[RanglisteService]) -> None:
    """Fuer Tests: einen eigenen Dienst einsetzen (None: beim naechsten Abruf neu)."""
    global _service
    _service = service
