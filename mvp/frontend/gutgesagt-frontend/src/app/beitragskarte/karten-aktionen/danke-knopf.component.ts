import { ChangeDetectionStrategy, Component, Input, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { UsageTrackingService } from '../../services/usage-tracking.service';
import { DANKE_ANGEKOMMEN, DANKE_FEHLER, DANKE_KNOPF, DANKE_SCHON_HEUTE } from '../../shared/wirkung-texte';

type Stand = 'offen' | 'sendet' | 'angekommen' | 'schon' | 'fehler';

/**
 * „Danke an die Autorin“ nach dem Kopieren (#791). Ein kleiner Knopf unter der
 * Aktionsleiste; nach dem Klick steht dort, dass das Danke angekommen ist. Die Summe sieht
 * nur die Autorin. Kein Zeitlimit, keine Punkte. Ob er überhaupt erscheint (Schalter,
 * eigener Beitrag), entscheidet die Aktionsleiste; was zählt, entscheidet der Server.
 * Gemerkt wird im Browser nichts.
 */
@Component({
  selector: 'app-danke-knopf',
  standalone: true,
  imports: [MatButtonModule, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (stand() === 'offen' || stand() === 'sendet' || stand() === 'fehler') {
      <button mat-stroked-button type="button" class="danke-knopf"
              [disabled]="stand() === 'sendet'"
              (click)="danken()">
        <mat-icon aria-hidden="true">favorite_border</mat-icon>
        <span>{{ beschriftung }}</span>
      </button>
    }
    <p class="danke-rueckmeldung" role="status" aria-live="polite">{{ rueckmeldung() }}</p>
  `,
  styles: [
    `
      :host {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--spacing-sm);
        padding: 0 var(--spacing-md) var(--spacing-md);
      }
      .danke-knopf {
        min-height: 40px;
      }
      .danke-rueckmeldung {
        margin: 0;
        font-size: 14px;
        color: var(--text-leise);
      }
      .danke-rueckmeldung:empty {
        display: none;
      }
    `,
  ],
})
export class DankeKnopfComponent {
  @Input({ required: true }) inhaltId!: string;

  readonly beschriftung = DANKE_KNOPF;
  readonly stand = signal<Stand>('offen');
  readonly rueckmeldung = signal('');

  constructor(private usageTrackingService: UsageTrackingService) {}

  danken(): void {
    if (this.stand() === 'sendet' || !this.inhaltId) {
      return;
    }
    this.stand.set('sendet');
    this.rueckmeldung.set('');
    this.usageTrackingService.dankeSagen(this.inhaltId).subscribe((ergebnis) => {
      switch (ergebnis) {
        case 'gezaehlt':
          this.stand.set('angekommen');
          this.rueckmeldung.set(DANKE_ANGEKOMMEN);
          break;
        case 'schon':
          this.stand.set('schon');
          this.rueckmeldung.set(DANKE_SCHON_HEUTE);
          break;
        case 'nicht_angeboten':
          // Ohne Einwilligung meldet sich der Auth-Interceptor; der Knopf bleibt bereit.
          this.stand.set('offen');
          break;
        default:
          this.stand.set('fehler');
          this.rueckmeldung.set(DANKE_FEHLER);
      }
    });
  }
}
