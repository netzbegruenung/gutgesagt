import { ChangeDetectionStrategy, ChangeDetectorRef, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

import { MetricsService } from '../services/metrics.service';
import { GetMetricsResponse, ZuwachsDto } from '../services/dtos/metricsDtos';
import { ROUTES } from '../shared/constants/app.constants';
import { selbstNachladen } from '../shared/selbst-nachladen';
import { Bestandszahl, bestandszahl } from './bestandszahl';

/** Die Unterzeile ohne Zahl: vor der ersten Antwort, bei zu wenig Bestand oder nach einem Fehler. */
export const HERO_UNTERZEILE = 'Bewährte Argumente aus der Community.';

/** Zusatz hinter der Bestandszahl, wenn es nichts Neues zu nennen gibt. */
export const OHNE_ZUWACHS = 'aus der Community.';

/** So oft lädt die Zahl nach; sie ist abgerundet und ändert sich selten. */
export const BESTAND_NACHLADEN_MS = 5 * 60 * 1000;

/** Ziel des Zusatzes: „Frisch aus der Community“ auf der Startseite. */
export const FRISCH_ANKER = 'recent-content';

/** So weit zurück nennt die Unterzeile den Tag; älter heißt „aus der Community“. */
const TAGE_HOECHSTENS = 7;

const zahl = (wert: number): string => wert.toLocaleString('de-DE');

/** „800 Antworten auf 250 Sprüche –“: der Teil vor dem Zusatz, mit Gedankenstrich. */
export function bestandTeil(z: Bestandszahl): string {
  return `${zahl(z.kommentare)} Antworten auf ${zahl(z.aussagen)} ${z.aussagen === 1 ? 'Spruch' : 'Sprüche'} –`;
}

/** Heutiger Kalendertag in deutscher Zeit als JJJJ-MM-TT (wie der Server ihn meldet). */
export function heuteInDeutschland(jetzt: Date): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Berlin' }).format(jetzt);
}

function tageszahl(tag: string): number | null {
  const teile = /^(\d{4})-(\d{2})-(\d{2})$/.exec(tag);
  return teile ? Date.UTC(+teile[1], +teile[2] - 1, +teile[3]) / 86_400_000 : null;
}

/**
 * Der Zusatz mit Verweis auf „Frisch aus der Community“: ab 3 neuen die genaue Zahl, darunter
 * der Tag des letzten Kommentars (heute, gestern, am TT.MM.), nie eine Uhrzeit. null: nichts
 * Neues in 7 Tagen, keine Angabe oder ein unlesbarer Tag; dann steht „aus der Community.“.
 */
export function zuwachsText(zuwachs: ZuwachsDto | null | undefined, jetzt: Date): string | null {
  if (!zuwachs) {
    return null;
  }
  if (typeof zuwachs.neu_7_tage === 'number' && zuwachs.neu_7_tage >= 3) {
    return `${zahl(zuwachs.neu_7_tage)} neu in 7 Tagen`;
  }
  const tag = zuwachs.zuletzt_ergaenzt ? tageszahl(zuwachs.zuletzt_ergaenzt) : null;
  const heute = tageszahl(heuteInDeutschland(jetzt));
  if (tag === null || heute === null) {
    return null;
  }
  const vor = heute - tag;
  if (vor > TAGE_HOECHSTENS) {
    return null;
  }
  if (vor <= 0) {
    return 'zuletzt ergänzt heute';
  }
  if (vor === 1) {
    return 'zuletzt ergänzt gestern';
  }
  const [, monat, tagImMonat] = zuwachs.zuletzt_ergaenzt!.split('-');
  return `zuletzt ergänzt am ${+tagImMonat}.${+monat}.`;
}

export interface Unterzeile {
  bestand: Bestandszahl;
  /** Zuwachs bzw. „zuletzt ergänzt …“; null: „aus der Community.“ */
  zuwachs: string | null;
}

/**
 * Unterzeile unter „Nie wieder sprachlos“ (Entscheidungen des Maintainers vom 25. und
 * 26.11.2026): Bestand und Zuwachs, ehrlich und nie „0 neu“, etwa „800 Antworten auf 250
 * Sprüche – 12 neu in 7 Tagen 🌱“. Ohne Bestandszahl die bisherige Unterzeile.
 *
 * Die Bestandszahl hängt an keinem Schalter: Sie zählt nur Inhalte, die ohnehin für alle
 * sichtbar sind, und /getMetrics liefert sie schon heute anonym (öffentlich, im Server 60 s
 * gecacht, nie 401/404). Den Zuwachs liefert der Server nur mit dem Schalter
 * `bestandszahl_zuwachs`; ohne steht „aus der Community.“. Eine gescheiterte Zählung (Fehler
 * oder 0, so meldet /getMetrics einen Ausfall) behält die letzte Zeile.
 *
 * Die Schrift kommt von der Startseite: Das Element trägt dort die Klasse `hero-subtitle`;
 * mobil hält sie zwei Zeilen frei, damit das Suchfeld nicht springt, wenn die Zahl kommt.
 * Umgebrochen wird nur nach dem Gedankenstrich.
 */
@Component({
  selector: 'app-hero-unterzeile',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (zeile; as z) {
      <span class="teil" data-testid="hero-unterzeile">{{ bestandText(z.bestand) }}</span>&ngsp;
      <!-- Umbruch nur hier, nach dem Gedankenstrich: beide Teile brechen selbst nicht um -->
      @if (z.zuwachs) {
        <a
          class="teil zuwachs"
          data-testid="hero-zuwachs"
          [routerLink]="startseite"
          [fragment]="anker"
          (click)="springen($event)"
          >{{ z.zuwachs }}<span class="visually-hidden">, zu „Frisch aus der Community“</span
          ><span aria-hidden="true"> 🌱</span></a
        >
      } @else {
        <span class="teil">{{ ohneZuwachs }}</span>
      }
    } @else {
      <span data-testid="hero-unterzeile">{{ ohneZahl }}</span>
    }
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .teil {
        white-space: nowrap;
      }
      .zuwachs {
        color: var(--akzent-tanne);
        font-weight: 600;
        text-decoration: underline;
        text-underline-offset: 3px;
      }
      .zuwachs:hover {
        text-decoration-thickness: 2px;
      }
    `,
  ],
})
export class HeroUnterzeileComponent implements OnInit {
  zeile: Unterzeile | null = null;

  protected readonly ohneZahl = HERO_UNTERZEILE;
  protected readonly ohneZuwachs = OHNE_ZUWACHS;
  protected readonly bestandText = bestandTeil;
  protected readonly startseite = ROUTES.SEARCH;
  protected readonly anker = FRISCH_ANKER;

  private readonly metrics = inject(MetricsService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    const folgen = {
      next: (zeile: Unterzeile | null) => {
        this.zeile = zeile;
        this.cdr.markForCheck();
      },
    };
    // Erster Abruf über den Frontend-Cache: Bei der Rückkehr auf die Startseite steht die Zahl
    // sofort da, statt erst die Zeile ohne Zahl zu zeigen. Das Nachladen fragt still und frisch.
    this.laden(false).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(folgen);
    selbstNachladen(() => this.laden(true), this.destroyRef, folgen, BESTAND_NACHLADEN_MS);
  }

  /**
   * Auf der Startseite direkt hinunter zu „Frisch aus der Community“, Fokus auf die Überschrift
   * (WCAG 2.4.3); mit Strg/Cmd/Umschalt oder ohne Ziel macht der Link, was Links tun.
   */
  springen(ereignis: MouseEvent): void {
    if (ereignis.ctrlKey || ereignis.metaKey || ereignis.shiftKey || ereignis.button !== 0) {
      return;
    }
    const ziel = document.getElementById(FRISCH_ANKER);
    if (!ziel) {
      return;
    }
    ereignis.preventDefault();
    const ruhig = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    ziel.scrollIntoView({ behavior: ruhig ? 'auto' : 'smooth', block: 'start' });
    ziel.querySelector<HTMLElement>('h2')?.focus({ preventScroll: true });
  }

  private laden(still: boolean): Observable<Unterzeile | null> {
    return this.metrics.getMetrics(still).pipe(
      map((m: GetMetricsResponse) => {
        if (!m?.commentary_count || !m?.statement_count) {
          return this.zeile;
        }
        const bestand = bestandszahl(m.commentary_count, m.statement_count);
        return bestand ? { bestand, zuwachs: zuwachsText(m.zuwachs, new Date()) } : null;
      }),
      catchError(() => of(this.zeile)),
    );
  }
}
