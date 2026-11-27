import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';

import { FunktionenService } from '../../services/funktionen.service';
import { gestoertDialogOeffnen } from './feedback-dialog.component';
import { FEEDBACK_GESTOERT_SCHALTER, gestoertOffen } from './feedback.service';

/**
 * Der Einstieg „Was hat dich gestört?“ für die Startphase auf der Startseite: ein
 * Knopf, der das Feedback-Formular mit der Kategorie „gestoert“ öffnet (nur Freitext,
 * ohne Kontakt). Nur solange der Dienst `feedback_gestoert` als an meldet (Not-Aus der
 * Basisfunktion); der Stand kommt über FunktionenService und kommt beim Umschalten ohne
 * Neuladen an. Ab dem 31.12.2026 (UTC) meldet der Dienst ihn aus, und die App prüft das
 * Datum zusätzlich selbst (gestoertOffen): Ein älterer Stand zeigt ihn dann nicht mehr.
 */
@Component({
  selector: 'app-gestoert-einstieg',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatIconModule],
  template: `
    @if (an()) {
      <button type="button" class="gestoert-einstieg" data-testid="gestoert-einstieg" (click)="oeffnen()">
        <mat-icon class="gestoert-icon" aria-hidden="true">chat_bubble_outline</mat-icon>
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

      /* Kanten wie die Mitmachen-Kacheln: 16 px Einzug, ab 752 px die mittige 720er-Spalte.
         Rand in --linie-tanne, damit sich der Knopf von der Fläche abhebt (gut sichtbarer Einstieg). */
      .gestoert-einstieg {
        display: flex;
        align-items: center;
        gap: var(--spacing-md, 16px);
        box-sizing: border-box;
        width: calc(100% - 2 * max(var(--spacing-md, 16px), calc((100% - var(--lesespalte, 720px)) / 2)));
        min-height: 48px;
        margin: var(--spacing-lg, 24px) max(var(--spacing-md, 16px), calc((100% - var(--lesespalte, 720px)) / 2)) 0;
        padding: var(--spacing-md, 16px) var(--spacing-lg, 24px);
        border: 2px solid var(--linie-tanne, var(--primaer));
        border-radius: 12px;
        background: var(--karte-kommentar, var(--flaeche));
        color: var(--text);
        font: inherit;
        text-align: left;
        cursor: pointer;
      }

      .gestoert-einstieg:hover,
      .gestoert-einstieg:focus-visible {
        background: color-mix(in srgb, var(--karte-kommentar, var(--flaeche)) 80%, var(--akzent-tanne, #00563a));
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
  private readonly gemeldet = inject(FunktionenService).an(FEEDBACK_GESTOERT_SCHALTER);
  /** Für Tests ersetzbar. */
  jetzt: () => number = () => Date.now();
  readonly an = computed(() => this.gemeldet() && gestoertOffen(this.jetzt()));
  private readonly dialog = inject(MatDialog);

  oeffnen(): void {
    gestoertDialogOeffnen(this.dialog);
  }
}
