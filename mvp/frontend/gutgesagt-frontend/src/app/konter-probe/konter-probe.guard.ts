import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs/operators';

import { FunktionenService } from '../services/funktionen.service';
import { ROUTES } from '../shared/constants/app.constants';
import { KONTER_PROBE_SCHALTER } from './konter-probe';

/**
 * Die Konter-Probe (#786) nur bei eingeschaltetem Schalter: Ist er aus (oder antwortet
 * der Server nicht), führt ein geteilter Link oder ein Lesezeichen auf die Startseite,
 * wie bei den App-Abkürzungen (abkuerzungGuard, #757). So zeigt die App bei
 * ausgeschaltetem Schalter nichts vom Spiel.
 */
export const konterProbeGuard: CanActivateFn = () => {
  const router = inject(Router);
  return inject(FunktionenService)
    .frisch(KONTER_PROBE_SCHALTER)
    .pipe(map((an) => an || router.parseUrl(ROUTES.SEARCH)));
};
