import {
  AfterViewInit,
  Component,
  DestroyRef,
  ElementRef,
  HostBinding,
  HostListener,
  Input,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { NavigationEnd, Router } from '@angular/router';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatDividerModule } from '@angular/material/divider';
import { MatDialog } from '@angular/material/dialog';
import { filter } from 'rxjs/operators';

import { AuthService } from '../../../auth/auth.service';
import { NavigationService } from '../../../services/navigation.service';
import { FarbschemaService } from '../../../services/farbschema.service';
import { RundgangService } from '../../../rundgang/rundgang.service';
import { RundgangId, rundgangBeschriftung } from '../../../rundgang/rundgang-daten';
import { hilfeOeffnen } from '../../../help-dialog/help-dialog.component';
import { feedbackDialogOeffnen } from '../../feedback/feedback-dialog.component';
import { OffeneMeldungenZahlComponent } from '../offene-meldungen-zahl/offene-meldungen-zahl.component';
import { MENUE_ICONS } from '../../fangkorb-texte';
import { PAGE_TITLES, ROUTES } from '../../constants/app.constants';
import { FangkorbNeuService, fangkorbZusatz } from './fangkorb-neu.service';

/** Kopf: sichtbare Links am Desktop. Leiste: feste untere Leiste am Handy. */
export type NavModus = 'kopf' | 'leiste';

export type ZielId = 'suchen' | 'einwerfen' | 'fangkorb' | 'meine';

export interface NavZiel {
  id: ZielId;
  /** Beschriftung im Kopf. */
  text: string;
  /** Beschriftung in der unteren Leiste, wo fünf Ziele nebeneinander passen müssen. */
  kurz: string;
  icon: string;
  pfad: string;
  /** Weitere Seiten, auf denen das Ziel als aktiv gilt (die Treffer gehören zum Suchen). */
  auch?: string[];
}

/**
 * Die Ziele der Hauptnavigation, Desktop und Handy in derselben Reihenfolge (WCAG 3.2.3).
 * Beitragen steht am Desktop als Knopf daneben, am Handy oben als (+).
 */
export const NAV_ZIELE: readonly NavZiel[] = [
  { id: 'suchen', text: 'Suchen', kurz: 'Suchen', icon: 'search', pfad: ROUTES.SEARCH, auch: [ROUTES.RESULT] },
  { id: 'einwerfen', text: 'Einwerfen', kurz: 'Einwerfen', icon: MENUE_ICONS.einwerfen, pfad: ROUTES.RAW_INPUT },
  { id: 'fangkorb', text: 'Fangkorb', kurz: 'Fangkorb', icon: MENUE_ICONS.fangkorb, pfad: ROUTES.RAW_INPUT_LIST },
  {
    id: 'meine',
    text: PAGE_TITLES.MEINE_BEITRAEGE,
    kurz: 'Meine',
    icon: MENUE_ICONS.meineBeitraege,
    pfad: ROUTES.MEINE_BEITRAEGE,
  },
];

/** Seiten aus „Mehr“: Steht man auf einer, ist „Mehr“ hervorgehoben. */
const MEHR_SEITEN = [ROUTES.HIER_FEHLT_EINE_ANTWORT, '/admin'];

/** Felder, für die das Handy die Bildschirmtastatur öffnet. */
const KEINE_TASTATUR = new Set(['button', 'checkbox', 'color', 'file', 'image', 'radio', 'range', 'reset', 'submit']);

export function oeffnetTastatur(ziel: EventTarget | null): boolean {
  if (!(ziel instanceof HTMLElement)) {
    return false;
  }
  if (ziel instanceof HTMLTextAreaElement || ziel.isContentEditable) {
    return true;
  }
  return ziel instanceof HTMLInputElement && !KEINE_TASTATUR.has(ziel.type);
}

/**
 * Die Bildschirmtastatur ist offen: Der sichtbare Ausschnitt (visualViewport) ist deutlich
 * niedriger als das Fenster, wie bei der Formular-Leiste (#616). Gezoomt zählt die
 * Höhe mal Zoom, damit Zoomen allein nicht als Tastatur gilt.
 */
export function tastaturSichtbar(): boolean {
  const ausschnitt = window.visualViewport;
  return !!ausschnitt && window.innerHeight - ausschnitt.height * ausschnitt.scale > 120;
}

/** Pfad ohne Query und Fragment. */
function ohneQuery(url: string): string {
  return url.split(/[?#]/)[0];
}

function liegtUnter(pfad: string, ziel: string): boolean {
  return pfad === ziel || pfad.startsWith(ziel + '/');
}

/**
 * Die Hauptnavigation (Navigation Variante 3, Sebastian 22.11.2026): Am Handy eine feste
 * untere Leiste Suchen · Einwerfen · Fangkorb · Meine · Mehr, am Desktop dieselben Ziele
 * als Links im Kopf, dazu der projizierte Knopf (Beitragen bzw. Anmelden) und „Mehr ▾“.
 * Ohne Anmeldung: Suchen · Hilfe · Mehr. Icons stehen immer mit Text.
 *
 * Die Ziele navigieren über den NavigationService, damit eine offene Destillier-Ansicht
 * ihren Satz vorher speichert; als echte Links mit href gehen Strg-Klick und Mittelklick
 * weiter in einen neuen Tab.
 */
@Component({
  selector: 'app-hauptnavigation',
  standalone: true,
  imports: [AsyncPipe, MatIconModule, MatMenuModule, MatDividerModule, OffeneMeldungenZahlComponent],
  templateUrl: './hauptnavigation.component.html',
  styleUrls: ['./hauptnavigation.component.css'],
})
export class HauptnavigationComponent implements OnInit, AfterViewInit {
  @Input() modus: NavModus = 'kopf';

  @HostBinding('class')
  get hostKlasse(): string {
    return `hauptnavigation hauptnavigation--${this.modus}` + (this.tastaturOffen() ? ' versteckt' : '');
  }

  private readonly router = inject(Router);
  private readonly navigation = inject(NavigationService);
  private readonly dialog = inject(MatDialog);
  private readonly rundgang = inject(RundgangService);
  private readonly host = inject(ElementRef<HTMLElement>);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly farbschema = inject(FarbschemaService);
  protected readonly fangkorbNeu$ = inject(FangkorbNeuService).anzahl$;
  protected readonly person = toSignal(inject(AuthService).userInfo$, { initialValue: null });

  protected readonly ziele = NAV_ZIELE;
  protected readonly hierFehltPfad = ROUTES.HIER_FEHLT_EINE_ANTWORT;
  protected readonly antwortFinden = rundgangBeschriftung('antwort-finden');
  protected readonly selbstBeitragen = rundgangBeschriftung('mitmachen');
  protected readonly selbstBeitragenOhneKonto = rundgangBeschriftung('mitmachen', false);
  protected readonly fangkorbZusatz = fangkorbZusatz;

  /** Pfad der aktuellen Seite, für aria-current und die Hervorhebung. */
  protected readonly pfad = signal(ohneQuery(this.router.url ?? ''));
  /** Am Handy: Ein Textfeld hat den Fokus, die Tastatur ist offen; die Leiste weicht. */
  protected readonly tastaturOffen = signal(false);
  private fokusImFeld = false;

  ngOnInit(): void {
    this.router.events
      .pipe(
        filter((e): e is NavigationEnd => e instanceof NavigationEnd),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((e) => this.pfad.set(ohneQuery(e.urlAfterRedirects)));
  }

  ngAfterViewInit(): void {
    if (this.modus === 'leiste') {
      this.hoeheMelden();
    }
  }

  get angemeldet(): boolean {
    return !!this.person()?.isAuthenticated;
  }

  get admin(): boolean {
    return !!this.person()?.isAdmin;
  }

  aktiv(ziel: NavZiel): boolean {
    const pfad = this.pfad();
    return [ziel.pfad, ...(ziel.auch ?? [])].some((p) => liegtUnter(pfad, p));
  }

  aufSeite(ziel: string): boolean {
    return liegtUnter(this.pfad(), ziel);
  }

  get mehrAktiv(): boolean {
    const pfad = this.pfad();
    return MEHR_SEITEN.some((p) => liegtUnter(pfad, p));
  }

  /** Normaler Klick: über den NavigationService; mit Strg, Umschalt oder Mittelklick wie ein Link. */
  gehe(event: MouseEvent, pfad: string): void {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) {
      return;
    }
    event.preventDefault();
    if (pfad === ROUTES.SEARCH) {
      void this.navigation.navigateHome();
    } else {
      void this.navigation.navigiereZu(pfad);
    }
  }

  hilfe(): void {
    hilfeOeffnen(this.dialog);
  }

  feedback(): void {
    feedbackDialogOeffnen(this.dialog);
  }

  rundgangStarten(id: RundgangId): void {
    void this.rundgang.starten(id);
  }

  /**
   * Die Leiste weicht nur, wenn ein Textfeld den Fokus hat und die Tastatur wirklich offen
   * ist: Am Tablet mit Tastatur, bei Fokus per Code ohne Tastatur oder nach dem Schließen
   * der Tastatur mit „Zurück“ (Feld bleibt fokussiert) bleibt sie stehen.
   */
  @HostListener('document:focusin', ['$event'])
  fokusRein(event: FocusEvent): void {
    this.fokusImFeld = oeffnetTastatur(event.target);
    this.tastaturPruefen();
  }

  @HostListener('document:focusout')
  fokusRaus(): void {
    this.fokusImFeld = false;
    this.tastaturPruefen();
  }

  tastaturPruefen(): void {
    if (this.modus !== 'leiste') {
      return;
    }
    this.tastaturOffen.set(this.fokusImFeld && tastaturSichtbar());
    this.sichtbarMelden();
  }

  /** Was die Leiste unten gerade belegt (0, solange sie der Tastatur weicht), für Formular-Leiste und FAB. */
  private sichtbarMelden(): void {
    const hoehe = this.tastaturOffen() ? 0 : this.host.nativeElement.offsetHeight;
    document.documentElement.style.setProperty('--unterleiste-sichtbar', `${hoehe}px`);
  }

  /**
   * Die Höhe der Leiste (mit Safe Area und bei großer Schrift) als --unterleiste-hoehe am
   * Dokument: Danach richten sich der Platz unter dem Inhalt und scroll-padding-bottom,
   * damit die Leiste weder Inhalt noch Fokus verdeckt (WCAG 2.4.11).
   */
  private hoeheMelden(): void {
    const wurzel = document.documentElement;
    const setzen = () => {
      wurzel.style.setProperty('--unterleiste-hoehe', `${this.host.nativeElement.offsetHeight}px`);
      this.sichtbarMelden();
    };
    setzen();
    const ausschnitt = window.visualViewport;
    const beiGroesse = () => this.tastaturPruefen();
    ausschnitt?.addEventListener('resize', beiGroesse);
    const beobachter = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(setzen);
    beobachter?.observe(this.host.nativeElement);
    this.destroyRef.onDestroy(() => {
      beobachter?.disconnect();
      ausschnitt?.removeEventListener('resize', beiGroesse);
      wurzel.style.removeProperty('--unterleiste-hoehe');
      wurzel.style.removeProperty('--unterleiste-sichtbar');
    });
  }
}
