import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { ERSTER_SPRUCH } from './erster-spruch';

/**
 * Begrüßung nach dem ersten Anmelden über eine Einladung ohne Team (UX-Review 25.11.2026,
 * Vorschlag 5): ein Satz zum Gewinn und ein Hauptknopf zur ersten Suche, statt gleich auf
 * der leeren Startseite zu stehen. Vorschlag 6 (Begrüßung über dem Formular) ist ein
 * eigener Schritt und hiermit nicht erledigt. einladung-anmelden führt hierher; die App fragt vorher
 * wie bisher nach Nutzungsbedingungen und Einwilligung (/willkommen steht nicht unter den
 * Seiten ohne Umleitung) und kommt danach zurück. Suchen geht auch ohne Einwilligung, der
 * Text verspricht deshalb nichts zum Beitragen.
 */
@Component({
  selector: 'app-willkommen',
  standalone: true,
  imports: [RouterLink, MatButtonModule, MatCardModule],
  template: `
    <mat-card class="willkommen">
      <mat-card-header>
        <mat-card-title>
          <h2 class="titel" data-testid="willkommen-titel">Schön, dass du dabei bist</h2>
        </mat-card-title>
      </mat-card-header>
      <mat-card-content>
        <p>Dein Konto ist bereit. Hier findest du gute Antworten auf Sprüche aus der Debatte, fertig zum Posten.</p>
        <p>{{ ersterSpruch.satz }}</p>
        <a mat-raised-button color="primary" class="hauptknopf" data-testid="erster-spruch"
           [routerLink]="ersterSpruch.ziel" [fragment]="ersterSpruch.fragment">{{ ersterSpruch.knopfNeuesKonto }}</a>
      </mat-card-content>
    </mat-card>
  `,
  styles: [
    `
      .willkommen {
        max-width: 560px;
        margin: 24px auto;
      }
      .titel {
        margin: 0;
        font: inherit;
      }
      .hauptknopf {
        min-height: 48px;
        height: auto;
        white-space: normal;
        line-height: 1.3;
      }
    `,
  ],
})
export class WillkommenComponent {
  readonly ersterSpruch = ERSTER_SPRUCH;
}
