import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';

import { FunktionenService } from '../../services/funktionen.service';
import { gestoertDialogOeffnen } from './feedback-dialog.component';
import { FEEDBACK_GESTOERT_SCHALTER, gestoertOffen } from './feedback.service';

/**
 * Der Einstieg „Was hat dich gestört?“ für die Startphase auf der Startseite: eine
 * Textzeile unter den Kacheln mit einem Knopf in Link-Optik (Startseite 28.11.), der das
 * Feedback-Formular mit der Kategorie „gestoert“ öffnet (nur Freitext, ohne Kontakt).
 * Nur solange der Dienst `feedback_gestoert` als an meldet (Not-Aus der Basisfunktion); der
 * Stand kommt über FunktionenService und kommt beim Umschalten ohne Neuladen an. Ab dem
 * 31.12.2026 (UTC) meldet der Dienst ihn aus, und die App prüft das
 * Datum zusätzlich selbst (gestoertOffen): Ein älterer Stand zeigt ihn dann nicht mehr.
 */
@Component({
  selector: 'app-gestoert-einstieg',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatIconModule],
  template: `
    @if (an()) {
      <p class="gestoert-zeile">
        <!-- Name ausdrücklich: Leerraum zwischen Flex-Items fällt im Layout weg, sonst „gestört?Sag“ -->
        <button
          type="button"
          class="gestoert-einstieg"
          data-testid="gestoert-einstieg"
          aria-label="Was hat dich gestört? Sag es uns in einem Satz"
          (click)="oeffnen()"
        >
          <span class="gestoert-frage">Was hat dich gestört?</span>&ngsp;<span class="gestoert-link">Sag es uns in einem Satz</span>&ngsp;<mat-icon class="gestoert-pfeil" aria-hidden="true">arrow_forward</mat-icon>
        </button>
      </p>
    }
  `,
  styles: [
    `
      :host {
        display: block;
      }

      /* Eine Textzeile unter den Aktions-Kacheln, keine eigene Karte (Startseite 28.11.).
         Kanten wie die Kacheln: 16 px Einzug, ab 752 px die mittige 720er-Spalte. */
      .gestoert-zeile {
        margin: var(--spacing-md, 16px) max(var(--spacing-md, 16px), calc((100% - var(--lesespalte, 720px)) / 2)) 0;
      }

      /* Knopf in der Optik eines Textlinks; mindestens 24 px hoch (WCAG 2.2, 2.5.8) */
      .gestoert-einstieg {
        display: inline-flex;
        flex-wrap: wrap;
        align-items: center;
        column-gap: 0.3em;
        min-height: 24px;
        padding: 0;
        border: 0;
        background: none;
        color: var(--text);
        font: inherit;
        text-align: left;
        cursor: pointer;
      }

      .gestoert-link {
        color: var(--akzent-schrift);
        text-decoration: underline;
        text-underline-offset: 2px;
      }

      .gestoert-einstieg:hover .gestoert-link {
        text-decoration-thickness: 2px;
      }

      .gestoert-einstieg:focus-visible {
        outline: 2px solid var(--akzent-tanne);
        outline-offset: 2px;
        border-radius: var(--border-radius-small, 4px);
      }

      .gestoert-pfeil {
        width: 18px;
        height: 18px;
        font-size: 18px;
        color: var(--akzent-schrift);
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
