import { Injectable, inject } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { BehaviorSubject, Observable, combineLatest, of } from 'rxjs';
import { distinctUntilChanged, filter, map, shareReplay, switchMap } from 'rxjs/operators';

import { AuthService } from '../../../auth/auth.service';
import { UsageTrackingService } from '../../../services/usage-tracking.service';
import { ROUTES } from '../../constants/app.constants';

/**
 * Die Zahl am Ziel „Fangkorb“ der Hauptnavigation: neue Einwürfe anderer seit dem letzten
 * Besuch (`neue_einwuerfe` aus der Antwort des Besuchs beim App-Start), dieselbe Zahl wie
 * die Kachel „neue Einwürfe im Fangkorb“ auf der Startseite. Keine Gesamtzahl: Die
 * wüchse nur und sagte nichts. Kein eigener Abruf.
 *
 * Wer den Fangkorb öffnet, hat das Neue gesehen: Dann verschwindet die Zahl an der
 * Navigation für diesen App-Start. Die Kachel auf der Startseite bleibt davon unberührt
 * (sie verschwindet weiter erst nach ihrem eigenen Klick, SeitLetztemBesuchService).
 * Kommt ein neuer Besuchsstand (etwa nach einem Kontowechsel), zählt er wieder.
 */
@Injectable({ providedIn: 'root' })
export class FangkorbNeuService {
  private readonly usage = inject(UsageTrackingService);
  private readonly router = inject(Router);
  /** Der Fangkorb war in diesem App-Start offen, seit der aktuelle Besuchsstand kam. */
  private readonly gesehen$ = new BehaviorSubject(false);

  /** Die Zahl, oder 0, wenn nichts Neues da ist, niemand angemeldet ist oder sie gesehen wurde. */
  readonly anzahl$: Observable<number> = inject(AuthService).userInfo$.pipe(
    map((info) => (info?.isAuthenticated && info.userId ? info.userId : null)),
    distinctUntilChanged(),
    switchMap((kennung) => {
      if (!kennung) {
        return of(0);
      }
      this.gesehen$.next(false);
      return combineLatest([this.usage.besuchStand$, this.gesehen$]).pipe(
        map(([stand, gesehen]) => {
          const zahl = stand?.neue_einwuerfe ?? 0;
          return zahl > 0 && !gesehen ? zahl : 0;
        }),
      );
    }),
    distinctUntilChanged(),
    shareReplay({ bufferSize: 1, refCount: true }),
  );

  constructor() {
    this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe((e) => {
        const pfad = e.urlAfterRedirects.split(/[?#]/)[0];
        if (pfad === ROUTES.RAW_INPUT_LIST || pfad.startsWith(ROUTES.RAW_INPUT_LIST + '/')) {
          this.gesehen$.next(true);
        }
      });
  }
}

/** Der Zusatz zum zugänglichen Namen des Ziels, etwa „, 3 neue Einwürfe“; leer ohne Neues. */
export function fangkorbZusatz(anzahl: number): string {
  if (anzahl <= 0) {
    return '';
  }
  return anzahl === 1 ? ', 1 neuer Einwurf' : `, ${anzahl} neue Einwürfe`;
}
