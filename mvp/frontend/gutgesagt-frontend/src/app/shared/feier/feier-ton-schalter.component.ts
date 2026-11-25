import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';

import { FeierTonService } from './feier-ton.service';

/** Beschriftung des Umschalters, auch für Tests. */
export const TON_BEI_ERFOLGEN = 'Ton bei Erfolgen';

/**
 * Der Umschalter „Ton bei Erfolgen“ an einem Feier-Moment (#787). Standard aus; beim
 * Einschalten spielt der Ton einmal zur Probe.
 */
@Component({
  selector: 'app-feier-ton-schalter',
  standalone: true,
  imports: [MatSlideToggleModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <mat-slide-toggle class="feier-ton-schalter" [checked]="ton.an()" (change)="ton.setzen($event.checked)">
      {{ beschriftung }}
    </mat-slide-toggle>
  `,
  styles: [
    `
      :host {
        display: inline-block;
      }
    `,
  ],
})
export class FeierTonSchalterComponent {
  readonly ton = inject(FeierTonService);
  readonly beschriftung = TON_BEI_ERFOLGEN;
}
