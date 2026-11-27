"""
Spielgefuehl als eine Einstellung in drei Stufen (GLOSSARY.md "Spielgefühl", Schalter
``spielgefuehl_buehne``): eine Frage statt der drei Einwilligungen "Punkte und
Meilensteine", "Abzeichen am Namen" und "Rangliste".

- ``aus``: nichts wird berechnet, nichts gezeigt.
- ``fuer_mich``: Punkte und Meilensteine, die nur die Person sieht.
- ``rangliste``: zusaetzlich in der Saison-Rangliste mit dem gewaehlten Namen
  (Anzeigename oder Zufallsname), Platz, Punkten und Abzeichen. Abzeichen erscheinen
  nur dort, nie am Anzeigenamen; die Rangliste sehen nur Mitspielende, erst ab zehn.

Eine Bühne, ein Zweck je Stufe: Jede Stufe fuegt genau einen Zweck mit einem
Empfaengerkreis hinzu, die Rangliste setzt die Punkte sachlich voraus (Jura 26.11.).
Die Stufen stehen gleich gross und ohne Vorauswahl nebeneinander; die
Gemeinschafts-Option zuerst, die sparsamere danach (``REIHENFOLGE``, Leitlinie
"Community zuerst, Datenschutz als Alternative"). Auch der Name in der Rangliste ist
eine Pflichtwahl ohne Vorauswahl (``NAMENS_VORBELEGUNG``).

Der Wortlaut traegt eine Kennung wie die anderen Einwilligungen; wer ihn aendert,
legt eine neue Kennung an und laesst die alte stehen. Dieses Modul ist rein.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Dict, FrozenSet, Iterable, Optional, Tuple


class Stufe(str, Enum):
    AUS = "aus"
    FUER_MICH = "fuer_mich"
    RANGLISTE = "rangliste"


# Gemeinschafts-Option zuerst, Datenschutz-Alternative danach (Sebastian 26.11.); die
# Knoepfe bleiben gleich gross und ohne Vorauswahl.
REIHENFOLGE: Tuple[Stufe, ...] = (Stufe.RANGLISTE, Stufe.FUER_MICH, Stufe.AUS)

AKTUELLER_WORTLAUT = "spielgefuehl-2026-11-28"
"""
Der Wortlaut, den die Frage zeigt, unabhaengig von den Schaltern (juristische Vorgabe
vom 27.11.): eine Fassung mit Quest-Punkten und gegenseitigen Zustimmungen.
"""

STIMMEN_WORTLAUTE: FrozenSet[str] = frozenset(
    {"spielgefuehl-2026-11-27", AKTUELLER_WORTLAUT}
)
"""
Die Wortlaute, die gegenseitige Zustimmungen im Schutz gegen Absprachen nennen:
Zustimmungen fliessen nur bei Paaren in die Muster-Hinweise ein, in denen beide Konten
zu einem davon ab ``fuer_mich`` eingewilligt haben (``stimmen_eingewilligt``).
"""

QUEST_WORTLAUT = AKTUELLER_WORTLAUT
"""
Der einzige Wortlaut, der Quest-Punkte nennt: Quest-Punkte bekommt nur, wer zu ihm ab
``fuer_mich`` eingewilligt hat, und nur fuer Beitraege ab dieser Einwilligung
(``quest_einwilligung_seit``).
"""

# Vorbelegung der Namenswahl in der Rangliste: None = keine, die Person waehlt aktiv.
# Eine Vorbelegung "Anzeigename" ist unzulaessig (Jura 26.11.: ErwGr 32, Planet49,
# Art. 25 Abs. 2 DSGVO); ohne Wahl ist "Mitspielen" nicht absendbar. So lassen.
NAMENS_VORBELEGUNG: Optional[bool] = None

# Einmal fuer Konten, die bisher Abzeichen am Anzeigenamen gezeigt haben (Jura 26.11.).
HINWEIS_ABZEICHEN_NUR_RANGLISTE = (
    "Abzeichen zeigen wir jetzt nur noch in der Rangliste."
)


# Name des Verantwortlichen genau wie im Abschnitt "Verantwortlicher" der
# Datenschutzerklaerung (VEREIN.NAME, frontend shared/legal-entity.ts; Jura 26.11.).
VERANTWORTLICHER = "NETZBEGRÜNUNG — Verein für grüne Netzkultur e. V."


@dataclass(frozen=True)
class StufenText:
    titel: str
    text: str


@dataclass(frozen=True)
class Wortlaut:
    ueberschrift: str
    einleitung: str
    stufen: Dict[Stufe, StufenText]
    # Direkt unter den drei Stufen: die Einwilligung in den Schutz gegen Absprachen
    # (Paar-Pruefwert, Muster-Hinweis an Admins) fuer beide Stufen ueber "aus"
    absprachen: str
    # Nur fuer Stufe rangliste: die Pflichtwahl des Namens und der Hilfetext dazu
    namenswahl_frage: str
    namenswahl_anzeigename: str
    namenswahl_zufallsname: str
    namenswahl_tipp: str
    fuss: str


# Wortlaut von Jura (26.11., vorlaeufig zum Bauen, endgueltig vor dem Go), Stufe 3
# und Namenswahl aus der Nachsteuerung vom selben Abend, der Satz zu Absprachen aus der
# Antwort auf die Fachfragen zu PR #849.
WORTLAUTE: Dict[str, Wortlaut] = {
    "spielgefuehl-2026-11-26": Wortlaut(
        ueberschrift="Spielgefühl: Wie möchtest du mitspielen?",
        einleitung=(
            "Aus deiner Mitwirkung, also deinen Beiträgen, Einwürfen und Bewertungen "
            "und wie andere deine Beiträge nutzen, können wir Punkte und Meilensteine "
            "berechnen. Daraus lässt sich schließen, dass und wie stark du dich bei "
            "Gut gesagt engagierst."
        ),
        stufen={
            Stufe.RANGLISTE: StufenText(
                titel="In der Saison-Rangliste mitspielen",
                text=(
                    "Ich willige ausdrücklich ein, dass aus meiner Mitwirkung Punkte und "
                    "Meilensteine berechnet werden und dass ich in der Rangliste der "
                    "laufenden Saison erscheine, mit dem Namen, den ich unten wähle, "
                    "meinem Platz, meinen Punkten und meinen Abzeichen (Art. 9 Abs. 2 "
                    "lit. a DSGVO). Die Rangliste sehen nur Angemeldete, die selbst "
                    "mitspielen, und erst ab zehn Teilnehmenden. Angemeldet sind nicht "
                    "nur Mitglieder, und Screenshots kann Gut gesagt nicht verhindern. "
                    "Mit meinem Anzeigenamen sehen die anderen Mitspielenden, dass und "
                    "wie stark gerade ich mich engagiere; ein Zufallsname macht das "
                    "schwerer, schützt aber nicht sicher davor, dass mich jemand erkennt."
                ),
            ),
            Stufe.FUER_MICH: StufenText(
                titel="Nur für mich",
                text=(
                    "Ich willige ausdrücklich ein, dass aus meiner Mitwirkung Punkte und "
                    "Meilensteine berechnet werden, die nur ich sehe (Art. 9 Abs. 2 "
                    "lit. a DSGVO)."
                ),
            ),
            Stufe.AUS: StufenText(
                titel="Aus",
                text="Wir berechnen nichts für dich und zeigen nichts.",
            ),
        },
        absprachen=(
            "Für ‚Nur für mich‘ und ‚In der Saison-Rangliste mitspielen‘ willige ich "
            "außerdem ein: Damit Punkte nicht durch Absprachen entstehen, prüft Gut gesagt, "
            "ob sich zwei Konten gegenseitig nutzen. Fällt das auf, sehen die "
            "Administratorinnen und Administratoren einen Hinweis mit den Kennungen beider "
            "Konten."
        ),
        namenswahl_frage="In der Rangliste als:",
        namenswahl_anzeigename="mein Anzeigename",
        namenswahl_zufallsname="ein Zufallsname",
        namenswahl_tipp=(
            "Datenschutz-Tipp: Mit dem Zufallsnamen bleibst du in der Rangliste "
            "unerkannter. Beides kannst du jederzeit unter „Meine Beiträge“ umstellen, "
            "den Zufallsnamen dort auch neu würfeln."
        ),
        fuss=(
            f"Verantwortlich ist {VERANTWORTLICHER}. Du kannst deine Wahl jederzeit unter "
            "„Meine Beiträge“ ändern oder ausschalten. Das wirkt sofort; was bis dahin "
            "geschah, bleibt rechtmäßig. Mehr dazu in der Datenschutzerklärung."
        ),
    ),
}

# Jura 27.11.: Nur der Absatz zu Absprachen aendert sich, die Stufentexte bleiben
# wortgleich.
WORTLAUTE["spielgefuehl-2026-11-27"] = replace(
    WORTLAUTE["spielgefuehl-2026-11-26"],
    absprachen=(
        "Für ‚Nur für mich‘ und ‚In der Saison-Rangliste mitspielen‘ willige ich "
        "außerdem ein: Damit Punkte nicht durch Absprachen entstehen, prüft Gut gesagt, "
        "ob sich zwei Konten auffällig oft gegenseitig nutzen oder einander zustimmen. "
        "Fällt das auf, sehen die Administratorinnen und Administratoren einen Hinweis "
        "mit den Kennungen beider Konten; an Punkten und Rangliste ändert das nichts."
    ),
)


def _mit_quest_punkten(text: str) -> str:
    alt = "dass aus meiner Mitwirkung Punkte und Meilensteine berechnet werden"
    if alt not in text:
        raise ValueError("Stufentext ohne den Satz zu Punkten und Meilensteinen")
    return text.replace(
        alt,
        "dass aus meiner Mitwirkung, einschließlich Quest-Punkten, Punkte und "
        "Meilensteine berechnet werden",
    )


# Juristische Vorgabe vom 27.11. (vorlaeufig): eine Fassung mit Quest-Punkten und
# Zustimmungen. Neu sind der zweite Satz der Einleitung, die Quest-Punkte in den Stufen
# "Nur für mich" und Rangliste und der Absatz zu Absprachen; der Rest ist wortgleich.
_VORIGER = WORTLAUTE["spielgefuehl-2026-11-27"]
WORTLAUTE[AKTUELLER_WORTLAUT] = replace(
    _VORIGER,
    einleitung=(
        "Aus deiner Mitwirkung, also deinen Beiträgen, Einwürfen und Bewertungen "
        "und wie andere deine Beiträge nutzen, können wir Punkte und Meilensteine "
        "berechnen. Bist du in einem Team und speicherst in einer Woche selbst einen "
        "Beitrag, bekommst du dafür auch Quest-Punkte, wenn dein Team sein Wochenziel "
        "erreicht. Dafür zählt nur die Wochensumme des Teams, nicht, wer wie viel "
        "beigetragen hat. Daraus lässt sich schließen, dass und wie stark du dich bei "
        "Gut gesagt engagierst."
    ),
    stufen={
        **_VORIGER.stufen,
        Stufe.RANGLISTE: StufenText(
            titel=_VORIGER.stufen[Stufe.RANGLISTE].titel,
            text=_mit_quest_punkten(_VORIGER.stufen[Stufe.RANGLISTE].text),
        ),
        Stufe.FUER_MICH: StufenText(
            titel=_VORIGER.stufen[Stufe.FUER_MICH].titel,
            text=_mit_quest_punkten(_VORIGER.stufen[Stufe.FUER_MICH].text),
        ),
    },
    absprachen=(
        "Für ‚Nur für mich‘ und ‚In der Saison-Rangliste mitspielen‘ willige ich "
        "außerdem ein: Damit Punkte nicht durch Absprachen entstehen, prüft Gut gesagt, "
        "ob sich zwei Konten auffällig oft gegenseitig nutzen und, sobald diese Prüfung "
        "eingeschaltet ist, auch ob sie einander zustimmen. Fällt das auf, sehen die "
        "Administratorinnen und Administratoren einen Hinweis mit den Anzeigenamen und "
        "Kennungen beider Konten; an Punkten und Rangliste ändert das nichts."
    ),
)

# Zu welchen Wortlauten eine Antwort gilt; eine neue Fassung mit mehr Zwecken fragt
# neu, indem sie die alte hier herausnimmt. Alle drei tragen Punkte, Meilensteine und
# die Rangliste; neu gefragt wird trotzdem (``neu_fragen``), damit die Person die
# Zwecke Quest-Punkte und Zustimmungen sieht. Bis zur neuen Antwort gilt die alte
# Kennung fuer das, was sie nennt.
GELTENDE_WORTLAUTE: FrozenSet[str] = frozenset(
    {"spielgefuehl-2026-11-26", "spielgefuehl-2026-11-27", AKTUELLER_WORTLAUT}
)


class UnbekannterWortlaut(ValueError):
    """Die Kennung gehoert zu keinem bekannten oder geltenden Wortlaut."""


class NamenswahlFehlt(ValueError):
    """Stufe rangliste ohne Wahl zwischen Anzeigename und Zufallsname."""


def punkte_wirksam(stufe: Optional[Stufe]) -> bool:
    """Punkte und Meilensteine werden berechnet: ab Stufe fuer_mich."""
    return stufe in (Stufe.FUER_MICH, Stufe.RANGLISTE)


def in_rangliste(stufe: Optional[Stufe]) -> bool:
    """Die Person spielt in der Saison-Rangliste mit."""
    return stufe is Stufe.RANGLISTE


def neu_fragen(wortlaut: str, stufe: Stufe) -> bool:
    """
    Ob eine geltende Antwort trotzdem neu gefragt wird: jede Stufe ueber ``aus`` zu
    einem anderen Wortlaut als dem aktuellen, unabhaengig von den Schaltern (juristische
    Vorgabe vom 27.11.: Konten mit ``-26`` oder ``-27`` einmal). ``aus`` willigt in
    nichts ein und wird nicht neu gefragt.
    """
    return punkte_wirksam(stufe) and wortlaut != AKTUELLER_WORTLAUT


def stimmen_eingewilligt(wortlaut: str, stufe: Optional[Stufe]) -> bool:
    """Ob Zustimmungen der Person in die Muster-Hinweise einfliessen duerfen."""
    return wortlaut in STIMMEN_WORTLAUTE and punkte_wirksam(stufe)


def quest_einwilligung_seit(
    antworten: Iterable[Tuple[str, Stufe, datetime]],
) -> Optional[datetime]:
    """
    Seit wann die Person ohne Unterbrechung zu ``QUEST_WORTLAUT`` ab ``fuer_mich``
    eingewilligt hat, oder None, wenn ihre juengste Antwort das nicht ist.
    ``antworten``: alle Antworten der Person als (Wortlaut, Stufe, Zeitpunkt), die
    juengste zuerst (wie ``SpielgefuehlRepository.lesen`` ordnet). Ein Wechsel zwischen ``fuer_mich`` und ``rangliste`` oder
    ein neuer Zufallsname unterbricht nicht; ``aus`` oder eine Antwort zu einem anderen
    Wortlaut schon. Quest-Punkte gibt es nur fuer Beitraege ab diesem Zeitpunkt, also
    nicht rueckwirkend fuer Wochen davor.
    """
    seit: Optional[datetime] = None
    for wortlaut, stufe, zeitpunkt in antworten:
        if wortlaut != QUEST_WORTLAUT or not punkte_wirksam(stufe):
            break
        seit = zeitpunkt
    return seit
