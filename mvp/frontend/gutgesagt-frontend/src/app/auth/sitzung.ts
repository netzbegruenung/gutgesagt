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

/**
 * Was /api/check-session sagt: angemeldet, sicher Besucher (200 mit isAuthenticated = false,
 * oder 401 eines aelteren BFF), oder unbekannt (Netz, 5xx beim Deploy). Unbekannt heisst nicht,
 * dass die Sitzung zu Ende ist; eine angemeldete Kopfzeile bleibt dann stehen.
 */
export type Sitzungsstand = 'angemeldet' | 'besucher' | 'unbekannt';

/** Ob eine Antwort der Anmelde-Pruefungen eine Anmeldung meldet; alles andere gilt als Besucher. */
export function meldetAnmeldung(antwort: Sitzungsantwort | null | undefined): boolean {
  return antwort?.isAuthenticated === true;
}

/** Fragt /api/check-session nach dem Stand der Sitzung (siehe Sitzungsstand). */
export function sitzungsstand(http: HttpClient): Observable<Sitzungsstand> {
  return http.get<Sitzungsantwort | null>(`${environment.baseUrl}/api/check-session`).pipe(
    map((antwort): Sitzungsstand => (meldetAnmeldung(antwort) ? 'angemeldet' : 'besucher')),
    catchError((fehler: { status?: number }) => of<Sitzungsstand>(fehler?.status === 401 ? 'besucher' : 'unbekannt')),
  );
}

/**
 * Fragt /api/check-session, ob das Anmelde-Cookie gilt. Ein Fehler (Netz, 5xx, ein 401 von
 * einem aelteren BFF) gilt wie bisher als nicht angemeldet.
 */
export function sitzungPruefen(http: HttpClient): Observable<boolean> {
  return sitzungsstand(http).pipe(map((stand) => stand === 'angemeldet'));
}
