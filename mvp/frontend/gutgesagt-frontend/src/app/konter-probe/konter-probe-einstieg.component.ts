import { ChangeDetectionStrategy, Component, DestroyRef, effect, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { Subscription } from 'rxjs';

import { FunktionenService } from '../services/funktionen.service';
import { ROUTES } from '../shared/constants/app.constants';
import { KONTER_PROBE_SCHALTER, KonterProbeService } from './konter-probe';

/**
 * Einstieg in die Konter-Probe auf der Startseite (#786): nur wenn der Schalter an ist
 * und es mindestens eine passende Aussage gibt. Sonst nichts, auch kein Platzhalter.
 * Schaltet ein Admin um, kommt das mit dem nächsten Stand der Funktionen an
 * (FunktionenService), ohne dass jemand neu lädt.
 */
@Component({
  selector: 'app-konter-probe-einstieg',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MatButtonModule],
  template: `
    @if (an() && sichtbar()) {
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
  readonly an = inject(FunktionenService).an(KONTER_PROBE_SCHALTER);
  readonly sichtbar = signal(false);
  readonly ziel = ROUTES.KONTER_PROBE;

  private anfrage: Subscription | null = null;

  constructor() {
    // Erst fragen, wenn der Schalter an ist: Aus kostet keinen Abruf.
    effect(() => {
      if (this.an() && !this.anfrage) {
        this.anfrage = this.service.proben().subscribe({
          next: (proben) => this.sichtbar.set(proben.length > 0),
          // Beiwerk der Startseite: Ohne Antwort bleibt der Einstieg weg.
          error: () => this.sichtbar.set(false),
        });
      }
    });
    inject(DestroyRef).onDestroy(() => this.anfrage?.unsubscribe());
  }
}
