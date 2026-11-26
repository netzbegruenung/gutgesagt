import { Component, DestroyRef, Injectable, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { environment } from '../../../environments/environment';
import { ohneRechte, selbstNachladen, stillerKontext } from '../../shared/selbst-nachladen';

export interface AnkunftZeile {
  /** UTC-Tag, ISO (2026-12-04) */
  tag: string;
  k: string;
  anzahl: number;
}

export interface AnkuenfteStand {
  /** Schalter `k_ankuenfte` wirksam; sonst ist `tage` leer. */
  aktiv: boolean;
  tage: AnkunftZeile[];
}

/** Ankünfte je Kampagnenwort und Tag, nur für Admins. */
@Injectable({ providedIn: 'root' })
export class AnkuenfteService {
  private readonly http = inject(HttpClient);

  stand(still = false): Observable<AnkuenfteStand> {
    return this.http.get<AnkuenfteStand>(`${environment.baseUrl}/api/v1/ankuenfte`, {
      context: still ? stillerKontext() : undefined,
    });
  }
}

const DATUM = new Intl.DateTimeFormat('de-DE', { weekday: 'short', day: 'numeric', month: 'numeric', timeZone: 'UTC' });

/**
 * Ankünfte je Kampagnenwort (?k=) und Tag in der Übersicht: eine kleine Tabelle der letzten
 * 30 Tage, neueste zuerst. Nur Zahlen je Wort und Tag, keine Person. Ist der Schalter
 * `k_ankuenfte` aus, steht hier nichts, auch keine leere Karte. Lädt selbst nach.
 */
@Component({
  selector: 'app-ankuenfte',
  standalone: true,
  imports: [CommonModule, MatCardModule, MatIconModule],
  template: `
    <mat-card *ngIf="stand?.aktiv" class="ankuenfte" data-testid="ankuenfte">
      <mat-card-header>
        <mat-card-title>
          <mat-icon aria-hidden="true">qr_code_2</mat-icon>
          Ankünfte je Kampagnenwort
        </mat-card-title>
        <mat-card-subtitle>
          Wie oft die App mit ?k=… geöffnet wurde, je Wort und Tag (UTC), letzte 30 Tage. Ohne Personenbezug.
        </mat-card-subtitle>
      </mat-card-header>
      <mat-card-content>
        <table *ngIf="stand!.tage.length; else leer" class="tabelle">
          <thead>
            <tr><th scope="col">Tag</th><th scope="col">Wort</th><th scope="col" class="zahl">Ankünfte</th></tr>
          </thead>
          <tbody>
            <tr *ngFor="let z of stand!.tage" data-testid="ankunft-zeile">
              <td>{{ datum(z.tag) }}</td>
              <td><code>{{ z.k }}</code></td>
              <td class="zahl">{{ z.anzahl }}</td>
            </tr>
          </tbody>
        </table>
        <ng-template #leer>
          <p class="hinweis" data-testid="ankuenfte-leer">Noch keine Ankünfte mit Kampagnenwort.</p>
        </ng-template>
      </mat-card-content>
    </mat-card>
  `,
  styles: [`
    .ankuenfte { margin-top: 24px; }
    .tabelle { border-collapse: collapse; width: 100%; max-width: 480px; }
    .tabelle th, .tabelle td { padding: 6px 8px; text-align: left; border-bottom: 1px solid var(--linie); }
    .tabelle th { font-weight: 700; }
    .zahl { text-align: right !important; font-variant-numeric: tabular-nums; }
    .hinweis { margin: 0; color: var(--text-leise); }
  `],
})
export class AnkuenfteComponent implements OnInit {
  stand: AnkuenfteStand | null = null;

  private readonly destroyRef = inject(DestroyRef);
  private readonly dienst = inject(AnkuenfteService);

  ngOnInit(): void {
    const folgen = { next: (daten: AnkuenfteStand) => (this.stand = daten) };
    this.dienst.stand().subscribe({ ...folgen, error: () => undefined });
    selbstNachladen(() => this.dienst.stand(true), this.destroyRef, folgen, {
      ms: 60_000,
      aufhoerenBei: ohneRechte,
    });
  }

  datum(tag: string): string {
    return DATUM.format(new Date(`${tag}T00:00:00Z`));
  }
}
