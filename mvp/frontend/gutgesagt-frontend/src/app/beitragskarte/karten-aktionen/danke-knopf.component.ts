import { ChangeDetectionStrategy, Component, Input, computed, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { UsageTrackingService } from '../../services/usage-tracking.service';
import { DANKE_ANGEKOMMEN, DANKE_FEHLER, DANKE_GESAGT, DANKE_KNOPF, DANKE_NICHT_GEZAEHLT } from '../../shared/wirkung-texte';

type Stand = 'offen' | 'sendet' | 'angekommen' | 'nicht_gezaehlt' | 'fehler';

/**
 * „Danke an die Autorin“ nach dem Kopieren (#791). Ein kleiner Knopf unter der
 * Aktionsleiste; nach dem Klick steht dort, dass das Danke angekommen ist. Die Summe sieht
 * nur die Autorin. Kein Zeitlimit, keine Punkte. Ob er überhaupt erscheint (Schalter,
 * eigener Beitrag), entscheidet die Aktionsleiste; was zählt, entscheidet der Server.
 * Gemerkt wird im Browser nichts.
 *
 * Der Knopf bleibt nach dem Klick stehen, nur als ``aria-disabled`` mit neuer Beschriftung:
 * Verschwaende er, fiele der Tastaturfokus auf den Seitenanfang (WCAG 2.4.3). Deshalb
 * auch beim Senden kein ``disabled``, das den Fokus ebenfalls nimmt.
 */
@Component({
  selector: 'app-danke-knopf',
  standalone: true,
  imports: [MatButtonModule, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button mat-stroked-button type="button" class="danke-knopf"
            [attr.aria-disabled]="gesperrt() ? 'true' : null"
            [class.danke-knopf--fertig]="fertig()"
            (click)="danken()">
      <mat-icon aria-hidden="true">{{ fertig() ? 'favorite' : 'favorite_border' }}</mat-icon>
      <span>{{ fertig() ? gesagt : beschriftung }}</span>
    </button>
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
      .danke-knopf[aria-disabled='true'] {
        cursor: default;
      }
      .danke-knopf--fertig {
        color: var(--text-leise);
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
  readonly gesagt = DANKE_GESAGT;
  readonly stand = signal<Stand>('offen');
  readonly rueckmeldung = signal('');
  /** Nach der Antwort des Servers: der Knopf sagt „Danke gesagt“ und tut nichts mehr. */
  readonly fertig = computed(() => this.stand() === 'angekommen' || this.stand() === 'nicht_gezaehlt');
  readonly gesperrt = computed(() => this.fertig() || this.stand() === 'sendet');

  constructor(private usageTrackingService: UsageTrackingService) {}

  danken(): void {
    if (this.gesperrt() || !this.inhaltId) {
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
        case 'nicht_gezaehlt':
          this.stand.set('nicht_gezaehlt');
          this.rueckmeldung.set(DANKE_NICHT_GEZAEHLT);
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
