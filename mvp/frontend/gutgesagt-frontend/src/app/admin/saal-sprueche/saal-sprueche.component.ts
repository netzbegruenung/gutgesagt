import { Component, DestroyRef, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';

import { SaalSpruch, SaalSpruchListe, SaalSpruchService } from '../../services/saal-spruch.service';
import { ohneRechte, selbstNachladen } from '../../shared/selbst-nachladen';

/** JJJJ-MM-TT als Wochentag und TT.MM.JJJJ, etwa „Fr 04.12.2026“. */
export function saalTag(iso: string): string {
  const [j, m, t] = iso.split('-').map(Number);
  const wochentag = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'][new Date(Date.UTC(j, m - 1, t)).getUTCDay()];
  return `${wochentag} ${`${t}`.padStart(2, '0')}.${`${m}`.padStart(2, '0')}.${j}`;
}

/**
 * Saal-Sprüche auf der Seite „Schalter“ (Schalter „saal_spruch“, Glossar „Saal-Spruch“): je
 * Tag ein öffentlicher Spruch, den die Startseite an diesem Tag als „Heute im Saal gehört:“
 * zeigt. Festlegen, ersetzen und entfernen geht auch bei Schalter aus, damit die Sprüche
 * vor dem Einschalten bereitstehen. Nur Text, nichts zur Person. Lädt selbst nach.
 */
@Component({
  selector: 'app-saal-sprueche',
  standalone: true,
  imports: [FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSnackBarModule],
  template: `
    <section class="saal-sprueche mat-elevation-z1" aria-labelledby="saal-sprueche-titel" data-testid="saal-sprueche">
      <div class="kopf"><h3 id="saal-sprueche-titel">Saal-Sprüche</h3></div>
      <p>
        Je Tag ein Spruch, den die Startseite an diesem Tag oben als „Heute im Saal gehört:“ zeigt, mit dem Knopf
        „Antworten ansehen“. Nur öffentlicher Text, keine Namen. Der Tag gilt in deutscher Zeit.
      </p>
      @if (liste; as l) {
        <p class="zustand" data-testid="saal-sprueche-zustand">
          Schalter „saal_spruch“: {{ l.schalter_wirksam ? 'wirksam' : 'aus' }}
        </p>
        @if (l.sprueche.length === 0) {
          <p class="leise">Ab heute kein Spruch festgelegt.</p>
        }
        <ul class="liste">
          @for (s of l.sprueche; track s.datum) {
            <li data-testid="saal-spruch-eintrag">
              <strong>{{ tag(s.datum) }}</strong>@if (s.datum === l.heute) {<span class="leise"> · heute</span>}
              <br />
              „{{ s.text }}“
              <span class="knoepfe">
                <button mat-stroked-button type="button" (click)="bearbeiten(s)"
                        [attr.aria-label]="'Spruch für ' + tag(s.datum) + ' ändern'">Ändern</button>
                <button mat-stroked-button type="button" (click)="entfernen(s)" [disabled]="speichernd"
                        [attr.aria-label]="'Spruch für ' + tag(s.datum) + ' entfernen'">Entfernen</button>
              </span>
            </li>
          }
        </ul>

        <form class="formular" (ngSubmit)="speichern()" data-testid="saal-spruch-formular">
          <h4>Spruch festlegen</h4>
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Tag</mat-label>
            <input matInput type="date" name="datum" [(ngModel)]="datum" [min]="l.heute" required />
            <mat-hint>Ein Tag mit Spruch wird ersetzt</mat-hint>
          </mat-form-field>
          <mat-form-field appearance="outline" subscriptSizing="dynamic" class="breit">
            <mat-label>Spruch</mat-label>
            <textarea matInput name="text" [(ngModel)]="text" [maxlength]="l.text_max" rows="2" required></textarea>
            <mat-hint>etwa „Klimaschutz können wir uns gerade nicht leisten.“ · höchstens {{ l.text_max }} Zeichen</mat-hint>
          </mat-form-field>
          <div class="knoepfe">
            <button mat-flat-button color="primary" type="submit" [disabled]="!vollstaendig() || speichernd"
                    data-testid="saal-spruch-speichern">Spruch speichern</button>
          </div>
        </form>
      } @else {
        <p role="status" class="leise">{{ fehler ? 'Saal-Sprüche gerade nicht erreichbar, neuer Versuch in Kürze …' : 'Lade Saal-Sprüche …' }}</p>
      }
    </section>
  `,
  styles: [
    `
      .saal-sprueche { overflow: hidden; padding: 0 0 12px; margin-bottom: 12px; overflow-wrap: anywhere; background: var(--flaeche); }
      .saal-sprueche > p { margin: 4px 16px; }
      .kopf { display: flex; align-items: center; min-height: 48px; margin-bottom: 8px; padding: 4px 8px 4px 16px; background: var(--karte-kommentar); }
      .kopf h3 { margin: 0; font-family: inherit; font-size: 17px; font-weight: 700; color: var(--akzent-schrift); }
      .zustand { font-weight: 500; }
      .leise { color: var(--text-leise); }
      .liste { margin: 8px 16px; padding: 0; list-style: none; }
      .liste li { padding: 8px 0; border-top: 1px solid var(--linie); }
      .knoepfe { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
      .formular { display: flex; flex-wrap: wrap; gap: 12px; margin: 8px 16px 4px; }
      .formular h4, .formular .knoepfe { flex-basis: 100%; margin: 4px 0; }
      .formular mat-form-field { flex: 1 1 200px; max-width: 280px; }
      .formular mat-form-field.breit { flex: 2 1 280px; max-width: none; }
    `,
  ],
})
export class SaalSpruecheComponent implements OnInit {
  liste: SaalSpruchListe | null = null;
  fehler = false;
  speichernd = false;
  datum = '';
  text = '';

  protected readonly tag = saalTag;

  private readonly service = inject(SaalSpruchService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    const folgen = {
      next: (daten: SaalSpruchListe) => this.uebernehmen(daten),
      error: () => (this.fehler = true),
    };
    this.service.liste().subscribe(folgen);
    selbstNachladen(() => this.service.liste(true), this.destroyRef, folgen, { aufhoerenBei: ohneRechte });
  }

  vollstaendig(): boolean {
    return !!this.datum && this.text.trim().length > 0;
  }

  bearbeiten(s: SaalSpruch): void {
    this.datum = s.datum;
    this.text = s.text;
  }

  speichern(): void {
    if (!this.vollstaendig() || this.speichernd) {
      return;
    }
    const datum = this.datum;
    this.speichernd = true;
    this.service.festlegen(datum, this.text.trim()).subscribe({
      next: (daten) => {
        this.speichernd = false;
        this.datum = '';
        this.text = '';
        this.uebernehmen(daten);
        this.snackBar.open(`Spruch für ${saalTag(datum)} gespeichert.`, 'OK', { duration: 4000 });
      },
      error: (fehler: { status?: number; error?: { detail?: unknown } }) => {
        this.speichernd = false;
        this.snackBar.open(this.fehlertext(fehler), 'OK', { duration: 8000 });
      },
    });
  }

  entfernen(s: SaalSpruch): void {
    if (this.speichernd) {
      return;
    }
    this.speichernd = true;
    this.service.entfernen(s.datum).subscribe({
      next: () => {
        this.speichernd = false;
        this.snackBar.open(`Spruch für ${saalTag(s.datum)} entfernt.`, 'OK', { duration: 4000 });
        this.service.liste().subscribe({ next: (daten) => this.uebernehmen(daten) });
      },
      error: (fehler: { status?: number; error?: { detail?: unknown } }) => {
        this.speichernd = false;
        this.snackBar.open(this.fehlertext(fehler), 'OK', { duration: 8000 });
      },
    });
  }

  /** 422 trägt einen Satz für den Admin; sonst ein allgemeiner. */
  private fehlertext(fehler: { status?: number; error?: { detail?: unknown } }): string {
    const detail = fehler?.error?.detail;
    if (fehler?.status === 422 && typeof detail === 'string') {
      return detail;
    }
    if (fehler?.status === 422) {
      return 'Bitte einen Tag ab heute und einen Spruch angeben.';
    }
    return 'Nicht gespeichert, bitte gleich noch einmal versuchen.';
  }

  private uebernehmen(daten: SaalSpruchListe): void {
    this.liste = daten;
    this.fehler = false;
  }
}
