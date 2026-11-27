"""
Der Punktestand einer Person (ADR 0004, GLOSSARY.md "Punkte", #352).

Punkte werden bei jedem Abruf aus dem Bestand berechnet und nicht gespeichert. Damit
verlieren gesperrte und endgueltig entfernte Beitraege ihre Punkte von selbst: Sie
stehen nicht mehr unter den sichtbaren Beitraegen der Person. Es gibt auch keine
Tabelle mit Punkten, die Fristen braeuchte.

Woher die drei Stufen kommen:
- Wirkung: die entdoppelte Nutzung der sichtbaren Beitraege (usage_tracking,
  services/entdoppelung.py) und die Zustimmung anderer zu ihnen. Eigene Stimmen und
  die von Startkonten zaehlen nicht; Ablehnung zieht nichts ab.
- Tun: je sichtbarem Beitrag, der mindestens BEITRAG_WARTEZEIT alt ist, und je
  Einwurf der Person, der ebenso lange in einem nicht gesperrten Beitrag
  ausformuliert ist; je Tag gedeckelt. Dazu je eigener Stimme zu einem fremden
  Beitrag ein kleiner Punkt, mit eigenem Tagesdeckel (Entscheidung Maintainer
  20.11.2026): Stimmen zu den eigenen sichtbaren Beitraegen zaehlen nicht, sonst liesse
  sich der Deckel am eigenen Bestand erklicken. Gezaehlt wird der Tag, an dem die
  Stimme zuletzt gesetzt wurde; eine zurueckgenommene Stimme faellt weg.
- Quests: Team-Quests (#792, services/team_fortschritt_service.py quest_tage): je
  erreichter Quest eines eigenen Teams mit deckender Einwilligung, wenn die Person in
  der Woche einen Beitrag gespeichert hat, der heute sichtbar und mindestens
  BEITRAG_WARTEZEIT alt ist; gezaehlt am Montag nach der Woche, je Tag gedeckelt. Nur
  mit Schalter team_quests, sonst bleibt die Stufe 0.

Ein Startkonto sammelt keine Punkte, ein Konto ohne geltende Einwilligung "Punkte
und Meilensteine" (nie erteilt oder widerrufen) auch nicht: Die
Datenschutzerklaerung stuetzt die Punkte auf diese eigene, freiwillige Einwilligung
(domain/punkte_einwilligung.py, #351), nicht mehr auf die Art.-9-Einwilligung zur
Mitwirkung. Gefragt wird je Abruf, damit ein Widerruf sofort wirkt.

Punkte je Saison (Rangliste, #793): Mit ``zeitraum`` zaehlt nur, was in diese Tage
faellt. Tun und Bewerten nach ihrem Tag, Quests nach ihrer Quest-Woche (deren
Montag liegt in der Saison, wie bei domain.saisons.wochen_der_saison; gutgeschrieben
wird erst am Montag danach, eine Quest der letzten Saisonwoche zaehlt also noch fuer
diese Saison), Zustimmung nach dem Tag ihrer letzten Aenderung, Nutzung nach den entdoppelten Nutzungsereignissen (usage_events mit
``entdoppelt``). Die gibt es nur fuer die Frist der usage_events (90 Tage,
cleanup_old_events): Was laenger zurueckliegt, zaehlt fuer die Saison nicht mehr.
Gespeichert wird dafuer nichts Neues.
"""

import asyncio
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from typing import (
    Any,
    Tuple,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Protocol,
    Set,
)

from core.config import Settings
from core.logging import get_logger
from domain.punkte import Punktegewichte, Punktestand, Wirkungsdaten, punkte_berechnen
from services import spielgefuehl_service

logger = get_logger(__name__)

BEITRAG_WARTEZEIT = timedelta(days=3)
"""
Ein Beitrag bringt Punkte fuers Tun erst, wenn er so lange steht (ADR 0004).
ANNAHME (#352): "drei Tage ohne Sperre" heisst: heute sichtbar und mindestens drei
Tage alt. Eine Sperre, die vorher schon wieder aufgehoben wurde, zaehlt nicht.
"""

KEINE_PUNKTE = Punktestand(tun=0, quests=0, wirkung=0, sammelt=False)
"""Startkonto oder keine geltende Einwilligung: kein Punktestand, nicht nur 0."""

SichtbareBeitraege = Callable[[str], Awaitable[List[Any]]]
"""Die sichtbaren Beitraege einer Person (ohne Aussagen und Herkuenfte), mit id und created."""


class NutzungsQuelle(Protocol):
    def get_nutzung_entdoppelt_batch(
        self, content_ids: List[Any]
    ) -> Dict[str, int]: ...

    def nutzung_entdoppelt_im_zeitraum(
        self, content_ids: List[Any], von: date, bis: date
    ) -> int: ...


class StimmenUndEinwuerfe(Protocol):
    def zustimmungen(
        self,
        content_ids: List[Any],
        ausgenommen: Set[str],
        zeitraum: Optional[Tuple[date, date]] = None,
    ) -> int: ...

    def einwuerfe_ausformuliert_je_tag(
        self, user_id: str, bis: datetime
    ) -> Dict[date, int]: ...

    def bewertungen_je_tag(
        self, user_id: str, ohne_beitraege: List[Any]
    ) -> Dict[date, int]: ...


def gewichte_aus(settings: Settings) -> Punktegewichte:
    return Punktegewichte(
        nutzung=settings.punkte_nutzung,
        zustimmung=settings.punkte_zustimmung,
        beitrag=settings.punkte_beitrag,
        einwurf_ausformuliert=settings.punkte_einwurf_ausformuliert,
        deckel_tun_je_tag=settings.punkte_deckel_tun_je_tag,
        quest=settings.punkte_quest,
        deckel_quests_je_tag=settings.punkte_deckel_quests_je_tag,
        bewertung=settings.punkte_bewertung,
        deckel_bewertungen_je_tag=settings.punkte_deckel_bewertungen_je_tag,
    )


def _je_tag(tage: Iterable[date]) -> Dict[date, int]:
    zaehler: Dict[date, int] = {}
    for tag in tage:
        zaehler[tag] = zaehler.get(tag, 0) + 1
    return zaehler


def _im_zeitraum(
    je_tag: Dict[date, int], zeitraum: Tuple[date, date]
) -> Dict[date, int]:
    von, bis = zeitraum
    return {tag: n for tag, n in je_tag.items() if von <= tag <= bis}


# quest_tage liefert den Montag nach der Quest-Woche; die Woche beginnt eine Woche davor.
QUEST_WOCHE = timedelta(days=7)


def _quests_der_saison(
    quests_je_tag: Dict[date, int], zeitraum: Tuple[date, date]
) -> Dict[date, int]:
    """
    Die Quest-Punkte, deren Quest-Woche zur Saison gehoert: Ihr Montag liegt im
    Zeitraum (Entscheidung Maintainer 25.11., #793), nicht der Tag der Gutschrift.
    """
    von, bis = zeitraum
    return {
        tag: n for tag, n in quests_je_tag.items() if von <= tag - QUEST_WOCHE <= bis
    }


class PunkteService:
    def __init__(
        self,
        sichtbare_beitraege: SichtbareBeitraege,
        nutzung: NutzungsQuelle,
        stimmen_und_einwuerfe: StimmenUndEinwuerfe,
        settings: Settings,
        jetzt: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        eingewilligt: Optional[Callable[[str], bool]] = None,
        quest_tage: Optional[
            Callable[[str, List[datetime], datetime], Dict[date, int]]
        ] = None,
    ):
        self._sichtbare_beitraege = sichtbare_beitraege
        self._nutzung = nutzung
        self._stimmen_und_einwuerfe = stimmen_und_einwuerfe
        self._settings = settings
        self._jetzt = jetzt
        # Ohne Angabe die gespeicherte Einwilligung "Punkte und Meilensteine"; spaet
        # geholt, damit Tests das Repository ersetzen koennen.
        self._eingewilligt = eingewilligt or (
            lambda user_id: spielgefuehl_service.punkte_eingewilligt(user_id)
        )
        # Team-Quests (#792); ohne Angabe keine Quest-Punkte.
        self._quest_tage = quest_tage

    async def _quests(self, user_id, beitraege, grenze) -> Tuple[Dict[date, int], bool]:
        """
        Quest-Punkte der Team-Quests und ob sie gelesen wurden. Scheitert das, fehlen
        nur sie (Fehler im Log), und der Stand gilt als unvollstaendig.
        """
        if self._quest_tage is None:
            return {}, True
        try:
            return (
                await asyncio.to_thread(
                    self._quest_tage, user_id, [b.created for b in beitraege], grenze
                ),
                True,
            )
        except Exception as e:
            logger.error(f"Team quest points not read: {type(e).__name__}")
            return {}, False

    async def punkte(
        self, user_id: str, zeitraum: Optional[Tuple[date, date]] = None
    ) -> Punktestand:
        """
        Der Punktestand; mit ``zeitraum`` (erster und letzter Tag, UTC, beide
        eingeschlossen) nur aus diesen Tagen, etwa fuer die Saison (#793).
        """
        gewichte = gewichte_aus(self._settings)
        if self._settings.ist_startkonto(user_id):
            return KEINE_PUNKTE
        if not await asyncio.to_thread(self._eingewilligt, user_id):
            return KEINE_PUNKTE

        beitraege = await self._sichtbare_beitraege(user_id)
        ids = [b.id for b in beitraege]
        # Die Repositories fragen PostgreSQL synchron ab: im Thread, nicht im Event-Loop.
        if zeitraum is None:
            nutzung = sum(
                (
                    await asyncio.to_thread(
                        self._nutzung.get_nutzung_entdoppelt_batch, ids
                    )
                ).values()
            )
        else:
            nutzung = await asyncio.to_thread(
                self._nutzung.nutzung_entdoppelt_im_zeitraum, ids, *zeitraum
            )
        ausgenommen = {user_id} | set(self._settings.startkonto_kennungen())
        if zeitraum is None:
            zustimmungen = await asyncio.to_thread(
                self._stimmen_und_einwuerfe.zustimmungen, ids, ausgenommen
            )
        else:
            zustimmungen = await asyncio.to_thread(
                self._stimmen_und_einwuerfe.zustimmungen, ids, ausgenommen, zeitraum
            )
        grenze = self._jetzt() - BEITRAG_WARTEZEIT
        einwuerfe = await asyncio.to_thread(
            self._stimmen_und_einwuerfe.einwuerfe_ausformuliert_je_tag,
            user_id,
            bis=grenze,
        )
        bewertungen = await asyncio.to_thread(
            self._stimmen_und_einwuerfe.bewertungen_je_tag, user_id, ids
        )
        stehende = [
            b.created.astimezone(timezone.utc).date()
            for b in beitraege
            if b.created.astimezone(timezone.utc) <= grenze
        ]
        beitraege_je_tag = _je_tag(stehende)
        quests, vollstaendig = await self._quests(user_id, beitraege, grenze)
        if zeitraum is not None:
            beitraege_je_tag = _im_zeitraum(beitraege_je_tag, zeitraum)
            einwuerfe = _im_zeitraum(einwuerfe, zeitraum)
            bewertungen = _im_zeitraum(bewertungen, zeitraum)
            # Quest-Punkte der Team-Quests (#792) nach der Woche der Quest
            quests = _quests_der_saison(quests, zeitraum)
        daten = Wirkungsdaten(
            nutzungen=nutzung,
            zustimmungen=zustimmungen,
            beitraege_je_tag=beitraege_je_tag,
            einwuerfe_ausformuliert_je_tag=einwuerfe,
            quests_je_tag=quests,
            bewertungen_je_tag=bewertungen,
        )
        stand = punkte_berechnen(daten, gewichte)
        return stand if vollstaendig else replace(stand, vollstaendig=False)
