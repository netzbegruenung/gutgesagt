import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { Subject, Subscription, timer } from 'rxjs';
import { takeUntil } from 'rxjs/operators';

import { ROUTES } from '../shared/constants/app.constants';
import { LadeWiederholung } from '../shared/lade-wiederholung';
import { KonterProbeService } from './konter-probe';

/** So oft fragt der Einstieg ohne passende Aussage erneut; so lange hält der Server seinen Vorrat. */
export const KONTER_PROBE_NACHFRAGEN_MS = 5 * 60 * 1000;

/**
 * Einstieg in die Konter-Probe auf der Startseite (#786, Basisfunktion seit dem
 * Schalter-Umbau 27.11.): nur wenn es mindestens eine passende Aussage gibt. Sonst nichts,
 * auch kein Platzhalter. Ohne Neuladen: Nach einem
 * Ladefehler fragt der Einstieg von selbst erneut (LadeWiederholung), ohne passende
 * Aussage alle KONTER_PROBE_NACHFRAGEN_MS.
 */
@Component({
  selector: 'app-konter-probe-einstieg',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MatButtonModule],
  template: `
    @if (sichtbar()) {
      <section class="konter-einstieg" aria-labelledby="konter-einstieg-titel">
        <h2 id="konter-einstieg-titel">Konter-Probe</h2>
        <div class="konter-einstieg-zeile">
          <p class="konter-einstieg-satz">
            Ein Spruch, drei echte Antworten: Welche wirkt am besten? Tipp an und sieh, wie oft jede genutzt wurde.
          </p>
          <a mat-flat-button color="primary" class="konter-einstieg-knopf" [routerLink]="ziel">Mitspielen</a>
        </div>
      </section>
    }
  `,
  styles: [
    `
      /* Kanten wie „Seit deinem letzten Besuch“: 16 px Einzug, ab 752 px die mittige 720er-Spalte */
      .konter-einstieg {
        margin: var(--spacing-xl, 32px) max(var(--spacing-md, 16px), calc((100% - var(--lesespalte, 720px)) / 2)) 0;
      }

      .konter-einstieg h2 {
        margin-bottom: var(--spacing-md, 16px);
      }

      .konter-einstieg-zeile {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--spacing-sm, 8px) var(--spacing-md, 16px);
        box-sizing: border-box;
        padding: 12px 16px;
        border: 2px solid var(--kachel-rand, var(--linie-tanne));
        border-radius: 12px;
        background: var(--karte-kommentar, var(--flaeche));
        color: var(--text);
        box-shadow: var(--elevation-2, 0 2px 4px rgba(0, 0, 0, 0.15));
      }

      .konter-einstieg-satz {
        flex: 1 1 240px;
        min-width: 0;
        margin: 0;
        font-size: 16px;
        line-height: 1.4;
        overflow-wrap: break-word;
      }

      .konter-einstieg-knopf {
        flex-shrink: 0;
      }

      @media (max-width: 599px) {
        .konter-einstieg {
          margin-top: var(--spacing-lg, 24px);
        }

        .konter-einstieg-knopf {
          flex-basis: 100%;
        }
      }
    `,
  ],
})
export class KonterProbeEinstiegComponent {
  private readonly service = inject(KonterProbeService);
  readonly sichtbar = signal(false);
  readonly ziel = ROUTES.KONTER_PROBE;

  private readonly ende$ = new Subject<void>();
  private readonly wiederholung = new LadeWiederholung(this.ende$);
  private anfrage: Subscription | null = null;
  private nachfrage: Subscription | null = null;

  constructor() {
    this.laden();
    inject(DestroyRef).onDestroy(() => {
      this.ende$.next();
      this.ende$.complete();
      this.beenden();
    });
  }

  private laden(): void {
    this.wiederholung.abbrechen();
    this.nachfrage?.unsubscribe();
    this.anfrage?.unsubscribe();
    this.anfrage = this.service.proben().subscribe({
      next: (proben) => {
        this.wiederholung.erfolg();
        this.sichtbar.set(proben.length > 0);
        // Noch keine passende Aussage: später von selbst noch einmal fragen.
        if (proben.length === 0) {
          this.spaeterNachfragen();
        }
      },
      // Beiwerk der Startseite: Ohne Antwort bleibt der Einstieg weg, bis ein neuer
      // Versuch (LadeWiederholung) klappt; 404 (älterer Suchdienst mit Schalter) wie leer.
      error: (fehler) => {
        this.sichtbar.set(false);
        if (fehler?.status === 404) {
          this.wiederholung.erfolg();
          this.spaeterNachfragen();
          return;
        }
        this.wiederholung.fehlgeschlagen(fehler, () => this.laden());
      },
    });
  }

  private spaeterNachfragen(): void {
    this.nachfrage = timer(KONTER_PROBE_NACHFRAGEN_MS)
      .pipe(takeUntil(this.ende$))
      .subscribe(() => this.laden());
  }

  private beenden(): void {
    this.wiederholung.abbrechen();
    this.nachfrage?.unsubscribe();
    this.nachfrage = null;
    this.anfrage?.unsubscribe();
    this.anfrage = null;
    this.sichtbar.set(false);
  }
}
