import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

import { motivBild, motivEmoji } from './teams';

/**
 * Das Motiv eines Teams: ein Emoji aus der festen Liste als Text, die sechs früheren Schlüssel
 * als Bild (public/meilensteine). Alt-Text ist der Name des Motivs (deutscher CLDR-Kurzname);
 * mit ``zierde`` steht der Name schon daneben und das Motiv wird für Screenreader ausgeblendet.
 * Unbekannte Motive zeichnen nichts.
 *
 * Das Emoji liegt auf einer eigenen hellen Scheibe (--emoji-grund), damit auch schwarze
 * Zeichen wie ♠️ oder ✔️ im Dunkelmodus lesbar bleiben.
 */
@Component({
  selector: 'app-team-motiv',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (bild) {
      <img class="motiv-bild" [src]="bild" [alt]="zierde ? '' : name || ''" [attr.title]="name || null"
           [style.width.px]="groesse" [style.height.px]="groesse" data-testid="motiv-bild">
    } @else if (emoji) {
      <span class="motiv-emoji" [style.font-size.px]="groesse" [attr.title]="name || null"
            [attr.role]="zierde ? null : 'img'" [attr.aria-label]="zierde ? null : name || null"
            [attr.aria-hidden]="zierde ? 'true' : null" data-testid="motiv-emoji">{{ emoji }}</span>
    }
  `,
  styles: [`
    :host { display: inline-flex; align-items: center; justify-content: center; line-height: 1; }
    .motiv-bild { display: block; }
    .motiv-emoji {
      display: inline-block; line-height: 1;
      font-family: 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', 'Twemoji Mozilla', sans-serif;
      /* Kein Fett und keine Textfarbe: Symbole mit Textdarstellung bleiben farbig */
      font-weight: normal; font-style: normal;
    }
  `],
})
export class TeamMotivComponent {
  /** Gespeicherter Schlüssel: Emoji oder einer der sechs früheren Schlüssel */
  @Input() motiv: string | null = null;
  /** Name des Motivs (vom Server, motiv_name) für Alt-Text und Titel */
  @Input() name: string | null = null;
  /** Kantenlänge in Pixeln */
  @Input() groesse = 16;
  /** Der Name steht schon sichtbar daneben: dann ohne eigenen Alt-Text */
  @Input() zierde = false;

  get bild(): string | null {
    return motivBild(this.motiv);
  }

  get emoji(): string | null {
    return motivEmoji(this.motiv);
  }
}
