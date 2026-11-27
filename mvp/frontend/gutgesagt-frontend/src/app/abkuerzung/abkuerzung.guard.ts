import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { ROUTES } from '../shared/constants/app.constants';

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
 * Leitet eine App-Abkürzung weiter (Basisfunktion seit dem Schalter-Umbau 27.11.).
 * Unbekannte Namen öffnen die normale Startseite wie das App-Symbol selbst.
 * Anmelden verlangen Einwerfen und Fangkorb selbst (AuthGuard am Ziel).
 */
export const abkuerzungGuard: CanActivateFn = (route) => {
  const name = route.paramMap.get('name') ?? '';
  // Nur eigene Eintraege: "constructor" oder "__proto__" kaemen sonst aus dem Prototyp
  const ziel = Object.hasOwn(ABKUERZUNGEN, name) ? ABKUERZUNGEN[name] : undefined;
  return inject(Router).parseUrl(ziel ?? ROUTES.SEARCH);
};
