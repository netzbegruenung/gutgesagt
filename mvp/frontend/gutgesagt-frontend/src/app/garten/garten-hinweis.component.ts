import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';

import { FunktionenService } from '../services/funktionen.service';
import { PAGE_TITLES, ROUTES } from '../shared/constants/app.constants';
import { GARTEN_SCHALTER } from './garten.service';

/**
 * Der Weg zur Gartenansicht (#783) auf der Startseite: eine Zeile mit Link, fuer alle,
 * nur solange der Schalter `gartenansicht` an ist (GET /api/v1/funktionen).
 */
@Component({
  selector: 'app-garten-hinweis',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MatIconModule],
  template: `
    @if (an()) {
      <a class="garten-hinweis" [routerLink]="ziel">
        <span class="garten-hinweis-text">
          <span class="garten-hinweis-titel">{{ titel }}</span>
          <span class="garten-hinweis-satz">Wo es schon viele Antworten gibt und wo noch welche fehlen</span>
        </span>
        <mat-icon class="garten-hinweis-pfeil" aria-hidden="true">arrow_forward</mat-icon>
      </a>
    }
  `,
  styles: [
    `
      :host {
        display: block;
      }

      /* Kanten wie die Mitmachen-Kacheln: 16 px Einzug, ab 752 px die mittige 720er-Spalte */
      .garten-hinweis {
        display: flex;
        align-items: center;
        gap: var(--spacing-md, 16px);
        min-height: 48px;
        margin: var(--spacing-lg, 24px) max(var(--spacing-md, 16px), calc((100% - var(--lesespalte, 720px)) / 2)) 0;
        padding: var(--spacing-md, 16px) var(--spacing-lg, 24px);
        border: 2px solid var(--kachel-rand, var(--linie-tanne));
        border-radius: 12px;
        background: var(--karte-kommentar, var(--flaeche));
        color: var(--text);
        text-decoration: none;
      }

      .garten-hinweis:hover,
      .garten-hinweis:focus-visible {
        background: color-mix(in srgb, var(--karte-kommentar, var(--flaeche)) 92%, var(--akzent-tanne, #00563a));
      }

      .garten-hinweis:focus-visible {
        outline: 3px solid var(--akzent-tanne);
        outline-offset: 2px;
      }

      .garten-hinweis-text {
        display: flex;
        flex-direction: column;
        flex: 1;
        gap: 2px;
      }

      .garten-hinweis-titel {
        font-weight: 700;
      }

      .garten-hinweis-satz {
        font-size: 15px;
      }

      .garten-hinweis-pfeil {
        flex-shrink: 0;
      }
    `,
  ],
})
export class GartenHinweisComponent {
  readonly an = inject(FunktionenService).an(GARTEN_SCHALTER);
  readonly ziel = ROUTES.GARTEN;
  readonly titel = PAGE_TITLES.GARTEN;
}
