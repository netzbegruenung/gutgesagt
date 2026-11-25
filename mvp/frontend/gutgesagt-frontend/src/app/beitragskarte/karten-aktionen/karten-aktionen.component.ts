import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  OnInit,
  Output,
  Injector,
  SimpleChanges,
  computed,
  inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Clipboard } from '@angular/cdk/clipboard';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatSnackBar, MatSnackBarRef } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Router } from '@angular/router';
import { Observable, Subject } from 'rxjs';
import { debounceTime, map, take } from 'rxjs/operators';

import { AuthService } from '../../auth/auth.service';
import { LoggingService } from '../../services/logging.service';
import { GEPOSTET_NICHT_ANGEBOTEN, UsageTrackingService } from '../../services/usage-tracking.service';
import { VotingService } from '../../services/voting.service';
import { meldeDialogOeffnen } from '../../shared/components/report-dialog/report-dialog.component';
import { ROUTES } from '../../shared/constants/app.constants';
import type { Fassung } from '../../shared/fassung';
import { kannVorlageSein, vorlageAdresse } from '../../beitragsformular/vorlage';
import { einwilligungFehlt } from '../../services/art9-einwilligung.service';
import { beitragsLink } from '../../shared/beitrags-link';
import { TeilenService, hatGeteilt } from '../../shared/teilen.service';
import { FunktionenService } from '../../services/funktionen.service';
import { sharepicDialogOeffnen } from '../../shared/sharepic/sharepic-dialog.component';
import { KOPIERT, KOPIERT_MIT_LUECKE, hatLuecke } from '../../shared/vorlagen-luecke';
import { platzhalterDialogOeffnen } from './platzhalter-dialog.component';
import { GEPOSTET_NICHT_GEZAEHLT, GEPOSTET_OHNE_KONTO_DANK, gepostetDank } from './gepostet-texte';
import { MeilensteinHinweisService } from '../../meine-beitraege/meilenstein-hinweis.service';
import { STIMM_DANK_MS, stimmDank } from './stimm-dank-texte';
import { DankeKnopfComponent } from './danke-knopf.component';
import { GepostetStand, KopiertErfolgComponent } from './kopiert-erfolg.component';
import type { AndereTonlage } from './kopiert-erfolg';
import { KopiertErfolgStelle } from './kopiert-erfolg-stelle';

/**
 * So lange steht „Kopiert“: Mit 1,5 s war es beim Wechsel in die andere App schon weg
 * (Persona-Runde 2, P10).
 */
export const KOPIERT_DAUER_MS = 4000;

/**
 * Die Aktionsleiste der vollen Beitragskarte: abstimmen, kopieren, teilen, melden, im
 * Menue der Weg zur eigenen Adresse des Beitrags (/beitrag/:id, #300) und,
 * angemeldet, als Vorlage nehmen (#356).
 * Hat der Beitrag eine Herkunft, steht die zweite Kopier-Variante (mit oder ohne
 * Herkunft) im Menue; welche der Knopf kopiert, entscheidet die Karte (#641).
 *
 * Abstimmen ist optimistisch mit Entprellung und Ruecknahme, dazu 401/403/429-Behandlung
 * (urspruenglich aus BaseResultItemComponent). Die Leiste sitzt in einer eigenen
 * Komponente, damit Einwurf- und Kopf-Karten, die keine Aktionsleiste haben,
 * keine Knoepfe und keine Dienste mitschleppen.
 *
 * In der Formular-Vorschau ist die Leiste sichtbar wie in der Suche, reagiert aber
 * nicht: kein Zeiger, kein Fokus, aria-disabled. Ausgegraut wird sie bewusst nicht,
 * die Vorschau soll zeigen, wie der Beitrag aussehen wird.
 */
type Stimme = 'like' | 'dislike' | null;

/** Eine zweite Art zu kopieren, als Eintrag im ⋮-Menue (#641). */
export interface KopierVariante {
  text: string;
  wort: string;
}

@Component({
  selector: 'app-karten-aktionen',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatIconModule, MatMenuModule, MatTooltipModule, DankeKnopfComponent, KopiertErfolgComponent],
  templateUrl: './karten-aktionen.component.html',
  styleUrls: ['./karten-aktionen.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[class.ist-vorschau]': 'vorschau' },
})
export class KartenAktionenComponent implements OnInit, OnChanges, OnDestroy {
  @Input({ required: true }) inhaltId!: string;
  /** Registry-Schluessel, geht an den Melde-Dialog. */
  @Input() typ: string | null = null;
  @Input() kopierText = '';
  @Input() kopierBeschriftung = 'Kopieren';
  /** Am Handy statt kopierBeschriftung sichtbar (Bild: "Kopieren"); null = kein Kurzwort. */
  @Input() kopierKurz: string | null = null;
  /** Was der Knopf kopiert, als Tooltip (MatTooltip haengt ihn als Beschreibung an); leer = keiner. */
  @Input() kopierHinweis = '';
  /** Die andere Variante (mit oder ohne Herkunft) im Menue; null = es gibt nur eine. */
  @Input() zweiteKopie: KopierVariante | null = null;
  @Input() stimme?: 'like' | 'dislike';
  @Input() vorschau = false;
  /** Aus beim eigenen Beitrag (Album-Sheet in Meine Beitraege); Kopieren und Melden bleiben. */
  @Input() abstimmenSichtbar = true;
  /** Die angezeigte Fassung eines Kommentars, gezaehlt wird je Fassung (#355); sonst null. */
  @Input() fassung: Fassung | null = null;
  /** Der Menueeintrag "Beitrag öffnen"; aus auf der eigenen Adresse selbst. */
  @Input() ansichtVerlinkt = true;
  /** Der Knopf "Teilen" (B7); die Karte gibt ansichtVerlinkt weiter, ausser auf der Beitragsseite. */
  @Input() teilbar = true;
  /** Teilen als Eintrag im ⋮-Menue statt als eigener Knopf (schlichte Karte der Trefferseite, V3 17.11.). */
  @Input() teilenImMenue = false;
  /** Der Titel des Beitrags: im Namen des Teilen-Knopfs und als Titel im Teilen-Menue. */
  @Input() titel: string | null = null;
  /**
   * Zaehler an den Stimm-Knoepfen (#427), wie der Server sie zuletzt gemeldet hat;
   * null = unter der Mindestzahl (der Server schickt dann keine, DSFA M5) oder
   * unbekannt, dann ohne Zahl. Die eigene Stimme rechnet die Leiste sofort ein.
   */
  @Input() hilfreich: number | null = null;
  @Input() nichtHilfreich: number | null = null;
  /** Aus am eigenen Beitrag: Die Zaehler zeigen nur Stimmen anderer (#427). */
  @Input() eigeneStimmeImZaehler = true;
  /**
   * Ob Stimmen an diesem Beitrag schon in die Güte zählen (`guete_stimmen_zaehlen`), wie die
   * Karte es zuletzt geladen hat; null = unbekannt. Nur für den Sofort-Dank.
   */
  @Input() stimmenZaehlen: boolean | null = null;

  /**
   * Eigenes Album in Meine Beitraege (Variante A, 20.11.): Aendern, Teilen als Hauptknopf,
   * im Menue Kopieren, Oeffnen, Als Vorlage und Loeschen; kein Abstimmen, kein Melden.
   */
  @Input() album = false;
  /** Im Album: der Knopf "Ändern" (nur Kommentar und Hintergrundinfo, istAenderbar). */
  @Input() aenderbar = false;

  /** Teilen als Bild (#756): der angezeigte Text der gewaehlten Fassung, ohne Herkunft. */
  @Input() bildText = '';
  /** Teilen als Bild: die Aussage, auf die der Beitrag antwortet; null ohne. */
  @Input() aussage: string | null = null;
  /** Teilen als Bild: das erste Thema der Aussage mit Motiv; null ohne. */
  @Input() thema: { name: string; motiv?: string } | null = null;

  /** „Als Bild teilen“ steht nur im Menue, wenn der Schalter an ist (#756, Standard aus). */
  readonly sharepicAn = inject(FunktionenService).an('sharepic');
  /** „Danke an die Autorin“ nach dem Kopieren (#791); ohne Konto nur mit Unterschalter. */
  readonly dankeKnopfAn = inject(FunktionenService).an('danke_knopf');
  readonly dankeOhneKontoAn = inject(FunktionenService).an('danke_ohne_konto');
  /** „Ja, gepostet“ auch ohne Konto (#799), nur als Wochenzähler „Meldungen ohne Konto“. */
  readonly gepostetOhneKontoAn = inject(FunktionenService).an('gepostet_ohne_konto');
  /**
   * Schon „Ja, gepostet“ getippt, mit oder ohne Konto (#643, #799): Danach fragt diese
   * Karte nicht mehr, bis die Seite neu geladen wird. Ohne Konto ist das die einzige
   * Entdoppelung; sie liegt nur in dieser Komponente, nicht im Browser-Speicher und nicht
   * am Server.
   */
  private gepostetGemeldet = false;
  /** Die Frage „Gepostet?“ im Erfolgskasten dieser Karte (Review Spielgefühl 25.11., Nr. 2). */
  gepostetStand: GepostetStand = 'aus';
  /** Der Dank nach „Ja, gepostet“, im Erfolgskasten. */
  gepostetDankText: string | null = null;
  /** Kennung beim Kopieren, für die Meldung; null ohne Konto. */
  private gepostetKennung: string | null = null;
  /** Zählt die Kopiervorgänge, damit eine späte Antwort nicht in ein neueres Kopieren fragt. */
  private kopierLauf = 0;
  /** Der laufende Kopiervorgang für den Erfolgskasten (Rückkehr-Moment). */
  get erfolgLauf(): number {
    return this.kopierLauf;
  }
  /** Ob die Frage „Gepostet?“ ohne Konto steht (#799): dann ohne „zählt mit“. */
  get gepostetOhneKonto(): boolean {
    return this.gepostetKennung === null;
  }
  /** Die Snackbar „Kopiert“, falls ohne Erfolgstext eine Frage sie ablöst. */
  private kopiertHinweis: MatSnackBarRef<unknown> | null = null;
  /** Seit dem ersten Kopieren auf dieser Karte; kein Zeitlimit. */
  dankeAngeboten = false;

  /** Erfolgstext nach dem Kopieren (#785): die Nutzung, wie die Karte sie zeigt; null = unbekannt. */
  @Input() nutzung: number | null = null;
  /** Erfolgstext nach dem Kopieren: eine Antwort zur selben Aussage in anderem Stil; null = kein Hinweis. */
  @Input() andereTonlage: AndereTonlage | null = null;
  /** Statt „Kopiert – jetzt unter dem Post einfügen.“ der Erfolgstext unter der Leiste (#785, Standard aus). */
  readonly kopiertErfolgAn = inject(FunktionenService).an('kopiert_erfolg');
  /** Welche Karte gerade ihren Erfolgstext zeigt; immer nur die zuletzt kopierte (#785). */
  private readonly erfolgStelle = inject(KopiertErfolgStelle);
  /** Kennung dieser Karte bei der Erfolgsstelle. */
  private readonly erfolgKennung = {};
  /** Ob der Erfolgstext gerade dasteht: bis die Person ihn schließt oder eine andere Karte kopiert. */
  readonly kopiertErfolg = computed(() => this.erfolgStelle.aktiv() === this.erfolgKennung);
  /**
   * Die Nutzung im Moment des Kopierens, bevor die Karte die eigene Kopie hochzählt: „Schon
   * N-mal genutzt“ nennt, wie oft die Antwort vorher genutzt wurde.
   */
  nutzungBeimKopieren: number | null = null;

  @Output() likeToggled = new EventEmitter<string>();
  /** Im Album: "Ändern" angetippt; den Dialog oeffnet die Seite. */
  @Output() aendern = new EventEmitter<void>();
  /** Im Album: "Beitrag löschen" angetippt; Rueckfrage und Loeschen macht die Seite. */
  @Output() loeschen = new EventEmitter<void>();
  @Output() dislikeToggled = new EventEmitter<string>();
  /** Nach erfolgreichem Kopieren oder Teilen; die Karte zaehlt daraufhin ihre Nutzung hoch. */
  @Output() kopiert = new EventEmitter<void>();

  isLiked = false;
  isDisliked = false;
  private injector = inject(Injector);
  isVoting = false;
  copyAnimationActive = false;

  /**
   * Die Stimme, wie sie vor dem ersten Tippen seit dem letzten Abgleich stand;
   * undefined, solange nichts aussteht. Gegen sie wird nach der Entprellung
   * abgeglichen: gesendet wird, was noetig ist, um vom Ausgangs- zum Zielzustand
   * zu kommen.
   *
   * Frueher trugen zwei Subjects je Knopf "war vorher an" durch
   * distinctUntilChanged. Like -> Dislike -> Like schickte dort zweimal false auf
   * den Like-Strom, das zweite fiel weg - die Karte zeigte Like, gespeichert war
   * Dislike.
   */
  private ausgang: Stimme | undefined;
  /** Die eigene Stimme, die in den zuletzt gemeldeten Zaehlern schon steckt. */
  private stimmeImZaehler: Stimme = null;
  private abgleich = new Subject<void>();
  private abonniert = false;

  constructor(
    private clipboard: Clipboard,
    private snackBar: MatSnackBar,
    private cdr: ChangeDetectorRef,
    private usageTrackingService: UsageTrackingService,
    private votingService: VotingService,
    private authService: AuthService,
    private logger: LoggingService,
    private dialog: MatDialog,
    private router: Router,
    private teilenService: TeilenService,
  ) {}

  ngOnInit(): void {
    this.initializeVoteState();

    if (this.abonniert) {
      return;
    }
    this.abonniert = true;
    this.abgleich.pipe(debounceTime(50)).subscribe(() => this.abgleichen());
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['stimme'] || changes['inhaltId']) {
      this.initializeVoteState();
      this.stimmeImZaehler = this.stimme ?? null;
    } else if (changes['hilfreich'] || changes['nichtHilfreich']) {
      // Frisch geladen nach einer abgeglichenen Stimme: Die angezeigte steckt jetzt drin.
      this.stimmeImZaehler = this.angezeigt;
    }
  }

  get zahlHilfreich(): number | null {
    return this.zahl(this.hilfreich, 'like');
  }

  get zahlNichtHilfreich(): number | null {
    return this.zahl(this.nichtHilfreich, 'dislike');
  }

  /** Der unsichtbare Name eines Stimm-Knopfs, mit Zaehler, sofern bekannt. */
  beschriftung(name: string, zahl: number | null): string {
    if (zahl === null) {
      return name;
    }
    return `${name}, ${zahl} ${zahl === 1 ? 'Stimme' : 'Stimmen'}`;
  }

  private zahl(gemeldet: number | null, richtung: 'like' | 'dislike'): number | null {
    if (gemeldet === null || !this.eigeneStimmeImZaehler) {
      return gemeldet;
    }
    const jetzt = this.angezeigt === richtung ? 1 : 0;
    const drin = this.stimmeImZaehler === richtung ? 1 : 0;
    return Math.max(0, gemeldet + jetzt - drin);
  }

  ngOnDestroy(): void {
    this.abgleich.complete();
    this.erfolgStelle.schliessen(this.erfolgKennung);
  }

  toggleLike(): void {
    this.umschalten(this.isLiked ? null : 'like');
  }

  toggleDislike(): void {
    this.umschalten(this.isDisliked ? null : 'dislike');
  }

  /** Was die Karte als Standard vorgibt. */
  kopieren(): void {
    this.inZwischenablage(this.kopierText);
  }

  /** Die zweite Variante aus dem Menue; zaehlt wie Kopieren als Nutzung. */
  zweiteKopieren(): void {
    this.inZwischenablage(this.zweiteKopie?.text ?? '');
  }

  /**
   * Mit Platzhalter „[Hier …]“ fragt erst der Dialog nach dem eigenen Satz und kopiert
   * selbst (Persona-Test Dennis, 13.11.); abgebrochen wird nichts kopiert und nichts gezählt.
   */
  private inZwischenablage(text: string): void {
    if (this.vorschau || !text) {
      return;
    }
    if (hatLuecke(text)) {
      platzhalterDialogOeffnen(this.dialog, text)
        .afterClosed()
        .subscribe((ergebnis) => {
          if (ergebnis) {
            this.nachKopieren(ergebnis.text);
          }
        });
      return;
    }
    this.clipboard.copy(text);
    this.nachKopieren(text);
  }

  /** Rückmeldung, Animation und Nutzung nach dem Kopieren, gleich ob mit oder ohne Dialog. */
  private nachKopieren(text: string): void {
    this.kopiertMelden(text);

    this.copyAnimationActive = true;
    setTimeout(() => {
      this.copyAnimationActive = false;
      this.cdr.markForCheck();
    }, 600);

    if (this.inhaltId) {
      this.usageTrackingService.trackContentUsage(this.inhaltId, this.fassung ?? undefined);
      this.kopiert.emit();
      this.dankeAngeboten = true;
    }
    this.cdr.markForCheck();
  }

  /**
   * Der Knopf „Danke an die Autorin“ (#791): nach dem Kopieren, nicht am eigenen Beitrag,
   * nicht in Vorschau und Album; angemeldet mit `danke_knopf`, ohne Konto nur mit
   * `danke_ohne_konto`.
   */
  get dankeSichtbar(): boolean {
    if (!this.dankeAngeboten || this.vorschau || this.album || !this.eigeneStimmeImZaehler) {
      return false;
    }
    const angemeldet = !!this.authService.getUserInfo()?.isAuthenticated;
    return angemeldet ? this.dankeKnopfAn() : this.dankeOhneKontoAn();
  }

  /**
   * Nach dem Kopieren: Mit dem Schalter `kopiert_erfolg` (#785) steht der Erfolgstext unter
   * der Leiste statt der Snackbar „Kopiert“. Wird „Ja, gepostet“ angeboten (angemeldet mit
   * Einwilligung und Schalter, #643, oder ohne Konto mit `gepostet_ohne_konto`, #799), steht
   * die Frage mit Knopf im selben Kasten, ohne Frist: Posten dauert länger als eine
   * Snackbar (Review Spielgefühl 25.11.). Ein Klick zählt die Person einmal je Woche als
   * öffentlich gekontert.
   *
   * Ist `kopiert_erfolg` aus, zeigt der Kasten nur „Kopiert – jetzt unter dem Post
   * einfügen.“ mit der Frage; ohne Frage bleibt es bei der Snackbar wie bisher.
   *
   * Hat der Text noch einen Platzhalter „[Hier …]“ (#640), bleibt es beim Hinweis aufs
   * Ausfüllen: Gepostet sein kann der Text dann noch nicht.
   */
  private kopiertMelden(text: string): void {
    // Sicherheitsnetz: Seit dem Platzhalter-Dialog kommt hier normalerweise kein Text mit
    // Luecke an (der Dialog fuellt oder entfernt sie). Bleibt er stehen, falls ein
    // eingegebener Satz selbst "[Hier …]" enthaelt oder ein Weg am Dialog vorbei kopiert.
    if (hatLuecke(text)) {
      // Mit Platzhalter "[Hier …]" erinnert der Hinweis ans Ausfuellen (#640, R38) und bleibt laenger stehen.
      this.snackBar.open(KOPIERT_MIT_LUECKE, 'OK', { duration: 6000 });
      return;
    }
    const lauf = ++this.kopierLauf;
    const person = this.authService.getUserInfo();
    const kennung = person?.isAuthenticated ? person.userId : null;
    this.gepostetKennung = kennung;
    this.gepostetDankText = null;
    const angeboten = this.gepostetSofortAngeboten(kennung);
    this.gepostetStand = angeboten === true ? 'frage' : 'aus';
    this.kopiertHinweis = null;
    if (this.kopiertErfolgAn() || angeboten === true) {
      this.kopiertErfolgZeigen();
    } else {
      // Ein offener Kasten (diese oder eine andere Karte) geht zu: „Kopiert“ steht nur einmal.
      this.erfolgStelle.ohneKasten(this.erfolgKennung);
      this.cdr.markForCheck();
      this.kopiertHinweis = this.snackBar.open(KOPIERT, 'Schließen', { duration: KOPIERT_DAUER_MS });
    }
    if (angeboten !== null || !kennung) {
      return;
    }
    // Noch unbekannt: Die Bestätigung steht schon; bietet der Server die Frage an, kommt
    // sie in den Kasten dazu (ohne Erfolgstext löst der Kasten die Snackbar ab).
    this.usageTrackingService
      .gepostetAngeboten(kennung)
      .pipe(take(1))
      .subscribe((ja) => {
        if (!ja || lauf !== this.kopierLauf || this.gepostetGemeldet) {
          return;
        }
        if (this.kopiertErfolgAn()) {
          // Geschlossen oder eine andere Karte kopiert: nicht wieder aufdrängen.
          if (this.kopiertErfolg()) {
            this.gepostetStand = 'frage';
            this.cdr.markForCheck();
          }
          return;
        }
        // Inzwischen eine andere Karte kopiert: deren Rückmeldung nicht wegnehmen.
        if (!this.erfolgStelle.istZuletzt(this.erfolgKennung)) {
          return;
        }
        this.kopiertHinweis?.dismiss();
        this.kopiertHinweis = null;
        this.gepostetStand = 'frage';
        this.kopiertErfolgZeigen();
      });
  }

  /**
   * Ob die Frage „Gepostet?“ ohne Warten kommt: true ja, false nein, null erst den Server
   * fragen (nur angemeldet, solange `gepostetBekannt` es nicht weiß).
   */
  private gepostetSofortAngeboten(kennung: string | null): boolean | null {
    if (this.gepostetGemeldet) {
      return false;
    }
    if (!kennung) {
      return this.gepostetOhneKontoAn();
    }
    return this.usageTrackingService.gepostetBekannt(kennung);
  }

  /**
   * Den Erfolgstext (neu) einblenden: erst weg, dann wieder da, damit Screenreader ihn
   * auch beim zweiten Kopieren erneut ansagen.
   */
  private kopiertErfolgZeigen(): void {
    // Vor kopiert.emit(): danach zählt die Karte die eigene Kopie schon mit.
    this.nutzungBeimKopieren = this.nutzung;
    if (this.kopiertErfolg()) {
      this.erfolgStelle.schliessen(this.erfolgKennung);
      this.cdr.detectChanges();
    }
    this.erfolgStelle.zeigen(this.erfolgKennung);
    this.cdr.markForCheck();
  }

  kopiertErfolgSchliessen(): void {
    this.erfolgStelle.schliessen(this.erfolgKennung);
    this.cdr.markForCheck();
  }

  /**
   * „Ja, gepostet“ im Erfolgskasten: angemeldet an /users/me/gepostet (mit dem Beitrag,
   * falls der Dienst ihn fürs Wirkungs-Echo mitschickt), ohne Konto an den neutralen
   * Sammelpfad (#799). Der Knopf sperrt sich sofort, ein Doppeltipp zählt einmal, und
   * diese Karte fragt bis zum Neuladen nicht mehr. Scheitert das Melden (Netz, 5xx), steht
   * der Knopf wieder bereit: Sonst ginge die Meldung stillschweigend verloren. Doppelt
   * zählt der Server mit Konto nicht (einmal je Woche).
   */
  jaGepostet(): void {
    if (this.gepostetStand !== 'frage' || this.gepostetGemeldet) {
      return;
    }
    this.gepostetGemeldet = true;
    this.gepostetStand = 'sendet';
    this.cdr.markForCheck();
    const kennung = this.gepostetKennung;
    // null = nicht (mehr) angeboten, 'fehler' = nicht angekommen, sonst der Dank.
    const dank$: Observable<string | null | 'fehler'> = kennung
      ? this.usageTrackingService
          .gepostetMelden(kennung, this.inhaltId)
          .pipe(
            map((personen) =>
              personen === GEPOSTET_NICHT_ANGEBOTEN ? null : personen === null ? 'fehler' : gepostetDank(personen),
            ),
          )
      : this.usageTrackingService
          .gepostetOhneKontoMelden()
          .pipe(
            map((ergebnis) =>
              ergebnis === 'nicht_angeboten' ? null : ergebnis === 'gezaehlt' ? GEPOSTET_OHNE_KONTO_DANK : 'fehler',
            ),
          );
    dank$.pipe(take(1)).subscribe((dank) => {
      if (dank === 'fehler') {
        // Nicht angekommen: Knopf wieder bereit, der Hinweis lädt zum zweiten Tippen ein.
        this.gepostetGemeldet = false;
        this.gepostetStand = 'frage';
        this.gepostetDankText = GEPOSTET_NICHT_GEZAEHLT;
      } else {
        // Nicht (mehr) angeboten: Die Frage verschwindet ohne Dank.
        this.gepostetStand = dank === null ? 'aus' : 'gemeldet';
        this.gepostetDankText = dank;
      }
      this.cdr.markForCheck();
    });
  }

  get teilenSichtbar(): boolean {
    return this.teilbar && !!this.inhaltId;
  }

  /** Der unsichtbare Name des Teilen-Knopfs, mit dem Titel des Beitrags, sofern er einen hat. */
  get teilenBeschriftung(): string {
    const titel = this.titel?.trim();
    return titel ? `Beitrag teilen: „${titel}“` : 'Beitrag teilen';
  }

  /** Der unsichtbare Name des Knopfs "Ändern", mit dem Titel wie beim Teilen. */
  get aendernBeschriftung(): string {
    const titel = this.titel?.trim();
    return titel ? `Beitrag ändern: „${titel}“` : 'Beitrag ändern';
  }

  /**
   * Teilen (B7): der Text, den auch "Kopieren" nimmt, und der Link auf die Beitragsseite,
   * ueber das Teilen-Menue, wo das Geraet eines hat, sonst nur der Link in die Zwischenablage. Eine Karte
   * teilen zaehlt als Nutzung (docs/VISION.md, Teilen; GLOSSARY.md, Nutzung), ueber
   * denselben Endpunkt wie Kopieren; ein Abbruch zaehlt nicht. Die eigene Nutzung
   * verwirft der Server (api/v1/usage.py).
   */
  async teilen(): Promise<void> {
    if (this.vorschau || !this.inhaltId) {
      return;
    }
    const ergebnis = await this.teilenService.teilen({
      url: beitragsLink(this.inhaltId),
      text: this.kopierText || undefined,
      titel: this.titel?.trim() || undefined,
    });
    if (hatGeteilt(ergebnis)) {
      this.usageTrackingService.trackContentUsage(this.inhaltId, this.fassung ?? undefined);
      this.kopiert.emit();
    }
    this.cdr.markForCheck();
  }

  /** Ob „Als Bild teilen“ angeboten wird: Schalter an und ein Text, der ins Bild kann. */
  get sharepicSichtbar(): boolean {
    const text = (this.bildText || this.kopierText).trim();
    // Vorlagen mit Platzhalter „[Hier …]“ nicht: Im Bild bliebe die Klammer stehen.
    return this.sharepicAn() && !this.vorschau && !!this.inhaltId && !!text && !hatLuecke(text);
  }

  /**
   * Teilen als Bild (#756): Vorschau und Teilen im Dialog. Gezaehlt wird nichts: Das
   * Bild verlaesst das Geraet nur ueber das Teilen-Menue, der Server erfaehrt davon nichts.
   */
  alsBildTeilen(): void {
    if (!this.sharepicSichtbar) {
      return;
    }
    sharepicDialogOeffnen(this.dialog, {
      titel: this.titel?.trim() || null,
      text: (this.bildText || this.kopierText).trim(),
      aussage: this.aussage?.trim() || null,
      thema: this.thema,
      link: beitragsLink(this.inhaltId),
    });
  }

  beitragOeffnen(): void {
    if (this.vorschau || !this.inhaltId) {
      return;
    }
    this.router.navigate([ROUTES.BEITRAG, this.inhaltId]);
  }

  /**
   * "Als Vorlage nehmen" (#356): nur angemeldet und nur, wo sich das Formular
   * vorbelegen laesst (Kommentar, Hintergrundinfo). Besucher sehen den Eintrag
   * nicht: Das Formular verlangt ohnehin eine Anmeldung.
   */
  get kannAlsVorlage(): boolean {
    return !this.vorschau && kannVorlageSein(this.typ) && !!this.authService.getUserInfo()?.isAuthenticated;
  }

  alsVorlageNehmen(): void {
    if (!this.kannAlsVorlage || !kannVorlageSein(this.typ)) {
      return;
    }
    const { pfad, queryParams } = vorlageAdresse(this.typ, this.inhaltId);
    this.router.navigate([pfad], { queryParams });
  }

  openReportDialog(): void {
    if (this.vorschau) {
      return;
    }
    meldeDialogOeffnen(this.dialog, { contentId: this.inhaltId, contentType: this.typ ?? '' });
  }

  private initializeVoteState(): void {
    this.anzeigen(this.stimme ?? null);
    this.ausgang = undefined;
  }

  private get angezeigt(): Stimme {
    return this.isLiked ? 'like' : this.isDisliked ? 'dislike' : null;
  }

  private anzeigen(stimme: Stimme): void {
    this.isLiked = stimme === 'like';
    this.isDisliked = stimme === 'dislike';
  }

  private umschalten(ziel: Stimme): void {
    // Waehrend eine Anfrage laeuft, bleibt der Knopf ohne Wirkung - die Anzeige
    // aendert sich dann auch nicht, es geht also keine Stimme stumm verloren.
    if (this.vorschau || this.isVoting) {
      return;
    }
    if (this.ausgang === undefined) {
      this.ausgang = this.angezeigt;
    }
    this.anzeigen(ziel);
    this.cdr.markForCheck();
    this.abgleich.next();
  }

  private abgleichen(): void {
    const ausgang = this.ausgang;
    const ziel = this.angezeigt;
    if (ausgang === undefined) {
      return;
    }
    if (ziel === ausgang) {
      this.ausgang = undefined;
      return;
    }

    const userInfo = this.authService.getUserInfo();
    if (!userInfo || !userInfo.isAuthenticated) {
      this.zuruecknehmen(ausgang);
      this.promptLogin();
      return;
    }

    const contentId = this.inhaltId;
    this.isVoting = true;
    // Stand vor der Stimme: Er entscheidet, ob die Person unter den Ersten ist.
    const dank = ziel === null ? null : stimmDank(this.stimmenZaehlen, !this.eigeneStimmeImZaehler);

    const anfrage =
      ziel === 'like'
        ? this.votingService.setLike(contentId)
        : ziel === 'dislike'
          ? this.votingService.setDislike(contentId)
          : ausgang === 'like'
            ? this.votingService.removeLike(contentId)
            : this.votingService.removeDislike(contentId);
    const gemeldet = ziel === 'like' || (ziel === null && ausgang === 'like') ? this.likeToggled : this.dislikeToggled;

    anfrage.subscribe({
      next: () => {
        this.ausgang = undefined;
        this.isVoting = false;
        // Die Frage „Gepostet?“ steht im Erfolgskasten, nicht als Snackbar: Der Dank
        // verdrängt sie nicht mehr.
        if (dank) {
          // Sofort-Dank als Snackbar wie beim Kopieren (Entscheidung 20.11.2026): unten
          // eingeblendet, per aria-live angesagt, ohne die Karte zu verschieben. Ist dabei
          // ein Meilenstein wie „Erste 10 Bewertungen“ neu, steht er in derselben Snackbar.
          // Den Dienst erst hier holen: Karten ohne Abstimmen brauchen ihn nicht.
          this.injector.get(MeilensteinHinweisService).bestaetigen(dank.text, 'Schließen', STIMM_DANK_MS, dank.icon);
        }
        gemeldet.emit(contentId);
        this.cdr.markForCheck();
      },
      error: (error) => {
        this.logger.error('Failed to submit vote:', error);
        this.isVoting = false;
        this.zuruecknehmen(ausgang);
        this.handleVoteError(error);
      },
    });
  }

  private zuruecknehmen(ausgang: Stimme): void {
    this.anzeigen(ausgang);
    this.ausgang = undefined;
    this.cdr.markForCheck();
  }

  private promptLogin(): void {
    this.snackBar
      .open('Bitte melde dich an, um abzustimmen', 'Anmelden', { duration: 5000 })
      .onAction()
      .subscribe(() => {
        // Zurueck auf diese Seite samt Suche, dort sagt ein Satz, dass Abstimmen jetzt geht
        this.authService.login('abstimmen');
      });
  }

  private handleVoteError(error: any): void {
    if (einwilligungFehlt(error)) {
      // Den Hinweis mit Knopf zur Einwilligung zeigt der Auth-Interceptor (#489).
      return;
    }
    if (error.status === 401 || error.status === 403) {
      this.promptLogin();
    } else if (error.status === 429) {
      const retryAfter = error.headers?.get('Retry-After') || '60';
      this.snackBar.open(`Zu viele Anfragen. Bitte warte ${retryAfter} Sekunden.`, 'OK', {
        duration: 5000,
      });
    } else {
      this.snackBar.open('Fehler beim Abstimmen', 'Schließen', { duration: 3000 });
    }
  }
}
