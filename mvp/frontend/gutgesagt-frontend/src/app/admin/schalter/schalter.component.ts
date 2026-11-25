import { Component, DestroyRef, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSlideToggleChange, MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { Einstellung, ModerationService, Schalter, SchalterListe } from '../../services/moderation.service';
import { ohneRechte, selbstNachladen } from '../../shared/selbst-nachladen';
import { SaisonsComponent } from '../saisons/saisons.component';

/** Anzeigenamen der Schalter; unbekannte zeigen ihren technischen Namen. */
const TITEL: Record<string, string> = {
  punkte: 'Punkte und Meilensteine',
  abzeichen_sichtbar: 'Abzeichen am Anzeigenamen',
  gepostet: 'Rückfrage „Ja, gepostet“',
  herkunft_pruefen: 'Links unter „Herkunft“ prüfen',
  abkuerzungen: 'App-Abkürzungen',
  antworten_hinweis: 'Neue Antworten auf eigene Aussagen',
  sharepic: 'Teilen als Bild',
  team_fortschritt: 'Team-Fortschritt',
  team_quests: 'Team-Quests',
  teams: 'Teams über Einladungen',
  teams_oeffentlich: 'Teams am Anzeigenamen',
  // Spielgefühl zur BDK (#782 bis #793)
  saison_ziel: 'Saison und Gemeinschaftsziel',
  gartenansicht: 'Gartenansicht',
  kopiert_erfolg: 'Erfolgstext nach dem Kopieren',
  konter_probe: 'Konter-Probe',
  luecke_zu_gross: '„Lücke zu!“ als großer Moment',
  einwilligung_im_gewinn: 'Einwilligung im passenden Moment',
  naechster_schritt: '„Dein nächster Schritt“',
  wirkungs_echo: 'Wirkungs-Echo „öffentlich gepostet“',
  danke_knopf: 'Danke-Knopf',
  danke_ohne_konto: 'Danke-Knopf ohne Konto',
  rangliste: 'Rangliste je Saison',
};

/** Schalter, die nur zusammen mit einem anderen wirken: Name → [Voraussetzung, Anzeige]. */
const VORAUSSETZUNG: Record<string, [string, string]> = {
  abzeichen_sichtbar: ['punkte', 'Punkte'],
  teams_oeffentlich: ['teams', 'Teams'],
  // Kette wie im Backend (schalter_service._wirksam): teams → team_fortschritt → team_quests
  team_fortschritt: ['teams', 'Teams'],
  team_quests: ['team_fortschritt', 'Team-Fortschritt'],
  danke_ohne_konto: ['danke_knopf', 'Danke-Knopf'],
  rangliste: ['punkte', 'Punkte'],
};

/** Status je Schalter für Pille und Filter (siehe status()). */
export type SchalterStatus = 'an' | 'frei' | 'recht' | 'gesperrt';
export type SchalterFilter = 'alle' | SchalterStatus;

const STATUS_TEXT: Record<SchalterStatus, string> = {
  an: 'an',
  frei: 'frei einschaltbar',
  recht: 'wartet auf Recht',
  gesperrt: 'gesperrt (Server)',
};

const FILTER: { wert: SchalterFilter; text: string }[] = [
  { wert: 'alle', text: 'Alle' },
  { wert: 'an', text: 'An' },
  { wert: 'frei', text: 'Frei einschaltbar' },
  { wert: 'recht', text: 'Wartet auf Recht' },
  { wert: 'gesperrt', text: 'Gesperrt' },
];

/** Ohne Gruppe vom Server (älterer Dienst) landet ein Schalter hier. */
const OHNE_GRUPPE = 'Weitere';

export interface SchalterGruppe {
  name: string;
  /** Schalter der Gruppe, die zum Filter passen */
  schalter: Schalter[];
  /** Wirksame Schalter der ganzen Gruppe, unabhängig vom Filter */
  an: number;
  gesamt: number;
}

/** Anzeigenamen der Einstellungen; unbekannte zeigen ihren technischen Namen. */
const EINSTELLUNG_TITEL: Record<string, string> = {
  aktuelle_saison: 'Aktuelle Saison',
};

/**
 * Schalter (#708, Glossar „Schalter“): je Schalter Erklärung, ob der Server ihn erlaubt
 * (Obergrenze aus der Umgebung) und der Admin-Wert als Umschalter. Wirksam ist er nur mit
 * beidem. Ist die Obergrenze aus, ist der Umschalter gesperrt. Die Seite lädt selbst nach,
 * nach dem Umschalten aus der Antwort des Servers.
 *
 * Gruppiert nach dem Feld ``gruppe`` des Servers, in dessen Reihenfolge (Sebastian 25.11.);
 * je Schalter eine Zeile mit Status-Pille, Details zum Aufklappen und Filter nach Status.
 */
@Component({
  selector: 'app-schalter',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSlideToggleModule,
    MatSnackBarModule,
    SaisonsComponent,
  ],
  template: `
    <h2>Schalter</h2>
    <p class="hinweis">
      Ein Schalter wirkt nur, wenn der Server ihn erlaubt und er hier eingeschaltet ist. Ohne Eintrag hier ist er aus.
    </p>

    <div *ngIf="liste === null" class="laedt" role="status">
      <mat-spinner diameter="32"></mat-spinner>
      <span>{{ fehler ? 'Schalter gerade nicht erreichbar, neuer Versuch in Kürze …' : 'Lade Schalter …' }}</span>
    </div>

    <ng-container *ngIf="liste !== null">
      <div *ngIf="fehler" class="laedt klein" role="status">
        <mat-spinner diameter="16"></mat-spinner>
        <span>Aktualisieren gerade nicht möglich, neuer Versuch in Kürze …</span>
      </div>

      <div class="filter" role="group" aria-label="Schalter filtern" data-testid="filter">
        <button
          *ngFor="let f of filterListe"
          type="button"
          class="chip"
          data-testid="filter-chip"
          [attr.aria-pressed]="filter === f.wert"
          (click)="filter = f.wert"
        >
          {{ f.text }} <span class="anzahl">{{ anzahl(f.wert) }}</span>
        </button>
      </div>
      <p class="leer" role="status" data-testid="filter-leer">
        <ng-container *ngIf="gruppen().length === 0">Kein Schalter passt zu diesem Filter.</ng-container>
      </p>

      <section
        *ngFor="let g of gruppen(); let i = index; trackBy: nachGruppe"
        class="gruppe mat-elevation-z1"
        [attr.aria-labelledby]="'gruppe-' + i"
        data-testid="gruppe"
      >
        <h3 [id]="'gruppe-' + i" class="gruppe-kopf">
          <span>{{ g.name }}</span>
          <span class="zaehler" data-testid="gruppe-zaehler">{{ g.an }} von {{ g.gesamt }} an</span>
        </h3>
        <ul class="zeilen">
          <li *ngFor="let s of g.schalter; trackBy: nachName" class="schalter" data-testid="schalter">
            <div class="zeile">
              <h4>{{ titel(s) }}</h4>
              <div class="steuer">
                <span class="pille" [ngClass]="'pille-' + status(s)" data-testid="status">{{ statusText(s) }}</span>
                <button
                  mat-icon-button
                  type="button"
                  class="aufklappen"
                  data-testid="aufklappen"
                  [attr.aria-expanded]="offen.has(s.name)"
                  [attr.aria-controls]="'details-' + s.name"
                  [attr.aria-label]="'Details zu ' + titel(s)"
                  (click)="umklappen(s)"
                >
                  <mat-icon aria-hidden="true">{{ offen.has(s.name) ? 'expand_less' : 'expand_more' }}</mat-icon>
                </button>
                <mat-slide-toggle
                  [checked]="s.admin_wert"
                  [disabled]="!s.obergrenze && !s.admin_wert || setzend !== null"
                  [aria-label]="titel(s) + ', Admin'"
                  [aria-describedby]="'zustand-' + s.name"
                  (change)="umschalten(s, $event)"
                >
                  Admin
                </mat-slide-toggle>
              </div>
            </div>
            <!-- Sichtbar, wenn aufgeklappt oder wenn der Admin-Wert an ist, aber nicht wirkt -->
            <p
              class="zustand"
              [id]="'zustand-' + s.name"
              [class.wirkt]="s.wirksam"
              [hidden]="!zustandSichtbar(s)"
              data-testid="zustand"
            >
              {{ zustand(s) }}
            </p>
            <div class="details" [id]="'details-' + s.name" [hidden]="!offen.has(s.name)" data-testid="details">
              <p>{{ s.erklaerung }}</p>
              <p class="obergrenze" [class.aus]="!s.obergrenze">
                <mat-icon aria-hidden="true">{{ s.obergrenze ? 'check_circle' : 'block' }}</mat-icon>
                Server erlaubt: {{ s.obergrenze ? 'ja' : 'nein' }}
                <code>{{ s.umgebungsvariable }}</code>
              </p>
              <p *ngIf="!s.obergrenze" class="gesperrt" data-testid="gesperrt">
                Gesperrt: Erst wenn der Server ihn erlaubt, lässt er sich hier einschalten.
              </p>
              <p *ngIf="s.dsfa_hinweis" class="dsfa" data-testid="dsfa-hinweis">
                <mat-icon aria-hidden="true">gavel</mat-icon>
                {{ s.dsfa_hinweis }}
              </p>
            </div>
          </li>
        </ul>
      </section>

      <!-- Einstellungen mit Textwert, etwa die aktuelle Saison der Teams -->
      <section *ngFor="let e of einstellungen" class="karte mat-elevation-z1" data-testid="einstellung">
        <div class="kopf">
          <h3 [id]="'einstellung-titel-' + e.name">{{ einstellungTitel(e) }}</h3>
        </div>
        <p>{{ e.erklaerung }}</p>
        <form class="einstellung" (ngSubmit)="einstellungSpeichern(e)">
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>{{ einstellungTitel(e) }}</mat-label>
            <input matInput [name]="e.name" [(ngModel)]="entwuerfe[e.name]" [maxlength]="e.max_laenge" required />
            <mat-hint>Standard: {{ e.standard }} · höchstens {{ e.max_laenge }} Zeichen</mat-hint>
          </mat-form-field>
          <button mat-stroked-button type="submit" data-testid="einstellung-speichern"
                  [disabled]="!einstellungGeaendert(e) || setzend !== null">Speichern</button>
        </form>
        <p class="zustand" role="status" data-testid="einstellung-stand">Gespeichert: {{ e.wert }}</p>
        <p *ngIf="e.hinweis" class="dsfa" data-testid="einstellung-hinweis">
          <mat-icon aria-hidden="true">info</mat-icon>
          {{ e.hinweis }}
        </p>
      </section>
      <!-- Saisons mit Gemeinschaftsziel (#782) -->
      <app-saisons></app-saisons>
    </ng-container>
  `,
  styles: [`
    h2 { margin: 0 0 8px; }
    .hinweis { margin: 0 0 16px; }
    .laedt { display: flex; align-items: center; gap: 12px; margin: 16px 0; }
    .laedt.klein { margin: 0 0 8px; font-size: 0.875rem; color: var(--text-leise); }

    /* Filter als Chips; der gewählte trägt aria-pressed */
    .filter { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 4px; }
    .chip {
      display: inline-flex; align-items: center; gap: 6px; min-height: 36px; padding: 4px 12px;
      font: inherit; font-size: 0.875rem; color: var(--text); background: var(--flaeche);
      border: 1px solid var(--feldrand); border-radius: 18px; cursor: pointer;
    }
    .chip[aria-pressed="true"] { background: var(--primaer-tint); border-color: var(--primaer-text); font-weight: 700; }
    .chip:focus-visible, .aufklappen:focus-visible { outline: 2px solid var(--primaer-text); outline-offset: 2px; }
    .chip .anzahl { color: var(--text-leise); font-weight: 400; }
    .leer { margin: 4px 0 8px; min-height: 1em; color: var(--text-leise); }

    /* Je Gruppe eine Karte, Kopf als Band in Klee-zart wie die übrigen Admin-Karten (Admin-Design 21.11.) */
    .gruppe, .karte { overflow: hidden; margin-bottom: 16px; overflow-wrap: anywhere; background: var(--flaeche); }
    .gruppe-kopf {
      display: flex; align-items: baseline; justify-content: space-between; gap: 4px 12px; flex-wrap: wrap;
      margin: 0; padding: 10px 16px; background: var(--karte-kommentar);
      font-family: inherit; font-size: 17px; font-weight: 700; color: var(--akzent-schrift);
    }
    .zaehler { font-size: 0.875rem; font-weight: 500; color: var(--text); }
    .zeilen { list-style: none; margin: 0; padding: 0; }
    .schalter { padding: 4px 8px 4px 16px; border-top: 1px solid var(--linie); }
    .schalter:first-child { border-top: 0; }
    .zeile { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 8px; min-height: 48px; }
    /* Name links, Pille, Aufklappen und Umschalter rechts; schmal rutschen sie in eine zweite Zeile */
    .zeile h4 { flex: 1 1 180px; margin: 0; font-size: 15px; font-weight: 600; }
    .steuer { display: flex; align-items: center; gap: 4px; margin-left: auto; }
    .steuer .pille { margin-right: 4px; }
    .pille {
      display: inline-block; padding: 2px 10px; border-radius: 12px; border: 1px solid transparent;
      font-size: 0.8125rem; line-height: 1.4; color: var(--text); white-space: nowrap;
    }
    .pille-an { background: var(--primaer-tint); border-color: var(--primaer-text); font-weight: 600; }
    .pille-frei { background: var(--info-tint); border-color: var(--info-rand); }
    .pille-recht { background: var(--hinweis-tint); border-color: var(--hinweis-rand); }
    .pille-gesperrt { background: var(--mulde); border-color: var(--feldrand); color: var(--text-leise); }
    .schalter p { margin: 4px 0; }
    .details { padding: 0 0 8px; }
    .zustand { font-weight: 500; color: var(--text-leise); }
    .zustand.wirkt { color: inherit; }
    .obergrenze, .dsfa { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .obergrenze code { font-size: 0.8125rem; color: var(--text-leise); }
    .obergrenze.aus, .gesperrt { color: var(--text-leise); }
    .dsfa {
      align-items: flex-start; flex-wrap: nowrap; margin-top: 8px; padding: 8px 12px;
      font-size: 0.875rem; background: var(--hinweis-tint); color: var(--text); border-radius: var(--border-radius-medium);
    }
    .dsfa mat-icon { flex-shrink: 0; font-size: 20px; width: 20px; height: 20px; color: var(--hinweis-text); }

    .karte { padding: 0 0 12px; }
    .karte p { margin: 4px 16px; }
    .kopf {
      display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
      min-height: 48px; margin-bottom: 8px; padding: 4px 8px 4px 16px; background: var(--karte-kommentar);
    }
    .kopf h3 { margin: 0; font-family: inherit; font-size: 17px; font-weight: 700; color: var(--akzent-schrift); }
    .einstellung { display: flex; flex-wrap: wrap; align-items: baseline; gap: 12px; margin: 8px 16px 4px; }
    .einstellung mat-form-field { flex: 1 1 220px; max-width: 320px; }
  `],
})
export class SchalterComponent implements OnInit {
  /** null: noch nie geladen. */
  liste: Schalter[] | null = null;
  fehler = false;
  /** Name des Schalters, der gerade gesetzt wird. */
  setzend: string | null = null;
  einstellungen: Einstellung[] = [];
  /** Eingaben je Einstellung; Nachladen überschreibt nur, was niemand geändert hat. */
  entwuerfe: Record<string, string> = {};
  /** Gewählter Filter, nur im Speicher. */
  filter: SchalterFilter = 'alle';
  /** Namen der aufgeklappten Schalter; bleibt beim Nachladen erhalten. */
  readonly offen = new Set<string>();
  readonly filterListe = FILTER;

  private readonly destroyRef = inject(DestroyRef);
  private readonly moderation = inject(ModerationService);
  private readonly snackBar = inject(MatSnackBar);

  ngOnInit(): void {
    const folgen = {
      next: (daten: SchalterListe) => this.uebernehmen(daten),
      error: () => (this.fehler = true),
    };
    this.moderation.getSchalter().subscribe(folgen);
    selbstNachladen(() => this.moderation.getSchalter(true), this.destroyRef, folgen, { aufhoerenBei: ohneRechte });
  }

  titel(s: Schalter): string {
    return TITEL[s.name] ?? s.name;
  }

  /**
   * Status für Pille und Filter: wirksam → an; sonst wartet ein Schalter mit offenem
   * rechtlichen Hinweis auf Recht (auch wenn der Server ihn noch sperrt, das ist meist der
   * Grund); sonst gesperrt, wenn der Server ihn nicht erlaubt; sonst frei einschaltbar.
   */
  status(s: Schalter): SchalterStatus {
    if (s.wirksam) {
      return 'an';
    }
    if (s.wartet_auf_recht) {
      return 'recht';
    }
    return s.obergrenze ? 'frei' : 'gesperrt';
  }

  statusText(s: Schalter): string {
    return STATUS_TEXT[this.status(s)];
  }

  anzahl(filter: SchalterFilter): number {
    const liste = this.liste ?? [];
    return filter === 'alle' ? liste.length : liste.filter((s) => this.status(s) === filter).length;
  }

  /** Gruppen in der Reihenfolge des Servers; Gruppen ohne passenden Schalter fehlen. */
  gruppen(): SchalterGruppe[] {
    const gruppen: SchalterGruppe[] = [];
    for (const s of this.liste ?? []) {
      const name = s.gruppe || OHNE_GRUPPE;
      let g = gruppen.find((x) => x.name === name);
      if (!g) {
        g = { name, schalter: [], an: 0, gesamt: 0 };
        gruppen.push(g);
      }
      g.gesamt++;
      if (s.wirksam) {
        g.an++;
      }
      if (this.filter === 'alle' || this.status(s) === this.filter) {
        g.schalter.push(s);
      }
    }
    return gruppen.filter((g) => g.schalter.length > 0);
  }

  /** Gruppen und Zeilen entstehen bei jedem Durchlauf neu: nach Namen verfolgen, sonst baut
   * Angular die Abschnitte jedes Mal neu und der Fokus ginge beim Aufklappen verloren. */
  nachGruppe(_: number, g: SchalterGruppe): string {
    return g.name;
  }

  nachName(_: number, s: Schalter): string {
    return s.name;
  }

  /** Zustandszeile: aufgeklappt, oder zugeklappt, wenn der Admin-Wert an ist und nicht wirkt. */
  zustandSichtbar(s: Schalter): boolean {
    return this.offen.has(s.name) || (s.admin_wert && !s.wirksam);
  }

  umklappen(s: Schalter): void {
    if (this.offen.has(s.name)) {
      this.offen.delete(s.name);
    } else {
      this.offen.add(s.name);
    }
  }

  /**
   * Admin-Wert und Wirkung in einer Zeile, damit ein eingeschalteter Umschalter neben
   * „aus“ nicht widersprüchlich aussieht: Der Umschalter zeigt den Admin-Wert, die Zeile
   * sagt, ob und warum er nicht wirkt.
   */
  zustand(s: Schalter): string {
    const admin = `Admin: ${s.admin_wert ? 'an' : 'aus'}`;
    if (s.wirksam) {
      return `${admin} · wirksam: an`;
    }
    if (s.admin_wert && !s.obergrenze) {
      return `${admin} · wirksam: aus (Server erlaubt nicht)`;
    }
    const [voraus, anzeige] = VORAUSSETZUNG[s.name] ?? [];
    const basis = voraus ? this.liste?.find((v) => v.name === voraus) : undefined;
    if (s.admin_wert && basis && !basis.wirksam) {
      return `${admin} · wirksam: aus, weil ${anzeige} aus`;
    }
    return `${admin} · wirksam: aus`;
  }

  umschalten(s: Schalter, ereignis: MatSlideToggleChange): void {
    this.setzend = s.name;
    this.moderation.schalterSetzen(s.name, ereignis.checked).subscribe({
      next: (daten) => {
        this.setzend = null;
        this.uebernehmen(daten);
      },
      error: (fehler: { status?: number; error?: { detail?: string } }) => {
        this.setzend = null;
        // Umschalter auf den Stand des Servers zurück
        ereignis.source.checked = s.admin_wert;
        const text =
          fehler?.status === 409 && fehler.error?.detail
            ? fehler.error.detail
            : 'Schalter nicht gesetzt, bitte gleich noch einmal versuchen.';
        this.snackBar.open(text, 'OK', { duration: 6000 });
      },
    });
  }

  einstellungTitel(e: Einstellung): string {
    return EINSTELLUNG_TITEL[e.name] ?? e.name;
  }

  einstellungGeaendert(e: Einstellung): boolean {
    const entwurf = (this.entwuerfe[e.name] ?? '').trim();
    return entwurf.length > 0 && entwurf !== e.wert;
  }

  einstellungSpeichern(e: Einstellung): void {
    if (!this.einstellungGeaendert(e) || this.setzend !== null) {
      return;
    }
    this.setzend = e.name;
    this.moderation.einstellungSetzen(e.name, this.entwuerfe[e.name].trim()).subscribe({
      next: (daten) => {
        this.setzend = null;
        // Der gespeicherte Wert gilt, auch wenn der Server ihn bereinigt hat
        delete this.entwuerfe[e.name];
        this.uebernehmen(daten);
        this.snackBar.open(`${this.einstellungTitel(e)} gespeichert.`, 'OK', { duration: 4000 });
      },
      error: (fehler: { status?: number }) => {
        this.setzend = null;
        const text =
          fehler?.status === 422
            ? `Ungültiger Wert: nicht leer, höchstens ${e.max_laenge} Zeichen, keine Steuerzeichen.`
            : 'Einstellung nicht gespeichert, bitte gleich noch einmal versuchen.';
        this.snackBar.open(text, 'OK', { duration: 6000 });
      },
    });
  }

  private uebernehmen(daten: SchalterListe): void {
    this.liste = daten.schalter;
    const neu = daten.einstellungen ?? [];
    for (const e of neu) {
      const alt = this.einstellungen.find((a) => a.name === e.name);
      const unveraendert = this.entwuerfe[e.name] === undefined || this.entwuerfe[e.name] === alt?.wert;
      if (unveraendert) {
        this.entwuerfe[e.name] = e.wert;
      }
    }
    this.einstellungen = neu;
    this.fehler = false;
  }
}
