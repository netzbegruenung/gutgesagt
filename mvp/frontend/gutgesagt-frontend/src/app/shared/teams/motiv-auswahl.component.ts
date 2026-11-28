import { ChangeDetectionStrategy, Component, EventEmitter, Input, OnChanges, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { TeamMotivComponent } from './team-motiv.component';
import { TeamMotivEintrag, TeamMotivKategorie, motiveSuchen } from './teams';

interface Gruppe {
  schluessel: string;
  name: string;
  motive: TeamMotivEintrag[];
}

/**
 * Auswahl des Team-Motivs im Admin-Formular: Suchfeld mit Vorschlagsliste (Combobox von Angular
 * Material, Pfeiltasten und Enter), gruppiert nach Kategorien, dazu ein Filter nach Kategorie.
 * Das gewählte Motiv steht über den Feldern mit seinem Namen; eine Änderung sagt die
 * Live-Region an. Die Liste kommt vom Server (feste Positivliste, domain/team_emoji.py).
 */
@Component({
  selector: 'app-motiv-auswahl',
  standalone: true,
  imports: [FormsModule, MatAutocompleteModule, MatFormFieldModule, MatInputModule, MatSelectModule, TeamMotivComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="motiv-auswahl" role="group" aria-labelledby="motiv-auswahl-titel">
      <span id="motiv-auswahl-titel" class="motiv-titel">Motiv</span>
      <p class="motiv-gewaehlt" aria-live="polite" data-testid="motiv-gewaehlt">
        @if (motiv) {
          <span class="medaillon" aria-hidden="true">
            <app-team-motiv [motiv]="motiv" [name]="gewaehltName" [zierde]="true" [groesse]="20"></app-team-motiv>
          </span>
          <span>Gewählt: <strong>{{ gewaehltName }}</strong></span>
        } @else {
          <span>Noch kein Motiv gewählt</span>
        }
      </p>
      <div class="motiv-felder">
        <mat-form-field appearance="outline" subscriptSizing="dynamic" class="motiv-kategorie">
          <mat-label>Kategorie</mat-label>
          <mat-select [(ngModel)]="kategorie" (selectionChange)="aktualisieren()" data-testid="motiv-kategorie">
            <mat-option value="">Alle Kategorien</mat-option>
            @for (k of kategorien; track k.schluessel) {
              <mat-option [value]="k.schluessel">{{ k.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic" class="motiv-suche">
          <mat-label>Motiv suchen</mat-label>
          <input matInput type="text" autocomplete="off" [matAutocomplete]="auto" [(ngModel)]="suche"
                 (ngModelChange)="aktualisieren()" data-testid="motiv-suche" />
          <mat-hint>Etwa „Baum“, „Fahrrad“ oder „Stern“. Pfeiltasten wählen, Enter übernimmt.</mat-hint>
          <mat-autocomplete #auto="matAutocomplete" hideSingleSelectionIndicator
                            (optionSelected)="waehlen($event.option.value)">
            @for (g of gruppen; track g.schluessel) {
              <mat-optgroup [label]="g.name">
                @for (m of g.motive; track m.schluessel) {
                  <mat-option [value]="m.schluessel" class="motiv-option" data-testid="motiv-option">
                    <span class="motiv-option-inhalt">
                      <span class="scheibe" aria-hidden="true">
                        <app-team-motiv [motiv]="m.schluessel" [name]="m.name" [zierde]="true" [groesse]="18"></app-team-motiv>
                      </span>
                      <span>{{ m.name }}</span>
                    </span>
                  </mat-option>
                }
              </mat-optgroup>
            } @empty {
              <mat-option disabled data-testid="motiv-leer">Kein Motiv gefunden</mat-option>
            }
          </mat-autocomplete>
        </mat-form-field>
      </div>
    </div>
  `,
  styles: [`
    .motiv-titel { display: block; margin-bottom: 4px; font-size: 0.875rem; color: var(--text-leise); }
    .motiv-gewaehlt { display: flex; align-items: center; gap: 8px; margin: 0 0 8px; }
    .medaillon {
      display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px;
      border-radius: 50%; background: var(--emoji-grund); box-shadow: inset 0 0 0 2px var(--akzent-tanne);
    }
    .motiv-felder { display: flex; flex-wrap: wrap; gap: 4px 12px; }
    .motiv-kategorie { flex: 0 1 14rem; }
    .motiv-suche { flex: 1 1 16rem; }
    .motiv-option-inhalt { display: inline-flex; align-items: center; gap: 10px; }
    /* Helle Scheibe wie in der Team-Pille: schwarze Symbole bleiben im Dunkelmodus lesbar */
    .scheibe {
      display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px;
      border-radius: 50%; background: var(--emoji-grund);
    }
  `],
})
export class MotivAuswahlComponent implements OnChanges {
  @Input() motive: readonly TeamMotivEintrag[] = [];
  @Input() kategorien: readonly TeamMotivKategorie[] = [];
  @Input() motiv = '';
  @Output() motivChange = new EventEmitter<string>();

  suche = '';
  kategorie = '';
  gruppen: Gruppe[] = [];

  ngOnChanges(): void {
    this.aktualisieren();
  }

  get gewaehltName(): string {
    return this.motive.find((m) => m.schluessel === this.motiv)?.name ?? '';
  }

  /** Treffer der Suche im gewählten Filter, nach Kategorien in der Reihenfolge des Servers. */
  aktualisieren(): void {
    const treffer = motiveSuchen(this.motive, this.suche, this.kategorien).filter(
      (m) => !this.kategorie || m.kategorie === this.kategorie,
    );
    const namen = this.kategorien.length
      ? this.kategorien
      : [...new Set(this.motive.map((m) => m.kategorie))].map((k) => ({ schluessel: k, name: k }));
    this.gruppen = namen
      .map((k) => ({ ...k, motive: treffer.filter((m) => m.kategorie === k.schluessel) }))
      .filter((g) => g.motive.length > 0);
  }

  waehlen(schluessel: string): void {
    this.motiv = schluessel;
    this.motivChange.emit(schluessel);
    // Das Suchfeld wird wieder leer: Das Gewählte steht darüber, die Liste zeigt wieder alle
    this.suche = '';
    this.aktualisieren();
  }
}
