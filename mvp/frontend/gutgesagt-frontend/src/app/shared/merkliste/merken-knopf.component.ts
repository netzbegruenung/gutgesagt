import { ChangeDetectionStrategy, Component, Input, computed, effect, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar } from '@angular/material/snack-bar';

import { AuthService } from '../../auth/auth.service';
import { MerklisteService } from '../../services/merkliste.service';

export const MERKEN_TEXTE = {
  merken: 'Merken',
  gemerkt: 'Gemerkt',
  gemerktMeldung: 'Gemerkt. Du findest es unter Meine Beiträge, „Gemerkt“.',
  entferntMeldung: 'Aus der Merkliste entfernt.',
  voll: 'Deine Merkliste ist voll. Entferne erst einen Beitrag.',
  fehler: 'Das hat gerade nicht geklappt. Versuch es noch einmal.',
} as const;

/**
 * Der Knopf „Merken“ an der Beitragskarte (#758): Symbol mit Wort, nach dem Tippen
 * „Gemerkt“. Nur angemeldet, mit Art.-9-Einwilligung und mit eingeschaltetem Schalter
 * `merkliste`; sonst
 * steht nichts da. Keine Zahl: Wie oft andere etwas gemerkt haben, zeigt Gut gesagt nicht.
 */
@Component({
  selector: 'app-merken-knopf',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button *ngIf="sichtbar()" mat-button type="button" class="merken-knopf"
            [class.ist-gemerkt]="gemerkt()" [attr.aria-busy]="laeuft() || null" (click)="umschalten()">
      <mat-icon aria-hidden="true">{{ gemerkt() ? 'bookmark' : 'bookmark_border' }}</mat-icon>
      <span>{{ gemerkt() ? texte.gemerkt : texte.merken }}</span>
    </button>
  `,
  styles: [
    `
      :host { display: contents; }
      .merken-knopf { min-height: 44px; min-width: 44px; padding: 0 12px; color: var(--akzent-schrift); }
      .merken-knopf mat-icon { margin-right: 6px; }
      .merken-knopf.ist-gemerkt { font-weight: 700; }
    `,
  ],
})
export class MerkenKnopfComponent {
  @Input({ required: true }) set inhaltId(id: string) {
    this.id.set(id);
  }

  readonly texte = MERKEN_TEXTE;
  private readonly merkliste = inject(MerklisteService);
  private readonly auth = inject(AuthService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly id = signal('');
  private readonly nutzer = toSignal(this.auth.userInfo$, { initialValue: this.auth.getUserInfo() });
  readonly laeuft = signal(false);

  // Nur mit Einwilligung: Ohne sie sperrt das Backend die Liste, und ein Knopf, der nur den
  // Hinweis zur Einwilligung ausloest, draengte (wie „Ja, gepostet“).
  readonly sichtbar = computed(() => this.merkliste.bereit() && !!this.nutzer()?.isAuthenticated && !!this.id());
  readonly gemerkt = computed(() => {
    this.merkliste.eintraege();
    return this.merkliste.istGemerkt(this.id());
  });

  constructor() {
    // Erst wenn der Knopf sichtbar ist, die Liste holen (einmal fuer alle Karten)
    effect(() => {
      if (this.sichtbar()) {
        this.merkliste.sicherstellen();
      }
    });
  }

  umschalten(): void {
    if (!this.sichtbar() || this.laeuft()) {
      return;
    }
    this.laeuft.set(true);
    this.merkliste.umschalten(this.id()).subscribe({
      next: (gemerkt) => {
        this.laeuft.set(false);
        this.snackBar.open(gemerkt ? this.texte.gemerktMeldung : this.texte.entferntMeldung, 'OK', { duration: 5000 });
      },
      error: (fehler) => {
        this.laeuft.set(false);
        this.snackBar.open(fehler?.status === 409 ? this.texte.voll : this.texte.fehler, 'OK', { duration: 8000 });
      },
    });
  }
}
