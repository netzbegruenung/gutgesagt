import {
  AfterViewChecked,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  HostListener,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  ViewChild,
  inject,
  ChangeDetectorRef,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { ROUTES } from '../../shared/constants/app.constants';
import { KOPIERT } from '../../shared/vorlagen-luecke';
import { AndereTonlage, KOPIERT_ERFOLG, KOPIERT_ERFOLG_ZEICHEN, nutzungSatz, tonlagenHinweis } from './kopiert-erfolg';
import {
  GEPOSTET_FRAGE,
  GEPOSTET_GEMELDET,
  GEPOSTET_RUECKKEHR,
  GEPOSTET_RUECKKEHR_OHNE_KONTO,
  JA_GEPOSTET,
} from './gepostet-texte';

/**
 * So lange nach dem Kopieren gilt das Zurückkommen erst als Rückkehr: Ein kurzer Blick in
 * einen anderen Tab soll den Kasten nicht flackern lassen.
 */
export const RUECKKEHR_AB_MS = 3000;
/** So lange leuchtet „Ja, gepostet“ bei der Rückkehr auf (die Animation dauert 1,6 s). */
export const RUECKKEHR_LEUCHTEN_MS = 2000;

/**
 * Wo die Frage „Gepostet?“ im Kasten steht: ``aus`` ohne Frage, ``frage`` mit Knopf,
 * ``sendet`` nach dem Tippen bis zur Antwort, ``gemeldet`` mit Dank.
 */
export type GepostetStand = 'aus' | 'frage' | 'sendet' | 'gemeldet';

/**
 * Der Erfolgstext unter der Aktionsleiste nach dem Kopieren (#785). Die Region steht in
 * jeder vollen Karte da (role="status"), auch mit Schalter aus, weil dann die Frage
 * „Gepostet?“ den Kasten braucht; so sagen Screenreader den Text an, sobald er erscheint;
 * er blockiert nichts und bleibt ohne Frist stehen, bis die Person ihn schliesst, damit
 * der Link nicht unter der Hand verschwindet.
 *
 * Hier steht auch „Ja, gepostet“ (#643, #799), statt als Snackbar für 8 s: Wer in die
 * andere App wechselt, postet und zurückkommt, findet den Knopf noch. Nach dem Tippen
 * bleibt der Knopf stehen, nur als ``aria-disabled`` mit „Gepostet“, damit der
 * Tastaturfokus nicht verloren geht (wie „Danke an die Autorin“); der Dank kommt in einer
 * eigenen Status-Zeile. Ohne Schalter `kopiert_erfolg` zeigt der Kasten statt des
 * Erfolgstexts nur die gewohnte Bestätigung, damit die Frage trotzdem bleiben kann.
 *
 * Rückkehr-Moment (Entscheidung 25.11.): Wird die Seite frühestens 3 s nach dem Kopieren
 * wieder sichtbar oder bekommt den Fokus zurück und steht die Frage noch offen, leuchtet
 * der Knopf einmal kurz auf und die Frage wird zu einem kurzen Hinweis, was das Tippen
 * bringt; einmal je Kopieren, ohne Speicher und ohne Popup. Mit „Bewegung reduzieren“
 * wechselt nur der Text. Die Region sagt dabei nur den geänderten Satz an
 * (``aria-atomic="false"``), nicht den ganzen Kasten noch einmal.
 */
@Component({
  selector: 'app-kopiert-erfolg',
  standalone: true,
  imports: [CommonModule, RouterLink, MatButtonModule, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="kopiert-erfolg-rahmen" [class.sichtbar]="sichtbar">
      <div class="kopiert-erfolg-inhalt">
        <div class="kopiert-erfolg-region" role="status" aria-atomic="false">
          <div class="kopiert-erfolg" *ngIf="sichtbar">
            <p class="erfolg-satz" *ngIf="erfolgstext; else schlicht">
              {{ erfolg }} <span aria-hidden="true">{{ zeichen }}</span>
              <ng-container *ngIf="nutzungText as n">&ngsp;<span class="erfolg-nutzung">{{ n }}</span></ng-container>
            </p>
            <ng-template #schlicht><p class="erfolg-satz">{{ kopiertSchlicht }}</p></ng-template>
            <p class="erfolg-tonlage" *ngIf="erfolgstext && tonlage as t">
              {{ t.frage }}&ngsp;<a class="erfolg-tonlage-link" [routerLink]="[beitragPfad, andereTonlage!.id]">{{ t.link }}</a>
            </p>
            <p class="erfolg-gepostet-frage" *ngIf="gepostet === 'frage' || gepostet === 'sendet'">{{ frageText }}</p>
          </div>
        </div>
        <!-- Ausserhalb der Status-Region: Knopf und Dank sollen beim Erscheinen nicht mit angesagt werden -->
        <div class="erfolg-gepostet" *ngIf="sichtbar && gepostet !== 'aus'">
          <button #jaKnopf mat-flat-button type="button" class="ja-gepostet"
                  [attr.aria-disabled]="gepostet === 'frage' ? null : 'true'"
                  [class.ja-gepostet--fertig]="gepostet === 'gemeldet'"
                  [class.ja-gepostet--rueckkehr]="leuchtet"
                  (click)="gepostetTippen()">
            <mat-icon aria-hidden="true" *ngIf="gepostet === 'gemeldet'">check</mat-icon>
            <span>{{ gepostet === 'gemeldet' ? gemeldet : jaGepostetWort }}</span>
          </button>
        </div>
        <!-- Dank, oder nach einem Fehler der Hinweis, es noch einmal zu versuchen -->
        <p class="erfolg-gepostet-dank" *ngIf="sichtbar" role="status">{{ dankZeile }}</p>
      </div>
      <!-- Ausserhalb der Status-Region: Der Knopf soll nicht mit angesagt werden -->
      <button #schliessenKnopf *ngIf="sichtbar" mat-icon-button type="button" class="erfolg-schliessen" aria-label="Hinweis schließen"
              (click)="schliessen.emit()">
        <mat-icon aria-hidden="true">close</mat-icon>
      </button>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .kopiert-erfolg-rahmen.sichtbar {
        display: flex;
        align-items: flex-start;
        gap: var(--spacing-sm);
        margin: 0 var(--spacing-md) var(--spacing-md);
        padding: var(--spacing-sm) var(--spacing-xs) var(--spacing-sm) var(--spacing-md);
        background: var(--primaer-tint);
        border-left: 4px solid var(--primaer-text);
        border-radius: var(--border-radius-small);
        color: var(--text);
      }
      .kopiert-erfolg-inhalt {
        flex: 1;
        min-width: 0;
      }
      .kopiert-erfolg-region {
        padding-top: var(--spacing-xs);
      }
      .kopiert-erfolg p {
        margin: 0;
        font-size: 15px;
        line-height: 1.45;
        overflow-wrap: anywhere;
      }
      .erfolg-satz {
        font-weight: 600;
      }
      .erfolg-nutzung {
        font-weight: 400;
      }
      .erfolg-tonlage {
        margin-top: var(--spacing-xs) !important;
      }
      .erfolg-tonlage-link {
        color: var(--primaer-text);
        text-decoration: underline;
        text-underline-offset: 2px;
        font-weight: 600;
      }
      .erfolg-gepostet-frage {
        margin-top: var(--spacing-sm) !important;
      }
      .erfolg-gepostet {
        margin-top: var(--spacing-sm);
      }
      /* Voller Knopf in der Markenfarbe wie „Kopieren“, auch im Dunkelmodus nicht aufgehellt */
      .ja-gepostet {
        min-height: 40px;
        background-color: var(--primaer);
        color: #fff;
      }
      .ja-gepostet--fertig {
        background-color: transparent;
        color: var(--text);
        box-shadow: inset 0 0 0 1px var(--text-leise);
      }
      .ja-gepostet[aria-disabled='true'] {
        cursor: default;
      }
      /* Rückkehr-Moment: einmal sanft aufleuchten, ohne den Knopf zu verschieben */
      .ja-gepostet--rueckkehr {
        animation: ja-gepostet-leuchten 1.6s ease-in-out 1;
      }
      @keyframes ja-gepostet-leuchten {
        0%,
        100% {
          box-shadow: 0 0 0 0 transparent;
        }
        40% {
          box-shadow: 0 0 0 6px var(--primaer-tint), 0 0 0 8px var(--primaer);
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .ja-gepostet--rueckkehr {
          animation: none;
        }
      }
      .erfolg-gepostet-dank {
        margin: var(--spacing-xs) 0 0;
        font-size: 15px;
        line-height: 1.45;
        overflow-wrap: anywhere;
      }
      .erfolg-gepostet-dank:empty {
        display: none;
      }
      .erfolg-schliessen {
        flex: none;
        width: 40px;
        height: 40px;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--text-leise);
      }
    `,
  ],
})
export class KopiertErfolgComponent implements OnChanges, AfterViewChecked, OnDestroy {
  @Input() sichtbar = false;
  /** Die Nutzung, wie die Karte sie gerade zeigt; null = unbekannt. */
  @Input() nutzung: number | null = null;
  /** Eine Antwort zur selben Aussage in anderem Stil; null = kein Hinweis. */
  @Input() andereTonlage: AndereTonlage | null = null;
  /** Aus mit Schalter `kopiert_erfolg` aus: dann nur „Kopiert – …“ ohne Pflänzchen, Nutzung und Tonlage. */
  @Input() erfolgstext = true;
  /** Die Frage „Gepostet?“; ``aus`` ohne (Schalter aus, nicht angeboten, schon gemeldet). */
  @Input() gepostet: GepostetStand = 'aus';
  /** Der Dank nach „Ja, gepostet“, sobald der Server geantwortet hat. */
  @Input() gepostetDank: string | null = null;
  /** Zählt die Kopiervorgänge der Karte; jeder neue startet den Rückkehr-Moment neu. */
  @Input() kopierLauf = 0;
  /** Ohne Konto (#799): der Rückkehr-Hinweis ohne „zählt mit“. */
  @Input() ohneKonto = false;
  @Output() schliessen = new EventEmitter<void>();
  /** „Ja, gepostet“ getippt; melden und danken macht die Aktionsleiste. */
  @Output() jaGepostet = new EventEmitter<void>();

  readonly kopiertSchlicht = KOPIERT;
  readonly jaGepostetWort = JA_GEPOSTET;
  readonly gemeldet = GEPOSTET_GEMELDET;
  readonly erfolg = KOPIERT_ERFOLG;
  readonly zeichen = KOPIERT_ERFOLG_ZEICHEN;
  readonly beitragPfad = ROUTES.BEITRAG;

  /** Seit wann der laufende Kopiervorgang steht (Date.now()). */
  private kopiertUm = 0;
  /** Der Rückkehr-Moment kam für diesen Kopiervorgang schon. */
  private rueckkehrGezeigt = false;
  /** Der Knopf leuchtet gerade auf. */
  leuchtet = false;
  private leuchtenFrist: ReturnType<typeof setTimeout> | null = null;
  private readonly cdr = inject(ChangeDetectorRef);

  /** Die Frage, nach der Rückkehr einmalig der Hinweis, was das Tippen bringt. */
  get frageText(): string {
    if (!this.rueckkehrGezeigt) {
      return GEPOSTET_FRAGE;
    }
    return this.ohneKonto ? GEPOSTET_RUECKKEHR_OHNE_KONTO : GEPOSTET_RUECKKEHR;
  }

  @HostListener('document:visibilitychange')
  sichtbarGeworden(): void {
    if (document.visibilityState === 'visible') {
      this.zurueckgekommen();
    }
  }

  @HostListener('window:focus')
  fokusZurueck(): void {
    this.zurueckgekommen();
  }

  /**
   * Zurück auf der Seite: nur einmal je Kopieren, nur mit offener Frage im offenen Kasten
   * und frühestens nach RUECKKEHR_AB_MS. Zu früh zählt nicht als verbraucht.
   */
  private zurueckgekommen(): void {
    if (this.rueckkehrGezeigt || !this.sichtbar || this.gepostet !== 'frage' || !this.kopierLauf) {
      return;
    }
    if (Date.now() - this.kopiertUm < RUECKKEHR_AB_MS) {
      return;
    }
    this.rueckkehrGezeigt = true;
    if (!bewegungReduziert()) {
      this.leuchtet = true;
      this.leuchtenFrist = setTimeout(() => {
        this.leuchtenFrist = null;
        this.leuchtet = false;
        this.cdr.markForCheck();
      }, RUECKKEHR_LEUCHTEN_MS);
    }
    this.cdr.markForCheck();
  }

  private leuchtenBeenden(): void {
    if (this.leuchtenFrist !== null) {
      clearTimeout(this.leuchtenFrist);
      this.leuchtenFrist = null;
    }
    this.leuchtet = false;
  }

  get nutzungText(): string | null {
    return nutzungSatz(this.nutzung);
  }

  get tonlage(): { frage: string; link: string } | null {
    return tonlagenHinweis(this.andereTonlage);
  }

  @ViewChild('jaKnopf', { read: ElementRef }) private jaKnopf?: ElementRef<HTMLButtonElement>;
  @ViewChild('schliessenKnopf', { read: ElementRef }) private schliessenKnopf?: ElementRef<HTMLButtonElement>;
  /** Der Fokus lag auf „Ja, gepostet“, als der Knopf verschwand (nicht mehr angeboten). */
  private fokusUmsetzen = false;

  /** Der Dank, nach einem Fehler (Knopf wieder bereit) der Hinweis darauf; leer beim Senden. */
  get dankZeile(): string {
    return this.gepostet === 'gemeldet' || this.gepostet === 'frage' ? (this.gepostetDank ?? '') : '';
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['kopierLauf']) {
      this.kopiertUm = Date.now();
      this.rueckkehrGezeigt = false;
      this.leuchtenBeenden();
    }
    // Verschwindet der Knopf unter dem Fokus (Server: nicht mehr angeboten), fiele der
    // Fokus auf <body> (WCAG 2.4.3); er geht stattdessen auf „Hinweis schließen“.
    const stand = changes['gepostet'];
    if (stand && !stand.firstChange && stand.currentValue === 'aus' && this.jaKnopf) {
      this.fokusUmsetzen = document.activeElement === this.jaKnopf.nativeElement;
    }
  }

  ngOnDestroy(): void {
    this.leuchtenBeenden();
  }

  ngAfterViewChecked(): void {
    if (this.fokusUmsetzen) {
      this.fokusUmsetzen = false;
      this.schliessenKnopf?.nativeElement.focus();
    }
  }

  gepostetTippen(): void {
    if (this.gepostet === 'frage') {
      this.jaGepostet.emit();
    }
  }
}

/** „Bewegung reduzieren“ im System: dann nur der Textwechsel, kein Aufleuchten. */
function bewegungReduziert(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}
