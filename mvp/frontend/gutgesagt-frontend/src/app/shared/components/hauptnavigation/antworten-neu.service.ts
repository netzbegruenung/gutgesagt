import { Injectable, inject } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { BehaviorSubject, Observable, combineLatest, of } from 'rxjs';
import { distinctUntilChanged, filter, map, shareReplay, switchMap } from 'rxjs/operators';

import { AuthService } from '../../../auth/auth.service';
import { UsageTrackingService } from '../../../services/usage-tracking.service';
import { ROUTES } from '../../constants/app.constants';

/**
 * Der Punkt am Ziel „Meine“ der Hauptnavigation (#760): neue Antworten anderer auf eigene
 * Aussagen (`antworten_auf_eigene_aussagen` aus dem Besuch beim App-Start), dieselbe Zahl
 * wie die Kachel auf der Startseite. Ein Punkt statt einer Zahl, damit er neben der Zahl am
 * Fangkorb nicht wie ein zweiter Zähler wirkt. Ohne Schalter `antworten_hinweis` ist die
 * Zahl null und es gibt keinen Punkt. Kein eigener Abruf.
 *
 * Wer „Meine Beiträge“ öffnet, hat den Hinweis gesehen: Dann verschwindet der Punkt für
 * diesen App-Start, wie die Zahl am Fangkorb (FangkorbNeuService).
 */
@Injectable({ providedIn: 'root' })
export class AntwortenNeuService {
  private readonly usage = inject(UsageTrackingService);
  private readonly router = inject(Router);
  private readonly gesehen$ = new BehaviorSubject(false);

  /** true, wenn es neue Antworten gibt und „Meine Beiträge“ seitdem nicht offen war. */
  readonly neu$: Observable<boolean> = inject(AuthService).userInfo$.pipe(
    map((info) => (info?.isAuthenticated && info.userId ? info.userId : null)),
    distinctUntilChanged(),
    switchMap((kennung) => {
      if (!kennung) {
        return of(false);
      }
      this.gesehen$.next(false);
      return combineLatest([this.usage.besuchStand$, this.gesehen$]).pipe(
        map(([stand, gesehen]) => (stand?.antworten_auf_eigene_aussagen ?? 0) > 0 && !gesehen),
      );
    }),
    distinctUntilChanged(),
    shareReplay({ bufferSize: 1, refCount: true }),
  );

  constructor() {
    this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe((e) => {
        if (e.urlAfterRedirects.split(/[?#]/)[0] === ROUTES.MEINE_BEITRAEGE) {
          this.gesehen$.next(true);
        }
      });
  }
}

/** Der Zusatz zum zugänglichen Namen des Ziels „Meine“; das Template hängt ihn nur bei Neuem an. */
export const ANTWORTEN_ZUSATZ = ', neue Antworten auf deine Aussagen';
