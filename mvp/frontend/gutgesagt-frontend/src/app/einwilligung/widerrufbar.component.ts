import { ChangeDetectionStrategy, ChangeDetectorRef, Component, ElementRef, OnInit, ViewChild, inject } from '@angular/core';
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
  /** „Team öffentlich am Namen zeigen“; fehlt bei einem älteren Backend. */
  team_oeffentlich?: { wortlaut: string } | null;
}

export type WiderrufArt = 'spielgefuehl' | 'punkte' | 'rangliste' | 'abzeichen' | 'team_oeffentlich';

export interface WiderrufZeile {
  art: WiderrufArt;
  /** „Spielgefühl: Nur für mich“ – was gespeichert ist, ohne Werbung fürs Ja. */
  text: string;
}

const BASIS = `${environment.baseUrl}/api/v1`;

/**
 * Widerruf jederzeit, auch wenn die Schalter aus sind (Art. 7 Abs. 3 DSGVO): je
 * gespeicherter Einwilligung zu Spielgefühl, Punkten, Rangliste, Abzeichen am Namen und
 * Teams am Namen („Team öffentlich am Namen zeigen“, auch bei Schalter teams_oeffentlich aus),
 * die nicht „aus“ ist, eine Zeile „… · Ausschalten“. Sie zeigt kein Ja und fragt nach
 * nichts; Einwilligen geht nur dort, wo die Frage steht. Die Punkte-Zeile fehlt, solange
 * das Häkchen „Punkte und Meilensteine“ darunter selbst den Widerruf anbietet.
 *
 * Der Server antwortet immer 200 (auch bei ausgeschalteten Schaltern, Gateway-fail2ban);
 * gefragt wird beim Öffnen der Seite, nach jedem Ausschalten, nach einem Widerruf über das
 * Punkte-Häkchen und wenn die Seite selbst widerruft (`neuLaden`).
 *
 * Nach dem Ausschalten verschwindet die Zeile samt Knopf: Der Fokus geht auf die nächste
 * Zeile oder, wenn keine bleibt, auf den Bereich mit der Bestätigung (WCAG 2.4.3); die
 * Bestätigung steht in einer Live-Region außerhalb der Zeilen (WCAG 4.1.3).
 */
@Component({
  selector: 'app-widerrufbar',
  standalone: true,
  imports: [CommonModule, MatButtonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section *ngIf="zeilen.length" class="widerrufbar" aria-labelledby="widerrufbar-titel" data-testid="widerrufbar">
      <h3 id="widerrufbar-titel">Einwilligungen ausschalten</h3>
      <ul>
        <li *ngFor="let zeile of zeilen; trackBy: art" [attr.data-testid]="'widerruf-' + zeile.art">
          <span>{{ zeile.text }}</span>
          <span aria-hidden="true"> · </span>
          <button mat-stroked-button type="button" (click)="ausschalten(zeile.art)" [disabled]="laeuft !== null"
            [attr.aria-label]="'Ausschalten: ' + zeile.text">
            Ausschalten
          </button>
        </li>
      </ul>
    </section>
    <!-- Außerhalb der Zeilen: bleibt stehen, auch wenn die letzte Zeile geht -->
    <div #meldungsBereich tabindex="-1" class="meldungen">
      <p role="status" data-testid="widerruf-status" class="status">{{ meldung }}</p>
      <p *ngIf="fehler" class="warnung" role="alert" data-testid="widerruf-fehler">
        Das hat nicht geklappt. Bitte versuch es gleich noch einmal.
      </p>
    </div>
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
      .meldungen:focus {
        outline: none;
      }
      .status:empty {
        display: none;
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
  /** Bestätigung nach dem Ausschalten, für Screenreader (role="status"). */
  meldung = '';
  @ViewChild('meldungsBereich') private meldungsBereich?: ElementRef<HTMLElement>;
  private readonly host = inject(ElementRef<HTMLElement>);

  readonly art = (_: number, zeile: WiderrufZeile) => zeile.art;

  constructor() {
    this.punkteDienst.stand$.pipe(takeUntilDestroyed()).subscribe((stand) => {
      const vorher = this.punkteImHaekchen;
      this.punkteImHaekchen = !!stand?.eingewilligt;
      if (vorher && !this.punkteImHaekchen) {
        // Über das Häkchen widerrufen: Die Punkte-Zeile darf nicht mit altem Stand wiederkommen,
        // und der Server hat dabei auch das Spielgefühl auf „aus“ gesetzt.
        this.stand = this.stand ? { ...this.stand, punkte: null } : this.stand;
        this.laden();
      }
      this.zeilenBauen();
    });
  }

  /** Nach einem Widerruf auf derselben Seite (Art.-9-Einwilligung): Stand neu holen. */
  neuLaden(): void {
    this.laden();
  }

  ngOnInit(): void {
    this.laden();
  }

  private laden(nachAusschalten: WiderrufArt | null = null): void {
    this.http.get<Widerrufbar>(`${BASIS}/usage/users/me/widerrufbar`).subscribe({
      next: (stand) => {
        this.stand = stand;
        this.zeilenBauen();
        if (nachAusschalten) this.fokusNachAusschalten();
      },
      error: (fehler) => {
        // Ohne Stand keine neuen Zeilen; nach einem Ausschalten die erledigte Zeile trotzdem weg.
        this.logger.error('Widerrufbares nicht geladen', fehler);
        if (nachAusschalten && this.stand) {
          this.stand = { ...this.stand, [nachAusschalten]: null };
          this.zeilenBauen();
          this.fokusNachAusschalten();
        }
      },
    });
  }

  /** Die Zeile samt Knopf ist weg: Fokus auf die nächste Zeile oder den Meldungsbereich. */
  private fokusNachAusschalten(): void {
    this.cdr.detectChanges();
    const naechster = (this.host.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('li button');
    (naechster ?? this.meldungsBereich?.nativeElement)?.focus();
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
    if (s?.team_oeffentlich) {
      zeilen.push({ art: 'team_oeffentlich', text: 'Teams am Namen: sichtbar' });
    }
    this.zeilen = zeilen;
    this.cdr.markForCheck();
  }

  ausschalten(art: WiderrufArt): void {
    const anfrage = this.anfrage(art);
    if (!anfrage || this.laeuft !== null) return;
    const text = this.zeilen.find((z) => z.art === art)?.text ?? '';
    this.laeuft = art;
    this.fehler = false;
    this.meldung = '';
    anfrage.subscribe({
      next: () => {
        this.laeuft = null;
        this.meldung = `Ausgeschaltet: ${text}`;
        if (art === 'punkte' || art === 'spielgefuehl') {
          // Ohne Punkte keine Meilensteine: ihr Merker im Browser geht mit.
          merkerEntfernen();
        }
        // Das Häkchen „Punkte und Meilensteine“ zeigt danach den neuen Stand.
        this.punkteDienst.laden().subscribe();
        this.laden(art);
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
      case 'team_oeffentlich':
        return s?.team_oeffentlich
          ? this.http.put(`${BASIS}/teams/oeffentlich`, {
              zeigen: false,
              wortlaut: s.team_oeffentlich.wortlaut,
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
