import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';

import { FunktionenService } from '../../services/funktionen.service';
import { gestoertDialogOeffnen } from './feedback-dialog.component';
import { FEEDBACK_GESTOERT_SCHALTER } from './feedback.service';

/**
 * Der Einstieg „Was hat dich gestört?“ für die Startphase auf der Startseite: ein
 * Knopf, der das Feedback-Formular mit der Kategorie „gestoert“ öffnet (nur Freitext,
 * ohne Kontakt). Nur solange der Schalter `feedback_gestoert` an ist; der Stand kommt
 * über FunktionenService und kommt beim Umschalten ohne Neuladen an. Ab dem 31.12.2026
 * meldet der Dienst ihn aus.
 */
@Component({
  selector: 'app-gestoert-einstieg',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatIconModule],
  template: `
    @if (an()) {
      <button type="button" class="gestoert-einstieg" data-testid="gestoert-einstieg" (click)="oeffnen()">
        <mat-icon class="gestoert-icon" aria-hidden="true">sentiment_dissatisfied</mat-icon>
        <span class="gestoert-text">
          <span class="gestoert-titel">Was hat dich gestört?</span>
          <span class="gestoert-satz">Sag es uns in einem Satz, damit Gut gesagt besser wird.</span>
        </span>
        <mat-icon class="gestoert-pfeil" aria-hidden="true">arrow_forward</mat-icon>
      </button>
    }
  `,
  styles: [
    `
      :host {
        display: block;
      }

      /* Kanten wie die Mitmachen-Kacheln: 16 px Einzug, ab 752 px die mittige 720er-Spalte */
      .gestoert-einstieg {
        display: flex;
        align-items: center;
        gap: var(--spacing-md, 16px);
        box-sizing: border-box;
        width: calc(100% - 2 * max(var(--spacing-md, 16px), calc((100% - var(--lesespalte, 720px)) / 2)));
        min-height: 48px;
        margin: var(--spacing-lg, 24px) max(var(--spacing-md, 16px), calc((100% - var(--lesespalte, 720px)) / 2)) 0;
        padding: var(--spacing-md, 16px) var(--spacing-lg, 24px);
        border: 2px solid var(--kachel-rand, var(--linie-tanne));
        border-radius: 12px;
        background: var(--karte-kommentar, var(--flaeche));
        color: var(--text);
        font: inherit;
        text-align: left;
        cursor: pointer;
      }

      .gestoert-einstieg:hover,
      .gestoert-einstieg:focus-visible {
        background: color-mix(in srgb, var(--karte-kommentar, var(--flaeche)) 92%, var(--akzent-tanne, #00563a));
      }

      .gestoert-einstieg:focus-visible {
        outline: 3px solid var(--akzent-tanne);
        outline-offset: 2px;
      }

      .gestoert-text {
        display: flex;
        flex-direction: column;
        flex: 1;
        gap: 2px;
      }

      .gestoert-titel {
        font-weight: 700;
      }

      .gestoert-satz {
        font-size: 15px;
      }

      .gestoert-icon,
      .gestoert-pfeil {
        flex-shrink: 0;
      }
    `,
  ],
})
export class GestoertEinstiegComponent {
  readonly an = inject(FunktionenService).an(FEEDBACK_GESTOERT_SCHALTER);
  private readonly dialog = inject(MatDialog);

  oeffnen(): void {
    gestoertDialogOeffnen(this.dialog);
  }
}
