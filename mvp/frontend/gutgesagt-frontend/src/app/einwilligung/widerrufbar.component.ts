import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  DestroyRef,
  ElementRef,
  Input,
  OnInit,
  ViewChild,
  inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Observable, Subject } from 'rxjs';

import { environment } from '../../environments/environment';
import { LoggingService } from '../services/logging.service';
import { PunkteEinwilligungService } from '../shared/punkte-einwilligung/punkte-einwilligung.service';
import { merkerEntfernen } from '../meine-beitraege/meilenstein-merker';
import { SpielgefuehlService } from '../services/spielgefuehl.service';
import { nachladeStrom, ohneRechte, stillerKontext } from '../shared/selbst-nachladen';

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
 * gefragt wird beim Öffnen, danach im Takt von `nachladeStrom` (Oberflächen laden selbst
 * nach, auch ein Widerruf in einem anderen Tab kommt an), nach jedem Ausschalten, nach
 * einem Widerruf über das Punkte-Häkchen oder die Spielgefühl-Karte und wenn die Seite
 * selbst widerruft (`neuLaden`). Die Abfragen sind still: Nach abgelaufener Sitzung leitet
 * nichts auf /login um (die Datenschutzerklärung ist öffentlich), das Nachladen hört auf.
 *
 * Eingebunden in den Datenschutz-Einstellungen, auf der Datenschutzseite (Anker
 * `#einwilligung-widerrufen`) und unter „Meine Beiträge“.
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
    <section *ngIf="zeilen.length" class="widerrufbar" [class.karte]="karte" aria-labelledby="widerrufbar-titel" data-testid="widerrufbar">
      <ng-container [ngSwitch]="ebene">
        <h2 *ngSwitchCase="2" id="widerrufbar-titel">{{ titel }}</h2>
        <h4 *ngSwitchCase="4" id="widerrufbar-titel">{{ titel }}</h4>
        <h3 *ngSwitchDefault id="widerrufbar-titel">{{ titel }}</h3>
      </ng-container>
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
    <p *ngIf="geladen && !zeilen.length && leerText" class="leer" data-testid="widerrufbar-leer">{{ leerText }}</p>
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
      /* Als eigene Karte unter „Meine Beiträge“, wie die Spielgefühl-Karte */
      .widerrufbar.karte {
        margin: 0 0 var(--spacing-md);
        padding: 12px 16px;
        border: 1px solid var(--feldrand);
        border-radius: 8px;
      }
      .widerrufbar.karte h2 {
        font-size: 1.1rem;
      }
      h2,
      h3,
      h4 {
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
  private readonly spielgefuehlDienst = inject(SpielgefuehlService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly destroyRef = inject(DestroyRef);

  /** Ebene der Überschrift, passend zur Gliederung der Seite (WCAG 1.3.1). */
  @Input() ebene: 2 | 3 | 4 = 3;
  /**
   * Steht das Häkchen „Punkte und Meilensteine“ auf derselben Seite (Datenschutz-Einstellungen)?
   * Nur dann fehlt die Punkte-Zeile, solange das Häkchen den Widerruf selbst anbietet.
   */
  @Input() punkteHaekchenDaneben = true;
  /**
   * Steht die Spielgefühl-Karte auf derselben Seite („Meine Beiträge“)? Dann fehlt die
   * Spielgefühl-Zeile, sobald die Karte die gewählte Stufe samt „Aus“ zeigt; ist die Karte
   * leer (Schalter spielgefuehl_buehne aus) oder ihr Stand unbekannt, steht die Zeile:
   * Im Zweifel lieber doppelt als kein Weg zum Widerruf.
   */
  @Input() spielgefuehlKarteDaneben = false;
  /** Mit Rahmen als eigene Karte („Meine Beiträge“). */
  @Input() karte = false;
  /** Satz, wenn nichts zu widerrufen ist; leer: dann zeigt die Komponente nichts. */
  @Input() leerText = '';

  readonly titel = 'Spielgefühl und Punkte ausschalten';
  private stand: Widerrufbar | null = null;
  /** Der erste Stand ist da: erst dann darf `leerText` stehen. */
  geladen = false;
  /** Das Häkchen „Punkte und Meilensteine“ hat eine Einwilligung (gemeinsamer Stand). */
  private punkteImHaekchen = false;
  /** Die Spielgefühl-Karte zeigt eine Stufe; undefined: noch nicht bekannt. */
  private karteZeigtSpielgefuehl: boolean | undefined = undefined;
  private karteStufe: string | null | undefined = undefined;
  /** Nach dem Ausschalten: diese Zeile ist erledigt, danach den Fokus versetzen. */
  private fokusNach: WiderrufArt | null = null;
  private readonly anstoss$ = new Subject<void>();
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
        this.anstoss$.next();
      }
      this.zeilenBauen();
    });
    this.spielgefuehlDienst.stand$.pipe(takeUntilDestroyed()).subscribe((stand) => {
      this.karteZeigtSpielgefuehl = stand === undefined ? undefined : !!stand && stand.stufe !== null;
      const stufe = stand === undefined ? undefined : (stand?.stufe ?? null);
      if (this.geladen && this.karteStufe !== undefined && stufe !== undefined && stufe !== this.karteStufe) {
        // Auf der Karte geändert: Was widerrufbar ist, hat sich mit geändert.
        this.anstoss$.next();
      }
      this.karteStufe = stufe;
      this.zeilenBauen();
    });
  }

  /** Nach einem Widerruf auf derselben Seite (Art.-9-Einwilligung): Stand neu holen. */
  neuLaden(): void {
    this.anstoss$.next();
  }

  ngOnInit(): void {
    const abo = nachladeStrom(
      () => this.http.get<Widerrufbar>(`${BASIS}/usage/users/me/widerrufbar`, { context: stillerKontext() }),
      { sofort: true, aufhoerenBei: ohneRechte, anstoss$: this.anstoss$ },
    ).subscribe((lauf) => {
      const nachAusschalten = this.fokusNach;
      this.fokusNach = null;
      if (lauf.fehler === null) {
        this.stand = lauf.daten;
        this.geladen = true;
        this.zeilenBauen();
        if (nachAusschalten) this.fokusNachAusschalten();
        return;
      }
      // Ohne Stand keine neuen Zeilen; nach einem Ausschalten die erledigte Zeile trotzdem weg.
      this.logger.error('Widerrufbares nicht geladen', lauf.fehler as Error);
      if (ohneRechte(lauf.fehler)) {
        // Sitzung abgelaufen: Knöpfe ohne Wirkung zeigen wir nicht.
        this.stand = null;
        this.geladen = false;
        this.zeilenBauen();
      } else if (nachAusschalten && this.stand) {
        this.stand = { ...this.stand, [nachAusschalten]: null };
        this.zeilenBauen();
        this.fokusNachAusschalten();
      }
    });
    this.destroyRef.onDestroy(() => abo.unsubscribe());
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
    if (s?.spielgefuehl && !(this.spielgefuehlKarteDaneben && this.karteZeigtSpielgefuehl === true)) {
      zeilen.push({ art: 'spielgefuehl', text: `Spielgefühl: ${s.spielgefuehl.titel}` });
    }
    if (s?.punkte && !(this.punkteHaekchenDaneben && this.punkteImHaekchen)) {
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
        this.fokusNach = art;
        this.anstoss$.next();
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
