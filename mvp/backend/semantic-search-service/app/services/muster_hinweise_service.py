"""
Muster-Hinweise fuer Admins (ADR 0004, GLOSSARY.md "Muster-Hinweis", #352).

Ein Muster-Hinweis nennt zwei Konten, die sich gegenseitig nutzen: Innerhalb von
MUSTER_FENSTER_TAGE (sieben) Tagen hat jedes einen Beitrag des anderen genutzt. Er
ist nur ein Hinweis fuer Admins; keine Automatik zieht Punkte ab oder sperrt jemanden.

Wer welchen Beitrag genutzt hat, steht nirgends: Fuer jede Richtung zwischen zwei
Konten merkt sich der Dienst einen Paar-Pruefwert mit dem letzten Tag dieser Richtung
(services/entdoppelung.py, Tabelle muster_pruefwerte; Schluessel nur im Speicher).
Erst wenn auch der Pruefwert der Gegenrichtung im Fenster liegt, entsteht eine Zeile
mit beiden Kennungen. Nutzung durch Besucher hat kein Konto und zaehlt hier nicht.

Fristen, angewendet von loeschen_im_takt, einem eigenen Hintergrund-Task aus main.py
(die Pruefwerte der entdoppelten Nutzung verwirft ein eigener, services/entdoppelung.py):
- Paar-Pruefwerte bleiben MUSTER_FENSTER_TAGE: der Lauf verwirft alle, deren letzter
  Tag davor liegt.
- Muster-Hinweise bleiben MUSTER_FRIST_TAGE nach dem letzten auffaelligen Tag (DSFA
  zu #374: 8 Wochen), dann gehen sie. Wird ein Konto geloescht, gehen seine Hinweise
  mit (mvp/scripts/manual/person_loeschen.sql).

Hinweise entstehen nur mit eingeschalteten Punkten (``punkte_aktiv``, geprueft im
Zaehl-Endpunkt api/v1/usage.py): Sie schuetzen die Punkte und haben ohne sie keinen
Zweck. Gemeldet wird dort auch nur, wenn beide Konten die Einwilligung "Punkte und
Meilensteine" gegeben haben (#351, domain/punkte_einwilligung.py; im Spielgefuehl-Modell
ab Stufe ``fuer_mich``); sonst entsteht kein Paar-Pruefwert.

Zustimmungen (Schalter ``muster_stimmen``, wirkt nur mit ``spielgefuehl_buehne``):
Ein eigener Hinweis der Art ``zustimmung`` nach derselben Regel, sieben Tage Fenster,
MUSTER_FRIST_TAGE Frist, dieselben Paar-Pruefwerte mit eigenem Praefix. Gemeldet wird
nur bei einer Zustimmung (nicht bei einer Ablehnung) und nur, wenn beide Konten zum
Spielgefuehl-Wortlaut mit Zustimmungen eingewilligt haben (domain/spielgefuehl.py
``STIMMEN_WORTLAUT``, geprueft in api/v1/voting.py); das Admin-Dashboard prueft das
beim Zeigen erneut. Keine Wirkung auf Punkte oder Rangliste.

Widerruf: Das Admin-Dashboard zeigt nur Hinweise, deren beide Konten aktuell
eingewilligt haben (``hinweise(eingewilligte)``, api/v1/metrics.py). Ein Widerruf
("Punkte und Meilensteine" Nein, Spielgefuehl ``aus``) loescht ausserdem die Hinweise,
die die Person nennen (``vergessen``). Paar-Pruefwerte lassen sich nicht per Kennung
loeschen (Schluessel nur im Speicher) und gehen nach MUSTER_FENSTER_TAGE von selbst.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterable, List, Optional, Set

from core.logging import get_logger
from repositories.muster_hinweis_repository import (
    NUTZUNG,
    ZUSTIMMUNG,
    MusterHinweis,
    MusterHinweisRepository,
)
from services.entdoppelung import (
    MUSTER_FENSTER_TAGE,
    paar_pruefwert,
    paar_pruefwerte_im_fenster,
)
from utils.aufrufer import ANONYM
from utils.utc_tag import heute_utc, sekunden_bis_mitternacht

logger = get_logger(__name__)

MUSTER_FRIST_TAGE = 56
"""Acht Wochen nach dem letzten auffaelligen Tag."""

ANZAHL = 50
"""So viele Hinweise zeigt das Admin-Dashboard hoechstens."""

VORRAT_FAKTOR = 3
"""Mit Einwilligungsfilter so viel mal ANZAHL lesen, dann kuerzen."""

LOESCH_TAKT_SEKUNDEN = 24 * 60 * 60


class MusterHinweiseService:
    def __init__(self, repository: MusterHinweisRepository):
        self._repository = repository

    def nutzung_melden(
        self,
        nutzende: Optional[str],
        autor: Optional[str],
        moment: Optional[datetime] = None,
    ) -> None:
        """Eine Nutzung eines Beitrags von ``autor`` durch das Konto ``nutzende``."""
        self._melden(nutzende, autor, moment, NUTZUNG)

    def zustimmung_melden(
        self,
        stimmende: Optional[str],
        autor: Optional[str],
        moment: Optional[datetime] = None,
    ) -> None:
        """
        Eine Zustimmung des Kontos ``stimmende`` zu einem Beitrag von ``autor``
        (Schalter ``muster_stimmen``): dasselbe Fenster, dieselbe Frist und dieselben
        Paar-Pruefwerte wie bei der Nutzung, mit eigenem Praefix und eigenem Hinweis.
        Ob beide eingewilligt haben, prueft der Aufrufer (api/v1/voting.py).
        """
        self._melden(stimmende, autor, moment, ZUSTIMMUNG)

    def _melden(
        self,
        von: Optional[str],
        autor: Optional[str],
        moment: Optional[datetime],
        art: str,
    ) -> None:
        if not von or not autor or ANONYM in (von, autor):
            return
        if von == autor:
            return
        moment = moment or datetime.now(timezone.utc)
        tag = moment.astimezone(timezone.utc).date()
        self._repository.nutzung_merken(
            paar_pruefwert(von, autor, tag, art),
            paar_pruefwerte_im_fenster(autor, von, tag, art),
            von,
            autor,
            tag,
            fenster_ab=_fenster_ab(tag),
            art=art,
        )

    def hinweise(
        self,
        eingewilligte: Optional[Callable[[Iterable[str]], Set[str]]] = None,
        stimmen_eingewilligte: Optional[Callable[[Iterable[str]], Set[str]]] = None,
    ) -> List[MusterHinweis]:
        """
        Die zuletzt aufgefallenen Hinweise. Mit ``eingewilligte`` (Kennungen -> die
        davon, die aktuell eingewilligt haben) nur Paare, bei denen beide eingewilligt
        haben; die anderen bleiben bis zu ihrer Frist in der Tabelle, werden aber nicht
        gezeigt. Hinweise aus Zustimmungen brauchen dann zusaetzlich beide Konten in
        ``stimmen_eingewilligte`` (Einwilligung zum Wortlaut mit Zustimmungen); ohne
        diesen Filter erscheinen sie nicht.
        """
        if eingewilligte is None:
            return self._repository.hinweise(ANZAHL)
        # Mehr holen als gezeigt, damit nach dem Filter moeglichst ANZAHL bleiben.
        # Ohne Filter fuer Zustimmungen nur Nutzungen lesen: Versteckte Zustimmungen
        # sollen keine Nutzungen aus der Liste draengen.
        if stimmen_eingewilligte is None:
            hinweise = self._repository.hinweise(ANZAHL * VORRAT_FAKTOR, art=NUTZUNG)
        else:
            hinweise = self._repository.hinweise(ANZAHL * VORRAT_FAKTOR)
        if not hinweise:
            return hinweise
        mit = eingewilligte({k for h in hinweise for k in (h.konto_a, h.konto_b)})
        zustimmungen = [h for h in hinweise if h.art == ZUSTIMMUNG]
        stimmen_mit: Set[str] = set()
        if zustimmungen and stimmen_eingewilligte is not None:
            stimmen_mit = stimmen_eingewilligte(
                {k for h in zustimmungen for k in (h.konto_a, h.konto_b)}
            )

        def gezeigt(h: MusterHinweis) -> bool:
            if h.konto_a not in mit or h.konto_b not in mit:
                return False
            if h.art == ZUSTIMMUNG:
                return h.konto_a in stimmen_mit and h.konto_b in stimmen_mit
            return True

        return [h for h in hinweise if gezeigt(h)][:ANZAHL]

    def vergessen(self, user_id: str, art: Optional[str] = None) -> None:
        """
        Beim Widerruf: alle Hinweise loeschen, die ``user_id`` nennen; mit ``art`` nur
        die dieser Art (Widerruf nur des Zwecks Zustimmungen).
        """
        if not user_id or user_id == ANONYM:
            return
        if art is None:
            self._repository.vergessen(user_id)
        else:
            self._repository.vergessen(user_id, art=art)

    def fristen_anwenden(self, heute: Optional[date] = None) -> None:
        heute = heute or heute_utc()
        paare = self._repository.paare_verwerfen_vor(_fenster_ab(heute))
        geloescht = self._repository.loeschen_vor(
            heute - timedelta(days=MUSTER_FRIST_TAGE)
        )
        logger.info(
            f"Discarded {paare} pair check values past the window, "
            f"deleted {geloescht} pattern notes past their Loeschfrist"
        )


def _fenster_ab(tag: date) -> date:
    """Der erste Tag des Fensters, das an ``tag`` endet."""
    return tag - timedelta(days=MUSTER_FENSTER_TAGE - 1)


async def loeschen_im_takt(
    service: MusterHinweiseService, takt_sekunden: float = LOESCH_TAKT_SEKUNDEN
) -> None:
    """
    Hintergrund-Task: wendet die Fristen sofort und dann taeglich an, spaetestens
    aber um Mitternacht (UTC), bis er abgebrochen wird.
    """
    while True:
        try:
            await asyncio.to_thread(service.fristen_anwenden)
        except Exception as e:
            logger.error(
                f"Error applying pattern note retention: {type(e).__name__}",
                exc_info=True,
            )
        await asyncio.sleep(min(takt_sekunden, sekunden_bis_mitternacht() + 1))
