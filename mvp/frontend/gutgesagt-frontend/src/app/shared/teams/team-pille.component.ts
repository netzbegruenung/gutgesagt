import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

import { TeamMotivComponent } from './team-motiv.component';
import { motivBild, motivEmoji } from './teams';

/**
 * Eine Team-Pille (Variante A aus dem Klickdummy): Motiv im kleinen Medaillon wie bei den
 * Meilensteinen, daneben immer der Teamname, auf Wunsch „Nr. N“ und die Saison. Das Motiv
 * ist ein Emoji der festen Liste oder eines der sechs früheren Bilder; sein Name steht als
 * Alt-Text und Titel daran (``motivName``), der Teamname trägt die Bedeutung.
 *
 * ``klein``: die Größe für den Anzeigenamen und die Admin-Liste. ``vergangen``: Abzeichen
 * einer vergangenen Saison, ruhiger gezeichnet.
 */
@Component({
  selector: 'app-team-pille',
  standalone: true,
  imports: [TeamMotivComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="team-pille" [class.klein]="klein" [class.vergangen]="vergangen" data-testid="team-pille">
      @if (hatMotiv) {
        <span class="medaillon" [class.emoji]="istEmoji">
          <app-team-motiv [motiv]="motiv" [name]="motivName" [zierde]="motivZierde || !motivName"
                          [groesse]="klein ? (istEmoji ? 12 : 11) : 15"></app-team-motiv>
        </span>
      }
      <span class="name">{{ name }}</span>
      @if (nummer !== null) {
        <span class="nr"><span class="visually-hidden">, </span>Nr. {{ nummer }}</span>
      }
      @if (saison) {
        <span class="saison"><span class="visually-hidden">, Saison </span>{{ saison }}</span>
      }
    </span>
  `,
  styles: [`
    :host { display: inline-flex; max-width: 100%; vertical-align: middle; }
    .team-pille {
      display: inline-flex; align-items: center; gap: 6px; min-width: 0; max-width: 100%;
      padding: 3px 10px 3px 3px; border: 1px solid var(--feldrand); border-radius: 999px;
      background: var(--primaer-tint); color: var(--text); font-size: 0.875rem; line-height: 1.2;
    }
    /* Medaillon wie bei den Meilensteinen: tannengruener Ring um das Motiv */
    .medaillon {
      flex: none; display: inline-flex; align-items: center; justify-content: center;
      width: 24px; height: 24px; border-radius: 50%; background: var(--flaeche);
      box-shadow: inset 0 0 0 2px var(--akzent-tanne);
    }
    /* Emoji auf heller Scheibe, auch im Dunkelmodus (schwarze Symbole bleiben lesbar) */
    .medaillon.emoji { background: var(--emoji-grund); }
    /* break-word statt anywhere: bricht nur, wenn der Platz wirklich fehlt. Mit anywhere
       rechnete eine Tabellenspalte die Pille auf einen Buchstaben Breite herunter
       („Sel / bstt / est“ in den Einladungen). */
    .name { font-weight: 700; min-width: 0; overflow-wrap: break-word; }
    .nr { flex: none; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--primaer-text); }
    .saison { flex: none; color: var(--text-leise); font-variant-numeric: tabular-nums; }
    .klein { gap: 4px; padding: 1px 8px 1px 1px; font-size: 0.75rem; }
    .klein .medaillon { width: 18px; height: 18px; }
    .klein .name { font-weight: 600; }
    /* Vergangene Saison: als Abzeichen, ohne Fuellung, Ring gestrichelt */
    .vergangen { background: transparent; }
    .vergangen .medaillon { box-shadow: none; border: 2px dashed var(--text-leise); box-sizing: border-box; }
  `],
})
export class TeamPilleComponent {
  @Input({ required: true }) name = '';
  @Input() motiv: string | null = null;
  /** Name des Motivs für Alt-Text und Titel (motiv_name vom Server) */
  @Input() motivName: string | null = null;
  /** Der Name des Motivs steht schon sichtbar daneben (Meine Teams): ohne Alt-Text */
  @Input() motivZierde = false;
  @Input() nummer: number | null = null;
  @Input() saison: string | null = null;
  @Input() klein = false;
  @Input() vergangen = false;

  get istEmoji(): boolean {
    return motivEmoji(this.motiv) !== null;
  }

  get hatMotiv(): boolean {
    return this.istEmoji || motivBild(this.motiv) !== null;
  }
}
