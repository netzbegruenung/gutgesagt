"""
Schalter mit Obergrenze und Admin-Wert (#708, GLOSSARY.md "Schalter").

Die Umgebungsvariable (``SEMANTIC_SEARCH_PUNKTE_AKTIV`` usw., ``core/config.py``) ist
die Obergrenze, der Admin-Wert liegt in der Tabelle ``schalter``. Wirksam ist ein
Schalter nur, wenn beide an sind; ohne Admin-Wert gilt aus. So kann auf Prod nichts
angehen, was der Server nicht erlaubt (etwa Punkte ohne beschlossene DSFA), und ein
Admin kann ohne Rollout ein- und ausschalten.

Alle Stellen im Code fragen ``schalter_wirksam``, nicht die Settings direkt. Die
Admin-Werte liest der Dienst mit kurzem Cache (``CACHE_SEKUNDEN``); eine Aenderung
ueber ``setzen`` gilt in diesem Prozess sofort, in anderen nach dem Cache. Ist die
Datenbank nicht erreichbar, gilt aus (wie ohne Eintrag), bis der naechste Versuch
gelingt.
"""

import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from core.config import Settings, settings as globale_settings
from core.logging import get_logger
from domain.feedback_gestoert import gestoert_offen
from utils.utc_tag import heute_utc

logger = get_logger(__name__)

CACHE_SEKUNDEN = 45.0

DSFA_HINWEIS = (
    "Vor dem Einschalten auf Prod: DSFA beschlossen (docs/DSFA.md Abschnitt 7)"
)

# Vorlaeufige juristische Einschaetzung vom 26.11.2026 fuer einen vereinsinternen Test
# (Einladungen bis zum Go nur an Mitglieder): Diese Schalter duerfen dafuer an, ihr Absatz
# steht in der Datenschutzerklaerung und haengt am Schalter. Rechtlich freigegeben sind
# sie damit nicht; vor der Ausweitung auf Vorhut oder BDK bleibt das Go des Vorstands
# noetig (Beschluss 25.11.).
JURA_26_11 = "Jura vorläufig ok 26.11. (interner Test)"
JURA_VORLAEUFIG = f"{JURA_26_11}, DSE-Absatz drin"
GO_VOR_AUSWEITUNG = "vor Vorhut/BDK das Go des Vorstands"

# Gruppen der Admin-Seite "Schalter", in dieser Reihenfolge (Sebastian 25.11.: die
# lange Liste gruppieren). Die Seite zeigt je Gruppe einen Abschnitt.
GRUNDFUNKTIONEN = "Grundfunktionen"
TEAMS = "Teams"
SPIELGEFUEHL = "Spielgefühl"
PUNKTE_ANERKENNUNG = "Punkte & Anerkennung"
GRUPPEN = (GRUNDFUNKTIONEN, TEAMS, SPIELGEFUEHL, PUNKTE_ANERKENNUNG)


@dataclass(frozen=True)
class Schalterart:
    name: str
    # Feld in Settings, das die Obergrenze traegt
    feld: str
    umgebungsvariable: str
    erklaerung: str
    dsfa_hinweis: bool = False
    # Ob GET /api/v1/funktionen den wirksamen Wert ohne Anmeldung meldet (api/v1/
    # funktionen.py): fuer Funktionen, die nur im Browser laufen und deshalb keinen
    # eigenen Endpunkt haben, der mit 404 antworten koennte (etwa Teilen als Bild).
    oeffentlich: bool = False
    # Eigene Bedingung fuers Einschalten auf Prod, die die Admin-Seite statt des
    # allgemeinen DSFA-Hinweises zeigt (etwa ein DSFA-Nachtrag oder ein Jura-OK).
    einschalt_hinweis: Optional[str] = None
    # Abschnitt auf der Admin-Seite, einer aus GRUPPEN
    gruppe: str = GRUNDFUNKTIONEN
    # Rechtlich freigegeben, obwohl ein Hinweis steht (der Hinweis sagt dann, was
    # weiter gilt): Die Admin-Seite zeigt den Schalter nicht als "wartet auf Recht".
    rechtlich_freigegeben: bool = False

    def __post_init__(self):
        # Beim Import auffallen statt mit 500 auf der Admin-Seite
        if self.gruppe not in GRUPPEN:
            raise ValueError(f"Unbekannte Gruppe {self.gruppe!r} fuer {self.name}")


# Spielgefuehl zur BDK (#782 bis #793, docs/ARCHITECTURE.md "Schalter fuer das
# Spielgefuehl"): je Baustein ein Schalter, Obergrenze von Haus aus aus. Die Bausteine
# selbst kommen in eigenen PRs; bis dahin schalten diese Schalter nichts.
SPIEL_SCHALTER = (
    Schalterart(
        name="saison_ziel",
        gruppe=SPIELGEFUEHL,
        feld="saison_ziel_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_SAISON_ZIEL_AKTIV",
        erklaerung=(
            "Saisons mit Gemeinschaftsziel und der Fortschrittsbalken auf der "
            "Startseite; für alle erst ab der Schwelle, vorher nur im Admin."
        ),
        oeffentlich=True,
    ),
    Schalterart(
        name="gartenansicht",
        gruppe=SPIELGEFUEHL,
        feld="gartenansicht_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_GARTENANSICHT_AKTIV",
        erklaerung=(
            "Gartenansicht für alle: je Thema die Zahl der Antworten und der "
            "Aussagen ohne Antwort; Besucher sehen nur die Zahlen."
        ),
        oeffentlich=True,
    ),
    Schalterart(
        name="kopiert_erfolg",
        gruppe=SPIELGEFUEHL,
        feld="kopiert_erfolg_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_KOPIERT_ERFOLG_AKTIV",
        erklaerung=(
            "Kurzer Erfolgstext nach dem Kopieren mit der Nutzung der Karte und "
            "einem Hinweis auf andere Tonlagen; speichert und zählt nichts Neues."
        ),
        oeffentlich=True,
    ),
    Schalterart(
        name="konter_probe",
        gruppe=SPIELGEFUEHL,
        feld="konter_probe_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_KONTER_PROBE_AKTIV",
        erklaerung=(
            "Spiel „Konter-Probe“: ein Spruch, drei echte Antworten, tippen, danach "
            "die echte Nutzung sehen; ohne Konto, der Tipp wird nicht gespeichert."
        ),
        oeffentlich=True,
    ),
    Schalterart(
        name="luecke_zu_gross",
        gruppe=SPIELGEFUEHL,
        feld="luecke_zu_gross_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_LUECKE_ZU_GROSS_AKTIV",
        erklaerung=(
            "„Lücke zu!“ nach dem Beantworten einer gesuchten Aussage als großer "
            "Moment mit dem Knopf „Nächste Lücke“; aus: der kleine Satz wie bisher."
        ),
        oeffentlich=True,
    ),
    Schalterart(
        name="einwilligung_im_gewinn",
        gruppe=SPIELGEFUEHL,
        feld="einwilligung_im_gewinn_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_EINWILLIGUNG_IM_GEWINN_AKTIV",
        erklaerung=(
            "Einwilligungsfragen im passenden Moment statt alle auf einmal: "
            "höchstens eine neue Frage je Besuch und vier im ersten Monat; die "
            "Wortlaute bleiben gleich."
        ),
        oeffentlich=True,
    ),
    Schalterart(
        name="naechster_schritt",
        gruppe=SPIELGEFUEHL,
        feld="naechster_schritt_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_NAECHSTER_SCHRITT_AKTIV",
        erklaerung=(
            "Karte „Dein nächster Schritt“ auf der Startseite: ein Vorschlag aus den "
            "eigenen Beiträgen, ohne Frist; speichert auf dem Server nichts zusätzlich."
        ),
        einschalt_hinweis=JURA_VORLAEUFIG,
        oeffentlich=True,
    ),
    Schalterart(
        name="saal_spruch",
        gruppe=SPIELGEFUEHL,
        feld="saal_spruch_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_SAAL_SPRUCH_AKTIV",
        erklaerung=(
            "Karte „Heute im Saal gehört:“ oben auf der Startseite mit dem heutigen "
            "Saal-Spruch (Abschnitt Saal-Sprüche) und dem Knopf „Antworten ansehen“; an "
            "Tagen ohne Spruch nichts. Speichert nichts zur Person."
        ),
        oeffentlich=True,
    ),
    Schalterart(
        name="null_treffer_anzahl",
        gruppe=SPIELGEFUEHL,
        feld="null_treffer_anzahl_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_NULL_TREFFER_ANZAHL_AKTIV",
        erklaerung=(
            "Seite ohne Treffer: „Danach wurde in den letzten vier Wochen schon "
            "N-mal gesucht“ ab N ≥ 3, auch ohne Anmeldung; nur zu für alle sichtbaren "
            "Aussagen, speichert nichts zusätzlich."
        ),
        einschalt_hinweis=(
            f"{JURA_VORLAEUFIG}: Anzeige erst ab N ≥ 3, Wortlaut „N-mal gesucht“"
        ),
        oeffentlich=True,
    ),
    Schalterart(
        name="wirkungs_echo",
        gruppe=PUNKTE_ANERKENNUNG,
        feld="wirkungs_echo_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_WIRKUNGS_ECHO_AKTIV",
        erklaerung=(
            "Wer schreibt, sieht je Beitrag, wie oft er öffentlich gepostet wurde, "
            "nur als Summe und nie, von wem."
        ),
        einschalt_hinweis=(
            f"{JURA_VORLAEUFIG} (drei gespeicherte Zahlen, Zählerstand des Echos); "
            "nur zusammen mit danke_knopf, der Absatz nennt beide Summen"
        ),
        # Die Datenschutzerklaerung blendet ihren Absatz danach ein (GET /api/v1/funktionen)
        oeffentlich=True,
    ),
    Schalterart(
        name="danke_knopf",
        gruppe=PUNKTE_ANERKENNUNG,
        feld="danke_knopf_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_DANKE_KNOPF_AKTIV",
        erklaerung=(
            "Knopf „Danke an die Autorin“ nach dem Kopieren, für Angemeldete; die "
            "Autorin sieht nur die Summe je Beitrag. Bringt keine Punkte."
        ),
        einschalt_hinweis=(
            f"{JURA_VORLAEUFIG}; nur zusammen mit wirkungs_echo, der Absatz nennt "
            "beide Summen"
        ),
        oeffentlich=True,
    ),
    Schalterart(
        name="danke_ohne_konto",
        gruppe=PUNKTE_ANERKENNUNG,
        feld="danke_ohne_konto_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_DANKE_OHNE_KONTO_AKTIV",
        erklaerung=(
            "Danke-Knopf auch ohne Konto, entdoppelt über das Besuchermerkmal; wirkt "
            "nur zusammen mit dem Danke-Knopf."
        ),
        einschalt_hinweis=(
            "Nicht einschalten (Jura 26.11.): erfüllt Variante B nicht, ohne Konto "
            "entdoppelt über einen Tages-Prüfwert aus dem Besuchermerkmal, Pfad nennt "
            "Beitrag und „danke“, Summe nicht getrennt ausgewiesen; kein DSE-Absatz"
        ),
        oeffentlich=True,
    ),
    Schalterart(
        name="rangliste",
        gruppe=PUNKTE_ANERKENNUNG,
        feld="rangliste_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_RANGLISTE_AKTIV",
        erklaerung=(
            "Rangliste je Saison, sichtbar nur für Angemeldete, die selbst "
            "eingewilligt haben; wirkt nur zusammen mit den Punkten."
        ),
        einschalt_hinweis=(
            f"{JURA_VORLAEUFIG}; Wortlaut rangliste-2026-11-25 wortgleich, sichtbar "
            f"erst ab 10 Teilnehmenden; {GO_VOR_AUSWEITUNG}"
        ),
        oeffentlich=True,
    ),
)


SCHALTER: Dict[str, Schalterart] = {
    s.name: s
    for s in (
        Schalterart(
            name="punkte",
            gruppe=PUNKTE_ANERKENNUNG,
            feld="punkte_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_PUNKTE_AKTIV",
            erklaerung=(
                "Punkte, Meilensteine und die Einwilligung dazu für Mitwirkende, "
                "dazu die Muster-Hinweise für Admins."
            ),
            dsfa_hinweis=True,
            einschalt_hinweis=f"{JURA_VORLAEUFIG}; {GO_VOR_AUSWEITUNG} (mit DSFA)",
            oeffentlich=True,
        ),
        Schalterart(
            name="abzeichen_sichtbar",
            gruppe=PUNKTE_ANERKENNUNG,
            feld="abzeichen_sichtbar_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_ABZEICHEN_SICHTBAR_AKTIV",
            erklaerung=(
                "Meilenstein-Abzeichen am Anzeigenamen, die andere Angemeldete sehen; "
                "wirkt nur zusammen mit den Punkten, erscheint spätestens nach 15 Minuten."
            ),
            dsfa_hinweis=True,
            einschalt_hinweis=(
                "Aus lassen (Jura 26.11.): nicht in der Ampel für den internen Test, "
                "DSFA offen; die Vertrauenszeile stimmt nur ohne Abzeichen"
            ),
        ),
        Schalterart(
            name="gepostet",
            feld="gepostet_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_GEPOSTET_AKTIV",
            erklaerung=(
                "Rückfrage „Ja, gepostet“ nach dem Kopieren und die Zahl je Woche "
                "in der Übersicht."
            ),
        ),
        Schalterart(
            name="gepostet_ohne_konto",
            feld="gepostet_ohne_konto_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_GEPOSTET_OHNE_KONTO_AKTIV",
            erklaerung=(
                "Rückfrage „Ja, gepostet“ auch ohne Konto, nur als Zahl je Woche "
                "„Meldungen ohne Konto“, getrennt von den Menschen; wirkt nur "
                "zusammen mit „gepostet“."
            ),
            einschalt_hinweis=f"{JURA_VORLAEUFIG} (Variante B)",
            oeffentlich=True,
        ),
        Schalterart(
            name="herkunft_pruefen",
            feld="herkunft_pruefen_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_HERKUNFT_PRUEFEN_AKTIV",
            erklaerung=(
                "Prüft nachts die Links unter „Herkunft“ und listet tote oder "
                "umgezogene in der Übersicht. Ruft dafür fremde Server ab."
            ),
        ),
        Schalterart(
            name="merkliste",
            gruppe=GRUNDFUNKTIONEN,
            feld="merkliste_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_MERKLISTE_AKTIV",
            erklaerung=(
                "Merken an der Beitragskarte und der Reiter „Gemerkt“ in Meine "
                "Beiträge, nur mit Art.-9-Einwilligung; der Widerruf löscht die "
                "Merkliste. Nur die Person selbst sieht sie."
            ),
            einschalt_hinweis=(
                "Aus lassen (Jura 26.11.): Zweck steht nicht im Wortlaut der "
                "Einwilligung; braucht neuen Einwilligungswortlaut + DSFA-Abschnitt + "
                "DSE-Absatz (neuer Zweck, politisches Interesse)"
            ),
            oeffentlich=True,
        ),
        Schalterart(
            name="aufrufe_zaehlen",
            gruppe=GRUNDFUNKTIONEN,
            feld="aufrufe_zaehlen_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_AUFRUFE_ZAEHLEN_AKTIV",
            erklaerung=(
                "Zählt Aufrufe und Besucher je Tag am Server aus den Abrufen von "
                "Startseite, Suche, Thema und Beitrag, ohne eigene Anfrage aus dem "
                "Browser und ohne Cookie; die IP-Adresse wird nicht gespeichert. "
                "Zeigt sie unter Kennzahlen."
            ),
            dsfa_hinweis=True,
            einschalt_hinweis=(
                "Aus lassen (Jura 26.11.): erst nach DSB-Antwort (§ 25 TDDDG, #495) "
                "und DSFA-Zeile V-Messung; kein DSE-Absatz"
            ),
        ),
        Schalterart(
            name="abkuerzungen",
            feld="abkuerzungen_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_ABKUERZUNGEN_AKTIV",
            erklaerung=(
                "App-Abkürzungen Einwerfen, Suchen und Fangkorb beim langen Drücken "
                "aufs App-Symbol. Aus: Sie öffnen die Startseite. Das Gerät zeigt sie "
                "trotzdem an, weil das Manifest fest ist."
            ),
            oeffentlich=True,
        ),
        Schalterart(
            name="antworten_hinweis",
            feld="antworten_hinweis_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_ANTWORTEN_HINWEIS_AKTIV",
            erklaerung=(
                "Kachel „neue Antworten auf deine Aussagen“ auf der Startseite und "
                "der Reiter „Meine Aussagen“; speichert nichts Neues."
            ),
            # Die Datenschutzerklaerung blendet ihren Absatz danach ein
            oeffentlich=True,
        ),
        Schalterart(
            name="sharepic",
            feld="sharepic_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_SHAREPIC_AKTIV",
            erklaerung=(
                "„Als Bild teilen“ im Menü der Beitragskarte: Das Bild entsteht im "
                "Browser und verlässt das Gerät nur über dessen Teilen-Menü."
            ),
            oeffentlich=True,
        ),
        Schalterart(
            name="meldeweg_sichtbar",
            feld="meldeweg_sichtbar_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_MELDEWEG_SICHTBAR_AKTIV",
            erklaerung=(
                "„Melden“ klein in der Meta-Zeile jeder Beitragskarte statt nur im "
                "⋮-Menü, dazu „Melden & Kontakt“ mit der Funktionsadresse im Fuß; "
                "speichert und zählt nichts Neues."
            ),
            oeffentlich=True,
        ),
        Schalterart(
            name="bestandszahl_zuwachs",
            feld="bestandszahl_zuwachs_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_BESTANDSZAHL_ZUWACHS_AKTIV",
            erklaerung=(
                "Zuwachs in der Unterzeile der Startseite: neue Antworten der letzten "
                "7 Tage, unter 3 nur der Tag der letzten; zählt nur öffentliche Inhalte."
            ),
            # Die Datenschutzerklaerung blendet ihren Absatz danach ein
            oeffentlich=True,
        ),
        Schalterart(
            name="feedback_gestoert",
            feld="feedback_gestoert_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_FEEDBACK_GESTOERT_AKTIV",
            erklaerung=(
                "Knopf „Was hat dich gestört?“ auf der Startseite für die Startphase: "
                "dasselbe Feedback-Formular, nur Freitext ohne Kontakt; alle Einträge "
                "werden am 31.12.2026 gelöscht, danach wirkt der Schalter nicht mehr."
            ),
            einschalt_hinweis=(
                f"{JURA_VORLAEUFIG}; ohne Kennung, der Löschlauf löscht alle am "
                "31.12.2026"
            ),
            oeffentlich=True,
        ),
        Schalterart(
            name="dse_kurzfassung",
            feld="dse_kurzfassung_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_DSE_KURZFASSUNG_AKTIV",
            erklaerung=(
                "Kasten „Kurz gesagt“ oben in der Datenschutzerklärung: wer "
                "verantwortlich ist, was gespeichert wird, wie man löscht und "
                "widerruft, je mit Sprunglink auf den Absatz im Volltext. Bleibt "
                "unsichtbar, solange ein Satz noch Platzhalter ist."
            ),
            einschalt_hinweis=(
                f"{JURA_26_11}, Wortlaut drin; Name des "
                "Verantwortlichen wie im Abschnitt „Verantwortlicher“"
            ),
            oeffentlich=True,
        ),
        Schalterart(
            name="stimmen_text_verfall",
            gruppe=GRUNDFUNKTIONEN,
            feld="stimmen_text_verfall_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_STIMMEN_TEXT_VERFALL_AKTIV",
            erklaerung=(
                "Stimmen verfallen auch, wenn die Autorin oder der Autor den Text durch "
                "einen ganz anderen ersetzt (#636). Gelöschte Stimmen kommen nicht "
                "zurück; wirkt nur, wenn die Prüfung auf dieselbe Aussage an ist."
            ),
            einschalt_hinweis=f"{JURA_VORLAEUFIG} (Halbsatz „Bewertungen“)",
            oeffentlich=True,
        ),
        Schalterart(
            name="teams",
            gruppe=TEAMS,
            rechtlich_freigegeben=True,
            feld="teams_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_TEAMS_AKTIV",
            erklaerung=(
                "Teams über Einladungen: Teamfelder an der Einladung, Beitreten mit "
                "eigener Einwilligung und „Meine Teams“. Aus: Einladungen wie bisher, "
                "Teamfelder werden ignoriert."
            ),
            einschalt_hinweis=(
                "Rechtlich freigegeben (25.11.): darf vor dem Beschluss der DSFA "
                "eingeschaltet werden. Die Anzeige am Namen (teams_oeffentlich) "
                "bleibt aus."
            ),
            oeffentlich=True,
        ),
        Schalterart(
            name="teams_oeffentlich",
            gruppe=TEAMS,
            feld="teams_oeffentlich_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_TEAMS_OEFFENTLICH_AKTIV",
            erklaerung=(
                "Teams der aktuellen Saison am Anzeigenamen, die andere Angemeldete "
                "sehen, nur mit eigener Einwilligung; wirkt nur zusammen mit „teams“. "
                "Aus, bis die Datenschutzbeauftragte geraten hat."
            ),
            dsfa_hinweis=True,
            einschalt_hinweis=(
                "Aus lassen (Jura 26.11.): Art. 9, Wortlaut ungeprüft, Rat der "
                "Datenschutzbeauftragten offen; kein DSE-Absatz"
            ),
            oeffentlich=True,
        ),
        Schalterart(
            name="teamlink_vertrauenssatz",
            gruppe=TEAMS,
            feld="teamlink_vertrauenssatz_aktiv",
            umgebungsvariable="SEMANTIC_SEARCH_TEAMLINK_VERTRAUENSSATZ_AKTIV",
            erklaerung=(
                "Vertrauenssatz vor der Frage beim Teambeitritt: „Beitreten heißt: Du "
                "zählst zu diesem Team und trägst zu seiner Summe bei.“, bei einem Team "
                "nach Gruppe dazu, dass die Gruppe keine Daten bekommt. Speichert "
                "nichts; wirkt nur zusammen mit „teams“."
            ),
            einschalt_hinweis=(
                f"{JURA_26_11}, Wortlaut drin; nennt die "
                "Team-Summe, also zusammen mit team_fortschritt einschalten"
            ),
            oeffentlich=True,
        ),
        *SPIEL_SCHALTER,
    )
}


# Team-Fortschritt (#784) und Team-Quests (#792): eigene Obergrenzen, von Haus aus
# aus. Beide zaehlen und zeigen nur mit Teams; die Quests nur mit dem Team-Fortschritt,
# weil sie dessen Wochenzaehler nutzen (services/team_fortschritt_service.py).
TEAM_SCHALTER = (
    Schalterart(
        name="team_fortschritt",
        gruppe=TEAMS,
        feld="team_fortschritt_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_TEAM_FORTSCHRITT_AKTIV",
        erklaerung=(
            "Team-Fortschritt in „Meine Teams“: Mitglieder sehen, was ihr Team in der "
            "letzten abgeschlossenen Woche gemeinsam bewirkt hat, gerundet und erst ab "
            "5 Mitgliedern mit Einwilligung. Zählt dafür je Team und Woche ohne "
            "Kennung; wirkt nur zusammen mit „teams“."
        ),
        dsfa_hinweis=True,
        einschalt_hinweis=(
            f"{JURA_VORLAEUFIG}; Summe erst ab 5 Mitgliedern mit Einwilligung; "
            f"{GO_VOR_AUSWEITUNG}"
        ),
        # Die Datenschutzerklaerung nimmt danach den Satz „noch nicht eingeschaltet“ weg
        oeffentlich=True,
    ),
    Schalterart(
        name="team_quests",
        gruppe=TEAMS,
        feld="team_quests_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_TEAM_QUESTS_AKTIV",
        erklaerung=(
            "Team-Quests: ein gemeinsames Wochenziel je Team aus dem Bedarf, mit "
            "Quest-Punkten für Mitglieder, die beigetragen haben; wirkt nur zusammen "
            "mit dem Team-Fortschritt."
        ),
        dsfa_hinweis=True,
        einschalt_hinweis=(
            "Aus lassen (Jura 26.11.): DSE-Satz nötig; Juras Entwurf passt nicht zum "
            "Code (gespeichert werden Thema und Ziel jeder Woche, nicht erfüllte Quests; "
            "eine Team-Löschung gibt es nicht, die Zeilen bleiben unbefristet)"
        ),
    ),
)
SCHALTER.update({s.name: s for s in TEAM_SCHALTER})


# Vertrauenszeile vor dem Anmelden (vorlaeufige juristische Einschaetzung 26.11.2026):
# Neues hinter einem Schalter, Obergrenze von Haus aus aus. Der Wortlaut nennt Team-Summe
# und Rangliste als die einzigen Wege, auf denen andere mehr als die Beitraege sehen;
# die Bedingung dafuer steht als Hinweis auf der Admin-Seite.
SCHALTER["vertrauenszeile"] = Schalterart(
    name="vertrauenszeile",
    gruppe=GRUNDFUNKTIONEN,
    feld="vertrauenszeile_aktiv",
    umgebungsvariable="SEMANTIC_SEARCH_VERTRAUENSZEILE_AKTIV",
    erklaerung=(
        "Zeile über den Anmeldewegen: Was man beiträgt, erscheint unter dem "
        "Anzeigenamen, wie viel man sonst mitmacht, sehen andere nicht, außer als "
        "Teil der Team-Summe und, selbst gewählt, in der Rangliste; mit Link "
        "„Datenschutz“. Speichert und zählt nichts."
    ),
    einschalt_hinweis=(
        f"{JURA_26_11}, Wortlaut mit Team-Summe und "
        "Rangliste drin; stimmt nur, solange teams_oeffentlich und "
        "abzeichen_sichtbar aus sind"
    ),
    oeffentlich=True,
)


# Kurze Hinweiszeile unter dem Suchknopf (Designwichtel Nr. 5): eine Zeile "Wie wir
# Suchen speichern · Datenschutz" statt des abgestimmten Wortlauts vom 16.11.; der Satz
# zur Veroeffentlichung klappt auf. Nur im Browser, deshalb oeffentlich. Nicht "Ohne
# Namen gespeichert" (Jura 26.11.): Suchvorgaenge Angemeldeter tragen bis Tagesende ein
# Tagespseudonym aus der Kennung (services/search_tracking_service.py).
HINWEIS_SCHALTER = (
    Schalterart(
        name="hinweiszeile_kurz",
        gruppe=GRUNDFUNKTIONEN,
        feld="hinweiszeile_kurz_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_HINWEISZEILE_KURZ_AKTIV",
        erklaerung=(
            "Unter dem Suchknopf eine Zeile „Wie wir Suchen speichern · Datenschutz“ "
            "statt zwei; „Nach Prüfung können Suchtexte öffentlich werden“ steht "
            "aufklappbar dahinter. Speichert nichts Neues."
        ),
        einschalt_hinweis=(
            f"{JURA_26_11}: Wortlaut „Wie wir Suchen "
            "speichern“, weil Suchvorgänge Angemeldeter an der Kennung hängen"
        ),
        oeffentlich=True,
    ),
)
SCHALTER.update({s.name: s for s in HINWEIS_SCHALTER})


# Kampagnenwort ?k= (GLOSSARY.md "Kampagnenwort"): vorlaeufige Jura-Einschaetzung
# 26.11.2026, Grundsatz Maintainer: alles hinter einem Schalter, Standard aus. Beide
# Obergrenzen von Haus aus aus. k_begruessung darf fuer den internen Test an (Jura
# vorlaeufig 26.11.), k_ankuenfte bleibt aus.
K_SCHALTER = (
    Schalterart(
        name="k_begruessung",
        gruppe=GRUNDFUNKTIONEN,
        feld="k_begruessung_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_K_BEGRUESSUNG_AKTIV",
        erklaerung=(
            "Wer über ?k=sticker oder ?k=bdk kommt, liest in der Rundgang-Zeile eine "
            "passende Begrüßung statt der allgemeinen; nur Anzeige, speichert nichts."
        ),
        einschalt_hinweis=f"{JURA_VORLAEUFIG} (nur Anzeige, nichts gespeichert)",
        oeffentlich=True,
    ),
    Schalterart(
        name="k_ankuenfte",
        gruppe=GRUNDFUNKTIONEN,
        feld="k_ankuenfte_aktiv",
        umgebungsvariable="SEMANTIC_SEARCH_K_ANKUENFTE_AKTIV",
        erklaerung=(
            "Zählt, wie oft die App mit ?k=<Wort> geöffnet wurde, je Wort aus der "
            "Positivliste und Tag; ohne Kennung, Konto, Adresse oder Beitrag. Die "
            "Zahlen stehen in der Übersicht."
        ),
        einschalt_hinweis=(
            "Aus lassen (Jura 26.11.): zusätzliche Anfrage aus dem Browser, § 25 "
            "TDDDG offen; kein DSE-Absatz"
        ),
        oeffentlich=True,
    ),
)
SCHALTER.update({s.name: s for s in K_SCHALTER})


class UnbekannterSchalter(KeyError):
    pass


class ObergrenzeAus(RuntimeError):
    """Einschalten ueber die Obergrenze hinaus: der Server erlaubt es nicht."""


@dataclass(frozen=True)
class Schalterstand:
    name: str
    erklaerung: str
    umgebungsvariable: str
    obergrenze: bool
    admin_wert: bool
    wirksam: bool
    dsfa_hinweis: Optional[str]
    gruppe: str
    # Ein Hinweis steht und der Schalter ist nicht rechtlich freigegeben
    wartet_auf_recht: bool


class SchalterService:
    def __init__(
        self,
        admin_werte_lesen: Callable[[], Dict[str, bool]],
        admin_wert_setzen: Callable[[str, bool, str], None],
        cache_sekunden: float = CACHE_SEKUNDEN,
        uhr: Callable[[], float] = time.monotonic,
    ):
        self._lesen = admin_werte_lesen
        self._setzen = admin_wert_setzen
        self._cache_sekunden = cache_sekunden
        self._uhr = uhr
        self._werte: Optional[Dict[str, bool]] = None
        self._gelesen_um = 0.0
        self._sperre = threading.Lock()

    def admin_werte(self, frisch: bool = False) -> Dict[str, bool]:
        """Admin-Werte mit Cache; synchron (kurze Abfrage hoechstens je Cache-Dauer).

        ``frisch``: am Cache vorbei lesen (Admin-Seite, mehrere Replikas) und den
        Cache dabei erneuern.
        """
        with self._sperre:
            if (
                not frisch
                and self._werte is not None
                and self._uhr() - self._gelesen_um < self._cache_sekunden
            ):
                return self._werte
            try:
                self._werte = dict(self._lesen())
            except Exception as e:
                logger.error(
                    f"Schalter nicht gelesen, gelten als aus: {type(e).__name__}",
                    exc_info=True,
                )
                self._werte = {}
            self._gelesen_um = self._uhr()
            return self._werte

    def admin_wert(self, name: str) -> bool:
        return bool(self.admin_werte().get(name, False))

    def wirksam(self, name: str, einstellungen: Settings) -> bool:
        # Ohne Obergrenze gar nicht erst lesen: Auf Prod fragt der Dienst die
        # Datenbank dann nicht.
        if not getattr(einstellungen, _art(name).feld):
            return False
        return _wirksam(name, einstellungen, self.admin_werte())

    def stand(
        self, einstellungen: Settings, frisch: bool = False
    ) -> List[Schalterstand]:
        """Stand aller Schalter nach Gruppen (GRUPPEN); ``frisch`` liest die
        Admin-Werte am Cache vorbei."""
        werte = self.admin_werte(frisch=frisch)
        return [
            _stand(art, einstellungen, werte)
            for art in sorted(SCHALTER.values(), key=lambda a: GRUPPEN.index(a.gruppe))
        ]

    def setzen(self, name: str, an: bool, admin: str, einstellungen: Settings) -> None:
        """Admin-Wert setzen. Ausschalten geht immer, Einschalten nur unter der Obergrenze."""
        art = _art(name)
        if an and not getattr(einstellungen, art.feld):
            raise ObergrenzeAus(name)
        self._setzen(name, an, admin)
        with self._sperre:
            self._werte = None


def _stand(
    art: Schalterart, einstellungen: Settings, werte: Dict[str, bool]
) -> Schalterstand:
    hinweis = art.einschalt_hinweis or (DSFA_HINWEIS if art.dsfa_hinweis else None)
    return Schalterstand(
        name=art.name,
        erklaerung=art.erklaerung,
        umgebungsvariable=art.umgebungsvariable,
        obergrenze=bool(getattr(einstellungen, art.feld)),
        admin_wert=bool(werte.get(art.name, False)),
        wirksam=_wirksam(art.name, einstellungen, werte),
        dsfa_hinweis=hinweis,
        gruppe=art.gruppe,
        wartet_auf_recht=bool(hinweis) and not art.rechtlich_freigegeben,
    )


def _wirksam(name: str, einstellungen: Settings, werte: Dict[str, bool]) -> bool:
    art = _art(name)
    an = bool(getattr(einstellungen, art.feld)) and bool(werte.get(name, False))
    if name == "team_fortschritt":
        # Ohne Teams keine Summe des Teams
        return an and _wirksam("teams", einstellungen, werte)
    if name == "team_quests":
        # Die Quests zaehlen mit dem Wochenzaehler des Team-Fortschritts
        return an and _wirksam("team_fortschritt", einstellungen, werte)
    if name == "abzeichen_sichtbar":
        # Ohne Punkte keine sichtbaren Abzeichen (wie Settings.abzeichen_sichtbar)
        return an and _wirksam("punkte", einstellungen, werte)
    if name == "teams_oeffentlich":
        # Ohne Teams keine Teams am Namen
        return an and _wirksam("teams", einstellungen, werte)
    if name == "teamlink_vertrauenssatz":
        # Ohne Teams keine Frage zum Teambeitritt, an der der Satz stehen koennte
        return an and _wirksam("teams", einstellungen, werte)
    if name == "gepostet_ohne_konto":
        # Unterschalter: ohne "Ja, gepostet" keine Meldungen ohne Konto
        return an and _wirksam("gepostet", einstellungen, werte)
    if name == "danke_ohne_konto":
        # Unterschalter: ohne Danke-Knopf kein Danke ohne Konto
        return an and _wirksam("danke_knopf", einstellungen, werte)
    if name == "rangliste":
        # Rangliste aus Punkten (ADR 0004): ohne Punkte keine Rangliste
        return an and _wirksam("punkte", einstellungen, werte)
    if name == "feedback_gestoert":
        # Nur in der Startphase: ab dem Loeschtag nimmt der Knopf nichts mehr an
        return an and gestoert_offen(heute_utc())
    return an


def oeffentliche_schalter() -> List[str]:
    """Namen der Schalter, deren wirksamen Wert GET /api/v1/funktionen meldet."""
    return [art.name for art in SCHALTER.values() if art.oeffentlich]


def _art(name: str) -> Schalterart:
    try:
        return SCHALTER[name]
    except KeyError:
        raise UnbekannterSchalter(name)


def _aus_datenbank() -> SchalterService:
    from repositories.schalter_repository import get_schalter_repository

    return SchalterService(
        admin_werte_lesen=lambda: get_schalter_repository().admin_werte(),
        admin_wert_setzen=lambda n, a, w: get_schalter_repository().setzen(n, a, w),
    )


_service: Optional[SchalterService] = None


def get_schalter_service() -> SchalterService:
    global _service
    if _service is None:
        _service = _aus_datenbank()
    return _service


def schalter_service_setzen(service: Optional[SchalterService]) -> None:
    """Fuer Tests: einen eigenen Dienst einsetzen (None: wieder aus der Datenbank)."""
    global _service
    _service = service


def schalter_wirksam(name: str, einstellungen: Optional[Settings] = None) -> bool:
    """Ob der Schalter wirkt: Obergrenze aus ``einstellungen`` (sonst global) und Admin-Wert."""
    return get_schalter_service().wirksam(
        name, einstellungen if einstellungen is not None else globale_settings
    )
