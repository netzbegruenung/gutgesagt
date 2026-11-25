import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { ROUTES } from '../../shared/constants/app.constants';
import { KOPIERT } from '../../shared/vorlagen-luecke';
import { AndereTonlage, KOPIERT_ERFOLG, KOPIERT_ERFOLG_ZEICHEN, nutzungSatz, tonlagenHinweis } from './kopiert-erfolg';
import { GEPOSTET_FRAGE, GEPOSTET_GEMELDET, JA_GEPOSTET } from './gepostet-texte';

/**
 * Wo die Frage „Gepostet?“ im Kasten steht: ``aus`` ohne Frage, ``frage`` mit Knopf,
 * ``sendet`` nach dem Tippen bis zur Antwort, ``gemeldet`` mit Dank.
 */
export type GepostetStand = 'aus' | 'frage' | 'sendet' | 'gemeldet';

/**
 * Der Erfolgstext unter der Aktionsleiste nach dem Kopieren (#785). Die Region steht da,
 * solange der Schalter an ist (role="status"), damit Screenreader den Text ansagen, sobald er erscheint;
 * er blockiert nichts und bleibt ohne Frist stehen, bis die Person ihn schliesst, damit
 * der Link nicht unter der Hand verschwindet.
 *
 * Hier steht auch „Ja, gepostet“ (#643, #799), statt als Snackbar für 8 s: Wer in die
 * andere App wechselt, postet und zurückkommt, findet den Knopf noch. Nach dem Tippen
 * bleibt der Knopf stehen, nur als ``aria-disabled`` mit „Gepostet“, damit der
 * Tastaturfokus nicht verloren geht (wie „Danke an die Autorin“); der Dank kommt in einer
 * eigenen Status-Zeile. Ohne Schalter `kopiert_erfolg` zeigt der Kasten statt des
 * Erfolgstexts nur die gewohnte Bestätigung, damit die Frage trotzdem bleiben kann.
 */
@Component({
  selector: 'app-kopiert-erfolg',
  standalone: true,
  imports: [CommonModule, RouterLink, MatButtonModule, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="kopiert-erfolg-rahmen" [class.sichtbar]="sichtbar">
      <div class="kopiert-erfolg-inhalt">
        <div class="kopiert-erfolg-region" role="status">
          <div class="kopiert-erfolg" *ngIf="sichtbar">
            <p class="erfolg-satz" *ngIf="erfolgstext; else schlicht">
              {{ erfolg }} <span aria-hidden="true">{{ zeichen }}</span>
              <ng-container *ngIf="nutzungText as n">&ngsp;<span class="erfolg-nutzung">{{ n }}</span></ng-container>
            </p>
            <ng-template #schlicht><p class="erfolg-satz">{{ kopiertSchlicht }}</p></ng-template>
            <p class="erfolg-tonlage" *ngIf="erfolgstext && tonlage as t">
              {{ t.frage }}&ngsp;<a class="erfolg-tonlage-link" [routerLink]="[beitragPfad, andereTonlage!.id]">{{ t.link }}</a>
            </p>
            <p class="erfolg-gepostet-frage" *ngIf="gepostet !== 'aus'">{{ frage }}</p>
          </div>
        </div>
        <!-- Ausserhalb der Status-Region: Knopf und Dank sollen beim Erscheinen nicht mit angesagt werden -->
        <div class="erfolg-gepostet" *ngIf="sichtbar && gepostet !== 'aus'">
          <button mat-flat-button type="button" class="ja-gepostet"
                  [attr.aria-disabled]="gepostet === 'frage' ? null : 'true'"
                  [class.ja-gepostet--fertig]="gepostet === 'gemeldet'"
                  (click)="gepostetTippen()">
            <mat-icon aria-hidden="true" *ngIf="gepostet === 'gemeldet'">check</mat-icon>
            <span>{{ gepostet === 'gemeldet' ? gemeldet : jaGepostetWort }}</span>
          </button>
        </div>
        <p class="erfolg-gepostet-dank" *ngIf="sichtbar" role="status">{{ gepostet === 'gemeldet' ? gepostetDank : '' }}</p>
      </div>
      <!-- Ausserhalb der Status-Region: Der Knopf soll nicht mit angesagt werden -->
      <button *ngIf="sichtbar" mat-icon-button type="button" class="erfolg-schliessen" aria-label="Hinweis schließen"
              (click)="schliessen.emit()">
        <mat-icon aria-hidden="true">close</mat-icon>
      </button>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .kopiert-erfolg-rahmen.sichtbar {
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
      .kopiert-erfolg-inhalt {
        flex: 1;
        min-width: 0;
      }
      .kopiert-erfolg-region {
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
      .erfolg-gepostet-frage {
        margin-top: var(--spacing-sm) !important;
      }
      .erfolg-gepostet {
        margin-top: var(--spacing-sm);
      }
      /* Voller Knopf in der Markenfarbe wie „Kopieren“, auch im Dunkelmodus nicht aufgehellt */
      .ja-gepostet {
        min-height: 40px;
        background-color: var(--primaer);
        color: #fff;
      }
      .ja-gepostet--fertig {
        background-color: transparent;
        color: var(--text);
        box-shadow: inset 0 0 0 1px var(--text-leise);
      }
      .ja-gepostet[aria-disabled='true'] {
        cursor: default;
      }
      .erfolg-gepostet-dank {
        margin: var(--spacing-xs) 0 0;
        font-size: 15px;
        line-height: 1.45;
        overflow-wrap: anywhere;
      }
      .erfolg-gepostet-dank:empty {
        display: none;
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
  /** Aus mit Schalter `kopiert_erfolg` aus: dann nur „Kopiert – …“ ohne Pflänzchen, Nutzung und Tonlage. */
  @Input() erfolgstext = true;
  /** Die Frage „Gepostet?“; ``aus`` ohne (Schalter aus, nicht angeboten, schon gemeldet). */
  @Input() gepostet: GepostetStand = 'aus';
  /** Der Dank nach „Ja, gepostet“, sobald der Server geantwortet hat. */
  @Input() gepostetDank: string | null = null;
  @Output() schliessen = new EventEmitter<void>();
  /** „Ja, gepostet“ getippt; melden und danken macht die Aktionsleiste. */
  @Output() jaGepostet = new EventEmitter<void>();

  readonly kopiertSchlicht = KOPIERT;
  readonly frage = GEPOSTET_FRAGE;
  readonly jaGepostetWort = JA_GEPOSTET;
  readonly gemeldet = GEPOSTET_GEMELDET;
  readonly erfolg = KOPIERT_ERFOLG;
  readonly zeichen = KOPIERT_ERFOLG_ZEICHEN;
  readonly beitragPfad = ROUTES.BEITRAG;

  get nutzungText(): string | null {
    return nutzungSatz(this.nutzung);
  }

  get tonlage(): { frage: string; link: string } | null {
    return tonlagenHinweis(this.andereTonlage);
  }

  gepostetTippen(): void {
    if (this.gepostet === 'frage') {
      this.jaGepostet.emit();
    }
  }
}
