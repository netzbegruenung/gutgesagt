import { Component, DestroyRef, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subject } from 'rxjs';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ohneRechte, selbstNachladen } from '../../shared/selbst-nachladen';
import { AuffaelligeHerkunft, HerkunftPruefenService, HerkunftPruefenStand } from './herkunft-pruefen.service';

/** Symbol und Wort je Ergebnis: nie nur Farbe oder nur Symbol. */
const ART: Record<string, { icon: string; wort: string }> = {
  tot: { icon: 'link_off', wort: 'Nicht gefunden' },
  umgezogen: { icon: 'east', wort: 'Umgezogen' },
  fehler: { icon: 'error_outline', wort: 'Fehler beim Abruf' },
  nicht_erreichbar: { icon: 'cloud_off', wort: 'Nicht erreichbar' },
  gesperrt: { icon: 'block', wort: 'Nicht geprüft: Adresse nicht erlaubt' },
};

const DATUM = new Intl.DateTimeFormat('de-DE', { day: 'numeric', month: 'numeric', year: 'numeric' });
const ZEIT = new Intl.DateTimeFormat('de-DE', { day: 'numeric', month: 'numeric', hour: '2-digit', minute: '2-digit' });

/**
 * Herkunft prüfen (#759) in der Übersicht: tote oder umgezogene Links unter „Herkunft“, nachts
 * geprüft. Ist der Schalter „herkunft_pruefen“ aus, steht hier nichts, auch keine leere Karte.
 * Lädt selbst nach; nach „Jetzt prüfen“ sofort und dann im Takt, bis der Lauf fertig ist.
 */
@Component({
  selector: 'app-herkunft-pruefen',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatCardModule, MatIconModule, MatProgressSpinnerModule, MatSnackBarModule],
  template: `
    <mat-card *ngIf="stand?.aktiv" class="herkunft-pruefen" data-testid="herkunft-pruefen">
      <mat-card-header>
        <mat-card-title>
          <mat-icon aria-hidden="true">link_off</mat-icon>
          Links unter „Herkunft“
        </mat-card-title>
        <mat-card-subtitle>
          Nachts geprüft: Links, die nicht mehr gehen oder umgezogen sind. An den Beiträgen ändert sich dadurch nichts.
        </mat-card-subtitle>
      </mat-card-header>
      <mat-card-content>
        <div class="kopfzeile">
          <p class="zusammenfassung" data-testid="zusammenfassung">{{ zusammenfassung(stand!) }}</p>
          <button mat-stroked-button type="button" (click)="anstossen()" [disabled]="stand!.laeuft || startet">
            <mat-icon aria-hidden="true">refresh</mat-icon>
            Jetzt prüfen
          </button>
        </div>
        <p *ngIf="stand!.laeuft" class="laeuft" role="status">
          <mat-spinner diameter="16" aria-hidden="true"></mat-spinner>
          Prüfung läuft, die Liste füllt sich von selbst …
        </p>

        <ul *ngIf="stand!.auffaellig.length; else alleGut" class="liste">
          <li *ngFor="let h of stand!.auffaellig; trackBy: kennung" [class]="'eintrag ' + h.ergebnis" data-testid="auffaellig">
            <p class="art">
              <mat-icon aria-hidden="true">{{ art(h).icon }}</mat-icon>
              <span>{{ artText(h) }}</span>
            </p>
            <a class="adresse" [href]="h.adresse" target="_blank" rel="noopener noreferrer nofollow">{{ h.adresse }}</a>
            <p *ngIf="h.ziel" class="ziel">
              <mat-icon aria-hidden="true">subdirectory_arrow_right</mat-icon>
              <span>Jetzt: <a [href]="h.ziel" target="_blank" rel="noopener noreferrer nofollow">{{ h.ziel }}</a></span>
            </p>
            <p *ngIf="h.auffaellig_seit" class="seit">Auffällig seit {{ datum(h.auffaellig_seit) }}</p>
          </li>
        </ul>
        <ng-template #alleGut>
          <p *ngIf="stand!.geprueft" class="hinweis">
            <mat-icon aria-hidden="true">check_circle</mat-icon>
            Alle geprüften Links gehen.
          </p>
        </ng-template>
      </mat-card-content>
    </mat-card>
  `,
  styles: [`
    .herkunft-pruefen { margin-top: 24px; }
    .kopfzeile { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 16px; }
    .zusammenfassung { margin: 0; }
    .laeuft, .hinweis { display: flex; align-items: center; gap: 8px; margin: 12px 0 0; color: var(--text-leise); }
    .hinweis mat-icon { color: var(--akzent-schrift); }
    .liste { list-style: none; margin: 12px 0 0; padding: 0; }
    .eintrag { padding: 12px 0; border-bottom: 1px solid var(--linie); overflow-wrap: anywhere; }
    .eintrag:last-child { border-bottom: none; }
    .eintrag p { margin: 0; }
    .art { display: flex; align-items: center; gap: 6px; font-weight: 700; }
    .art mat-icon, .ziel mat-icon { flex-shrink: 0; font-size: 20px; width: 20px; height: 20px; }
    .adresse { display: inline-block; margin: 4px 0 0; }
    .adresse, .ziel a { color: var(--primaer-text); text-decoration: underline; }
    .ziel { display: flex; align-items: flex-start; gap: 6px; margin-top: 4px !important; }
    .seit { margin-top: 4px !important; font-size: 0.875rem; color: var(--text-leise); }
  `],
})
export class HerkunftPruefenComponent implements OnInit {
  stand: HerkunftPruefenStand | null = null;
  startet = false;

  private readonly destroyRef = inject(DestroyRef);
  private readonly dienst = inject(HerkunftPruefenService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly anstoss$ = new Subject<void>();

  ngOnInit(): void {
    const folgen = { next: (daten: HerkunftPruefenStand) => (this.stand = daten) };
    this.dienst.stand().subscribe({ ...folgen, error: () => undefined });
    selbstNachladen(() => this.dienst.stand(true), this.destroyRef, folgen, {
      // Waehrend eines Laufs oefter, sonst im ueblichen Takt
      ms: () => (this.stand?.laeuft ? 5_000 : 60_000),
      aufhoerenBei: ohneRechte,
      anstoss$: this.anstoss$,
    });
  }

  anstossen(): void {
    this.startet = true;
    this.dienst.anstossen().subscribe({
      next: () => {
        this.startet = false;
        this.anstoss$.next();
      },
      error: (fehler: { status?: number }) => {
        this.startet = false;
        this.anstoss$.next();
        if (fehler?.status !== 409) {
          this.snackBar.open('Prüfung nicht gestartet, bitte gleich noch einmal versuchen.', 'OK', { duration: 6000 });
        }
      },
    });
  }

  zusammenfassung(s: HerkunftPruefenStand): string {
    if (!s.letzter_lauf) {
      return s.laeuft ? 'Erste Prüfung läuft.' : 'Noch nicht geprüft; die erste Prüfung läuft heute Nacht.';
    }
    const zahl = s.auffaellig.length;
    const auffaellig = zahl === 1 ? '1 auffällig' : `${zahl} auffällig`;
    return `${s.geprueft} Links geprüft, ${auffaellig}, zuletzt ${ZEIT.format(new Date(s.letzter_lauf))}`;
  }

  art(h: AuffaelligeHerkunft): { icon: string; wort: string } {
    return ART[h.ergebnis] ?? { icon: 'help_outline', wort: h.ergebnis };
  }

  artText(h: AuffaelligeHerkunft): string {
    const wort = this.art(h).wort;
    return h.http_status && h.ergebnis !== 'umgezogen' ? `${wort} (HTTP ${h.http_status})` : wort;
  }

  datum(wert: string): string {
    return DATUM.format(new Date(wert));
  }

  kennung(_: number, h: AuffaelligeHerkunft): string {
    return h.herkunft_id;
  }
}
