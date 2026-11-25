import { HttpClient } from '@angular/common/http';
import { inject } from '@angular/core';
import { ActivatedRouteSnapshot, CanActivateFn, Router, UrlTree } from '@angular/router';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { AuthService } from '../auth/auth.service';
import { sitzungPruefen } from '../auth/sitzung';
import { ZIEL_PARAM, vorschauZiel } from './vorschau-schritte';

/**
 * Die Vorschau ist nur für Besucher: Wer angemeldet ist, geht gleich zum Ziel, statt eine
 * Seite über das Anmelden zu sehen. Besucher bekommen dieselben Anmeldedaten gesetzt wie
 * auf öffentlichen Seiten (PublicGuard).
 */
export const mitKontoVorschauGuard: CanActivateFn = (route: ActivatedRouteSnapshot): Observable<boolean | UrlTree> => {
  const http = inject(HttpClient);
  const router = inject(Router);
  const auth = inject(AuthService);
  return sitzungPruefen(http).pipe(
    map((angemeldet) => {
      if (angemeldet) {
        return router.parseUrl(vorschauZiel(route.queryParamMap.get(ZIEL_PARAM)));
      }
      auth.setUserInfo({ isAuthenticated: false, userId: null, userName: null, claims: null });
      return true;
    }),
  );
};
