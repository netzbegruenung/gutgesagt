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
from enum import Enum
from typing import Dict, FrozenSet, Optional, Tuple


class Stufe(str, Enum):
    AUS = "aus"
    FUER_MICH = "fuer_mich"
    RANGLISTE = "rangliste"


# Gemeinschafts-Option zuerst, Datenschutz-Alternative danach (Sebastian 26.11.); die
# Knoepfe bleiben gleich gross und ohne Vorauswahl.
REIHENFOLGE: Tuple[Stufe, ...] = (Stufe.RANGLISTE, Stufe.FUER_MICH, Stufe.AUS)

AKTUELLER_WORTLAUT = "spielgefuehl-2026-11-26"
"""Der Wortlaut, solange der Schalter ``muster_stimmen`` nicht wirkt."""

STIMMEN_WORTLAUT = "spielgefuehl-2026-11-27"
"""
Der Wortlaut mit gegenseitigen Zustimmungen im Schutz gegen Absprachen (Jura 27.11.):
gefragt nur, solange der Schalter ``muster_stimmen`` wirkt (``aktueller_wortlaut``).
Zustimmungen fliessen nur bei Paaren in die Muster-Hinweise ein, in denen beide Konten
zu genau diesem Wortlaut ab ``fuer_mich`` eingewilligt haben (``stimmen_eingewilligt``).
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
WORTLAUTE[STIMMEN_WORTLAUT] = replace(
    WORTLAUTE[AKTUELLER_WORTLAUT],
    absprachen=(
        "Für ‚Nur für mich‘ und ‚In der Saison-Rangliste mitspielen‘ willige ich "
        "außerdem ein: Damit Punkte nicht durch Absprachen entstehen, prüft Gut gesagt, "
        "ob sich zwei Konten auffällig oft gegenseitig nutzen oder einander zustimmen. "
        "Fällt das auf, sehen die Administratorinnen und Administratoren einen Hinweis "
        "mit den Kennungen beider Konten; an Punkten und Rangliste ändert das nichts."
    ),
)

# Zu welchen Wortlauten eine Antwort gilt; eine neue Fassung mit mehr Zwecken fragt
# neu, indem sie die alte hier herausnimmt. ``spielgefuehl-2026-11-26`` bleibt mit dem
# Schalter ``muster_stimmen`` gueltig fuer alles, was sie nennt (Punkte, Rangliste,
# gegenseitige Nutzung); neu gefragt wird trotzdem (``neu_fragen``), damit die Person
# den Zweck Zustimmungen sieht. Ohne Schalter gilt auch ``-27`` weiter: Sie umfasst
# alles aus ``-26``, und niemand soll beim Ausschalten neu gefragt werden.
GELTENDE_WORTLAUTE: FrozenSet[str] = frozenset({AKTUELLER_WORTLAUT, STIMMEN_WORTLAUT})


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


def aktueller_wortlaut(stimmen: bool) -> str:
    """Der Wortlaut, den die Frage zeigt: mit wirksamem ``muster_stimmen`` der neue."""
    return STIMMEN_WORTLAUT if stimmen else AKTUELLER_WORTLAUT


def neu_fragen(wortlaut: str, stufe: Stufe, stimmen: bool) -> bool:
    """
    Ob eine geltende Antwort trotzdem neu gefragt wird: mit wirksamem
    ``muster_stimmen`` jede Stufe ueber ``aus`` zu einem anderen Wortlaut als dem
    neuen (Jura 27.11.: Konten mit ``-26`` beim naechsten Besuch). ``aus`` willigt in
    nichts ein und wird nicht neu gefragt.
    """
    return stimmen and punkte_wirksam(stufe) and wortlaut != STIMMEN_WORTLAUT


def stimmen_eingewilligt(wortlaut: str, stufe: Optional[Stufe]) -> bool:
    """Ob Zustimmungen der Person in die Muster-Hinweise einfliessen duerfen."""
    return wortlaut == STIMMEN_WORTLAUT and punkte_wirksam(stufe)
