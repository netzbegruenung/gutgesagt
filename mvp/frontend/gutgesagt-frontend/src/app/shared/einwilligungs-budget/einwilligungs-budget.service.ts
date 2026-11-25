import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { environment } from '../../../environments/environment';
import { LoggingService } from '../../services/logging.service';
import {
  BudgetLage,
  EinwilligungsFrage,
  EinwilligungsMoment,
  frageErlaubt,
  punkteFrageFaellig,
} from './einwilligungs-budget';

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
  /** Für Tests ersetzbar. */
  jetzt: () => number = () => Date.now();

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
        catchError((fehler) => {
          if (fehler?.status !== 404 && fehler?.status !== 401) {
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
