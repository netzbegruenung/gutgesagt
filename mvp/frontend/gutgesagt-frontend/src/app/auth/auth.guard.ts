import { Injectable } from '@angular/core';
import { CanActivate, Router, ActivatedRouteSnapshot, RouterStateSnapshot, UrlTree } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { MIT_KONTO_PFAD, ZIEL_PARAM } from '../mit-konto/vorschau-schritte';
import { AuthService } from './auth.service';
import { sitzungPruefen } from './sitzung';

/**
 * Routendaten-Schlüssel: Besucher sehen vor der Anmeldung erst „Das erwartet dich mit Konto“
 * (/mit-konto), statt direkt auf der Login-Auswahl zu landen. Gesetzt an den Einstiegen
 * ins Mitmachen (Einwerfen, Beitragen, Fangkorb); andere geschützte Seiten führen weiter
 * direkt zur Anmeldung.
 */
export const MIT_KONTO_VORSCHAU = 'mitKontoVorschau';

@Injectable({
  providedIn: 'root',
})
export class AuthGuard implements CanActivate {
  constructor(
    private http: HttpClient,
    private router: Router,
    private authService: AuthService
  ) {}

  canActivate(route: ActivatedRouteSnapshot, state: RouterStateSnapshot): Observable<boolean | UrlTree> {
    return sitzungPruefen(this.http).pipe(
      map((angemeldet) => {
        if (angemeldet) {
          return true;
        }
        // Die Sitzung ist zu Ende (abgelaufen, Konto geloescht), die Kopfzeile zeigt aber
        // noch die Person: Frueher setzte der Auth-Interceptor bei der 401 von check-session
        // den Besucher, die Antwort ist jetzt 200 mit isAuthenticated = false.
        if (this.authService.getUserInfo()?.isAuthenticated) {
          this.authService.setUserInfo({ isAuthenticated: false, userId: null, userName: null, claims: null });
        }
        // Nicht angemeldet: zur Vorschau oder zur Anmeldung, das Ziel geht jeweils mit
        const ziel = state.url;
        if (route.data?.[MIT_KONTO_VORSCHAU]) {
          return this.router.createUrlTree([MIT_KONTO_PFAD], { queryParams: { [ZIEL_PARAM]: ziel } });
        }
        return this.router.createUrlTree(['/login'], { queryParams: { returnUrl: ziel } });
      })
    );
  }
}
