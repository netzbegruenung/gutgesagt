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
Meilensteine" gilt und seit wann die zum Spielgefuehl-Wortlaut mit Quest-Punkten
(spielgefuehl-2026-11-28, nur mit wirksamem Schalter spielgefuehl_buehne), prueft services/punkte_service.py davor und reicht nur
Beitraege ab dieser Einwilligung herein.

Quasi-live (Schalter ``team_live``, wirkt nur mit ``teams``; Jura-Akte 28.11.2026,
Regeln in domain/team_fortschritt.py): Waehrend der Schalter wirkt, erhoeht ``zaehlen``
fuer Teams ab 20 Mitgliedern mit Einwilligung zusaetzlich den Stundenzaehler des
laufenden Blocks (team_stunden: Team, Saison, Blockbeginn, Zahl, ohne Kennung) und
merkt sich in ``StundenPruefwerte`` (nur Arbeitsspeicher, Schluessel je Tag) einen
HMAC-Pruefwert je Mitglied, Team und Block. Gezaehlt wird dasselbe wie im
Wochenzaehler, nach dessen Entdoppelung. ``bloecke_veroeffentlichen`` (Takt
``live_im_takt``, 15 min nach jeder vollen Stunde) rechnet jeden abgelaufenen Block
einmal vor: Mit den uebertragenen Bloecken desselben Tages ab 10 verschiedenen
Beitragenden wird er freigegeben (``freigabe`` = seine Zahl samt der uebertragenen),
sonst uebertragen. Fehlt die Menge der Pruefwerte fuer den Block (Neustart seit
Blockbeginn, Schalter zwischendurch aus), wird uebertragen, nie freigegeben. Die
Mitgliederzahl wird dabei mit abgelegt. "Meine Teams" (``staende``) liest nur diese
vorberechneten Werte: die Summe der heute freigegebenen Bloecke (auf 10 abgerundet),
bis zu welcher vollen Stunde, ob die letzte Stunde noch laeuft, die Mitgliederzahl und
die Quest-Stufe aus den in der Woche freigegebenen Bloecken. Die Stundenzaehler
loescht der Loeschlauf mit dem Wochenwechsel (services/loeschfristen_service.py). Mit
mehreren Workern sieht jeder nur einen Teil der Pruefwerte und gibt seltener frei,
nie zu frueh; vorberechnet wird je Block nur einmal (``stunde_abschliessen``).

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
import secrets
from datetime import date, datetime, time, timedelta, timezone
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
    BLOCK,
    SUMME_GEDECKT,
    VEROEFFENTLICHUNG_NACH,
    ZEITZONE,
    Art,
    Wochenzaehlung,
    anzeige,
    bis_stunde,
    blockbeginn,
    freigeben,
    live_anzeige,
    live_zeigbar,
    mitglieder_anzeige,
    quest_stufe,
    quest_ziel,
    tagesbeginn,
    wochenbeginn_live,
    zeigbar,
)
from domain.themen import THEMEN
from repositories.team_fortschritt_repository import (
    FREIGEGEBEN,
    OFFEN,
    UEBERTRAGEN,
    EigenesTeam,
    Quest,
    Stunde,
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


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


class StundenPruefwerte:
    """
    Die Pruefwerte der Stundenbloecke fuer den Live-Stand, nur im Arbeitsspeicher: je
    Team und Block die Menge der HMAC-Werte der Mitglieder, die beigetragen haben, mit
    einem Schluessel je Tag (deutsche Zeit), der nur hier liegt. So laesst sich zaehlen,
    wie viele verschiedene beigetragen haben, ohne dass eine Kennung irgendwo steht.

    ``beobachtet``: ob die Menge eines Blocks vollstaendig ist, also seit Blockbeginn
    kein Neustart war und der Speicher nicht geleert wurde. Die Mengen eines Blocks
    verfallen mit seiner Freigabe, alle uebrigen mit dem Tag.
    """

    def __init__(self, jetzt: Callable[[], datetime] = _jetzt):
        self._jetzt = jetzt
        self._seit = jetzt()
        self._schluessel: Dict[date, bytes] = {}
        self._werte: Dict[Tuple[TeamSchluessel, datetime], Set[str]] = {}
        self._sperre = threading.Lock()

    @staticmethod
    def _tag(block: datetime) -> date:
        return block.astimezone(ZEITZONE).date()

    def merken(self, team: TeamSchluessel, block: datetime, kennung: str) -> None:
        with self._sperre:
            tag = self._tag(block)
            schluessel = self._schluessel.setdefault(tag, secrets.token_bytes(32))
            wert = hmac.new(
                schluessel,
                f"stunde|{team[0]}|{team[1]}|{kennung}".encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            self._werte.setdefault((team, block), set()).add(wert)

    def verschiedene(self, team: TeamSchluessel, bloecke: Iterable[datetime]) -> int:
        """Wie viele verschiedene in diesen Bloecken (eines Tages) beigetragen haben."""
        with self._sperre:
            alle: Set[str] = set()
            for block in bloecke:
                alle |= self._werte.get((team, block), set())
            return len(alle)

    def beobachtet(self, block: datetime) -> bool:
        with self._sperre:
            return self._seit <= block

    def vergessen(self, team: TeamSchluessel, bloecke: Iterable[datetime]) -> None:
        with self._sperre:
            for block in bloecke:
                self._werte.pop((team, block), None)

    def aufraeumen(self, vor: datetime) -> None:
        """Mengen der Bloecke vor ``vor`` und Schluessel der Tage davor verwerfen."""
        with self._sperre:
            for schluessel in [k for k in self._werte if k[1] < vor]:
                del self._werte[schluessel]
            tag = self._tag(vor)
            for alt in [t for t in self._schluessel if t < tag]:
                del self._schluessel[alt]

    def leeren(self) -> None:
        """Alles verwerfen (Schalter aus); laufende Bloecke gelten danach als unbeobachtet."""
        with self._sperre:
            self._werte = {}
            self._schluessel = {}
            self._seit = self._jetzt()


@dataclass(frozen=True)
class TeamLiveWerte:
    """
    Die freigegebenen Werte eines Teams fuer den Live-Stand (``live_werte``), ohne Bezug
    zu einer Person: die heute freigegebene Summe (abgerundeter Text) bis zur vollen
    Stunde ``bis``, ob die letzte Stunde noch laeuft, die abgerundete Mitgliederzahl und
    die in der Woche freigegebene Summe (nur fuer die Quest-Stufe, nie gezeigt).
    """

    laeuft_noch: bool
    mitglieder: Optional[int]
    bis: Optional[int]
    tagessumme: Optional[str]
    woche_freigegeben: int


@dataclass(frozen=True)
class TeamLive:
    """
    Der Live-Stand eines Teams (team_live), nur aus vorberechneten Werten: die heute
    freigegebene Summe (abgerundeter Text) bis zur vollen Stunde ``bis``, ob die letzte
    Stunde noch laeuft, die abgerundete Mitgliederzahl, die Quest-Stufe (0 bis 3, None
    ohne Quest) und ob der Hinweis an Bestandsmitglieder faellig ist.
    """

    laeuft_noch: bool
    mitglieder: Optional[int]
    bis: Optional[int] = None
    tagessumme: Optional[str] = None
    quest_stufe: Optional[int] = None
    hinweis_neu: bool = False


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
    live: Optional[TeamLive] = None


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
        jetzt: Callable[[], datetime] = _jetzt,
        stunden: Optional[StundenPruefwerte] = None,
        live_seit: Optional[Callable[[], Optional[datetime]]] = None,
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
        self._jetzt = jetzt
        self._stunden = stunden or StundenPruefwerte(jetzt)
        # Seit wann team_live eingeschaltet ist (Hinweis an Bestandsmitglieder)
        self._live_seit = live_seit or _team_live_eingeschaltet_am
        # Der zuletzt vorberechnete Block in diesem Prozess
        self._vorberechnet_bis: Optional[datetime] = None

    @property
    def _einstellungen(self) -> Settings:
        return self._settings if self._settings is not None else globale_settings

    # --- Schalter --------------------------------------------------------------

    def zaehlt(self) -> bool:
        # Der Team-Fortschritt gehoert seit dem Schalter-Umbau zum Paket Teams
        return schalter_wirksam("teams", self._settings)

    def quests_wirksam(self) -> bool:
        return schalter_wirksam("team_quests", self._settings)

    def live_wirksam(self) -> bool:
        return schalter_wirksam("team_live", self._settings)

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
            self._stunde_zaehlen(kennung, zu_zaehlen, groessen)
        return len(zu_zaehlen)

    def _stunde_zaehlen(
        self,
        kennung: str,
        teams: List[TeamSchluessel],
        groessen: Dict[TeamSchluessel, int],
    ) -> None:
        """Den Stundenzaehler der Teams ab 20 erhoehen und den Pruefwert merken."""
        live = [t for t in teams if live_zeigbar(groessen.get(t, 0))]
        if not live or not self.live_wirksam():
            return
        block = blockbeginn(self._jetzt())
        for team in live:
            self._stunden.merken(team, block, kennung)
        self._repository.stunde_erhoehen(live, block)

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
        live: Dict[TeamSchluessel, TeamLive] = {}
        if grosse and self.live_wirksam():
            live = await self._live_staende(
                [t for t in teams if t.schluessel in grosse], quests
            )

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
                live.get(s),
            )
        return staende

    # --- Live-Stand (team_live) ------------------------------------------------

    def live_werte(
        self, teams: Iterable[TeamSchluessel]
    ) -> Dict[TeamSchluessel, "TeamLiveWerte"]:
        """
        Die freigegebenen Werte je Team, ohne Bezug zur aufrufenden Person; synchron.
        Nur aus vorberechneten Stundenzaehlern, alle Schwellen und Rundungen sind hier
        schon angewendet. "Meine Teams" zeigt sie Mitgliedern; eine spaetere weitere
        Darstellung derselben Werte (etwa eine Saalansicht; die braucht vorher einen
        neuen Wortlaut, eine neue Kennung und eine eigene Pruefung) liest nur hier.
        Teams fehlen, deren letzter vorberechneter Block unter 20 Mitgliedern lag oder
        vor der letzten Stunde des Vortags liegt; die Schwelle wird bei jedem
        Vorberechnen neu geprueft, Austritte zaehlen also mit.

        Die Tagessumme enthaelt nur freigegebene Bloecke, bis zur letzten freigegebenen
        Blockgrenze: Ein uebertragener Block fehlt, bis er mit dem naechsten freigegeben
        ist, und laesst sich so nicht als Differenz herausrechnen.
        """
        teams = list(teams)
        if not teams:
            return {}
        jetzt = self._jetzt()
        heute_ab = tagesbeginn(jetzt)
        woche_ab = wochenbeginn_live(jetzt)
        # Bis der letzte Block des Vortags vorberechnet ist (0:15), zaehlt der davor
        frisch_ab = heute_ab - 2 * BLOCK
        je_team: Dict[TeamSchluessel, List[Stunde]] = {}
        for stunde in self._repository.stunden(teams, min(frisch_ab, woche_ab)):
            if stunde.stand != OFFEN:
                je_team.setdefault(stunde.schluessel, []).append(stunde)
        ergebnis: Dict[TeamSchluessel, TeamLiveWerte] = {}
        for team in teams:
            fertig = je_team.get(team, [])
            if not fertig:
                continue
            letzte = fertig[-1]
            if letzte.block_beginn < frisch_ab or not live_zeigbar(
                letzte.mitglieder or 0
            ):
                continue
            heute = [x for x in fertig if x.block_beginn >= heute_ab]
            frei = [x for x in heute if x.stand == FREIGEGEBEN]
            ergebnis[team] = TeamLiveWerte(
                laeuft_noch=not heute or heute[-1].stand != FREIGEGEBEN,
                mitglieder=mitglieder_anzeige(letzte.mitglieder or 0),
                bis=bis_stunde(frei[-1].block_beginn) if frei else None,
                tagessumme=(
                    live_anzeige(sum(x.freigabe or 0 for x in frei)) if frei else None
                ),
                woche_freigegeben=sum(
                    x.freigabe or 0
                    for x in fertig
                    if x.stand == FREIGEGEBEN and x.block_beginn >= woche_ab
                ),
            )
        return ergebnis

    async def _live_staende(
        self, teams: List[EigenesTeam], quests: Dict[TeamSchluessel, TeamQuestStand]
    ) -> Dict[TeamSchluessel, TeamLive]:
        """Je eigenem Team die freigegebenen Werte samt Quest-Stufe und Hinweis."""
        werte = await asyncio.to_thread(self.live_werte, [t.schluessel for t in teams])
        if not werte:
            return {}
        live_seit = await self._live_seit_lesen()
        ergebnis: Dict[TeamSchluessel, TeamLive] = {}
        for team in teams:
            w = werte.get(team.schluessel)
            if w is None:
                continue
            quest = quests.get(team.schluessel)
            ergebnis[team.schluessel] = TeamLive(
                laeuft_noch=w.laeuft_noch,
                mitglieder=w.mitglieder,
                bis=w.bis,
                tagessumme=w.tagessumme,
                quest_stufe=(
                    quest_stufe(w.woche_freigegeben, quest.laufende.ziel)
                    if quest is not None and quest.laufende is not None
                    else None
                ),
                hinweis_neu=(
                    live_seit is not None
                    and team.einwilligung_zeitpunkt is not None
                    and team.einwilligung_zeitpunkt < live_seit
                ),
            )
        return ergebnis

    async def _live_seit_lesen(self) -> Optional[datetime]:
        try:
            return await asyncio.to_thread(self._live_seit)
        except Exception as e:
            logger.warning(f"Team live switch-on time not read: {type(e).__name__}")
            return None

    def bloecke_veroeffentlichen(self) -> int:
        """
        Jeden Block, der seit mindestens 15 min abgelaufen ist und in diesem Prozess
        noch nicht vorberechnet wurde, einmal vorberechnen (nur Bloecke des Tages, in
        den der letzte faellige faellt); synchron. Gibt die Zahl der freigegebenen
        Bloecke zurueck.

        Wirkt team_live nicht (aus oder nach team_live_bis): verwirft die Pruefwerte,
        rechnet nichts und loescht sofort alle Stundenzaehler (Jura 28.11.: die DSE
        nennt sie dann nicht mehr), in jedem Lauf: Waehrend des Schalter-Caches kann
        ein Ereignis noch einen Zaehler anlegen.
        """
        if not self.live_wirksam():
            self._stunden.leeren()
            self._vorberechnet_bis = None
            self._repository.stunden_loeschen_vor(self._jetzt() + BLOCK)
            return 0
        letzter = blockbeginn(self._jetzt() - VEROEFFENTLICHUNG_NACH - BLOCK)
        tag_ab = tagesbeginn(letzter)
        block = tag_ab
        if self._vorberechnet_bis is not None:
            block = max(block, self._vorberechnet_bis + BLOCK)
        freigegeben = 0
        while block <= letzter:
            freigegeben += self._block_vorberechnen(block)
            self._vorberechnet_bis = block
            block += BLOCK
        self._stunden.aufraeumen(tag_ab)
        return freigegeben

    def _block_vorberechnen(self, block: datetime) -> int:
        saison = self._saison()
        tag_ab = tagesbeginn(block)
        groessen = self._repository.einwilligende_der_saison(saison, SUMME_GEDECKT)
        teams = {t for t, n in groessen.items() if live_zeigbar(n)}
        teams |= set(self._repository.teams_mit_stunden(saison, tag_ab))
        if not teams:
            return 0
        je_team: Dict[TeamSchluessel, List[Stunde]] = {}
        for stunde in self._repository.stunden(list(teams), tag_ab):
            if stunde.block_beginn <= block:
                je_team.setdefault(stunde.schluessel, []).append(stunde)
        beobachtet = self._stunden.beobachtet(block)
        freigegeben = 0
        for team in sorted(teams):
            stunden = je_team.get(team, [])
            eigene = next((x for x in stunden if x.block_beginn == block), None)
            if eigene is not None and eigene.stand != OFFEN:
                continue
            frei_davor = [x.block_beginn for x in stunden if x.stand == FREIGEGEBEN]
            ab = max(frei_davor) if frei_davor else None
            offen = [
                x
                for x in stunden
                if x.stand == UEBERTRAGEN and (ab is None or x.block_beginn > ab)
            ]
            summe = sum(x.anzahl for x in offen) + (eigene.anzahl if eigene else 0)
            bloecke = [x.block_beginn for x in offen] + [block]
            mitglieder = groessen.get(team, 0)
            frei = live_zeigbar(mitglieder) and freigeben(
                self._stunden.verschiedene(team, bloecke), beobachtet
            )
            abgeschlossen = self._repository.stunde_abschliessen(
                team,
                block,
                FREIGEGEBEN if frei else UEBERTRAGEN,
                summe if frei else None,
                mitglieder,
            )
            if abgeschlossen and frei:
                self._stunden.vergessen(team, bloecke)
                freigegeben += 1
        return freigegeben

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


def _team_live_eingeschaltet_am() -> Optional[datetime]:
    """
    Seit wann team_live wirkt: der frueheste Stundenblock. Wirkt der Schalter nicht,
    loescht der Takt alle Stundenzaehler; der frueheste ist also der erste seit dem
    letzten Wirksamwerden (Obergrenze, Admin-Wert und Enddatum zusammen), nicht der
    Zeitpunkt des Admin-Werts allein.
    """
    from repositories.team_fortschritt_repository import (
        get_team_fortschritt_repository,
    )

    return get_team_fortschritt_repository().erste_stunde()


def _sekunden_bis_zum_takt(jetzt: datetime) -> float:
    """Sekunden bis 15 min (und 5 s Puffer) nach der naechsten vollen Stunde."""
    naechste = blockbeginn(jetzt) + VEROEFFENTLICHUNG_NACH + timedelta(seconds=5)
    if naechste <= jetzt:
        naechste += BLOCK
    return (naechste - jetzt).total_seconds()


async def live_im_takt(service: "TeamFortschrittService") -> None:
    """
    Hintergrund-Task: rechnet sofort und dann 15 min nach jeder vollen Stunde die
    abgelaufenen Stundenbloecke vor (``bloecke_veroeffentlichen``), bis er abgebrochen
    wird; wirkt team_live nicht, loescht er die Stundenzaehler. Ein Fehler wird nur protokolliert; der naechste Lauf holt nach.
    """
    while True:
        try:
            # Bewusst ohne Log je Block oder Team: gezaehlt wird nur im Speicher.
            await asyncio.to_thread(service.bloecke_veroeffentlichen)
        except Exception as e:
            logger.error(
                f"Team hour blocks not computed: {type(e).__name__}", exc_info=True
            )
        await asyncio.sleep(_sekunden_bis_zum_takt(_jetzt()))


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
