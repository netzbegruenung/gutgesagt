import { Component, DestroyRef, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';

import { Saison, SaisonEingabe, SaisonListe, SaisonService } from '../../services/saison.service';
import { ohneRechte, selbstNachladen } from '../../shared/selbst-nachladen';

const ZUSTAND: Record<string, string> = { geplant: 'geplant', laufend: 'läuft', vorbei: 'vorbei' };

const zahl = (wert: number): string => wert.toLocaleString('de-DE');

/** JJJJ-MM-TT als TT.MM.JJJJ. */
const tag = (iso: string): string => {
  const [j, m, t] = iso.split('-');
  return `${t}.${m}.${j}`;
};

function leer(): SaisonEingabe {
  return { name: '', beginn: '', ende: '', ziel: 1000 };
}

/**
 * Saisons mit Gemeinschaftsziel (#782) auf der Seite „Schalter“: anlegen, ändern, vor dem
 * Beginn löschen, dazu je Saison der Stand in Widerspruchs-Wochen. Die laufende Saison ist
 * mit dem Schalter „saison_ziel“ die aktuelle Saison der Teams; den Balken auf der
 * Startseite sehen alle erst ab der Schwelle, bis dahin nur Admins hier. Lädt selbst nach.
 */
@Component({
  selector: 'app-saisons',
  standalone: true,
  imports: [CommonModule, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSnackBarModule],
  template: `
    <section class="saisons mat-elevation-z1" aria-labelledby="saisons-titel" data-testid="saisons">
      <div class="kopf"><h3 id="saisons-titel">Saisons</h3></div>
      <p>
        Höchstens eine Saison läuft. Mit dem Schalter „Saison und Gemeinschaftsziel“ ist sie die aktuelle Saison der
        Teams, und die Startseite zeigt ihr Ziel als Balken.
      </p>
      @if (liste; as l) {
        <p class="zustand" data-testid="saisons-zustand">
          Schalter: {{ l.schalter_wirksam ? 'wirksam' : 'aus' }} · Balken für alle:
          {{ l.schwelle_erreicht ? 'ja' : 'noch nicht' }}
          (ab {{ l.schwelle_wochen }} Wochen in Folge mit je mindestens {{ l.schwelle_menschen }} Menschen, die
          „Ja, gepostet“ melden)
        </p>
        @if (l.saisons.length === 0) {
          <p class="leise">Noch keine Saison angelegt.</p>
        }
        <ul class="liste">
          @for (s of l.saisons; track s.id) {
            <li data-testid="saison">
              <strong>{{ s.name }}</strong>
              <span class="leise"> · {{ zustand(s) }} · {{ tag(s.beginn) }} bis {{ tag(s.ende) }}</span>
              <br />
              {{ zahl(s.erreicht) }} von {{ zahl(s.ziel) }} Widerspruchs-Wochen
              @if (s.laufende_woche !== null) {
                <span class="leise"> · laufende Woche bisher {{ zahl(s.laufende_woche) }}</span>
              }
              @if (s.zustand !== 'vorbei') {
                <span class="knoepfe">
                  <button mat-stroked-button type="button" (click)="bearbeiten(s)" [attr.aria-label]="'Saison ' + s.name + ' ändern'">
                    Ändern
                  </button>
                  @if (s.zustand === 'geplant') {
                    <button mat-stroked-button type="button" (click)="loeschen(s)" [disabled]="speichernd"
                            [attr.aria-label]="'Saison ' + s.name + ' löschen'">Löschen</button>
                  }
                </span>
              }
            </li>
          }
        </ul>

        <form class="formular" (ngSubmit)="speichern()" data-testid="saison-formular">
          <h4>{{ bearbeitet ? 'Saison ' + bearbeitet.name + ' ändern' : 'Neue Saison' }}</h4>
          @if (bearbeitet?.zustand === 'laufend') {
            <p class="leise">Bei einer laufenden Saison lassen sich nur Ziel und Ende ändern.</p>
          }
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Name</mat-label>
            <input matInput name="name" [(ngModel)]="eingabe.name" [maxlength]="l.name_max" required
                   [readonly]="bearbeitet?.zustand === 'laufend'" />
            <mat-hint>etwa „Frühjahr 27“ · höchstens {{ l.name_max }} Zeichen</mat-hint>
          </mat-form-field>
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Erster Tag</mat-label>
            <input matInput type="date" name="beginn" [(ngModel)]="eingabe.beginn" required
                   [readonly]="bearbeitet?.zustand === 'laufend'" />
          </mat-form-field>
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Letzter Tag</mat-label>
            <input matInput type="date" name="ende" [(ngModel)]="eingabe.ende" required />
          </mat-form-field>
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Gemeinschaftsziel</mat-label>
            <input matInput type="number" name="ziel" [(ngModel)]="eingabe.ziel" min="1" max="1000000" required />
            <mat-hint>in Widerspruchs-Wochen</mat-hint>
          </mat-form-field>
          <div class="knoepfe">
            <button mat-flat-button color="primary" type="submit" [disabled]="!vollstaendig() || speichernd"
                    data-testid="saison-speichern">{{ bearbeitet ? 'Änderung speichern' : 'Saison anlegen' }}</button>
            @if (bearbeitet) {
              <button mat-stroked-button type="button" (click)="abbrechen()">Abbrechen</button>
            }
          </div>
        </form>
      } @else {
        <p role="status" class="leise">{{ fehler ? 'Saisons gerade nicht erreichbar, neuer Versuch in Kürze …' : 'Lade Saisons …' }}</p>
      }
    </section>
  `,
  styles: [
    `
      .saisons { overflow: hidden; padding: 0 0 12px; margin-bottom: 12px; overflow-wrap: anywhere; background: var(--flaeche); }
      .saisons > p { margin: 4px 16px; }
      .kopf { display: flex; align-items: center; min-height: 48px; margin-bottom: 8px; padding: 4px 8px 4px 16px; background: var(--karte-kommentar); }
      .kopf h3 { margin: 0; font-family: inherit; font-size: 17px; font-weight: 700; color: var(--akzent-schrift); }
      .zustand { font-weight: 500; }
      .leise { color: var(--text-leise); }
      .liste { margin: 8px 16px; padding: 0; list-style: none; }
      .liste li { padding: 8px 0; border-top: 1px solid var(--linie); }
      .knoepfe { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
      .formular { display: flex; flex-wrap: wrap; gap: 12px; margin: 8px 16px 4px; }
      .formular h4, .formular p, .formular .knoepfe { flex-basis: 100%; margin: 4px 0; }
      .formular mat-form-field { flex: 1 1 200px; max-width: 280px; }
    `,
  ],
})
export class SaisonsComponent implements OnInit {
  liste: SaisonListe | null = null;
  fehler = false;
  speichernd = false;
  eingabe: SaisonEingabe = leer();
  /** Die Saison im Formular; null: neue Saison. */
  bearbeitet: Saison | null = null;

  protected readonly zahl = zahl;
  protected readonly tag = tag;

  private readonly saisons = inject(SaisonService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    const folgen = {
      next: (daten: SaisonListe) => this.uebernehmen(daten),
      error: () => (this.fehler = true),
    };
    this.saisons.liste().subscribe(folgen);
    selbstNachladen(() => this.saisons.liste(true), this.destroyRef, folgen, { aufhoerenBei: ohneRechte });
  }

  zustand(s: Saison): string {
    return ZUSTAND[s.zustand] ?? s.zustand;
  }

  vollstaendig(): boolean {
    const e = this.eingabe;
    return e.name.trim().length > 0 && !!e.beginn && !!e.ende && Number(e.ziel) >= 1;
  }

  bearbeiten(s: Saison): void {
    this.bearbeitet = s;
    this.eingabe = { name: s.name, beginn: s.beginn, ende: s.ende, ziel: s.ziel };
  }

  abbrechen(): void {
    this.bearbeitet = null;
    this.eingabe = leer();
  }

  speichern(): void {
    if (!this.vollstaendig() || this.speichernd) {
      return;
    }
    const eingabe = { ...this.eingabe, name: this.eingabe.name.trim(), ziel: Number(this.eingabe.ziel) };
    const anfrage = this.bearbeitet ? this.saisons.aendern(this.bearbeitet.id, eingabe) : this.saisons.anlegen(eingabe);
    const text = this.bearbeitet ? 'Saison geändert.' : 'Saison angelegt.';
    this.speichernd = true;
    anfrage.subscribe({
      next: (daten) => {
        this.speichernd = false;
        this.abbrechen();
        this.uebernehmen(daten);
        this.snackBar.open(text, 'OK', { duration: 4000 });
      },
      error: (fehler: { status?: number; error?: { detail?: unknown } }) => {
        this.speichernd = false;
        this.snackBar.open(this.fehlertext(fehler), 'OK', { duration: 8000 });
      },
    });
  }

  loeschen(s: Saison): void {
    if (this.speichernd) {
      return;
    }
    this.speichernd = true;
    this.saisons.loeschen(s.id).subscribe({
      next: () => {
        this.speichernd = false;
        if (this.bearbeitet?.id === s.id) {
          this.abbrechen();
        }
        this.snackBar.open(`Saison ${s.name} gelöscht.`, 'OK', { duration: 4000 });
        this.saisons.liste().subscribe({ next: (daten) => this.uebernehmen(daten) });
      },
      error: (fehler: { status?: number; error?: { detail?: unknown } }) => {
        this.speichernd = false;
        this.snackBar.open(this.fehlertext(fehler), 'OK', { duration: 8000 });
      },
    });
  }

  /** 409 und 422 aus den Regeln tragen einen Satz für den Admin; sonst ein allgemeiner. */
  private fehlertext(fehler: { status?: number; error?: { detail?: unknown } }): string {
    const detail = fehler?.error?.detail;
    if ((fehler?.status === 409 || fehler?.status === 422) && typeof detail === 'string') {
      return detail;
    }
    if (fehler?.status === 422) {
      return 'Bitte Name, beide Tage und ein Ziel ab 1 angeben.';
    }
    return 'Nicht gespeichert, bitte gleich noch einmal versuchen.';
  }

  private uebernehmen(daten: SaisonListe): void {
    this.liste = daten;
    this.fehler = false;
  }
}
