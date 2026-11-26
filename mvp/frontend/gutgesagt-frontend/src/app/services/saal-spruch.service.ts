import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, of, throwError } from 'rxjs';
import { catchError, map, switchMap } from 'rxjs/operators';

import { environment } from '../../environments/environment';
import { stillerKontext } from '../shared/selbst-nachladen';
import { FunktionenService } from './funktionen.service';

/** Name des Schalters (services/schalter_service.py, SPIEL_SCHALTER). */
export const SAAL_SPRUCH_SCHALTER = 'saal_spruch';

export const SAAL_SPRUCH_HEUTE_URL = `${environment.baseUrl}/api/v1/saal-spruch/heute`;

/** Ein Saal-Spruch auf der Admin-Seite. */
export interface SaalSpruch {
  /** ISO-Datum JJJJ-MM-TT, Tag in Europe/Berlin */
  datum: string;
  text: string;
}

export interface SaalSpruchListe {
  /** Ab heute, nach Datum */
  sprueche: SaalSpruch[];
  schalter_wirksam: boolean;
  /** Der heutige Tag im Saal (ISO-Datum), früher lässt sich nichts festlegen */
  heute: string;
  text_max: number;
}

/**
 * Saal-Spruch (Schalter „saal_spruch“, Glossar „Saal-Spruch“): der Spruch für
 * die Startseite und die Pflege für Admins (Seite „Schalter“).
 */
@Injectable({ providedIn: 'root' })
export class SaalSpruchService {
  private readonly http = inject(HttpClient);
  private readonly funktionen = inject(FunktionenService);
  private readonly admin = `${environment.baseUrl}/api/v1/moderation/saal-sprueche`;

  /**
   * Der Spruch für heute; null ohne Spruch oder bei Schalter aus. Meldet FunktionenService
   * den Schalter sicher aus, fragt die Startseite den Endpunkt gar nicht; sonst antwortet
   * er auch bei Schalter aus mit 200 (`aktiv: false`), nie 404 (Gateway-fail2ban,
   * Saal-WLAN). Ein 404 käme nur von einem älteren Backend und gilt ebenso als aus.
   */
  heute(): Observable<string | null> {
    return this.funktionen.stand$(SAAL_SPRUCH_SCHALTER).pipe(
      switchMap((an) =>
        an === false
          ? of(null)
          : this.http
              .get<{ spruch: string | null; aktiv?: boolean }>(SAAL_SPRUCH_HEUTE_URL, { context: stillerKontext() })
              .pipe(
                map((antwort) => (antwort?.aktiv === false ? null : antwort?.spruch?.trim() || null)),
                catchError((fehler: { status?: number }) =>
                  fehler?.status === 404 ? of(null) : throwError(() => fehler),
                ),
              ),
      ),
    );
  }

  liste(still = false): Observable<SaalSpruchListe> {
    return this.http.get<SaalSpruchListe>(this.admin, { context: still ? stillerKontext() : undefined });
  }

  festlegen(datum: string, text: string): Observable<SaalSpruchListe> {
    return this.http.put<SaalSpruchListe>(`${this.admin}/${encodeURIComponent(datum)}`, { text });
  }

  entfernen(datum: string): Observable<void> {
    return this.http.delete<void>(`${this.admin}/${encodeURIComponent(datum)}`);
  }
}
