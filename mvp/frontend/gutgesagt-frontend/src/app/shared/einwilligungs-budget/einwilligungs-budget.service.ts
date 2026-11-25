import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, Subject, of } from 'rxjs';
import { catchError, timeout } from 'rxjs/operators';

import { environment } from '../../../environments/environment';
import { LoggingService } from '../../services/logging.service';
import {
  BudgetLage,
  lobNochFrisch,
  EinwilligungsFrage,
  EinwilligungsMoment,
  frageErlaubt,
  punkteFrageFaellig,
} from './einwilligungs-budget';

/** So lange wartet moment() auf den Server, dann gilt: Schalter aus. */
export const MOMENT_WARTEN_MS = 3000;

/**
 * Hält das Einwilligungs-Budget eines Besuchs (einwilligungs-budget.ts): was in diesem
 * Laden der App schon gefragt wurde und ob seitdem ein Gewinn kam. Alles nur im
 * Arbeitsspeicher; ein Neuladen beginnt einen neuen Besuch.
 */
@Injectable({ providedIn: 'root' })
export class EinwilligungsBudgetService {
  private readonly http = inject(HttpClient, { optional: true });
  private readonly logger = inject(LoggingService, { optional: true });
  private readonly gezeigtImBesuch = new Set<EinwilligungsFrage>();
  private gewinnUm: number | null = null;
  private readonly gewinne = new Subject<void>();
  /** Meldet jeden Gewinn mit Lob, damit eine offene Frage zurücktritt. */
  readonly gewinn$ = this.gewinne.asObservable();
  /** Für Tests ersetzbar. */
  jetzt: () => number = () => Date.now();
  /**
   * true erst, wenn der Server den Schalter sicher als aus gemeldet hat (404). Bei einem
   * Fehler oder ohne Antwort bleibt es false: Dann ist unklar, ob der Schalter an ist,
   * und wer schon geantwortet hat, wird nicht noch einmal eingeladen (#788, Jura 25.11.).
   */
  schalterAus = false;

  /**
   * Die Fakten vom Server; null ohne Schalter (404) oder bei einem Fehler. Dann fragt
   * die App wie bisher.
   */
  moment(): Observable<EinwilligungsMoment | null> {
    if (!this.http) {
      return of(null);
    }
    return this.http
      .get<EinwilligungsMoment>(`${environment.baseUrl}/api/v1/usage/users/me/einwilligungs-moment`)
      .pipe(
        // Antwortet der Server nicht, fragt die App wie bisher, statt nichts zu zeigen.
        timeout(MOMENT_WARTEN_MS),
        catchError((fehler) => {
          this.schalterAus = fehler?.status === 404;
          if (fehler?.status !== 404 && fehler?.status !== 401 && fehler?.name !== 'TimeoutError') {
            this.logger?.error('Einwilligungs-Moment nicht geladen', fehler);
          }
          return of(null);
        }),
      );
  }

  /** Eine Frage steht jetzt auf dem Bildschirm. */
  gezeigt(frage: EinwilligungsFrage): void {
    this.gezeigtImBesuch.add(frage);
  }

  /** Ein Gewinn mit Lob: eine Stimme oder „Ja, gepostet“. */
  gewinn(): void {
    this.gewinnUm = this.jetzt();
    this.gewinne.next();
  }

  /** Wie lange das letzte Lob noch frisch ist (ms); 0: keins. */
  lobFrischNoch(): number {
    return lobNochFrisch({ gewinnUm: this.gewinnUm, jetzt: this.jetzt() });
  }

  /** Ob die Frage gestellt werden darf; vermerkt sie nicht. */
  darf(frage: EinwilligungsFrage, moment: EinwilligungsMoment): boolean {
    return frageErlaubt(frage, this.lage(moment));
  }

  /** Ob die Frage nach Punkten und Meilensteinen jetzt fällig ist; vermerkt sie nicht. */
  punkteFaellig(moment: EinwilligungsMoment): boolean {
    return punkteFrageFaellig(this.lage(moment));
  }

  private lage(moment: EinwilligungsMoment): BudgetLage {
    return { gezeigt: this.gezeigtImBesuch, moment, gewinnUm: this.gewinnUm, jetzt: this.jetzt() };
  }
}
