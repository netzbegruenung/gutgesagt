import { ChangeDetectionStrategy, ChangeDetectorRef, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

import { MetricsService } from '../services/metrics.service';
import { selbstNachladen } from '../shared/selbst-nachladen';
import { Bestandszahl, bestandszahl } from './bestandszahl';

/** Die Unterzeile ohne Zahl: vor der ersten Antwort, bei zu wenig Bestand oder nach einem Fehler. */
export const HERO_UNTERZEILE = 'Bewährte Argumente aus der Community.';

/** So oft lädt die Zahl nach; sie ist abgerundet und ändert sich selten. */
export const BESTAND_NACHLADEN_MS = 5 * 60 * 1000;

const zahl = (wert: number): string => wert.toLocaleString('de-DE');

/** „800 bewährte Antworten auf 250 Sprüche – aus der Community.“ */
export function unterzeileMitZahl(z: Bestandszahl): string {
  return `${zahl(z.antworten)} bewährte Antworten auf ${zahl(z.sprueche)} ${z.sprueche === 1 ? 'Spruch' : 'Sprüche'} – aus der Community.`;
}

/**
 * Unterzeile unter „Nie wieder sprachlos“ (Entscheidung des Maintainers vom 25.11.2026): mit der
 * Bestandszahl (bestandszahl.ts) statt einer eigenen Karte, sonst die bisherige Unterzeile.
 *
 * Unabhängig von Schaltern: Die Zahl zählt nur Inhalte, die ohnehin für alle sichtbar sind, und
 * dieselben Zahlen liefert /getMetrics schon heute anonym (öffentlich, im Server 60 s gecacht, nie
 * 401/404). Eine gescheiterte Zählung (Fehler oder 0, so meldet /getMetrics einen Ausfall) behält
 * die letzte Zahl; ohne letzte Zahl bleibt die bisherige Unterzeile.
 *
 * Die Schrift kommt von der Startseite: Das Element trägt dort die Klasse `hero-subtitle`.
 */
@Component({
  selector: 'app-hero-unterzeile',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span data-testid="hero-unterzeile">{{ bestand ? mitZahl(bestand) : ohneZahl }}</span>`,
  styles: [':host { display: block; }'],
})
export class HeroUnterzeileComponent implements OnInit {
  bestand: Bestandszahl | null = null;

  protected readonly ohneZahl = HERO_UNTERZEILE;
  protected readonly mitZahl = unterzeileMitZahl;

  private readonly metrics = inject(MetricsService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    const folgen = {
      next: (bestand: Bestandszahl | null) => {
        this.bestand = bestand;
        this.cdr.markForCheck();
      },
    };
    this.laden().subscribe(folgen);
    selbstNachladen(() => this.laden(), this.destroyRef, folgen, BESTAND_NACHLADEN_MS);
  }

  private laden(): Observable<Bestandszahl | null> {
    return this.metrics.getMetrics(true).pipe(
      map((m) =>
        m?.commentary_count && m?.statement_count ? bestandszahl(m.commentary_count, m.statement_count) : this.bestand,
      ),
      catchError(() => of(this.bestand)),
    );
  }
}
