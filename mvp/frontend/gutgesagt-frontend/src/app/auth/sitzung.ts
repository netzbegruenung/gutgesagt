import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { environment } from '../../environments/environment';

/**
 * Die Anmelde-Pruefungen des BFF (/api/check-session, /api/user-info) antworten immer mit 200;
 * ob jemand angemeldet ist, steht im Feld isAuthenticated. Besucher bekamen dort frueher 401.
 * Das Frontend fragt bei jedem Seitenaufruf, und am IPv4-Gateway sperrt fail2ban eine IP nach
 * 20 Antworten 401 in 5 Minuten: Im Saal-WLAN (BDK) teilen sich hunderte Besucher eine IP.
 * Deshalb zaehlt hier das Feld, nicht der Status.
 */
export interface Sitzungsantwort {
  isAuthenticated?: boolean;
}

/** Ob eine Antwort der Anmelde-Pruefungen eine Anmeldung meldet; alles andere gilt als Besucher. */
export function meldetAnmeldung(antwort: Sitzungsantwort | null | undefined): boolean {
  return antwort?.isAuthenticated === true;
}

/**
 * Fragt /api/check-session, ob das Anmelde-Cookie gilt. Ein Fehler (Netz, 5xx, ein 401 von
 * einem aelteren BFF) gilt wie bisher als Besucher.
 */
export function sitzungPruefen(http: HttpClient): Observable<boolean> {
  return http.get<Sitzungsantwort | null>(`${environment.baseUrl}/api/check-session`).pipe(
    map((antwort) => meldetAnmeldung(antwort)),
    catchError(() => of(false)),
  );
}
