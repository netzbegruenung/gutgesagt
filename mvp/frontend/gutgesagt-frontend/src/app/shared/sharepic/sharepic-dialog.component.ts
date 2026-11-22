import { ChangeDetectionStrategy, ChangeDetectorRef, Component, Inject, OnDestroy, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialog, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { TEILEN_NAVIGATOR } from '../teilen.service';
import { SHAREPIC_FORMAT_LABEL, SharepicDaten, SharepicFormat, sharepicDatei } from './sharepic';

/** Wie das Bild die Karte verlassen hat; undefined = geschlossen ohne Bild. */
export type SharepicErgebnis = 'geteilt' | 'heruntergeladen';

export const SHAREPIC_TEXTE = {
  titel: 'Als Bild teilen',
  format: 'Format',
  teilen: 'Bild teilen',
  herunterladen: 'Bild herunterladen',
  schliessen: 'Schließen',
  laedt: 'Bild wird gemalt …',
  fehler: 'Das Bild ließ sich nicht malen. Versuch es noch einmal oder teile den Link.',
  hinweis: 'Das Bild entsteht auf deinem Gerät. Gut gesagt speichert es nicht.',
} as const;

/**
 * Teilen als Bild (#756): Vorschau im gewählten Format (Quadrat oder Story), darunter
 * „Bild teilen“ über das Teilen-Menü des Geräts, wo es Dateien teilen kann, sonst nur
 * „Bild herunterladen“. Das Bild wird schon beim Öffnen und beim Formatwechsel gemalt:
 * Teilen muss im Tipp selbst starten, sonst lassen manche Browser es nicht zu.
 */
@Component({
  selector: 'app-sharepic-dialog',
  standalone: true,
  imports: [CommonModule, MatDialogModule, MatButtonModule, MatButtonToggleModule, MatIconModule, MatProgressSpinnerModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title id="sharepic-titel">{{ texte.titel }}</h2>
    <mat-dialog-content class="sharepic-inhalt">
      <mat-button-toggle-group class="sharepic-format" [attr.aria-label]="texte.format"
                               [value]="format" [hideSingleSelectionIndicator]="true"
                               (change)="formatWaehlen($event.value)">
        <mat-button-toggle *ngFor="let f of formate" [value]="f">
          <mat-icon aria-hidden="true">{{ f === 'quadrat' ? 'crop_square' : 'crop_portrait' }}</mat-icon>
          <span>{{ label[f] }}</span>
        </mat-button-toggle>
      </mat-button-toggle-group>

      <div class="sharepic-vorschau" [class.story]="format === 'story'">
        <img *ngIf="vorschau && !laedt" [src]="vorschau" [alt]="bildBeschreibung" data-testid="sharepic-vorschau">
        <div *ngIf="laedt" class="sharepic-laedt" role="status">
          <mat-spinner diameter="32"></mat-spinner><span>{{ texte.laedt }}</span>
        </div>
        <p *ngIf="fehler && !laedt" class="sharepic-fehler" role="alert">
          <mat-icon aria-hidden="true">error_outline</mat-icon>{{ texte.fehler }}
        </p>
      </div>
      <p class="sharepic-hinweis">{{ texte.hinweis }}</p>
    </mat-dialog-content>
    <mat-dialog-actions class="sharepic-aktionen">
      <button mat-button type="button" class="sharepic-schliessen" mat-dialog-close>{{ texte.schliessen }}</button>
      <button mat-stroked-button type="button" class="sharepic-herunterladen" [disabled]="!datei" (click)="herunterladen()">
        <mat-icon aria-hidden="true">download</mat-icon>{{ texte.herunterladen }}
      </button>
      <button mat-flat-button type="button" class="sharepic-teilen" *ngIf="kannDateienTeilen" [disabled]="!datei" (click)="teilen()">
        <mat-icon aria-hidden="true">share</mat-icon>{{ texte.teilen }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [
    `
      .sharepic-inhalt { display: flex; flex-direction: column; gap: 12px; }
      .sharepic-format { align-self: flex-start; }
      .sharepic-format .mat-button-toggle { min-height: 44px; }
      .sharepic-format mat-icon { margin-right: 6px; vertical-align: middle; }
      /* Gewaehlt deutlich, auch im Dunkelmodus: Markenfarbe mit weisser Schrift wie der Hauptknopf */
      .sharepic-format .mat-button-toggle-checked { background-color: var(--primaer); color: white; font-weight: 700; }
      .sharepic-vorschau {
        display: flex; align-items: center; justify-content: center;
        aspect-ratio: 1 / 1; max-height: 50vh; margin: 0 auto; width: 100%;
        background: var(--mulde); border-radius: 8px;
      }
      .sharepic-vorschau.story { aspect-ratio: 9 / 16; width: auto; height: 50vh; }
      .sharepic-vorschau img { display: block; max-width: 100%; max-height: 100%; border-radius: 8px; }
      .sharepic-laedt { display: flex; align-items: center; gap: 12px; }
      .sharepic-fehler { display: flex; align-items: flex-start; gap: 6px; margin: 16px; color: var(--fehler); }
      .sharepic-hinweis { margin: 0; font-size: 0.875rem; color: var(--text-leise); }
      .sharepic-aktionen { flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
      .sharepic-aktionen button { min-height: 44px; }
      .sharepic-aktionen mat-icon { margin-right: 6px; }
      .sharepic-teilen:not([disabled]) { background-color: var(--primaer); color: white; }
    `,
  ],
})
export class SharepicDialogComponent implements OnInit, OnDestroy {
  readonly texte = SHAREPIC_TEXTE;
  readonly label = SHAREPIC_FORMAT_LABEL;
  readonly formate: SharepicFormat[] = ['quadrat', 'story'];
  format: SharepicFormat = 'quadrat';
  datei: File | null = null;
  vorschau: string | null = null;
  laedt = false;
  fehler = false;

  private readonly nav = inject(TEILEN_NAVIGATOR);
  private readonly cdr = inject(ChangeDetectorRef);
  private auftrag = 0;

  constructor(
    @Inject(MAT_DIALOG_DATA) readonly daten: SharepicDaten,
    private dialogRef: MatDialogRef<SharepicDialogComponent, SharepicErgebnis>,
  ) {}

  ngOnInit(): void {
    void this.malen();
  }

  ngOnDestroy(): void {
    // Etwas später: Ein Herunterladen direkt vor dem Schließen liest die Adresse noch.
    const adresse = this.vorschau;
    this.vorschau = null;
    if (adresse) {
      setTimeout(() => URL.revokeObjectURL(adresse), 10_000);
    }
  }

  /** Ob das Gerät Dateien über sein Teilen-Menü teilen kann; geprüft mit einer leeren PNG-Datei. */
  get kannDateienTeilen(): boolean {
    if (typeof this.nav.share !== 'function' || typeof this.nav.canShare !== 'function') {
      return false;
    }
    const probe = this.datei ?? new File([], 'probe.png', { type: 'image/png' });
    try {
      return this.nav.canShare({ files: [probe] });
    } catch {
      return false;
    }
  }

  /** Alternativtext der Vorschau: was im Bild steht. */
  get bildBeschreibung(): string {
    const titel = this.daten.titel?.trim();
    return `Vorschau, ${this.label[this.format]}: ${titel ? titel + '. ' : ''}${this.daten.text}`;
  }

  formatWaehlen(format: SharepicFormat): void {
    if (format === this.format) {
      return;
    }
    this.format = format;
    void this.malen();
  }

  async teilen(): Promise<void> {
    if (!this.datei || !this.nav.share) {
      return;
    }
    const titel = this.daten.titel?.trim();
    try {
      await this.nav.share({ files: [this.datei], title: titel || 'Gut gesagt', text: this.daten.link });
      this.dialogRef.close('geteilt');
    } catch (fehler) {
      if ((fehler as { name?: string } | null)?.name !== 'AbortError') {
        // Teilen ging nicht (etwa ohne Geste): dann wenigstens speichern.
        this.herunterladen();
      }
    }
  }

  herunterladen(): void {
    if (!this.datei || !this.vorschau) {
      return;
    }
    const link = document.createElement('a');
    link.href = this.vorschau;
    link.download = this.datei.name;
    link.rel = 'noopener';
    document.body.appendChild(link);
    link.click();
    link.remove();
    this.dialogRef.close('heruntergeladen');
  }

  private async malen(): Promise<void> {
    const auftrag = ++this.auftrag;
    this.laedt = true;
    this.fehler = false;
    this.datei = null;
    this.cdr.markForCheck();
    try {
      const datei = await sharepicDatei(this.daten, this.format);
      if (auftrag !== this.auftrag) {
        return;
      }
      this.vorschauFreigeben();
      this.datei = datei;
      this.vorschau = URL.createObjectURL(datei);
    } catch {
      if (auftrag === this.auftrag) {
        this.fehler = true;
      }
    } finally {
      if (auftrag === this.auftrag) {
        this.laedt = false;
        this.cdr.markForCheck();
      }
    }
  }

  private vorschauFreigeben(): void {
    if (this.vorschau) {
      URL.revokeObjectURL(this.vorschau);
      this.vorschau = null;
    }
  }
}

/** Öffnet den Dialog; schmal genug fürs Handy. */
export function sharepicDialogOeffnen(
  dialog: MatDialog,
  daten: SharepicDaten,
): MatDialogRef<SharepicDialogComponent, SharepicErgebnis> {
  return dialog.open<SharepicDialogComponent, SharepicDaten, SharepicErgebnis>(SharepicDialogComponent, {
    width: '520px',
    maxWidth: '95vw',
    data: daten,
    autoFocus: 'first-tabbable',
    ariaLabelledBy: 'sharepic-titel',
  });
}
