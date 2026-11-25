import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { BreakpointObserver } from '@angular/cdk/layout';
import { ContentService, RecentContentResponse } from '../services/content.service';
import { LoggingService } from '../services/logging.service';
import { ContentRefreshService } from '../services/content-refresh.service';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { ResultCarouselComponent } from '../result-carousel/result-carousel.component';
import { KartenlisteComponent } from '../beitragskarte/kartenliste.component';
import { KartenDaten, ausSuchergebnis } from '../beitragskarte/karten-daten';
import { LoadingSpinnerComponent } from '../shared/components/loading-spinner/loading-spinner.component';
import { ErrorMessageComponent } from '../shared/components/error-message/error-message.component';
import { ROUTES } from '../shared/constants/app.constants';

/** So viele Beitraege zeigt der Teaser auf der Startseite. */
export const TEASER_ANZAHL = 5;

/**
 * Mobil zeigt die Liste nur so viele: fuenf volle Karten untereinander schoben den Rest
 * der Startseite um rund vier Bildschirmhoehen nach unten (#599). Eine Seite "Alle neuen
 * Inhalte" gibt es nicht, deshalb nur gekuerzt.
 */
export const MOBIL_ANZAHL = 3;

/** /recent liefert nur diese beiden Typen (api/v1/content.py). */
const TEASER_TYPEN = ['commentary', 'generictext'];

/**
 * Frisch heisst: in den letzten 7 Tagen ergaenzt, wie die Kachel „Frisch aus der Community“
 * unter „Seit deinem letzten Besuch“ (GLOSSARY.md, Rueckmeldung). /recent selbst kennt
 * kein Zeitfenster, es liefert die neuesten sichtbaren Beitraege jeden Alters.
 */
export const FRISCH_TAGE = 7;

/** Ist nichts frisch, zeigt der Bereich so viele der zuletzt ergaenzten (Entscheidung 26.11.). */
export const ZULETZT_ANZAHL = 3;

/**
 * Was der Bereich zeigt: frische Beitraege, sonst die zuletzt ergaenzten jeden Alters,
 * und nur ganz ohne Beitraege den Anfang (Entscheidung 26.11.: nie „Noch keine neuen
 * Beitraege“).
 */
export type RecentContentStand = 'frisch' | 'zuletzt' | 'anfang';

export const RECENT_CONTENT_TITEL: Record<RecentContentStand, string> = {
  frisch: 'Frisch aus der Community',
  zuletzt: 'Zuletzt ergänzt',
  anfang: 'Frisch aus der Community',
};

/** Ob ein Beitrag mit diesem Zeitstempel noch frisch ist; ohne lesbares Datum nicht. */
export function istFrisch(erstellt: string | undefined, jetzt: number = Date.now()): boolean {
  const zeit = erstellt ? Date.parse(erstellt) : NaN;
  return !Number.isNaN(zeit) && jetzt - zeit <= FRISCH_TAGE * 24 * 60 * 60 * 1000;
}

@Component({
  selector: 'app-recent-content',
  standalone: true,
  imports: [
    CommonModule,
    ResultCarouselComponent,
    KartenlisteComponent,
    RouterLink,
    LoadingSpinnerComponent,
    ErrorMessageComponent
  ],
  templateUrl: './recent-content.component.html',
  styleUrls: ['./recent-content.component.css']
})
export class RecentContentComponent implements OnInit, OnDestroy {
  karten: KartenDaten[] = [];
  stand: RecentContentStand = 'frisch';
  loading = false;
  error = '';
  /** Bis 599 px eine Liste, darueber das Karussell. */
  istMobil = false;
  readonly beitragen = ROUTES.CONTRIBUTE;
  private destroy$ = new Subject<void>();

  get titel(): string {
    return RECENT_CONTENT_TITEL[this.stand];
  }

  /** Mobil die neuesten drei, ab 600 px alle im Karussell. */
  get angezeigteKarten(): KartenDaten[] {
    return this.istMobil ? this.karten.slice(0, MOBIL_ANZAHL) : this.karten;
  }

  constructor(
    private contentService: ContentService,
    private logger: LoggingService,
    private cdr: ChangeDetectorRef,
    private contentRefreshService: ContentRefreshService,
    private breakpointObserver: BreakpointObserver
  ) {}

  ngOnInit(): void {
    this.breakpointObserver
      .observe('(max-width: 599px)')
      .pipe(takeUntil(this.destroy$))
      .subscribe((zustand) => {
        this.istMobil = zustand.matches;
        this.cdr.markForCheck();
      });

    this.loadRecentContent();

    this.contentRefreshService.refresh$
      .pipe(takeUntil(this.destroy$))
      .subscribe(() => {
        this.logger.info('Neueste Inhalte: Aktualisierung angefordert');
        this.loading = true;
        this.cdr.markForCheck();
        this.loadRecentContent();
      });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadRecentContent(): void {
    this.loading = true;
    this.error = '';

    this.contentService.getRecentContent(TEASER_ANZAHL).subscribe({
      next: (response: RecentContentResponse) => {
        const eintraege = response.results.filter((item) => TEASER_TYPEN.includes(item.result_type));
        // Nichts frisch: die zuletzt ergaenzten statt eines leeren Bereichs
        this.stand =
          eintraege.length === 0 ? 'anfang' : eintraege.some((item) => istFrisch(item.created)) ? 'frisch' : 'zuletzt';
        this.karten = (this.stand === 'zuletzt' ? eintraege.slice(0, ZULETZT_ANZAHL) : eintraege)
          .map((item) =>
            ausSuchergebnis({
              score: 1.0,
              statement_text: '',
              statement_similarity_score: 0,
              reply_relevance: 0,
              content_type: item.result_type,
              [`${item.result_type}_result`]: item,
            }),
          );
        this.logger.info(`Neueste Inhalte (${this.stand}): ${this.karten.length} Karten`, this.karten.map((karte) => karte.id));
        this.loading = false;
        this.cdr.detectChanges();
      },
      error: (error) => {
        this.logger.error('Failed to load recent content', error);
        this.error = 'Die neuesten Beiträge konnten gerade nicht geladen werden.';
        this.loading = false;
        this.cdr.detectChanges();
      }
    });
  }

  retryLoad = () => {
    this.loadRecentContent();
  }
}
