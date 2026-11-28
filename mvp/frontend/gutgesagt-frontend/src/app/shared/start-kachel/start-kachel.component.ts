import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';

/**
 * Die eine Kachelart für Aktionen auf der Startseite (Einwerfen, Beitragen, Themen im
 * Überblick; Startseite 28.11.): Symbol, Titel, ein Halbsatz darunter, Pfeil. Gleiche Fläche,
 * kein Rahmen, ein Schatten und ein Radius für alle. Am Desktop stehen die Kacheln im Raster
 * der Startseite nebeneinander (.start-kacheln), dann mit dem Symbol über dem Titel; am Handy
 * untereinander, Symbol links.
 */
@Component({
  selector: 'app-start-kachel',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MatIconModule],
  template: `
    <a class="start-kachel" [routerLink]="ziel()">
      <span class="kachel-icon" aria-hidden="true">{{ icon() }}</span>
      <span class="kachel-text">
        <span class="kachel-titel">{{ titel() }}@if (mitKonto()) {&nbsp;<span class="kachel-konto">mit Konto</span>}</span>
        <!-- &ngsp;: Leerzeichen im zugänglichen Namen zwischen Titel und Halbsatz -->
        &ngsp;<span class="kachel-satz">{{ satz() }}</span>
      </span>
      <mat-icon class="kachel-pfeil" aria-hidden="true">arrow_forward</mat-icon>
    </a>
  `,
  styleUrls: ['./start-kachel.component.scss'],
})
export class StartKachelComponent {
  readonly ziel = input.required<string>();
  /** Ein Emoji wie in KETTEN_ICONS, nur zur Zierde (aria-hidden). */
  readonly icon = input.required<string>();
  readonly titel = input.required<string>();
  readonly satz = input.required<string>();
  /** Anonym: kleine Marke „mit Konto“ neben dem Titel (#644). */
  readonly mitKonto = input(false);
}
