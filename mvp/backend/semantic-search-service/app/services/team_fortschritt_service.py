"""
Team-Fortschritt (#784) und Team-Quests (#792): was ein Team gemeinsam bewirkt hat,
nur als Summe, nur fuer seine Mitglieder (GLOSSARY.md "Team-Fortschritt",
"Team-Quest", "Wochenzaehler"). Die Regeln (Schwelle, Rundung, Ziel) stehen in
domain/team_fortschritt.py.

Zaehlen (``zaehlen``): Speichert eine Person einen Beitrag (jeder Beitragstyp,
Kommentare eingeschlossen), gibt eine Stimme ab oder meldet "Ja, gepostet", erhoeht
der Dienst fuer jedes ihrer Teams mit deckender Einwilligung (``SUMME_GEDECKT``) den
Wochenzaehler dieser Art. Am Zaehler stehen nur Team, Saison und Woche, keine Kennung,
kein Beitrag. Entdoppelt wird ueber einen Wochen-Pruefwert im Arbeitsspeicher
(``WochenPruefwerte``): ein HMAC ueber Art, Kennung, Gegenstand und Team mit einem
Schluessel, der nur im Speicher liegt und jede Woche neu entsteht; die Werte der
Vorwoche verfallen mit dem Wochenwechsel. In der Datenbank steht kein Pruefwert. So
zaehlt ein Beitrag einmal, eine Stimme je Person und Beitrag einmal je Woche (auch
wenn sie umgedreht wird), "Ja, gepostet" je Person einmal je Woche. Der Preis wie bei
"Ja, gepostet" (services/gepostet_service.py): Nach einem Neustart kann dasselbe in
derselben Woche ein zweites Mal zaehlen; das setzt einen uvicorn-Worker voraus.
Bekannte Grenze: Doppelzaehlung nach Neustart oder bei mehreren Workern zaehlt zu
hoch, nie zu niedrig.

Wer nicht zaehlt: Startkonten; ohne geltende Art.-9-Einwilligung keine Meldung "Ja,
gepostet" (Bedingung des Nordsterns, docs/DSFA.md V9a; Beitraege und Stimmen
verlangen sie an ihren Endpunkten ohnehin); Teams unter der Schwelle
(``MINDESTMITGLIEDER``), damit eine Woche aus der Zeit eines kleinen Teams nicht
spaeter sichtbar wird. Schalter ``team_fortschritt`` aus: Es wird nichts gezaehlt und
nichts gezeigt, und die Datenbank wird nicht gefragt.

Nur Teams der aktuellen Saison zaehlen und werden gezeigt; Quest-Punkte aus frueheren
Saisons bleiben (``quest_tage`` liest alle Saisons).

Was Mitglieder trotz Rundung erfahren (fuer DSFA V29 benannt): "geschafft" sagt, dass
die Woche mindestens das Ziel erreicht hat (mindestens 3, auch wenn jede Art "weniger
als 10" zeigt), und das Ziel verraet grob die Zahl der Mitglieder mit Einwilligung
(aufgerundet ein Drittel). Beides verlangt #792.

Zeigen (``staende``): nur die Teams der aufrufenden Person (eigene Kennung, nie fremde
Mitgliedschaften), nur die letzte abgeschlossene Woche (nie die laufende), erst ab der
Schwelle und nur gerundet; darunter nur, dass das Team noch waechst.

Team-Quests (Schalter ``team_quests``, wirkt nur mit ``team_fortschritt``): Beim ersten
Abruf in einer Woche bekommt jedes Team ueber der Schwelle ein Wochenziel aus dem
Bedarf (``bedarf``: das Thema mit den meisten unbeantworteten Aussagen und deren
Zahl, solange es kein Wochenthema gibt). Gezaehlt wird mit demselben Wochenzaehler,
also alles, was er zaehlt. Waehrend der Woche zeigt "Meine Teams" nur das Ziel, nach
Wochenende nur, ob es geschafft ist; ein verfehltes Ziel erwaehnt nichts. Nie Team
gegen Team. Quest-Punkte (``quest_tage``, ADR 0004 Stufe 2) bekommt, wer zum Team
gehoert, mit deckender Einwilligung, und in der Woche einen Beitrag gespeichert hat,
der heute sichtbar und mindestens drei Tage alt ist; ob die Einwilligung "Punkte und
Meilensteine" gilt, prueft services/punkte_service.py davor.

Kontoloeschung und "Team verlassen" loeschen die Mitgliedschaft; der Zaehler bleibt,
er traegt nichts zur Person. Eine Zuordnung Person -> Zaehler entsteht nirgends: Die
Quest-Punkte werden bei jedem Abruf aus den eigenen Mitgliedschaften und Beitraegen
gerechnet und nicht gespeichert.
"""

import asyncio
import hashlib
import hmac
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import (
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
)

from core.config import Settings, settings as globale_settings
from core.logging import get_logger
from domain.team_fortschritt import (
    SUMME_GEDECKT,
    Art,
    Wochenzaehlung,
    anzeige,
    quest_ziel,
    zeigbar,
)
from domain.themen import THEMEN
from repositories.team_fortschritt_repository import (
    Quest,
    TeamFortschrittRepository,
    TeamSchluessel,
)
from services.schalter_service import schalter_wirksam
from utils.besucher_pseudonym import Tagesschluessel
from utils.utc_tag import heute_utc, wochenbeginn

logger = get_logger(__name__)

WOCHE = timedelta(days=7)

Bedarf = Callable[[], Awaitable[Tuple[Optional[str], int]]]
"""Das Thema mit dem meisten Bedarf und die Zahl seiner unbeantworteten Aussagen."""


class WochenPruefwerte:
    """
    Die Pruefwerte der laufenden Woche, nur im Arbeitsspeicher. Ein Wert ist ein HMAC
    mit einem Schluessel je Woche, der nur hier liegt; mit dem Wochenwechsel
    verfallen Schluessel und Werte. Eine Anfrage, die noch zur Vorwoche gehoert,
    zaehlt nicht: Die Vorwoche ist abgeschlossen und darf sich nicht mehr aendern.
    Die Menge waechst mit jedem gezaehlten Ereignis bis zum Wochenwechsel (je Wert 64
    Zeichen; bei einigen tausend Ereignissen je Woche unerheblich).
    """

    def __init__(self):
        self._schluessel = Tagesschluessel()
        self._woche: Optional[date] = None
        self._werte: Set[str] = set()
        self._sperre = threading.Lock()

    def erstmals(self, inhalt: str, woche: date) -> bool:
        """True, wenn ``inhalt`` in ``woche`` zum ersten Mal kommt (und merkt ihn)."""
        with self._sperre:
            if self._woche is None or woche > self._woche:
                self._woche = woche
                self._werte = set()
            elif woche < self._woche:
                return False
            wert = hmac.new(
                self._schluessel.fuer(woche),
                f"team|{woche.isoformat()}|{inhalt}".encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if wert in self._werte:
                return False
            self._werte.add(wert)
            return True


@dataclass(frozen=True)
class TeamWirkung:
    """
    Was Mitglieder von der letzten abgeschlossenen Woche sehen. Unter der Schwelle nur
    ``waechst_noch``; sonst je Art der gerundete Text (domain/team_fortschritt.anzeige),
    nie die genaue Zahl.
    """

    woche: date
    waechst_noch: bool
    # Bewusst keine Gesamtsumme neben den Arten: Aus zwei getrennt gerundeten Zahlen
    # liesse sich eine Art unter 10 zurueckrechnen (Review zu #813).
    beitraege: Optional[str] = None
    bewertungen: Optional[str] = None
    gepostet: Optional[str] = None


@dataclass(frozen=True)
class TeamQuestStand:
    """Die laufende Quest (nur Ziel, nie der Stand) und ob die vorige geschafft ist."""

    laufende: Optional[Quest]
    vorige_geschafft: bool
    vorige_thema: Optional[str] = None


@dataclass(frozen=True)
class TeamStand:
    wirkung: TeamWirkung
    quest: Optional[TeamQuestStand] = None


def bedarf_aus(themen_je_aussage: Iterable[Sequence[str]]) -> Tuple[Optional[str], int]:
    """
    Das Thema mit den meisten unbeantworteten Aussagen und deren Zahl; bei Gleichstand
    das erste in der festen Liste (domain/themen.py). Ohne Aussagen mit Thema (None, 0).
    """
    zaehler: Dict[str, int] = {}
    for themen in themen_je_aussage:
        for thema in set(themen):
            zaehler[thema] = zaehler.get(thema, 0) + 1
    reihenfolge = {t.schluessel: i for i, t in enumerate(THEMEN)}
    bekannte = [t for t in zaehler if t in reihenfolge]
    if not bekannte:
        return None, 0
    bestes = min(bekannte, key=lambda t: (-zaehler[t], reihenfolge[t]))
    return bestes, zaehler[bestes]


async def _kein_bedarf() -> Tuple[Optional[str], int]:
    return None, 0


class TeamFortschrittService:
    def __init__(
        self,
        repository: TeamFortschrittRepository,
        settings: Optional[Settings] = None,
        art9: Optional[Callable[[str], bool]] = None,
        bedarf: Bedarf = _kein_bedarf,
        heute: Callable[[], date] = heute_utc,
        pruefwerte: Optional[WochenPruefwerte] = None,
        saison: Optional[Callable[[], str]] = None,
    ):
        self._repository = repository
        self._settings = settings
        # Ohne Angabe die gespeicherte Art.-9-Einwilligung; spaet geholt, damit Tests
        # das Repository ersetzen koennen.
        self._art9 = art9 or _art9_eingewilligt
        self._bedarf = bedarf
        self._heute = heute
        self._pruefwerte = pruefwerte or WochenPruefwerte()
        # Gezaehlt und gezeigt wird nur fuer Teams der aktuellen Saison; vergangene
        # Saisons sind Abzeichen (GLOSSARY.md "Saison"). Ohne Angabe die Einstellung.
        self._saison = saison or _aktuelle_saison
        self._bedarf_je_woche: Dict[date, Tuple[Optional[str], int]] = {}

    @property
    def _einstellungen(self) -> Settings:
        return self._settings if self._settings is not None else globale_settings

    # --- Schalter --------------------------------------------------------------

    def zaehlt(self) -> bool:
        return schalter_wirksam("team_fortschritt", self._settings)

    def quests_wirksam(self) -> bool:
        return schalter_wirksam("team_quests", self._settings)

    def _aktuelle(self, teams):
        saison = self._saison()
        return [t for t in teams if t.saison == saison]

    # --- Zaehlen ---------------------------------------------------------------

    def zaehlen(self, kennung: Optional[str], art: Art, gegenstand: str = "") -> int:
        """
        Ein Ereignis der Person fuer ihre Teams zaehlen; synchron, im Thread aufrufen.
        ``gegenstand``: woran entdoppelt wird (Beitrag bei Beitrag und Stimme, leer bei
        "Ja, gepostet"). Gibt zurueck, fuer wie viele Teams gezaehlt wurde.
        """
        if not kennung or kennung == "anonymous" or not self.zaehlt():
            return 0
        if self._einstellungen.ist_startkonto(kennung):
            return 0
        if art == Art.GEPOSTET and not self._art9(kennung):
            return 0
        teams = self._aktuelle(self._repository.eigene_teams(kennung, SUMME_GEDECKT))
        if not teams:
            return 0
        groessen = self._repository.einwilligende_je_team(
            [t.schluessel for t in teams], SUMME_GEDECKT
        )
        woche = wochenbeginn(self._heute())
        zu_zaehlen = [
            t.schluessel
            for t in teams
            if zeigbar(groessen.get(t.schluessel, 0))
            and self._pruefwerte.erstmals(
                f"{art.value}|{kennung}|{gegenstand}|{t.team_name}|{t.saison}", woche
            )
        ]
        if zu_zaehlen:
            self._repository.erhoehen(zu_zaehlen, woche, art)
        return len(zu_zaehlen)

    # --- Zeigen ----------------------------------------------------------------

    async def staende(self, kennung: str) -> Dict[TeamSchluessel, TeamStand]:
        """
        Je eigenem Team mit deckender Einwilligung, was "Meine Teams" zeigt. Leer bei
        ausgeschaltetem Schalter; Teams ohne deckende Einwilligung fehlen.
        """
        if not self.zaehlt():
            return {}
        teams = self._aktuelle(
            await asyncio.to_thread(
                self._repository.eigene_teams, kennung, SUMME_GEDECKT
            )
        )
        if not teams:
            return {}
        schluessel = [t.schluessel for t in teams]
        groessen = await asyncio.to_thread(
            self._repository.einwilligende_je_team, schluessel, SUMME_GEDECKT
        )
        laufende = wochenbeginn(self._heute())
        vorige = laufende - WOCHE
        grosse = [s for s in schluessel if zeigbar(groessen.get(s, 0))]
        zaehler = (
            await asyncio.to_thread(self._repository.wochen, grosse, vorige)
            if grosse
            else {}
        )
        quests: Dict[TeamSchluessel, TeamQuestStand] = {}
        if grosse and self.quests_wirksam():
            quests = await self._quest_staende(grosse, groessen, zaehler, laufende)

        staende: Dict[TeamSchluessel, TeamStand] = {}
        for s in schluessel:
            if s not in grosse:
                staende[s] = TeamStand(TeamWirkung(woche=vorige, waechst_noch=True))
                continue
            z = zaehler.get(s, Wochenzaehlung())
            staende[s] = TeamStand(
                TeamWirkung(
                    woche=vorige,
                    waechst_noch=False,
                    beitraege=anzeige(z.beitraege),
                    bewertungen=anzeige(z.bewertungen),
                    gepostet=anzeige(z.gepostet),
                ),
                quests.get(s),
            )
        return staende

    async def _quest_staende(
        self,
        grosse: List[TeamSchluessel],
        groessen: Dict[TeamSchluessel, int],
        zaehler_vorige: Dict[TeamSchluessel, Wochenzaehlung],
        laufende: date,
    ) -> Dict[TeamSchluessel, TeamQuestStand]:
        vorige = laufende - WOCHE
        laufend = await asyncio.to_thread(self._repository.quests, grosse, laufende)
        fehlend = [s for s in grosse if s not in laufend]
        bedarf = await self._bedarf_der_woche(laufende) if fehlend else None
        if bedarf is not None:
            thema, brachflaechen = bedarf
            for s in fehlend:
                laufend[s] = await asyncio.to_thread(
                    self._repository.quest_anlegen,
                    Quest(
                        team_name=s[0],
                        saison=s[1],
                        woche=laufende,
                        thema=thema,
                        ziel=quest_ziel(brachflaechen, groessen.get(s, 0)),
                    ),
                )
        vorige_quests = await asyncio.to_thread(self._repository.quests, grosse, vorige)
        staende = {}
        for s in grosse:
            vq = vorige_quests.get(s)
            geschafft = (
                vq is not None
                and zaehler_vorige.get(s, Wochenzaehlung()).gesamt >= vq.ziel
            )
            staende[s] = TeamQuestStand(
                laufende=laufend.get(s),
                vorige_geschafft=geschafft,
                # Ein verfehltes Ziel erwaehnt nichts, auch nicht sein Thema.
                vorige_thema=vq.thema if geschafft else None,
            )
        return staende

    async def _bedarf_der_woche(
        self, woche: date
    ) -> Optional[Tuple[Optional[str], int]]:
        """
        Einmal je Woche und Prozess; fuer alle Teams derselbe Bedarf. None, wenn er sich
        nicht lesen laesst: Dann entsteht noch keine Quest, der naechste Abruf versucht
        es wieder (sonst stuende die Woche fest auf dem Mindestziel).
        """
        if woche not in self._bedarf_je_woche:
            try:
                ergebnis = await self._bedarf()
            except Exception as e:
                logger.warning(f"Team quest demand not read: {type(e).__name__}")
                return None
            self._bedarf_je_woche = {woche: ergebnis}
        return self._bedarf_je_woche[woche]

    # --- Quest-Punkte ----------------------------------------------------------

    def quest_tage(
        self, kennung: str, beitraege: Iterable[datetime], grenze: datetime
    ) -> Dict[date, int]:
        """
        Je Tag die Zahl der erreichten Team-Quests, fuer die die Person Quest-Punkte
        bekommt; synchron. ``beitraege``: Zeitpunkte ihrer heute sichtbaren Beitraege;
        es zaehlen nur die bis ``grenze`` (drei Tage ohne Sperre). Der Tag ist der
        Montag nach der Quest-Woche (Auswertung nach Wochenende).
        """
        if not self.quests_wirksam():
            return {}
        teams = self._repository.eigene_teams(kennung, SUMME_GEDECKT)
        if not teams:
            return {}
        eintritt = {t.schluessel: t.eingetreten_am for t in teams}
        erreicht = self._repository.erreichte_quests(
            list(eintritt), vor=wochenbeginn(self._heute())
        )
        zeitpunkte = [
            z.astimezone(timezone.utc)
            for z in beitraege
            if z.astimezone(timezone.utc) <= grenze
        ]
        tage: Dict[date, int] = {}
        for quest in erreicht:
            ende = quest.woche + WOCHE
            eingetreten = eintritt[(quest.team_name, quest.saison)]
            beigetragen = any(
                max(quest.woche, eingetreten) <= z.date() < ende for z in zeitpunkte
            )
            if beigetragen:
                tage[ende] = tage.get(ende, 0) + 1
        return tage


def _aktuelle_saison() -> str:
    from services.einstellungen_service import aktuelle_saison

    return aktuelle_saison()


def _art9_eingewilligt(kennung: str) -> bool:
    from services.art9_einwilligung_service import get_art9_einwilligung_service

    return get_art9_einwilligung_service().eingewilligt(kennung)


_service: Optional[TeamFortschrittService] = None


def get_team_fortschritt_service() -> TeamFortschrittService:
    global _service
    if _service is None:
        from dependencies import team_bedarf
        from repositories.team_fortschritt_repository import (
            get_team_fortschritt_repository,
        )

        _service = TeamFortschrittService(
            get_team_fortschritt_repository(), bedarf=team_bedarf
        )
    return _service


def team_fortschritt_service_setzen(service: Optional[TeamFortschrittService]) -> None:
    """Fuer Tests: einen eigenen Dienst einsetzen (None: wieder aus der Datenbank)."""
    global _service
    _service = service


def team_zaehlen(kennung: Optional[str], art: Art, gegenstand: str = "") -> None:
    """
    Fuer die Endpunkte: zaehlen und jeden Fehler nur loggen. Der Wochenzaehler ist
    Beiwerk; ein Beitrag, eine Stimme oder "Ja, gepostet" gilt auch ohne ihn.
    """
    try:
        get_team_fortschritt_service().zaehlen(kennung, art, gegenstand)
    except Exception as e:
        logger.error(f"Team week counter not raised: {type(e).__name__}")


async def team_zaehlen_async(
    kennung: Optional[str], art: Art, gegenstand: str = ""
) -> None:
    """Wie team_zaehlen, aus einem async-Endpunkt (die Abfragen laufen im Thread)."""
    await asyncio.to_thread(team_zaehlen, kennung, art, gegenstand)
