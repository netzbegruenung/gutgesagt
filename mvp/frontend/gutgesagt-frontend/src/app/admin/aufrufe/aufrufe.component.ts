import { Component, DestroyRef, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { environment } from '../../../environments/environment';
import { ohneRechte, selbstNachladen, stillerKontext } from '../../shared/selbst-nachladen';

export interface AufrufTag {
  tag: string;
  aufrufe: number;
  besucher: number;
}

export interface AufrufeStand {
  /** Schalter „aufrufe_zaehlen“ wirksam; sonst ist alles andere leer. */
  aktiv: boolean;
  heute: AufrufTag | null;
  tage: AufrufTag[];
}

const TAG = new Intl.DateTimeFormat('de-DE', { weekday: 'short', day: 'numeric', month: 'numeric', timeZone: 'UTC' });
const ZAHL = new Intl.NumberFormat('de-DE');

/**
 * Seitenaufrufe und Besucher je Tag (#761) unter Kennzahlen: Zahlen als Text, daneben ein Balken
 * für die Besucher (nur Schmuck, die Zahl steht daneben). Ist der Schalter „aufrufe_zaehlen“ aus,
 * steht hier nichts, auch keine leere Karte. Lädt selbst nach.
 */
@Component({
  selector: 'app-aufrufe',
  standalone: true,
  imports: [CommonModule, MatCardModule, MatIconModule],
  template: `
    <mat-card *ngIf="stand?.aktiv" class="aufrufe" data-testid="aufrufe">
      <mat-card-header>
        <mat-card-title>
          <mat-icon aria-hidden="true">visibility</mat-icon>
          Aufrufe und Besucher pro Tag
        </mat-card-title>
        <mat-card-subtitle>
          Auch wer nur liest: gezählt am Server aus Startseite, Suche, Thema und Beitrag, dieselbe Seite binnen fünf
          Minuten einmal. Ohne IP-Adresse und ohne Cookie: Ein Besucher ist ein Anschluss an einem Tag
          (Tagespseudonym), am Tagesende bleiben nur die zwei Zahlen. Tage nach UTC.
        </mat-card-subtitle>
      </mat-card-header>
      <mat-card-content>
        <table>
          <thead>
            <tr>
              <th scope="col">Tag</th>
              <th scope="col" class="zahl">Aufrufe</th>
              <th scope="col" class="zahl">Besucher</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let t of zeilen()" [class.heute]="t === stand!.heute" data-testid="aufruf-tag">
              <th scope="row">{{ t === stand!.heute ? 'Heute bisher' : tag(t.tag) }}</th>
              <td class="zahl">{{ zahl(t.aufrufe) }}</td>
              <td class="besucher">
                <span class="besucher-zahl">{{ zahl(t.besucher) }}</span>
                <!-- Nur Schmuck: die Zahl steht daneben -->
                <span class="balken-spur" aria-hidden="true"><span class="balken" [style.width.%]="anteil(t)"></span></span>
              </td>
            </tr>
          </tbody>
        </table>
        <p *ngIf="!stand!.tage.length" class="hinweis">Abgeschlossene Tage erscheinen hier ab morgen.</p>
      </mat-card-content>
    </mat-card>
  `,
  styles: [`
    .aufrufe { margin-top: 24px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 8px; border-bottom: 1px solid var(--linie); }
    tbody th { font-weight: 400; white-space: nowrap; }
    tr.heute th, tr.heute td { font-weight: 700; }
    .zahl { text-align: right; white-space: nowrap; width: 1%; }
    .besucher { display: flex; align-items: center; gap: 8px; }
    .besucher-zahl { min-width: 3ch; text-align: right; font-variant-numeric: tabular-nums; }
    .balken-spur { flex: 1 1 auto; min-width: 48px; }
    .balken { display: block; height: 10px; min-width: 2px; border-radius: 5px; background: var(--akzent-tanne); }
    .hinweis { color: var(--text-leise); margin: 12px 0 0; }
    @media (max-width: 479px) {
      th, td { padding: 6px 4px; }
    }
  `],
})
export class AufrufeComponent implements OnInit {
  stand: AufrufeStand | null = null;

  private readonly http = inject(HttpClient);
  private readonly destroyRef = inject(DestroyRef);
  private readonly url = `${environment.baseUrl}/api/v1/aufrufe`;

  ngOnInit(): void {
    const folgen = { next: (daten: AufrufeStand) => (this.stand = daten) };
    this.http.get<AufrufeStand>(this.url).subscribe({ ...folgen, error: () => undefined });
    selbstNachladen(() => this.http.get<AufrufeStand>(this.url, { context: stillerKontext() }), this.destroyRef, folgen, {
      ms: 60_000,
      aufhoerenBei: ohneRechte,
    });
  }

  /** Heute zuerst, dann die abgeschlossenen Tage, neueste zuerst. */
  zeilen(): AufrufTag[] {
    const s = this.stand;
    return s ? [...(s.heute ? [s.heute] : []), ...s.tage] : [];
  }

  anteil(t: AufrufTag): number {
    const groesste = Math.max(1, ...this.zeilen().map((z) => z.besucher));
    return Math.round((t.besucher / groesste) * 100);
  }

  tag(wert: string): string {
    return TAG.format(new Date(`${wert}T00:00:00Z`));
  }

  zahl(wert: number): string {
    return ZAHL.format(wert);
  }
}
