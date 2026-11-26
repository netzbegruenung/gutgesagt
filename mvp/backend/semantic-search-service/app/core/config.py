import os
import logging
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import AliasChoices, Field
from typing import Literal, Optional
from dotenv import load_dotenv

# Set up logger for module
logger = logging.getLogger(__name__)

# Load .env file if it exists (for local development)
env_file = Path(__file__).parent.parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    logger.debug(f"Loaded environment from {env_file}")

# Das Einbettungsmodell. Die Aehnlichkeitsschwellen in Settings sind dafuer gemessen;
# das Dockerfile laedt es beim Bauen vor und muss mitgezogen werden.
EMBEDDING_MODELL = "intfloat/multilingual-e5-base"
# Name seines Vektors in der Qdrant-Collection (Named Vector, #395): weitere Modelle
# bekommen daneben einen eigenen Namen, statt die Collection zu ersetzen.
EMBEDDING_VEKTOR = "e5_base"
# Das NLI-Modell der NLI-Stufe (#387, services/dieselbe_behauptung): mehrsprachiger
# Cross-Encoder mit XNLI-Training, MIT-Lizenz, nur fp32. Die Schwellen nli_* in Settings
# sind dafuer gemessen (tests/regression/MESSSET.md); das Dockerfile laedt es vor.
NLI_MODELL = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
# Der Bestaetiger (nli_bestaetiger in Settings): zweites NLI-Modell, MIT-Lizenz (Model
# Card), fp32, rund 2,2 GB RAM. Tokenizer aus dem Basismodell (gleiches Vokabular, aber
# als schneller Tokenizer, ohne sentencepiece). Das Dockerfile laedt beide vor.
NLI_BESTAETIGER_MODELL = "joeddav/xlm-roberta-large-xnli"
NLI_BESTAETIGER_TOKENIZER = "FacebookAI/xlm-roberta-large"
# aus: nur die Einbettung entscheidet (Regel vor #387). schatten: Die Einbettung
# entscheidet, die NLI-Stufe urteilt im Hintergrund mit und wird nur gezaehlt.
# an: Die NLI-Stufe entscheidet ueber dieselbe Aussage.
NliModus = Literal["aus", "schatten", "an"]

# Wie der Mailversand mit dem SMTP-Server spricht (infrastructure/mail/versand.py).
# Nur verschluesselt: Adresse und Text der Mail gehen nie lesbar ueber das Netz.
SmtpVerschluesselung = Literal["starttls", "ssl"]


class Settings(BaseSettings):

    # Qdrant configuration
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "content_collection"

    # Threads, die Torch fuer Einbettungen nutzt (#480). Ohne Angabe so viele wie
    # Kerne sichtbar sind. Auf einem ausgelasteten Host bremsen sich viele Threads
    # gegenseitig aus; in #478 dauerte eine kurze Einbettung mit 8 Threads Sekunden,
    # mit 2 Zehntelsekunden. Gilt fuer den ganzen Prozess.
    embedding_threads: Optional[int] = Field(default=None, ge=1)

    # Application database configuration (PostgreSQL for usage tracking, votes, etc.)
    app_database_url: str = (
        "postgresql+psycopg2://app_user:changeme@localhost:5433/gutgesagt_app"
    )

    def _get_project_root(self) -> str:
        """Get the project root directory path."""
        config_file_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up from core -> app -> semantic-search-service -> backend -> mvp
        return os.path.abspath(os.path.join(config_file_dir, "..", "..", "..", ".."))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Trim any whitespace from the qdrant_url
        if self.qdrant_url:
            self.qdrant_url = self.qdrant_url.strip()

        # Set up paths based on environment (Docker vs Local)
        if os.getenv("DOCKER_CONTAINER") == "true":
            # Running in Docker - paths MUST be provided via environment variables
            if not self.data_path:
                self.data_path = os.getenv(
                    "SEMANTIC_SEARCH_DATA_PATH", "/data/seed/v1.0"
                )
            if not self.metadata_path:
                self.metadata_path = os.getenv(
                    "SEMANTIC_SEARCH_METADATA_PATH", "/metadata"
                )
            if not self.migrations_path:
                self.migrations_path = "/migrations"
        else:
            # Running locally - use relative paths from project root
            project_root = self._get_project_root()
            if not self.data_path:
                self.data_path = os.path.join(project_root, "data", "seed", "v1.0")
            if not self.metadata_path:
                self.metadata_path = os.path.join(project_root, "temp_data", "metadata")
            if not self.migrations_path:
                self.migrations_path = os.path.join(
                    project_root, "backend", "postgres-app", "migrations"
                )

        # Legacy compatibility - will be removed in future version
        self.initial_data_path = self.data_path
        self.index_initial_data_path = os.path.join(self.data_path, "index_data")

        # Validate paths at startup
        self._validate_paths()

        # Log configuration
        logger = logging.getLogger(__name__)
        logger.debug(f"Data path: {self.data_path}")
        logger.debug(f"Metadata path: {self.metadata_path}")

    initial_data_author: str = "Gut gesagt Team"

    # Logging configuration
    log_level: str = "INFO"
    log_file: Optional[str] = None

    def get_logging_config(self):
        """Get logging configuration object."""
        from core.logging import LoggingConfig
        import os

        # Show logger names only if explicitly requested
        show_names = (
            os.getenv("SEMANTIC_SEARCH_SHOW_LOGGER_NAMES", "").lower() == "true"
        )

        return LoggingConfig(
            level=self.log_level, file_path=self.log_file, show_logger_name=show_names
        )

    # Business logic configuration

    # Dublettenpruefung. Die Schwellen gelten nur fuer EMBEDDING_MODELL - bei einem
    # Modellwechsel neu messen (tests/regression/test_aehnlichkeit_messset.py).
    # Normalisiert gleicher Text zaehlt immer als dasselbe, unabhaengig vom Score
    # (utils/text_normalisierung.py).
    #
    # Aussage still wiederverwenden: query/query-Einbettung, >= Schwelle.
    # Modell: intfloat/multilingual-e5-base. Gesetzt an 77 Paaren (hoechster
    # D-Wert 0,969), in Stufe 2 mit echten Formularentscheidungen ueberpruefen.
    # Das Messset mit Paar-Labels (tests/regression/MESSSET.md) zeigt: Verneinungen,
    # Gegenteile und Fragen liegen auch ueber 0,98 - das faengt erst #387 ab.
    # Inhaltlich aehnliche Aussagen werden nicht still uebernommen, sondern im
    # Formular vorgeschlagen (aussage_vorschlag_schwelle).
    statement_similarity_threshold: float = 0.98
    # NLI-Stufe (#387): zweite Stufe der Pruefung auf dieselbe Aussage. Gilt in
    # StatementService fuer alle Wege (Formular, Suche, Seeding). Ohne verfuegbares
    # Modell gilt die Schwelle oben. Gemessen am Messset (tests/regression/MESSSET.md,
    # Abschnitt NLI-Stufe): tau und kappa am Train-Teil, Ergebnis am Test-Teil.
    # Standard an wie auf Test und Produktion seit 09.11.2026 (#575); der naechtliche
    # Lauf misst damit (tests/regression/SUCHTESTSET.md).
    dieselbe_aussage_nli: NliModus = "an"
    # Kandidaten: Vektortreffer ab dieser query/query-Aehnlichkeit, hoechstens so viele.
    # Das niedrigste gleich-Paar der Aussagen liegt bei 0,887.
    nli_kandidaten_ab: float = Field(default=0.85, ge=0.0, le=1.0)
    nli_kandidaten_hoechstens: int = Field(default=5, ge=1, le=10)
    # tau: beide Richtungen folgern mindestens so sicher. kappa: keine Richtung
    # widerspricht mit dieser Wahrscheinlichkeit oder mehr.
    nli_folgerung_ab: float = Field(default=0.95, ge=0.0, le=1.0)
    nli_widerspruch_unter: float = Field(default=0.05, ge=0.0, le=1.0)
    # Bestaetiger: Ein Kandidat wird auch dann dieselbe Aussage, wenn das zweite Modell
    # (NLI_BESTAETIGER_MODELL) mit tau und kappa dieselbe Behauptung sieht und das erste
    # nicht widerspricht (kappa) und beidseitig mindestens nli_bestaetiger_veto_ab
    # folgert (regel.bestaetigt). Gerechnet wird nur in diesem Band. Aus, solange die
    # Ziel-VM die rund 2,2 GB zusaetzlich nicht nachweislich hat; wirkt nur, wenn die
    # NLI-Stufe nicht aus ist. Gemessen in tests/regression/MESSSET.md und SUCHTESTSET.md.
    nli_bestaetiger: bool = False
    nli_bestaetiger_veto_ab: float = Field(default=0.1, ge=0.0, le=1.0)
    # CPU-Threads: wie die Einbettung (embedding_threads); torch.set_num_threads gilt
    # prozessweit, ein eigener Wert fuer das NLI-Modell braeche die Einbettung.
    # Kommentar-Dublette: passage/passage-Einbettung, >= Schwelle.
    # Modell: intfloat/multilingual-e5-base. Umformulierungen hoechstens 0,972,
    # trivial abweichende Kopien und Kopien mit angehaengter Herkunft ab 0,996, andere
    # Kommentare zur selben Aussage hoechstens 0,899. Nur klein geschrieben erreicht
    # 0,955 - das faengt die Normalform. Der Abstand der Umformulierungen zur Schwelle
    # (0,003) ist kleiner als die Toleranz des Messsets in tests/regression (0,005):
    # Wer Schwelle oder Modell aendert, misst die Kommentar-Paare neu.
    commentary_similarity_threshold: float = 0.975
    # Hintergrundinfo-Dublette: dieselbe Einbettung und Schwelle wie beim Kommentar.
    # Gemessen an Hintergrundinfo-Paaren (Zahlen in tests/regression/MESSSET.md):
    # Derselbe Text mit anderer Zahl liegt darueber und gilt als Dublette,
    # Umformulierungen zum Teil darunter. Die Schwelle trennt das nicht; siehe #387.
    generic_text_similarity_threshold: float = 0.975
    # Vorschlaege im Feld "Antwort auf" (#387, frueher Konstante im Frontend):
    # Aussagen ab dieser query/query-Aehnlichkeit. Gemessen fuer EMBEDDING_MODELL
    # (passende Aussagen 0,892-0,940). Widerspricht eine Aussage dem Getippten in einer
    # Richtung mindestens so wahrscheinlich, schlaegt das Feld sie nicht vor. Der Filter
    # wirkt schon im Schattenbetrieb (#387: zuerst als Filter der Vorschlaege), nur bei
    # dieselbe_aussage_nli = aus nicht.
    aussage_vorschlag_schwelle: float = Field(default=0.885, ge=0.0, le=1.0)
    aussage_vorschlag_widerspruch_ab: float = Field(default=0.5, ge=0.0, le=1.0)
    default_search_limit: int = 10
    max_reply_suggestions: int = 50
    statement_search_limit: int = 5
    min_reply_suggestions_for_search: int = 1

    # Konten im Realm von Gut gesagt anlegen, wenn jemand eine Einladung einloest (#429).
    # Ohne URL, Client und Secret lassen sich Einladungen nur verwalten, nicht einloesen.
    # Einrichten: docs/KEYCLOAK_REALM.md. keycloak_url ist die Basis ohne /realms/...
    keycloak_url: Optional[str] = None
    keycloak_realm: str = "gutgesagt"
    keycloak_admin_client_id: Optional[str] = None
    keycloak_admin_client_secret: Optional[str] = None
    # Wohin der Link in der Mail "Passwort festlegen" danach fuehrt: Client der App und
    # ihre Adresse; der Link zeigt auf <app_url>/einladung/anmelden, die Seite startet
    # gleich die Anmeldung (ANMELDEN_PFAD in infrastructure/keycloak_konten.py). Ohne
    # beide endet er auf der Kontoseite von Keycloak.
    keycloak_app_client_id: Optional[str] = None
    app_url: Optional[str] = None

    # Mailversand an meldende Personen (#493): Eingangsbestaetigung und Entscheidung
    # nach Art. 16 Abs. 4 und 5 DSA (infrastructure/mail/versand.py). Ohne Host und
    # Absender geht keine Mail hinaus; die Entscheidung teilt dann ein Admin per Hand
    # mit. Einrichten: docs/DEPLOYMENT.md, "Mail".
    smtp_host: Optional[str] = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_benutzer: Optional[str] = None
    smtp_passwort: Optional[str] = None
    # starttls (Port 587) oder ssl (Port 465); unverschluesselt verschickt der Dienst nicht
    smtp_verschluesselung: SmtpVerschluesselung = "starttls"
    mail_absender: Optional[str] = None
    # Wohin Antworten gehen; ohne Angabe an den Absender. Die Mail der Entscheidung
    # nennt die Antwort als Weg, gegen sie vorzugehen: keine Adresse, die nichts annimmt.
    mail_antwort_an: Optional[str] = None

    # Admin users (comma-separated list)
    admin_users: str = ""

    def is_admin_user(self, user_id: Optional[str]) -> bool:
        """Check if a user is an admin.

        Args:
            user_id: User identifier to check

        Returns:
            True if user is admin, False otherwise
        """
        if not user_id or not self.admin_users:
            return False
        admin_list = [u.strip() for u in self.admin_users.split(",") if u.strip()]
        return user_id in admin_list

    # Startkonten (GLOSSARY.md "Startkonto", #352): Kennungen von Beta-Zugaengen,
    # unter denen das Gruendungsteam den Startbestand schreibt, kommagetrennt wie
    # admin_users. Ein Startkonto vergibt keine Nutzung und keine Stimmen, die andere
    # sehen oder die Punkte bringen, und sammelt selbst keine Punkte. Nutzung durch ein
    # Startkonto wird gar nicht erst gezaehlt; Nutzung von davor ist nicht mehr
    # zuzuordnen (usage_events traegt keine Kennung).
    startkonten: str = ""

    def startkonto_kennungen(self) -> frozenset:
        return frozenset(u.strip() for u in self.startkonten.split(",") if u.strip())

    @property
    def abzeichen_sichtbar(self) -> bool:
        """
        Obergrenze beider Schalter: ohne Punkte keine sichtbaren Abzeichen. Ob sie
        wirken, sagt schalter_wirksam (services/schalter_service.py, #708).
        """
        return self.punkte_aktiv and self.abzeichen_sichtbar_aktiv

    def ist_startkonto(self, user_id: Optional[str]) -> bool:
        return bool(user_id) and user_id in self.startkonto_kennungen()

    # Seit #708 sind punkte_aktiv, abzeichen_sichtbar_aktiv, gepostet_aktiv und die
    # Felder der spaeteren Schalter (SCHALTER in services/schalter_service.py) nur die
    # Obergrenze: Wirksam sind sie erst, wenn zusaetzlich ein Admin sie auf der Seite
    # "Schalter" einschaltet (services/schalter_service.py, schalter_wirksam). Im Code
    # nicht direkt abfragen.
    #
    # Punkte (ADR 0004, #352). Standard aus.
    # ANNAHME (#352): Rechtsgrundlage ist die Einwilligung beim ersten Login, die
    # Punkte als Zweck nennt (DSFA zu #374); bis sie steht und die
    # Datenschutzerklaerung den Abschnitt hat (#222), bleibt der Schalter aus. Er
    # schaltet die Punkte (/api/v1/usage/users/me/punkte) und die Muster-Hinweise
    # fuer Admins; Entdoppelung und Startkonten wirken immer.
    #
    # Punkte und Meilensteine haengen seit dem Wortlaut 2026-11-13 nicht mehr an der
    # Art.-9-Einwilligung, sondern an einer eigenen, freiwilligen Einwilligung "Punkte
    # und Meilensteine" (Entscheidung Maintainer 13.11.2026, gebaut mit #668:
    # domain/punkte_einwilligung.py, Tabelle punkte_einwilligung). Ohne sie startete
    # der Dienst mit punkte_aktiv nicht (PUNKTE_EINWILLIGUNG_GEBAUT,
    # punkte_schalter_pruefen, main.py).
    punkte_aktiv: bool = False
    # Meilenstein-Abzeichen am Anzeigenamen, die andere Angemeldete sehen (#351).
    # Standard aus und nur zusammen mit punkte_aktiv: Wie die Punkte haengen sie an
    # der DSFA (docs/DSFA.md), zusaetzlich an der Zustimmung zur Sichtbarkeit, die
    # jede Person selbst gibt (domain/abzeichen_sichtbarkeit.py).
    abzeichen_sichtbar_aktiv: bool = False
    # Rueckmeldung "Gepostet?" nach dem Kopieren (#643): Angemeldete mit
    # Art.-9-Einwilligung melden mit einem Klick, dass sie oeffentlich gekontert haben;
    # gezaehlt wird je Person und Kalenderwoche einmal (services/gepostet_service.py).
    # Standard aus, unabhaengig von punkte_aktiv: eine eigene Verarbeitung, die erst
    # mit Satz in DSFA und Datenschutzerklaerung eingeschaltet wird.
    gepostet_aktiv: bool = False
    # Meldungen ohne Konto (#799, services/gepostet_ohne_konto_service.py): "Ja, gepostet"
    # ohne Anmeldung als reiner Wochenzaehler, ohne Pruefwert. Standard aus und nur
    # zusammen mit gepostet_aktiv; erst nach DSE-Absatz und DSFA-Nachtrag (Jura).
    gepostet_ohne_konto_aktiv: bool = False
    # Drosselung von POST /api/v1/ereignis (#799): hoechstens so viele Meldungen je
    # Sekunde fuer alle zusammen, nur im Arbeitsspeicher, ohne Adresse.
    ereignis_je_sekunde: int = Field(default=10, ge=1)
    # Kampagnenwort ?k= (GLOSSARY.md "Kampagnenwort"): Begruessung nach dem Wort (nur
    # Anzeige im Browser) und Ankuenfte je Wort und Tag (services/ankunft_service.py),
    # beide Standard aus (vorlaeufige Jura-Einschaetzung 26.11.2026). Gezaehlt werden nur
    # Woerter aus k_woerter (kommagetrennt, klein); andere zaehlen nicht.
    k_begruessung_aktiv: bool = False
    k_ankuenfte_aktiv: bool = False
    k_woerter: str = "vorhut,g1,g2,g3,g4,bdk,sticker,karte,technik"
    # Drosselung von POST /api/v1/ankunft: hoechstens so viele Ankuenfte je Sekunde fuer
    # alle zusammen, nur im Arbeitsspeicher, ohne Adresse (wie ereignis_je_sekunde).
    ankunft_je_sekunde: int = Field(default=20, ge=1)

    def kampagnenwoerter(self) -> frozenset:
        """Die erlaubten Kampagnenwoerter, klein geschrieben; laengere als 20 Zeichen
        (Spalte ``ankuenfte_je_tag.k``) fallen weg."""
        return frozenset(
            w.strip().lower()
            for w in self.k_woerter.split(",")
            if w.strip() and len(w.strip()) <= 20
        )

    # Herkunft pruefen (#759): nachts die Links aller Herkuenfte abrufen und tote oder
    # umgezogene fuer Admins auflisten (services/herkunft_pruefen.py). Obergrenze an,
    # weil dabei nichts zur Person entsteht: kein Name, keine Kennung, nur Adresse und
    # Ergebnis. Wirksam erst, wenn ein Admin den Schalter einschaltet (Standard aus).
    herkunft_pruefen_aktiv: bool = True
    # Merkliste (#758): Angemeldete merken Beitraege und finden sie unter "Meine
    # Beitraege" wieder (Tabelle merkliste, api/v1/merkliste.py), nur mit
    # Art.-9-Einwilligung. Obergrenze Standard aus: Vor dem Einschalten auf Prod braucht
    # es Einwilligungswortlaut, DSFA-Abschnitt und DSE-Absatz (Hinweis auf der Admin-Seite).
    merkliste_aktiv: bool = False
    # App-Abkuerzungen im Manifest (#757): Langes Druecken aufs App-Symbol bietet
    # Einwerfen, Suchen und Fangkorb an. Das Manifest ist statisch, der Schalter wirkt an
    # der Zielroute /abkuerzung/<name> (aus: Startseite). Obergrenze an, weil nichts
    # uebertragen wird; Standard aus ist der Admin-Wert (ohne Eintrag aus).
    abkuerzungen_aktiv: bool = True
    # Antworten auf eigene Aussagen (#760): Kachel auf der Startseite und Reiter "Meine
    # Aussagen" (services/antworten_hinweis.py). Nichts wird gespeichert, aber die
    # Datenschutzerklaerung nennt bisher nur zwei 7-Tage-Zahlen: Standard aus wie bei
    # gepostet_aktiv, bis der Satz dort steht.
    antworten_hinweis_aktiv: bool = False
    # Seitenaufrufe und Besucher je Tag (#761, services/aufrufe_service.py): das
    # Tagespseudonym (#446) an einer Zeile je Besucher und Tag, am Tagesende zu zwei
    # Zahlen verdichtet. Standard aus: eine weitere Verarbeitung mit dem Pseudonym, die
    # erst mit Satz in Datenschutzerklaerung und DSFA und nach der Antwort auf die
    # DSB-Frage 2 (#495) eingeschaltet wird.
    aufrufe_zaehlen_aktiv: bool = False
    # Teilen als Bild (#756): Die Karte malt im Browser ein Bild (Sharepic) und gibt es
    # ans Teilen-Menue des Geraets; der Server sieht davon nichts. Obergrenze an, weil
    # nichts uebertragen oder gespeichert wird; Standard aus ist der Admin-Wert
    # (services/schalter_service.py, ohne Eintrag aus).
    sharepic_aktiv: bool = True
    # Zuwachs zur Bestandszahl (domain/bestandszahl.py): /getMetrics nennt dazu die neuen
    # Kommentare der letzten 7 Tage bzw. den Tag des letzten. Obergrenze an, weil nur
    # oeffentliche Inhalte beim Aufruf gezaehlt werden und nichts gespeichert wird;
    # wirksam erst mit dem Admin-Wert (Feature-Toggle fuer Neues, Sebastian 26.11.).
    bestandszahl_zuwachs_aktiv: bool = True
    # Kurzfassung "Kurz gesagt" oben in der Datenschutzerklaerung (Jura b): Standard aus,
    # bis der Wortlaut von Jura im Frontend steht (datenschutz/dse-kurzfassung.ts). Ohne
    # Wortlaut bleibt der Kasten auch eingeschaltet unsichtbar.
    dse_kurzfassung_aktiv: bool = False
    # Teams ueber Einladungen (services/team_service.py): Teamfelder an der Einladung,
    # Beitreten mit eigener Einwilligung, "Meine Teams". Standard aus: Die
    # Mitgliedschaft ist im Zweifel ein Art.-9-Datum; erst mit DSFA-Nachtrag,
    # Loeschkonzept und Abschnitt "Teams" in der Datenschutzerklaerung einschalten.
    teams_aktiv: bool = False
    # Team-Fortschritt (#784) und Team-Quests (#792), services/team_fortschritt_service.py:
    # eigene Obergrenzen, Standard aus; erst nach DSFA-Nachtrag V29 und Jura-OK
    # einschalten. team_fortschritt wirkt nur mit teams, team_quests nur mit
    # team_fortschritt.
    team_fortschritt_aktiv: bool = False
    team_quests_aktiv: bool = False
    # Teams oeffentlich am Namen (eigene Einwilligung, domain/teams.py). Eigene
    # Obergrenze, bewusst nicht an abzeichen_sichtbar_aktiv gekoppelt: Auf Prod bleibt
    # sie aus, bis die Datenschutzbeauftragte geraten hat. Wirkt nur mit teams_aktiv.
    teams_oeffentlich_aktiv: bool = False
    # Vertrauenssatz beim Teambeitritt (Begruessung eines Teamlinks): nur ein Text, speichert
    # nichts. Von Haus aus aus, bis Jura teams.py geprueft hat (was Mitglieder voneinander
    # sehen). Wirkt nur mit teams_aktiv.
    teamlink_vertrauenssatz_aktiv: bool = False
    # Knopf "Was hat dich gestört?" fuer die Startphase (domain/feedback_gestoert.py):
    # Feedback ohne Kontakt, geloescht bis 31.12.2026. Standard aus; einschalten erst
    # mit dem Absatz der Datenschutzerklaerung (Jura-Paket 27.11.).
    feedback_gestoert_aktiv: bool = False
    # Spielgefuehl zur BDK (#782 bis #793, services/schalter_service.py SPIEL_SCHALTER):
    # je Baustein eine Obergrenze, von Haus aus aus; Einschalt-Bedingungen je Schalter in
    # docs/ARCHITECTURE.md. danke_ohne_konto wirkt nur mit danke_knopf, rangliste nur mit
    # punkte.
    saison_ziel_aktiv: bool = False
    gartenansicht_aktiv: bool = False
    kopiert_erfolg_aktiv: bool = False
    konter_probe_aktiv: bool = False
    luecke_zu_gross_aktiv: bool = False
    einwilligung_im_gewinn_aktiv: bool = False
    naechster_schritt_aktiv: bool = False
    # "Danach wurde schon N-mal gesucht" (#362, Jura vorlaeufig 26.11.)
    null_treffer_anzahl_aktiv: bool = False
    wirkungs_echo_aktiv: bool = False
    danke_knopf_aktiv: bool = False
    danke_ohne_konto_aktiv: bool = False
    rangliste_aktiv: bool = False
    # Vertrauenszeile vor dem Anmelden (services/schalter_service.py, vorlaeufige
    # juristische Einschaetzung 26.11.): reiner Text, speichert nichts; Obergrenze trotzdem
    # von Haus aus aus, bis die Einschaetzung endgueltig ist.
    vertrauenszeile_aktiv: bool = False
    # Kurze Hinweiszeile unter dem Suchknopf (services/schalter_service.py
    # HINWEIS_SCHALTER): Obergrenze von Haus aus aus, bis Jura den Wortlaut bestaetigt.
    hinweiszeile_kurz_aktiv: bool = False
    # Saal-Spruch (services/saal_spruch_service.py): Karte auf der Startseite
    # mit einem vorab festgelegten, oeffentlichen Spruch je Tag; nur Text, nichts zur Person.
    saal_spruch_aktiv: bool = False
    # Saison und Gemeinschaftsziel (#782, domain/saisons.py): Den Balken sehen alle erst,
    # wenn es einmal so viele abgeschlossene Wochen hintereinander mit je mindestens so
    # vielen verschiedenen Menschen gab, die "Ja, gepostet" gemeldet haben; vorher nur
    # Admins. Die Datenschutzerklaerung nennt beide Zahlen: wer sie aendert, zieht den
    # Satz in datenschutz.component.html ("Rueckmeldung 'Ja, gepostet'") nach.
    saison_ziel_schwelle_menschen: int = Field(default=25, ge=0)
    saison_ziel_schwelle_wochen: int = Field(default=3, ge=0)
    # Gewichte und Deckel der drei Stufen (domain/punkte.py): Tun klein und je Tag
    # gedeckelt, Quests mehr, Wirkung bei anderen am meisten.
    punkte_nutzung: int = Field(default=10, ge=0)
    punkte_zustimmung: int = Field(default=5, ge=0)
    punkte_beitrag: int = Field(default=1, ge=0)
    punkte_einwurf_ausformuliert: int = Field(default=1, ge=0)
    punkte_deckel_tun_je_tag: int = Field(default=3, ge=0)
    punkte_quest: int = Field(default=4, ge=0)
    punkte_deckel_quests_je_tag: int = Field(default=8, ge=0)
    # Bewerten (Entscheidung Maintainer 20.11.2026): ein kleiner Punkt je Stimme zu
    # einem fremden Beitrag, je Tag eigens gedeckelt gegen Massenklicks und getrennt vom
    # Deckel fuers Tun, damit Abstimmen das Schreiben nicht verdraengt.
    punkte_bewertung: int = Field(default=1, ge=0)
    punkte_deckel_bewertungen_je_tag: int = Field(default=3, ge=0)

    # Guete eines Beitrags (#427, domain/guete.py): Stimmen anderer zaehlen erst ab
    # so vielen verschiedenen Stimmenden (DSFA, Massnahme M5), ihr Gewicht waechst mit
    # ihrer Zahl bis hoechstens zum Anteil ``guete_stimmen_gewicht_max``; beim
    # Halbwert ist die Haelfte davon erreicht. Der Rest kommt aus dem Gegenlesen.
    guete_stimmen_ab: int = Field(default=3, ge=1)
    guete_stimmen_gewicht_max: float = Field(default=0.6, ge=0, le=1)
    guete_stimmen_halbwert: int = Field(default=5, ge=1)

    # "Diese Woche oft genutzt" (services/oft_genutzt_service.py): Ein Beitrag gilt ab so
    # vielen entdoppelten Nutzungen in sieben Tagen als oft genutzt, und den Bereich gibt
    # es erst ab so vielen solchen Beitraegen. Entdoppelt wird je Person und Tag, nicht je
    # Woche: Eine Person allein kann den Bereich ausloesen, wenn sie die noetigen Beitraege
    # an zwei Tagen kopiert (ohne Anmeldung auch ueber wechselnde Anschluesse). Das galt
    # auch bei 3 und ist fuer die Startphase in Kauf genommen; wer was kopiert hat, zeigt
    # der Bereich nicht. Die Mindestnutzung bleibt mindestens 2: eine einzelne Kopie ist
    # Zufall, kein "oft". Startphase zur BDK (Maintainer 25.11.2026: bei kleinen Zahlen
    # frueher zeigen): Standard 2 Beitraege; mit mehr Nutzung hebt der Betrieb ihn an.
    # Hoechstens 5, so viele zeigt der Bereich (ANZAHL dort).
    oft_genutzt_mindest_nutzungen: int = Field(default=2, ge=2)
    oft_genutzt_mindest_beitraege: int = Field(default=2, ge=1, le=5)

    # Rate-Limit am Zaehl-Endpunkt (POST /usage/content/{id}/usage, #352): so viele
    # Kopien je Person (Besucher: je Adresse) im Fenster. Die Entdoppelung schuetzt
    # Punkte und "oft genutzt", nicht den Zaehler der Karte, der jede Kopie zaehlt.
    # 60 in 10 Minuten liegt weit ueber dem, was eine Person kopiert, und laesst
    # Raum fuer mehrere Besucher hinter einer Adresse.
    nutzung_rate_limit_anfragen: int = Field(default=60, ge=1)
    nutzung_rate_limit_minuten: int = Field(default=10, ge=1)

    # Tagesdeckel (GLOSSARY.md, middleware/tagesdeckel.py): so viele Beitraege,
    # Aussagen und Einwuerfe darf eine Person je UTC-Tag anlegen. Admins und
    # Startkonten sind ausgenommen (Redaktion, Import).
    tagesdeckel_beitraege: int = Field(default=20, ge=1)

    # Rate-Limit an den Anlege-Routen (middleware/rate_limit.py): so viele Anfragen
    # je Person und Minute bzw. Stunde. Startkonten sind ausgenommen (Import des
    # Startbestands), Admins nicht.
    anlege_rate_limit_je_minute: int = Field(default=10, ge=1)
    anlege_rate_limit_je_stunde: int = Field(default=100, ge=1)

    # Anfragen je Fenster der Rate-Limiter ohne Anmeldung (utils/rate_limiter.py).
    # Sie zaehlen je Anschluss; im Saal-WLAN eines Parteitags teilen sich alle eine
    # Adresse, dort hebt der Betrieb die Zahl an. Einstellbar ist nur die Zahl, nicht
    # das Fenster: Die Datenschutzerklaerung nennt die Fristen, die aus den Fenstern
    # folgen (test_rate_limiter_cleanup.py).
    aehnliche_aussagen_rate_limit_anfragen: int = Field(default=60, ge=1)
    suchaussage_rate_limit_anfragen: int = Field(default=60, ge=1)
    feedback_rate_limit_anfragen: int = Field(default=5, ge=1)
    meldung_rate_limit_anfragen: int = Field(default=5, ge=1)
    einladung_rate_limit_anfragen: int = Field(default=30, ge=1)
    einladung_pruefen_rate_limit_anfragen: int = Field(default=60, ge=1)
    # Angemeldet einem Team beitreten (POST /einladungen/beitreten): je Person, nicht je
    # Anschluss, damit Beitritte im Saal-WLAN nicht das Budget fuers Einloesen aufbrauchen.
    team_beitreten_rate_limit_anfragen: int = Field(default=20, ge=1)

    # Secret key for the daily search-actor pseudonym (see SearchTrackingService).
    # Set SEMANTIC_SEARCH_ACTOR_HASH_SECRET in production so the daily-active-user
    # count stays correct across service restarts. If it is left unset a random
    # secret is generated per process: privacy-safe, but every restart starts a new
    # pseudonym space and inflates the DAU count for that day.
    actor_hash_secret: Optional[str] = None

    # Der taegliche Bereinigungsjob (services/cleanup/bereinigungsjob.py) mit der
    # Frist der Nutzungsereignisse. Suchereignisse verdichtet er nicht mehr: Das
    # geschieht am Tagesende ohne Schalter (services/loeschfristen_service.py, #495).
    # Der fruehere Name ENABLE_USAGE_CLEANUP gilt
    # weiter, damit ein abgeschalteter Job nach dem Umbenennen nicht still wieder
    # loescht; der neue Name geht vor.
    enable_bereinigungsjob: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "SEMANTIC_SEARCH_ENABLE_BEREINIGUNGSJOB",
            "SEMANTIC_SEARCH_ENABLE_USAGE_CLEANUP",
        ),
    )
    usage_retention_days: int = 90
    cleanup_hour: int = 2  # 2 AM
    cleanup_minute: int = 0

    # Polarity filtering configuration
    enable_polarity_filtering: bool = (
        True  # Enable negation detection and polarity filtering
    )
    # Polaritaetsstrafe der Suche mit dem NLI-Modell statt der Wortlisten (#574,
    # services/search/polaritaet_nli.py). aus: Wortlisten. schatten: Wortlisten
    # entscheiden, das Modell urteilt im Hintergrund mit und wird gezaehlt. an: Das Modell
    # straft Aussagen, die der Suchanfrage in beiden Richtungen mit mindestens
    # suche_polaritaet_widerspruch_ab widersprechen, und laesst ihre Antworten auch
    # direkt nicht zu; Fragen, Schlagwoerter und ohne Modell: die Wortlisten.
    # Dasselbe Modell wie die NLI-Stufe (NLI_MODELL), kein zweites im Speicher.
    # Gemessen in tests/regression/SUCHTESTSET.md (Abschnitt Polaritaet mit NLI).
    suche_polaritaet_nli: NliModus = "schatten"
    suche_polaritaet_widerspruch_ab: float = Field(default=0.9, ge=0.0, le=1.0)
    # Bezug (services/search/bezug.py), fuer Suchanfragen ab drei Woertern, an der
    # Aehnlichkeit der Einbettung: Eine Aussage unter suche_bezug_ab zaehlt nicht als
    # Aussagetreffer. Gegen "Erkannt als" mit einer fremden Aussage, die nur ein
    # Schlagwort teilt ("Open Source ist unsicher!" zu "Migranten machen unsere Staedte
    # unsicher.", 0,862). Bei einer Behauptung (keine Frage) zaehlt eine Aussage bis
    # suche_bezug_sicher_ab zudem nur, wenn das NLI-Modell (NLI_MODELL) in einer Richtung
    # mindestens suche_bezug_folgerung_ab Folgerung sieht (ohne Modell: zaehlt); das
    # haelt auch gleich gebaute Saetze fern. suche_bezug_nli = false laesst nur die
    # Untergrenze. Gemessen in tests/regression/SUCHTESTSET.md (Abschnitt Bezug).
    suche_bezug_nli: bool = True
    suche_bezug_ab: float = Field(default=0.87, ge=0.0, le=1.0)
    suche_bezug_sicher_ab: float = Field(default=0.92, ge=0.0, le=1.0)
    suche_bezug_folgerung_ab: float = Field(default=0.2, ge=0.0, le=1.0)
    # Antworten einer Aussage ohne Bezug kommen auch ueber den direkten Weg nur, wenn
    # ihr eigener Rohscore zur Suchanfrage mindestens so hoch ist. Gemessen am
    # Startbestand (SUCHTESTSET.md, Abschnitt Bezug): unpassende solche Antworten bis
    # 0,872, passende ab 0,82; eine Schwelle trennt beides nicht. 0,86 haelt den Befund
    # von Produktion 0.9.2 (0,83) und zwei weitere fremde Faelle fern und laesst Recall@10 am Seed
    # ueber dem Tor; ganz ohne Ausnahme fiele er darunter.
    suche_bezug_direkt_ab: float = Field(default=0.86, ge=0.0, le=1.01)
    # Inhaltstor (services/search/inhaltstor.py), nur fuer Suchanfragen ab drei Woertern:
    # Ein Aussagetreffer mit Aehnlichkeit von suche_inhaltstor_ab bis unter
    # suche_inhaltstor_aussage_bis und ein direkter Treffer mit Rohscore ueber
    # suche_inhaltstor_ab bis unter suche_inhaltstor_direkt_bis zaehlen nur, wenn
    # Suchanfrage und Treffer ein Inhaltswort teilen (Lemma eines Nomens oder
    # Eigennamens der Suchanfrage). Gegen eine fremde Antwort, deren Aussage nicht unter
    # den Aussagetreffern ist ("Open Source ist unsicher!", 0,821 auf Produktion 0.9.3).
    # Gemessen in tests/regression/SUCHTESTSET.md (Abschnitt Inhaltstor).
    suche_inhaltstor: bool = True
    suche_inhaltstor_ab: float = Field(default=0.82, ge=0.0, le=1.0)
    suche_inhaltstor_aussage_bis: float = Field(default=0.92, ge=0.0, le=1.01)
    suche_inhaltstor_direkt_bis: float = Field(default=0.90, ge=0.0, le=1.01)
    # Themenvorschlaege (#401, services/themen_vorschlag.py): ein Thema wird
    # vorgeschlagen ab dieser Aehnlichkeit zu seinem Prototyp (um die Mitte verschoben,
    # daher Werte um 0 bis 0,5) und hoechstens so weit hinter dem naechsten Thema. Mit
    # themen_vorschlag_nli streicht das NLI-Modell Kandidaten unter
    # themen_vorschlag_folgerung_ab; aus, weil es in der Messung mehr Treffer strich
    # als Fehler. Standard aus, bis es etwa 200 Zuordnungen von Hand gibt (Maintainer,
    # 22.11.2026): Dann meldet /themen vorschlaege = false, das Frontend fragt nicht,
    # und der Endpunkt liefert eine leere Liste. Einschalten mit
    # SEMANTIC_SEARCH_THEMEN_VORSCHLAEGE=true. Gemessen in tests/regression/THEMEN.md.
    themen_vorschlaege: bool = False
    themen_vorschlag_ab: float = Field(default=0.10, ge=-1.0, le=1.0)
    themen_vorschlag_abstand_hoechstens: float = Field(default=0.05, ge=0.0, le=2.0)
    themen_vorschlag_nli: bool = False
    themen_vorschlag_folgerung_ab: float = Field(default=0.5, ge=0.0, le=1.0)
    # Karte "Dein naechster Schritt" (#789, services/naechster_schritt.py): unter so
    # vielen eigenen Stimmen schlaegt sie Bewerten vor, wenn es so viele frische
    # Antworten anderer gibt; der Satz nennt die Zahl.
    naechster_schritt_stimmen: int = Field(default=3, ge=1, le=20)

    # Keyword overlap boosting configuration
    enable_keyword_overlap_boost: bool = (
        True  # Enable keyword overlap boosting for search results
    )
    keyword_overlap_boost_strength: float = (
        0.15  # Strength of keyword overlap boost/penalty (0.0-1.0)
    )

    # Path configuration
    # Override with SEMANTIC_SEARCH_DATA_PATH and SEMANTIC_SEARCH_METADATA_PATH env vars
    data_path: str = ""  # Path to seed data (e.g., /data/seed/v1.0)
    metadata_path: str = ""  # Path to persistent metadata storage
    # SQL-Migrationen, die der Dienst beim Start einspielt
    # (infrastructure/database/migrationen.py). Im Image /migrations.
    migrations_path: str = ""

    # Legacy fields - deprecated, use data_path instead
    initial_data_path: str = ""  # Deprecated: use data_path
    index_initial_data_path: str = ""  # Deprecated: for backward compatibility only

    class Config:
        # Loads all env variables starting with the prefix
        env_prefix = "SEMANTIC_SEARCH_"
        # Also load standard environment variables for logging
        env_ignore_empty = True
        # Felder mit validation_alias (enable_bereinigungsjob) auch per Feldname
        # setzbar, etwa Settings(enable_bereinigungsjob=False); aus der Umgebung
        # gelten nur die Aliase mit Praefix.
        populate_by_name = True

    def _validate_paths(self):
        """Validate that required paths exist or can be created."""
        logger = logging.getLogger(__name__)

        # Data path validation
        if not os.path.exists(self.data_path):
            if os.getenv("DOCKER_CONTAINER") == "true":
                # In Docker, missing data path is critical
                raise ValueError(
                    f"Data path does not exist: {self.data_path}\n"
                    f"Please ensure the data volume is mounted correctly in docker-compose.yml"
                )
            else:
                # For local development, warn but continue
                logger.warning(
                    f"Data path not found at {self.data_path}. "
                    f"Seeding will not be available until path exists."
                )
        else:
            # Verify expected structure exists
            expected_dirs = [
                "statements_with_commentaries",
                "statements_with_generictexts",
            ]
            missing_dirs = [
                d
                for d in expected_dirs
                if not os.path.exists(os.path.join(self.data_path, d))
            ]
            if missing_dirs and os.listdir(
                self.data_path
            ):  # Only warn if directory is not empty
                logger.debug(
                    f"Expected directories not found in {self.data_path}: {missing_dirs}"
                )

        # Create metadata directory if it doesn't exist
        os.makedirs(self.metadata_path, exist_ok=True)
        logger.debug(f"Metadata directory ensured at: {self.metadata_path}")


# Create global settings instance
settings = Settings()


# Die eigene, freiwillige Einwilligung "Punkte und Meilensteine" ist gebaut (#668:
# domain/punkte_einwilligung.py, repositories/punkte_einwilligung_repository.py,
# GET/PUT /api/v1/usage/users/me/punkte-einwilligung). Bleibt als Sicherung stehen:
# Auf False verhindert punkte_schalter_pruefen, dass jemand punkte_aktiv einschaltet
# (Review zu #670).
PUNKTE_EINWILLIGUNG_GEBAUT = True


def punkte_schalter_pruefen(einstellungen: "Settings") -> None:
    """
    Beim Start: Punkte nur mit eigener Einwilligung (#668); sonst startet der Dienst nicht.
    Prueft nur die Obergrenze aus der Umgebung, nicht den Admin-Wert (#708).
    """
    if einstellungen.punkte_aktiv and not PUNKTE_EINWILLIGUNG_GEBAUT:
        raise RuntimeError(
            "SEMANTIC_SEARCH_PUNKTE_AKTIV ist an, aber die eigene Einwilligung "
            "'Punkte und Meilensteine' (#668) ist noch nicht gebaut. Erst nach dem "
            "Merge von #668 einschalten."
        )
