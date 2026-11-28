import { ChangeDetectionStrategy, ChangeDetectorRef, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { MatDialog } from '@angular/material/dialog';
import { RouterLink } from '@angular/router';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

import { MetricsService } from '../services/metrics.service';
import { GetMetricsResponse, ZuwachsDto } from '../services/dtos/metricsDtos';
import { ROUTES } from '../shared/constants/app.constants';
import { selbstNachladen } from '../shared/selbst-nachladen';
import { Bestandszahl, abgerundet, bestandszahl } from './bestandszahl';
import { AuthService } from '../auth/auth.service';
import { HILFE_MITMACHEN, hilfeOeffnen } from '../help-dialog/help-dialog.component';

/** Die Unterzeile ohne Zahl: vor der ersten Antwort, bei zu wenig Bestand oder nach einem Fehler. */
export const HERO_UNTERZEILE = 'Bewährte Argumente aus der Community.';

/** Der Link am Ende der Zeile, auf „Beitragen“ (Rundgang 28.11.). */
export const NAECHSTE_FRAGE = 'ist deine die nächste?';

/** So oft lädt die Zahl nach; sie ist abgerundet und ändert sich selten. */
export const BESTAND_NACHLADEN_MS = 5 * 60 * 1000;

/** Erst ab so vielen neuen Antworten in sieben Tagen nennt die Zeile den Zuwachs, nie „0 neu“. */
export const ZUWACHS_AB = 3;

const zahl = (wert: number): string => wert.toLocaleString('de-DE');

/**
 * Der Zuwachs für die Zeile: ``neu_7_tage`` ab ZUWACHS_AB, abgerundet wie der Bestand und nie
 * größer als er; sonst null, dann steht „aus der Community“.
 *
 * ``kommentare`` ist die genaue Zahl aus /getMetrics; ohne sie nur gerundet, ohne Deckel.
 */
export function zuwachsZahl(zuwachs: ZuwachsDto | null | undefined, kommentare?: number): number | null {
  const neu = zuwachs?.neu_7_tage;
  if (typeof neu !== 'number' || neu < ZUWACHS_AB) {
    return null;
  }
  const bestand = typeof kommentare === 'number' && kommentare > 0 ? kommentare : null;
  return bestand !== null ? Math.min(abgerundet(neu), abgerundet(bestand)) : abgerundet(neu);
}

/**
 * Der Teil vor dem Link, mit Gedankenstrich: „800 Antworten, 10 neu diese Woche –“ oder
 * ohne Zuwachs „800 Antworten aus der Community –“. „Diese Woche“ heißt die letzten sieben
 * Tage, wie im Deckel von „Meine Beiträge“ und in der Datenschutzerklärung.
 */
export function bestandTeil(z: Unterzeile): string {
  const antworten = `${zahl(z.bestand.kommentare)} Antworten`;
  return z.neu !== null ? `${antworten}, ${zahl(z.neu)} neu diese Woche –` : `${antworten} aus der Community –`;
}

export interface Unterzeile {
  bestand: Bestandszahl;
  /** Neue Antworten der letzten sieben Tage, abgerundet; null: zu wenige oder keine Angabe. */
  neu: number | null;
}

/**
 * Unterzeile unter „Nie wieder sprachlos“ (Rundgang 28.11., davor Entscheidungen des
 * Maintainers vom 25. und 26.11.2026): „800 Antworten, 10 neu diese Woche – ist deine die
 * nächste?“, mit weniger als drei neuen oder ohne Zuwachswert „800 Antworten aus der Community
 * – ist deine die nächste?“. Gezählt werden nur die Antworten (Kommentare); die Frage am Ende
 * führt Angemeldete auf „Beitragen“, Abgemeldete in die Hilfe, Abschnitt „Mitmachen“ (wie man
 * ein Konto bekommt; Sebastian 28.11.). Ohne Bestandszahl die bisherige Unterzeile, ohne Link.
 *
 * Die Bestandszahl hängt an keinem Schalter: Sie zählt nur Inhalte, die ohnehin für alle
 * sichtbar sind, und /getMetrics liefert sie anonym (öffentlich, im Server 60 s gecacht, nie
 * 401/404). Eine gescheiterte Zählung (Fehler oder 0, so meldet /getMetrics einen Ausfall)
 * behält die letzte Zeile.
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
      <span class="teil" data-testid="hero-unterzeile">{{ bestandText(z) }}</span>&ngsp;
      <!-- Umbruch nur hier, nach dem Gedankenstrich: beide Teile brechen selbst nicht um -->
      @if (angemeldet()) {
        <a class="teil naechste" data-testid="hero-beitragen" [routerLink]="beitragen">{{ naechsteFrage }}</a>
      } @else {
        <!-- Ohne Konto: die Hilfe „Mitmachen“ statt der Anmeldung, die /contribute verlangt -->
        <button type="button" class="teil naechste textknopf" data-testid="hero-mitmachen"
                aria-haspopup="dialog" (click)="mitmachenHilfe()">{{ naechsteFrage }}</button>
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
      .naechste {
        color: var(--akzent-tanne);
        font-weight: 600;
        text-decoration: underline;
        text-underline-offset: 3px;
      }
      .naechste:hover {
        text-decoration-thickness: 2px;
      }
      .textknopf {
        padding: 0;
        border: 0;
        background: none;
        font: inherit;
        cursor: pointer;
      }
      .textknopf:focus-visible {
        outline: 2px solid var(--akzent-tanne);
        outline-offset: 2px;
      }
    `,
  ],
})
export class HeroUnterzeileComponent implements OnInit {
  zeile: Unterzeile | null = null;

  protected readonly ohneZahl = HERO_UNTERZEILE;
  protected readonly naechsteFrage = NAECHSTE_FRAGE;
  protected readonly bestandText = bestandTeil;
  protected readonly beitragen = ROUTES.CONTRIBUTE;

  /** Angemeldet: der Link auf Beitragen; sonst der Knopf in die Hilfe. */
  protected readonly angemeldet = toSignal(
    inject(AuthService).userInfo$.pipe(map((info) => info?.isAuthenticated === true)),
    { initialValue: false },
  );
  private readonly dialog = inject(MatDialog);

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

  /** Abgemeldet: die Hilfe gleich beim Abschnitt „Mitmachen“. */
  mitmachenHilfe(): void {
    hilfeOeffnen(this.dialog, HILFE_MITMACHEN);
  }

  private laden(still: boolean): Observable<Unterzeile | null> {
    return this.metrics.getMetrics(still).pipe(
      map((m: GetMetricsResponse) => {
        if (!m?.commentary_count || !m?.statement_count) {
          return this.zeile;
        }
        const bestand = bestandszahl(m.commentary_count, m.statement_count);
        return bestand ? { bestand, neu: zuwachsZahl(m.zuwachs, m.commentary_count) } : null;
      }),
      catchError(() => of(this.zeile)),
    );
  }
}
