"""
Spielgefuehl als eine Einstellung in drei Stufen (domain/spielgefuehl.py, Schalter
``spielgefuehl_buehne``).

Der Schalter waehlt das Modell:

- **aus** (Standard): die bisherigen drei Einwilligungen "Punkte und Meilensteine",
  "Abzeichen am Namen" und "Rangliste" gelten unveraendert.
- **an**: es gilt nur die Antwort in der Tabelle ``spielgefuehl``. Die bisherigen
  Antworten bleiben als Nachweis stehen, werden aber nicht ausgewertet und nicht
  uebernommen: Wer noch keine Antwort im neuen Modell hat, hat "keine Antwort" und
  wird neu gefragt (Jura 26.11., verbindlich). Punkte wirken ab Stufe ``fuer_mich``,
  die Rangliste nur mit Stufe ``rangliste``, Abzeichen am Anzeigenamen nie; Abzeichen
  erscheinen nur in der Rangliste.

Alle Stellen, die bisher die Einwilligung "Punkte und Meilensteine" oder die
Teilnahme an der Rangliste gefragt haben, fragen hier (``punkte_eingewilligt``,
``punkte_eingewilligte``, ``RanglistenQuelle``). Ein Herabstufen wirkt sofort, weil
jeder Abruf neu fragt.
"""

import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional, Set

from core.config import Settings
from core.logging import get_logger
from domain.rangliste import neuer_ranglistenname
from domain.spielgefuehl import (
    NAMENS_VORBELEGUNG,
    WORTLAUTE,
    NamenswahlFehlt,
    Stufe,
    UnbekannterWortlaut,
    aktueller_wortlaut,
    in_rangliste,
    neu_fragen,
    punkte_wirksam,
    stimmen_eingewilligt,
)
from repositories.rangliste_einwilligung_repository import (
    RanglisteAntwort,
    RanglisteEinwilligungRepository,
    Teilnahme,
)
from repositories.spielgefuehl_repository import (
    SpielgefuehlAntwort,
    SpielgefuehlRepository,
)

logger = get_logger(__name__)

SCHALTER = "spielgefuehl_buehne"
STIMMEN_SCHALTER = "muster_stimmen"


class NichtInRangliste(RuntimeError):
    """Neu wuerfeln geht nur mit Stufe rangliste."""


class ZuOftGewuerfelt(RuntimeError):
    """Neu wuerfeln hoechstens einmal je WUERFELN_ABSTAND_SEKUNDEN und Person."""


# Rang der Stufen fuers Herabstufen: hoeher heisst mehr eingewilligt.
_RANG: Dict[Stufe, int] = {Stufe.AUS: 0, Stufe.FUER_MICH: 1, Stufe.RANGLISTE: 2}


# Jeder Wurf ist eine Nachweiszeile: gegen Klick-Serien hoechstens einer je so viele
# Sekunden und Person (nur im Arbeitsspeicher).
WUERFELN_ABSTAND_SEKUNDEN = 10.0


def buehne_aktiv(einstellungen: Optional[Settings] = None) -> bool:
    """Ob das neue Modell gilt (Obergrenze und Admin-Wert, services/schalter_service.py)."""
    from services.schalter_service import schalter_wirksam

    return schalter_wirksam(SCHALTER, einstellungen)


def stimmen_aktiv(einstellungen: Optional[Settings] = None) -> bool:
    """
    Ob gegenseitige Zustimmungen in die Muster-Hinweise einfliessen und die Frage den
    Wortlaut ``STIMMEN_WORTLAUT`` zeigt (Schalter ``muster_stimmen``, wirkt nur mit
    ``spielgefuehl_buehne``).
    """
    from services.schalter_service import schalter_wirksam

    return schalter_wirksam(STIMMEN_SCHALTER, einstellungen)


def _neues_repository() -> SpielgefuehlRepository:
    from repositories.spielgefuehl_repository import get_spielgefuehl_repository

    return get_spielgefuehl_repository()


def stufe_punkte_wirksam(user_id: str) -> bool:
    """Im neuen Modell: Stufe fuer_mich oder rangliste zu einem geltenden Wortlaut."""
    antwort = _neues_repository().lesen(user_id)
    return antwort is not None and punkte_wirksam(antwort.wirksame_stufe)


def punkte_eingewilligt(user_id: str) -> bool:
    """
    Werden fuer die Kennung Punkte und Meilensteine berechnet? Im neuen Modell ab
    Stufe ``fuer_mich``, sonst die Einwilligung "Punkte und Meilensteine". Synchron,
    je Aufruf gefragt: Ein Herabstufen oder Widerruf wirkt sofort.
    """
    if buehne_aktiv():
        return stufe_punkte_wirksam(user_id)
    from repositories.punkte_einwilligung_repository import (
        get_punkte_einwilligung_repository,
    )

    return get_punkte_einwilligung_repository().eingewilligt(user_id)


def punkte_eingewilligte(
    kennungen: Iterable[str], einstellungen: Optional[Settings] = None
) -> Set[str]:
    """
    Wie ``punkte_eingewilligt`` fuer viele Kennungen in einer Abfrage (Rangliste,
    Muster-Hinweise im Admin-Dashboard).
    """
    liste = list(kennungen)
    if buehne_aktiv(einstellungen):
        stufen = _neues_repository().wirksame_stufen(liste)
        return {k for k, stufe in stufen.items() if punkte_wirksam(stufe)}
    from repositories.punkte_einwilligung_repository import (
        get_punkte_einwilligung_repository,
    )

    return get_punkte_einwilligung_repository().eingewilligte(liste)


def stimmen_eingewilligte(kennungen: Iterable[str]) -> Set[str]:
    """
    Die Kennungen, deren Zustimmungen in die Muster-Hinweise einfliessen duerfen: Stufe
    ab ``fuer_mich`` zum Wortlaut ``STIMMEN_WORTLAUT`` (domain/spielgefuehl.py) und eine
    geltende Art.-9-Einwilligung. Ohne diese gibt es keine Stimmen (ihr Widerruf loescht
    sie), also auch keinen Hinweis daraus, auch nicht aus einem Paar-Pruefwert von davor.
    Fragt den Schalter nicht; das tun die Aufrufer.
    """
    liste = list(set(kennungen))
    if not liste:
        return set()
    mit = _neues_repository().stimmen_eingewilligte(liste)
    if not mit:
        return set()
    from services.art9_einwilligung_service import get_art9_einwilligung_service

    return mit & get_art9_einwilligung_service().eingewilligte(mit)


class RanglistenQuelle:
    """
    Wer in der Rangliste mitspielt, fuer services/rangliste_service.py: mit Schalter
    aus der Tabelle ``spielgefuehl`` (Stufe rangliste), sonst aus der bisherigen
    Einwilligung zur Rangliste. Dieselbe Schnittstelle wie
    RanglisteEinwilligungRepository, soweit der Dienst sie liest.
    """

    def __init__(
        self,
        alt: RanglisteEinwilligungRepository,
        neu: SpielgefuehlRepository,
        aktiv: Callable[[], bool] = buehne_aktiv,
    ):
        self._alt = alt
        self._neu = neu
        self._aktiv = aktiv

    def lesen(self, user_id: str) -> Optional[RanglisteAntwort]:
        if not self._aktiv():
            return self._alt.lesen(user_id)
        antwort = self._neu.lesen(user_id)
        if antwort is None:
            return None
        return RanglisteAntwort(
            teilnehmen=in_rangliste(antwort.wirksame_stufe),
            mit_anzeigename=antwort.mit_anzeigename,
            wortlaut=antwort.wortlaut,
            beantwortet_am=antwort.beantwortet_am,
            ranglistenname=antwort.ranglistenname,
        )

    def teilnehmende(self) -> Dict[str, Teilnahme]:
        if not self._aktiv():
            return self._alt.teilnehmende()
        return self._neu.teilnehmende()

    def vergebene_namen(self) -> Set[str]:
        return self._alt.vergebene_namen() | self._neu.vergebene_namen()

    def antworten(self, *args, **kwargs) -> None:
        # Die bisherige Frage zur Rangliste gibt es im neuen Modell nicht mehr
        # (api/v1/rangliste.py antwortet dann mit 404).
        if self._aktiv():
            raise RuntimeError(
                "Rangliste wird im neuen Modell ueber das Spielgefuehl gewaehlt"
            )
        self._alt.antworten(*args, **kwargs)


@dataclass(frozen=True)
class SpielgefuehlStand:
    # None: keine Antwort im neuen Modell oder zu einem nicht mehr geltenden Wortlaut
    stufe: Optional[Stufe]
    mit_anzeigename: Optional[bool]
    ranglistenname: Optional[str]
    # Bisher Abzeichen am Anzeigenamen gezeigt und noch nicht neu geantwortet
    abzeichen_hinweis: bool


class SpielgefuehlService:
    def __init__(
        self,
        repository: SpielgefuehlRepository,
        alte_namen: Callable[[], Set[str]],
        zeigte_abzeichen: Callable[[str], bool],
        abzeichen_vergessen: Callable[[str], None] = lambda user_id: None,
        alt_zuruecknehmen: Callable[[str, Stufe], None] = lambda user_id, stufe: None,
        uhr: Callable[[], float] = time.monotonic,
        hinweise_vergessen: Callable[[str], None] = lambda user_id: None,
        stimmen: Callable[[], bool] = lambda: False,
        stimmen_hinweise_vergessen: Callable[[str], None] = lambda user_id: None,
    ):
        """
        ``alte_namen``: Ranglistennamen aus der bisherigen Einwilligung (zum Wuerfeln
        ohne Doppelung); ``zeigte_abzeichen(kennung)``: ob die juengste bisherige
        Antwort zur Sichtbarkeit "zeigen" war; ``abzeichen_vergessen``: die Abzeichen
        der Person sofort aus der Rangliste nehmen (AbzeichenService.vergessen);
        ``alt_zuruecknehmen(kennung, stufe)``: die gewaehlte Stufe in den bisherigen
        Einwilligungen festhalten, soweit sie dort ein Nein ist, damit sie auch nach
        dem Ausschalten des Schalters gilt; ``hinweise_vergessen(kennung)``: die
        Muster-Hinweise der Person loeschen (bei ``aus``); ``stimmen``: ob der
        Schalter ``muster_stimmen`` wirkt; ``stimmen_hinweise_vergessen(kennung)``: nur
        die Muster-Hinweise aus Zustimmungen loeschen (Antwort ohne den Zweck
        Zustimmungen nach einer mit ihm). Alle synchron.
        """
        self._repository = repository
        self._alte_namen = alte_namen
        self._zeigte_abzeichen = zeigte_abzeichen
        self._abzeichen_vergessen = abzeichen_vergessen
        self._alt_zuruecknehmen = alt_zuruecknehmen
        self._uhr = uhr
        self._hinweise_vergessen = hinweise_vergessen
        self._stimmen = stimmen
        self._stimmen_hinweise_vergessen = stimmen_hinweise_vergessen
        self._gewuerfelt: Dict[str, float] = {}
        self._sperre = threading.Lock()

    def stand(self, user_id: str, stimmen: Optional[bool] = None) -> SpielgefuehlStand:
        """
        Ohne Antwort, zu einem nicht mehr geltenden Wortlaut oder mit ``neu_fragen``
        (Schalter ``muster_stimmen``, Antwort zu ``-26``) ist die Stufe None: Die App
        fragt neu. Bis dahin gilt die bisherige Antwort fuer das, was ihr Wortlaut nennt.
        ``stimmen``: ob ``muster_stimmen`` wirkt, wie der Aufrufer es schon gefragt hat
        (sonst fragt der Dienst selbst).
        """
        if stimmen is None:
            stimmen = self._stimmen()
        antwort = self._repository.lesen(user_id)
        if (
            antwort is None
            or not antwort.gilt
            or neu_fragen(antwort.wortlaut, antwort.stufe, stimmen)
        ):
            return SpielgefuehlStand(
                stufe=None,
                mit_anzeigename=None,
                ranglistenname=antwort.ranglistenname if antwort else None,
                abzeichen_hinweis=self._zeigte_abzeichen(user_id),
            )
        return SpielgefuehlStand(
            stufe=antwort.stufe,
            mit_anzeigename=(
                antwort.mit_anzeigename if in_rangliste(antwort.stufe) else None
            ),
            ranglistenname=antwort.ranglistenname,
            abzeichen_hinweis=False,
        )

    def herabstufung(self, user_id: str, stufe: Stufe) -> bool:
        """
        Ob ``stufe`` ein Widerruf ist: ``aus`` immer, sonst nur unter der wirksamen
        Stufe der Person (rangliste -> fuer_mich). Ein Widerruf geht auch bei
        ausgeschaltetem Schalter (Art. 7 Abs. 3 DSGVO, api/v1/spielgefuehl.py);
        ``aus`` ohne Datenbankabfrage.
        """
        if stufe is Stufe.AUS:
            return True
        antwort = self._repository.lesen(user_id)
        bisher = antwort.wirksame_stufe if antwort is not None else Stufe.AUS
        return _RANG[stufe] < _RANG[bisher]

    def antworten(
        self,
        user_id: str,
        stufe: Stufe,
        mit_anzeigename: Optional[bool],
        wortlaut: str,
        stimmen: Optional[bool] = None,
    ) -> None:
        """
        Eine Stufe waehlen, jederzeit. Eine Stufe ueber ``aus`` nur zum aktuellen
        Wortlaut, ``aus`` zu jedem bekannten. Stufe rangliste braucht die Namenswahl
        (``NAMENS_VORBELEGUNG`` ist None); das erste Mitspielen wuerfelt den
        Zufallsnamen, auch wenn die Person den Anzeigenamen waehlt, damit sie jederzeit
        wechseln kann. Herabstufen nimmt die Abzeichen sofort aus der Rangliste und
        haelt es auch in den bisherigen Einwilligungen fest: Ein "Aus" gilt dann auch,
        wenn der Schalter wieder ausgeht (Widerruf, Art. 7 Abs. 3 DSGVO). Hochgestuft
        wird dort nie. Ein frueheres Ja zu Abzeichen am Namen wird bei jeder Antwort
        zum Nein, auch bei Stufe rangliste: Die Person liest, dass Abzeichen jetzt nur
        noch in der Rangliste stehen, und sie sollen nach dem Ausschalten des Schalters
        nicht wieder am Namen erscheinen. ``aus`` loescht auch die Muster-Hinweise,
        die die Person nennen; Fehler dabei nur im Log (die Admin-Ansicht filtert
        ohnehin nach der aktuellen Einwilligung).
        """
        if stimmen is None:
            stimmen = self._stimmen()
        if wortlaut not in WORTLAUTE or (
            stufe is not Stufe.AUS and wortlaut != aktueller_wortlaut(stimmen)
        ):
            raise UnbekannterWortlaut(wortlaut)
        vorher = self._repository.lesen(user_id)
        name: Optional[str] = None
        if in_rangliste(stufe):
            if mit_anzeigename is None:
                mit_anzeigename = NAMENS_VORBELEGUNG
            if mit_anzeigename is None:
                raise NamenswahlFehlt()
            if vorher is None or vorher.ranglistenname is None:
                name = self._wuerfeln()
        else:
            mit_anzeigename = False
        self._repository.antworten(user_id, stufe, mit_anzeigename, wortlaut, name)
        if not in_rangliste(stufe):
            self._abzeichen_vergessen(user_id)
        self._alt_zuruecknehmen(user_id, stufe)
        if stufe is Stufe.AUS:
            try:
                self._hinweise_vergessen(user_id)
            except Exception as e:
                logger.error(
                    f"Muster-Hinweise nach Spielgefuehl aus nicht geloescht: {type(e).__name__}",
                    exc_info=True,
                )
        elif (
            vorher is not None
            and stimmen_eingewilligt(vorher.wortlaut, vorher.wirksame_stufe)
            and not stimmen_eingewilligt(wortlaut, stufe)
        ):
            # Widerruf nur des Zwecks Zustimmungen (etwa "Nur fuer mich" zu -26 nach
            # einer Antwort zu -27, wenn der Schalter wieder aus ist).
            try:
                self._stimmen_hinweise_vergessen(user_id)
            except Exception as e:
                logger.error(
                    f"Muster-Hinweise aus Zustimmungen nicht geloescht: {type(e).__name__}",
                    exc_info=True,
                )

    def neu_wuerfeln(self, user_id: str) -> str:
        """Ein neuer Zufallsname als neue Nachweiszeile; nur mit Stufe rangliste."""
        antwort = self._repository.lesen(user_id)
        if antwort is None or not in_rangliste(antwort.wirksame_stufe):
            raise NichtInRangliste()
        jetzt = self._uhr()
        with self._sperre:
            zuletzt = self._gewuerfelt.get(user_id)
            if zuletzt is not None and jetzt - zuletzt < WUERFELN_ABSTAND_SEKUNDEN:
                raise ZuOftGewuerfelt()
            # Abgelaufene mitnehmen, damit das Woerterbuch nicht waechst.
            self._gewuerfelt = {
                k: v
                for k, v in self._gewuerfelt.items()
                if jetzt - v < WUERFELN_ABSTAND_SEKUNDEN
            }
            self._gewuerfelt[user_id] = jetzt
        name = self._wuerfeln()
        self._repository.antworten(
            user_id, antwort.stufe, antwort.mit_anzeigename, antwort.wortlaut, name
        )
        return name

    def _wuerfeln(self) -> str:
        return neuer_ranglistenname(
            self._repository.vergebene_namen() | self._alte_namen()
        )


def zuruecknehmen(
    user_id: str,
    repository: Optional[SpielgefuehlRepository] = None,
    bis: Stufe = Stufe.FUER_MICH,
) -> bool:
    """
    Eine hoehere Stufe als ``bis`` als ``bis`` festhalten, auch bei ausgeschaltetem
    Schalter; nie hochstufen. Wer darunter steht oder nie geantwortet hat, bekommt
    keine Zeile. Liefert, ob herabgestuft wurde. Synchron.

    - Widerruf der Art.-9-Einwilligung (api/v1/art9_einwilligung.py) und Nein zur
      bisherigen Rangliste (api/v1/rangliste.py): ``rangliste`` als ``fuer_mich``, wie
      im bisherigen Modell Rangliste und Abzeichen am Namen zurueckgenommen werden und
      "Punkte und Meilensteine" als eigene Einwilligung bleibt.
    - Widerruf von "Punkte und Meilensteine" (api/v1/usage.py): ``bis=aus``.

    Sonst stuende die Person nach dem Einschalten des Schalters spielgefuehl_buehne
    oder einer neuen Art.-9-Einwilligung ohne neue Frage wieder auf der alten Stufe.
    """
    repository = repository or _neues_repository()
    antwort: Optional[SpielgefuehlAntwort] = repository.lesen(user_id)
    if antwort is not None and _RANG[antwort.stufe] > _RANG[bis]:
        repository.antworten(user_id, bis, False, antwort.wortlaut)
        return True
    return False


_service: Optional[SpielgefuehlService] = None


def _zeigte_abzeichen(user_id: str) -> bool:
    from repositories.abzeichen_sichtbarkeit_repository import (
        get_abzeichen_sichtbarkeit_repository,
    )

    antwort = get_abzeichen_sichtbarkeit_repository().lesen(user_id)
    return antwort is not None and antwort.zeigen


def _abzeichen_vergessen(user_id: str) -> None:
    from services.abzeichen_service import get_abzeichen_service

    dienst = get_abzeichen_service()
    if dienst is not None:
        dienst.vergessen(user_id)


def _alt_zuruecknehmen(user_id: str, stufe: Stufe) -> None:
    """
    Die Stufe auch in den bisherigen Einwilligungen festhalten (nur ein frueheres Ja
    als Nein, nie hochstufen): Abzeichen am Namen bei jeder Stufe (im neuen Modell nie
    am Namen, sonst lebte ein altes Ja nach dem Ausschalten des Schalters wieder auf),
    Rangliste unter ``rangliste``,
    "Punkte und Meilensteine" bei ``aus``.
    """
    from repositories.abzeichen_sichtbarkeit_repository import (
        get_abzeichen_sichtbarkeit_repository,
    )
    from repositories.punkte_einwilligung_repository import (
        get_punkte_einwilligung_repository,
    )
    from services import rangliste_service

    sichtbarkeit = get_abzeichen_sichtbarkeit_repository()
    antwort = sichtbarkeit.lesen(user_id)
    if antwort is not None and antwort.zeigen:
        sichtbarkeit.antworten(user_id, False, antwort.wortlaut)
    if not in_rangliste(stufe):
        rangliste_service.zuruecknehmen(user_id)
    if stufe is Stufe.AUS:
        punkte = get_punkte_einwilligung_repository()
        stand = punkte.lesen(user_id)
        if stand is not None and stand.eingewilligt:
            punkte.antworten(user_id, False, stand.wortlaut)


def muster_hinweise_vergessen(user_id: str) -> None:
    """Die Muster-Hinweise, die die Person nennen, loeschen (Widerruf)."""
    from dependencies import get_muster_hinweise_service

    get_muster_hinweise_service().vergessen(user_id)


def muster_stimmen_hinweise_vergessen(user_id: str) -> None:
    """Nur die Muster-Hinweise aus Zustimmungen, die die Person nennen, loeschen."""
    from dependencies import get_muster_hinweise_service
    from repositories.muster_hinweis_repository import ZUSTIMMUNG

    get_muster_hinweise_service().vergessen(user_id, art=ZUSTIMMUNG)


def get_spielgefuehl_service() -> SpielgefuehlService:
    global _service
    if _service is None:
        from repositories.rangliste_einwilligung_repository import (
            get_rangliste_einwilligung_repository,
        )

        _service = SpielgefuehlService(
            _neues_repository(),
            lambda: get_rangliste_einwilligung_repository().vergebene_namen(),
            _zeigte_abzeichen,
            _abzeichen_vergessen,
            _alt_zuruecknehmen,
            hinweise_vergessen=muster_hinweise_vergessen,
            stimmen=stimmen_aktiv,
            stimmen_hinweise_vergessen=muster_stimmen_hinweise_vergessen,
        )
    return _service


def spielgefuehl_service_setzen(service: Optional[SpielgefuehlService]) -> None:
    """Fuer Tests: einen eigenen Dienst einsetzen (None: beim naechsten Abruf neu)."""
    global _service
    _service = service
