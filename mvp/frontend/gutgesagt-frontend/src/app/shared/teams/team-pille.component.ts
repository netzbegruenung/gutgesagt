import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

import { motivBild } from './teams';

/**
 * Eine Team-Pille (Variante A aus dem Klickdummy): Motiv im kleinen Medaillon wie bei den
 * Meilensteinen, daneben immer der Teamname, auf Wunsch „Nr. N“ und die Saison. Das Motiv
 * ist Zierde (alt=""), der Name trägt die Bedeutung.
 *
 * ``klein``: die Größe für den Anzeigenamen und die Admin-Liste. ``vergangen``: Abzeichen
 * einer vergangenen Saison, ruhiger gezeichnet.
 */
@Component({
  selector: 'app-team-pille',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="team-pille" [class.klein]="klein" [class.vergangen]="vergangen" data-testid="team-pille">
      @if (bild) {
        <span class="medaillon" aria-hidden="true"><img [src]="bild" alt="" width="24" height="24"></span>
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
    .medaillon img { display: block; width: 15px; height: 15px; }
    .name { font-weight: 700; min-width: 0; overflow-wrap: anywhere; }
    .nr { flex: none; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--primaer-text); }
    .saison { flex: none; color: var(--text-leise); font-variant-numeric: tabular-nums; }
    .klein { gap: 4px; padding: 1px 8px 1px 1px; font-size: 0.75rem; }
    .klein .medaillon { width: 18px; height: 18px; }
    .klein .medaillon img { width: 11px; height: 11px; }
    .klein .name { font-weight: 600; }
    /* Vergangene Saison: als Abzeichen, ohne Fuellung, Ring gestrichelt */
    .vergangen { background: transparent; }
    .vergangen .medaillon { box-shadow: none; border: 2px dashed var(--text-leise); box-sizing: border-box; }
  `],
})
export class TeamPilleComponent {
  @Input({ required: true }) name = '';
  @Input() motiv: string | null = null;
  @Input() nummer: number | null = null;
  @Input() saison: string | null = null;
  @Input() klein = false;
  @Input() vergangen = false;

  get bild(): string | null {
    return motivBild(this.motiv);
  }
}
