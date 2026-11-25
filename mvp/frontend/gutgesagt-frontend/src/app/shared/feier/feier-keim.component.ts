import { ChangeDetectionStrategy, Component, InjectionToken, inject } from '@angular/core';

/** Ob Bewegung erlaubt ist: nein, wenn das Gerät „Bewegung reduzieren“ verlangt. */
export const FEIER_BEWEGUNG = new InjectionToken<boolean>('FEIER_BEWEGUNG', {
  providedIn: 'root',
  factory: () =>
    !(typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false),
});

/**
 * Das Bild eines Feier-Moments (#787, „Wir begrünen das Netz“): Die Lücke im Boden schließt
 * sich, ein Keim wächst aus ihr und öffnet zwei Blätter, kleine Blätter fliegen auf. Einmal,
 * in 1,4 s, ohne Schleife und ohne Blinken. Mit „Bewegung reduzieren“ steht gleich das
 * Endbild (geschlossener Boden, Keim mit zwei Blättern). Reine Zierde, für Screenreader
 * unsichtbar; die Aussage trägt die Überschrift daneben. Eigene Zeichnung, Farben aus den
 * Tokens (Tanne, Klee, Grashalm).
 */
@Component({
  selector: 'app-feier-keim',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { 'aria-hidden': 'true', '[class.bewegt]': 'bewegt' },
  template: `
    <svg viewBox="0 0 120 96" width="140" height="112" focusable="false">
      <path class="boden boden-links" d="M28 82 H60" />
      <path class="boden boden-rechts" d="M60 82 H92" />
      <path class="stiel" d="M60 82 C58 70 62 60 60 50" pathLength="1" />
      <path class="blatt blatt-links" d="M60 52 C49 52 40 45 37 34 C49 33 58 41 60 52 Z" />
      <path class="blatt blatt-rechts" d="M60 50 C71 49 81 41 84 29 C71 29 62 37 60 50 Z" />
      <g class="flug">
        @for (n of fluege; track n) {
          <ellipse [class]="'flugblatt flugblatt-' + n" cx="60" cy="44" rx="6" ry="2.8" />
        }
      </g>
    </svg>
  `,
  styleUrls: ['./feier-keim.component.css'],
})
export class FeierKeimComponent {
  readonly bewegt = inject(FEIER_BEWEGUNG);
  readonly fluege = [1, 2, 3, 4, 5, 6, 7];
}
