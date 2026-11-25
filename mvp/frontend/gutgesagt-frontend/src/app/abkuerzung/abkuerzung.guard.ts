import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs/operators';

import { FunktionenService } from '../services/funktionen.service';
import { ROUTES } from '../shared/constants/app.constants';

/** Name des Schalters auf der Admin-Seite (#757). */
export const ABKUERZUNGEN_SCHALTER = 'abkuerzungen';

/**
 * Die App-Abkürzungen aus dem Manifest (`shortcuts`, #757): Langes Drücken aufs App-Symbol
 * bietet sie an, das Ziel ist `/abkuerzung/<name>`. Hier steht, wohin jede führt.
 */
export const ABKUERZUNGEN: Record<string, string> = {
  einwerfen: ROUTES.RAW_INPUT,
  suchen: ROUTES.SEARCH,
  fangkorb: ROUTES.RAW_INPUT_LIST,
};

/**
 * Leitet eine App-Abkürzung weiter. Das Manifest ist statisch und das Betriebssystem
 * merkt sich die Abkürzungen beim Installieren; der Schalter wirkt deshalb hier, an der
 * Zielroute: Ist er aus (oder antwortet der Server nicht), öffnet jede Abkürzung die
 * normale Startseite wie das App-Symbol selbst. Unbekannte Namen ebenso.
 * Anmelden verlangen Einwerfen und Fangkorb selbst (AuthGuard am Ziel).
 */
export const abkuerzungGuard: CanActivateFn = (route) => {
  const router = inject(Router);
  const name = route.paramMap.get('name') ?? '';
  // Nur eigene Eintraege: "constructor" oder "__proto__" kaemen sonst aus dem Prototyp
  const ziel = Object.hasOwn(ABKUERZUNGEN, name) ? ABKUERZUNGEN[name] : undefined;
  return inject(FunktionenService)
    .frisch(ABKUERZUNGEN_SCHALTER)
    .pipe(map((an) => router.parseUrl(an && ziel ? ziel : ROUTES.SEARCH)));
};
