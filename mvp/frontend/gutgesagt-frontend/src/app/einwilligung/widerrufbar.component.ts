import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { LoggingService } from '../services/logging.service';
import { PunkteEinwilligungService } from '../shared/punkte-einwilligung/punkte-einwilligung.service';
import { merkerEntfernen } from '../meine-beitraege/meilenstein-merker';

/** GET /api/v1/usage/users/me/widerrufbar: gespeicherte Antworten über Nein bzw. „aus“. */
export interface Widerrufbar {
  /** titel: der Name der Stufe aus dem Wortlaut des Servers. */
  spielgefuehl: { stufe: 'fuer_mich' | 'rangliste'; titel: string; wortlaut: string } | null;
  punkte: { wortlaut: string } | null;
  rangliste: { wortlaut: string } | null;
  abzeichen: { wortlaut: string } | null;
}

export type WiderrufArt = 'spielgefuehl' | 'punkte' | 'rangliste' | 'abzeichen';

export interface WiderrufZeile {
  art: WiderrufArt;
  /** „Spielgefühl: Nur für mich“ – was gespeichert ist, ohne Werbung fürs Ja. */
  text: string;
}

const BASIS = `${environment.baseUrl}/api/v1`;

/**
 * Widerruf jederzeit, auch wenn die Schalter aus sind (Art. 7 Abs. 3 DSGVO): je
 * gespeicherter Einwilligung zu Spielgefühl, Punkten, Rangliste und Abzeichen am Namen,
 * die nicht „aus“ ist, eine Zeile „… · Ausschalten“. Sie zeigt kein Ja und fragt nach
 * nichts; Einwilligen geht nur dort, wo die Frage steht. Die Punkte-Zeile fehlt, solange
 * das Häkchen „Punkte und Meilensteine“ darunter selbst den Widerruf anbietet.
 *
 * Der Server antwortet immer 200 (auch bei ausgeschalteten Schaltern, Gateway-fail2ban);
 * gefragt wird einmal beim Öffnen der Seite und nach jedem Ausschalten.
 */
@Component({
  selector: 'app-widerrufbar',
  standalone: true,
  imports: [CommonModule, MatButtonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section *ngIf="zeilen.length" class="widerrufbar" aria-labelledby="widerrufbar-titel" data-testid="widerrufbar">
      <h3 id="widerrufbar-titel">Spielgefühl und Punkte</h3>
      <ul>
        <li *ngFor="let zeile of zeilen" [attr.data-testid]="'widerruf-' + zeile.art">
          <span>{{ zeile.text }}</span>
          <span aria-hidden="true"> · </span>
          <button mat-stroked-button type="button" (click)="ausschalten(zeile.art)" [disabled]="laeuft !== null"
            [attr.aria-label]="'Ausschalten: ' + zeile.text">
            Ausschalten
          </button>
        </li>
      </ul>
      <p *ngIf="fehler" class="warnung" role="alert" data-testid="widerruf-fehler">
        Das hat nicht geklappt. Bitte versuch es gleich noch einmal.
      </p>
    </section>
  `,
  styles: [
    `
      .widerrufbar {
        margin-top: 24px;
      }
      h3 {
        font-size: 16px;
        margin: 0 0 8px;
      }
      ul {
        list-style: none;
        padding: 0;
        margin: 0;
      }
      li {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 4px 8px;
        margin: 0 0 8px;
      }
      .warnung {
        color: var(--fehler);
      }
    `,
  ],
})
export class WiderrufbarComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly logger = inject(LoggingService);
  private readonly punkteDienst = inject(PunkteEinwilligungService);
  private readonly cdr = inject(ChangeDetectorRef);

  private stand: Widerrufbar | null = null;
  /** Das Häkchen „Punkte und Meilensteine“ bietet den Widerruf selbst an. */
  private punkteImHaekchen = false;
  zeilen: WiderrufZeile[] = [];
  laeuft: WiderrufArt | null = null;
  fehler = false;

  constructor() {
    this.punkteDienst.stand$.pipe(takeUntilDestroyed()).subscribe((stand) => {
      this.punkteImHaekchen = !!stand?.eingewilligt;
      this.zeilenBauen();
    });
  }

  ngOnInit(): void {
    this.laden();
  }

  private laden(): void {
    this.http.get<Widerrufbar>(`${BASIS}/usage/users/me/widerrufbar`).subscribe({
      next: (stand) => {
        this.stand = stand;
        this.zeilenBauen();
      },
      // Ohne Stand keine Zeilen; die Fragen selbst bleiben, wo sie sind.
      error: (fehler) => this.logger.error('Widerrufbares nicht geladen', fehler),
    });
  }

  private zeilenBauen(): void {
    const s = this.stand;
    const zeilen: WiderrufZeile[] = [];
    if (s?.spielgefuehl) {
      zeilen.push({ art: 'spielgefuehl', text: `Spielgefühl: ${s.spielgefuehl.titel}` });
    }
    if (s?.punkte && !this.punkteImHaekchen) {
      zeilen.push({ art: 'punkte', text: 'Punkte und Meilensteine: an' });
    }
    if (s?.rangliste) {
      zeilen.push({ art: 'rangliste', text: 'Rangliste: dabei' });
    }
    if (s?.abzeichen) {
      zeilen.push({ art: 'abzeichen', text: 'Abzeichen am Namen: sichtbar' });
    }
    this.zeilen = zeilen;
    this.cdr.markForCheck();
  }

  ausschalten(art: WiderrufArt): void {
    const anfrage = this.anfrage(art);
    if (!anfrage || this.laeuft !== null) return;
    this.laeuft = art;
    this.fehler = false;
    anfrage.subscribe({
      next: () => {
        this.laeuft = null;
        if (art === 'punkte' || art === 'spielgefuehl') {
          // Ohne Punkte keine Meilensteine: ihr Merker im Browser geht mit.
          merkerEntfernen();
        }
        // Das Häkchen „Punkte und Meilensteine“ zeigt danach den neuen Stand.
        this.punkteDienst.laden().subscribe();
        this.laden();
      },
      error: (fehler) => {
        this.logger.error('Widerruf nicht gespeichert', fehler);
        this.laeuft = null;
        this.fehler = true;
        this.cdr.markForCheck();
      },
    });
  }

  private anfrage(art: WiderrufArt): Observable<unknown> | null {
    const s = this.stand;
    switch (art) {
      case 'spielgefuehl':
        return s?.spielgefuehl
          ? this.http.put(`${BASIS}/usage/users/me/spielgefuehl`, {
              stufe: 'aus',
              mit_anzeigename: null,
              wortlaut: s.spielgefuehl.wortlaut,
            })
          : null;
      case 'punkte':
        return s?.punkte
          ? this.http.put(`${BASIS}/usage/users/me/punkte-einwilligung`, {
              eingewilligt: false,
              wortlaut: s.punkte.wortlaut,
            })
          : null;
      case 'rangliste':
        return s?.rangliste
          ? this.http.put(`${BASIS}/rangliste/einwilligung`, {
              teilnehmen: false,
              mit_anzeigename: false,
              wortlaut: s.rangliste.wortlaut,
            })
          : null;
      case 'abzeichen':
        return s?.abzeichen
          ? this.http.put(`${BASIS}/usage/users/me/abzeichen-sichtbarkeit`, {
              zeigen: false,
              wortlaut: s.abzeichen.wortlaut,
            })
          : null;
    }
  }
}
