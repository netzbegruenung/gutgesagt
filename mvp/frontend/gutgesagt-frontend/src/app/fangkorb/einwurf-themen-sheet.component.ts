import { ChangeDetectionStrategy, Component, Inject, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MAT_BOTTOM_SHEET_DATA, MatBottomSheetRef } from '@angular/material/bottom-sheet';
import { MatButtonModule } from '@angular/material/button';

import { Thema } from '../services/dtos/themenDtos';
import { EinwurfThemenComponent } from '../shared/themen/einwurf-themen.component';

/** Was das Sheet braucht: der Einwurf und seine Themen, wie die Karte sie zeigt. */
export interface EinwurfThemenSheetDaten {
  einwurfId: string;
  themen: Thema[];
  /** Die Aufschrift der Karte, damit klar ist, um welchen Einwurf es geht. */
  titel: string | null;
}

/**
 * „Themen ändern“ aus dem ⋮-Menue einer Einwurf-Karte, im Fangkorb und unter „Meine
 * Einwürfe“. Jeder Klick speichert gleich (app-einwurf-themen); „Fertig“ schliesst nur.
 * Schliesst mit true, wenn sich etwas geaendert hat: Dann laedt die Seite ihre Liste neu.
 */
@Component({
  selector: 'app-einwurf-themen-sheet',
  standalone: true,
  imports: [CommonModule, MatButtonModule, EinwurfThemenComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="sheet-griff" aria-hidden="true"></div>
    <h2 class="sheet-titel" id="einwurf-themen-titel">Themen ändern</h2>
    <p *ngIf="daten.titel" class="sheet-einwurf">{{ daten.titel }}</p>
    <p class="sheet-erklaerung">Ein Fingerzeig für andere und die Vorauswahl für die Aussage beim Ausformulieren.</p>
    <app-einwurf-themen [einwurfId]="daten.einwurfId" [themen]="themen" [immerOffen]="true"
                        (themenChange)="themen = $event"></app-einwurf-themen>
    <div class="sheet-knoepfe">
      <button type="button" mat-flat-button class="fertig" (click)="schliessen()">Fertig</button>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        padding-bottom: 16px;
      }

      .sheet-griff {
        width: 40px;
        height: 4px;
        margin: 4px auto 12px;
        border-radius: 2px;
        background: var(--feldrand);
      }

      .sheet-titel {
        margin: 0 0 4px;
        font-size: 18px;
        font-weight: 600;
        color: var(--text);
      }

      .sheet-einwurf {
        margin: 0 0 8px;
        font-size: 14px;
        color: var(--text);
        overflow-wrap: anywhere;
      }

      .sheet-erklaerung {
        margin: 0 0 12px;
        font-size: 13px;
        color: var(--text-leise);
      }

      .sheet-knoepfe {
        display: flex;
        justify-content: flex-end;
        margin-top: 12px;
      }

      .fertig {
        min-height: 44px;
        background-color: var(--primaer);
        color: white;
      }
    `,
  ],
})
export class EinwurfThemenSheetComponent {
  themen: Thema[];

  @ViewChild(EinwurfThemenComponent) private auswahl?: EinwurfThemenComponent;

  constructor(
    @Inject(MAT_BOTTOM_SHEET_DATA) readonly daten: EinwurfThemenSheetDaten,
    private sheet: MatBottomSheetRef<EinwurfThemenSheetComponent, boolean>,
  ) {
    this.themen = daten.themen;
  }

  /** Ob etwas gespeichert ist; auch fuers Schliessen durch Wischen oder Tippen daneben. */
  get geaendert(): boolean {
    return this.auswahl?.geaendert ?? false;
  }

  schliessen(): void {
    this.sheet.dismiss(this.geaendert);
  }
}
