import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { map } from 'rxjs/operators';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { AuthService } from '../auth/auth.service';
import { PAGE_TITLES, ROUTES } from '../shared/constants/app.constants';
import { nachladeStrom } from '../shared/selbst-nachladen';
import { MIT_KONTO_PFAD, ZIEL_PARAM } from '../mit-konto/vorschau-schritte';
import { Beet, GartenService, antwortenText, ohneAntwortText } from './garten.service';

/** Nach diesen Antworten fragt die Seite nicht weiter: aus (404) oder ohne Rechte. */
function endgueltig(fehler: unknown): boolean {
  const status = (fehler as { status?: unknown } | null)?.status;
  return status === 404 || status === 401 || status === 403;
}

/**
 * Gartenansicht fuer alle (#783): je Thema eine Kachel mit Motiv und Name, der Zahl der
 * Antworten und der Zahl der Sprueche ohne Antwort. Besucher sehen nur die Zahlen; den
 * Wortlaut zeigt wie bisher „Hier fehlt eine Antwort“, nur fuer Angemeldete.
 *
 * Ein Tipp auf die Kachel sucht nach dem Namen des Themas und zeigt so „Alles zum Thema“;
 * Angemeldete haben bei Spruechen ohne Antwort einen zweiten Link auf „Hier fehlt eine
 * Antwort“, gefiltert auf das Thema. Die Seite laedt selbst nach (nachladeStrom); ohne den
 * Schalter `gartenansicht` antwortet der Server 404, dann steht ein Satz da.
 */
@Component({
  selector: 'app-gartenansicht',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [AsyncPipe, RouterLink, MatProgressSpinnerModule],
  templateUrl: './gartenansicht.component.html',
  styleUrls: ['./gartenansicht.component.css'],
})
export class GartenansichtComponent implements OnInit {
  private readonly garten = inject(GartenService);
  private readonly destroyRef = inject(DestroyRef);

  readonly titel = PAGE_TITLES.GARTEN;
  readonly ergebnisse = ROUTES.RESULT;
  readonly hierFehlt = ROUTES.HIER_FEHLT_EINE_ANTWORT;
  readonly mitKonto = MIT_KONTO_PFAD;
  readonly mitKontoParams = { [ZIEL_PARAM]: ROUTES.HIER_FEHLT_EINE_ANTWORT };
  readonly antwortenText = antwortenText;
  readonly ohneAntwortText = ohneAntwortText;

  readonly beete = signal<Beet[] | null>(null);
  /** Der Server sagt 404: Der Schalter ist aus. */
  readonly aus = signal(false);
  /** Der letzte Versuch ist gescheitert; die Seite versucht es von selbst weiter. */
  readonly fehler = signal(false);
  /** 401/403: Die Seite fragt nicht weiter und verspricht keinen neuen Versuch. */
  readonly gestoppt = signal(false);

  readonly angemeldet$ = inject(AuthService).userInfo$.pipe(map((info) => info?.isAuthenticated === true));

  ngOnInit(): void {
    nachladeStrom(() => this.garten.beete(), { sofort: true, aufhoerenBei: endgueltig })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((lauf) => {
        if (lauf.fehler === null) {
          this.beete.set(lauf.daten?.beete ?? []);
          this.fehler.set(false);
          this.aus.set(false);
          this.gestoppt.set(false);
          return;
        }
        if ((lauf.fehler as { status?: unknown } | null)?.status === 404) {
          this.aus.set(true);
          this.beete.set(null);
          return;
        }
        if (endgueltig(lauf.fehler)) {
          this.gestoppt.set(true);
          return;
        }
        this.fehler.set(true);
      });
  }
}
