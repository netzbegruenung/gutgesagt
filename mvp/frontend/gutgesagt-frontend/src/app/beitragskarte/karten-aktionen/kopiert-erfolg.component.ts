import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { ROUTES } from '../../shared/constants/app.constants';
import { AndereTonlage, KOPIERT_ERFOLG, KOPIERT_ERFOLG_ZEICHEN, nutzungSatz, tonlagenHinweis } from './kopiert-erfolg';

/**
 * Der Erfolgstext unter der Aktionsleiste nach dem Kopieren (#785). Die Region steht
 * immer da (role="status"), damit Screenreader den Text ansagen, sobald er erscheint;
 * er blockiert nichts und bleibt ohne Frist stehen, bis die Person ihn schliesst, damit
 * der Link nicht unter der Hand verschwindet.
 */
@Component({
  selector: 'app-kopiert-erfolg',
  standalone: true,
  imports: [CommonModule, RouterLink, MatButtonModule, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="kopiert-erfolg-region" role="status">
      <div class="kopiert-erfolg" *ngIf="sichtbar">
        <div class="kopiert-erfolg-text">
          <p class="erfolg-satz">
            {{ erfolg }} <span aria-hidden="true">{{ zeichen }}</span>
            <ng-container *ngIf="nutzungText as n">&ngsp;<span class="erfolg-nutzung">{{ n }}</span></ng-container>
          </p>
          <p class="erfolg-tonlage" *ngIf="tonlage as t">
            {{ t.frage }}&ngsp;<a class="erfolg-tonlage-link" [routerLink]="[beitragPfad, andereTonlage!.id]">{{ t.link }}</a>
          </p>
        </div>
        <button mat-icon-button type="button" class="erfolg-schliessen" aria-label="Hinweis schließen" (click)="schliessen.emit()">
          <mat-icon aria-hidden="true">close</mat-icon>
        </button>
      </div>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .kopiert-erfolg {
        display: flex;
        align-items: flex-start;
        gap: var(--spacing-sm);
        margin: 0 var(--spacing-md) var(--spacing-md);
        padding: var(--spacing-sm) var(--spacing-xs) var(--spacing-sm) var(--spacing-md);
        background: var(--primaer-tint);
        border-left: 4px solid var(--primaer-text);
        border-radius: var(--border-radius-small);
        color: var(--text);
      }
      .kopiert-erfolg-text {
        flex: 1;
        min-width: 0;
        padding-top: var(--spacing-xs);
      }
      .kopiert-erfolg p {
        margin: 0;
        font-size: 15px;
        line-height: 1.45;
        overflow-wrap: anywhere;
      }
      .erfolg-satz {
        font-weight: 600;
      }
      .erfolg-nutzung {
        font-weight: 400;
      }
      .erfolg-tonlage {
        margin-top: var(--spacing-xs) !important;
      }
      .erfolg-tonlage-link {
        color: var(--primaer-text);
        text-decoration: underline;
        text-underline-offset: 2px;
        font-weight: 600;
      }
      .erfolg-schliessen {
        flex: none;
        width: 40px;
        height: 40px;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--text-leise);
      }
    `,
  ],
})
export class KopiertErfolgComponent {
  @Input() sichtbar = false;
  /** Die Nutzung, wie die Karte sie gerade zeigt; null = unbekannt. */
  @Input() nutzung: number | null = null;
  /** Eine Antwort zur selben Aussage in anderem Stil; null = kein Hinweis. */
  @Input() andereTonlage: AndereTonlage | null = null;
  @Output() schliessen = new EventEmitter<void>();

  readonly erfolg = KOPIERT_ERFOLG;
  readonly zeichen = KOPIERT_ERFOLG_ZEICHEN;
  readonly beitragPfad = ROUTES.BEITRAG;

  get nutzungText(): string | null {
    return nutzungSatz(this.nutzung);
  }

  get tonlage(): { frage: string; link: string } | null {
    return tonlagenHinweis(this.andereTonlage);
  }
}
