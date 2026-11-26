import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, Observable, combineLatest, of, timer } from 'rxjs';
import { distinctUntilChanged, map, shareReplay, startWith, switchMap } from 'rxjs/operators';

import { UsageTrackingService } from '../services/usage-tracking.service';
import { NeuesArt, NeuesEintrag, StartVorrang, startKacheln, startVorrang } from './neues-liste';
import type { Vorschlag } from '../naechster-schritt/naechster-schritt';

export type { NeuesArt } from './neues-liste';

/**
 * Wie lange Block und Karte auf der Startseite hoechstens auf die jeweils andere Antwort
 * (Besuch, Vorschlaege) warten, bevor sie ohne sie entscheiden. Kommt beides schneller,
 * zeigt nichts eine Karte, die gleich wieder verschwindet.
 */
export const START_WARTEZEIT_MS = 1500;

/** Was Block und Karte aus einer Quelle lesen: wer Vorrang hat, und die Kacheln des Blocks. */
export interface StartStand {
  vorrang: StartVorrang;
  kacheln: NeuesEintrag[];
}

/** Liefert den Wert sofort; steht er noch aus (null), erst undefined und nach der Wartezeit null. */
function mitZeitgrenze<T>(wert$: Observable<T | null>): Observable<T | null | undefined> {
  return wert$.pipe(
    switchMap((wert) =>
      wert === null ? timer(START_WARTEZEIT_MS).pipe(map(() => null), startWith(undefined)) : of(wert),
    ),
  );
}

/**
 * Vorgaenger-Staende im Browser aus der Entwicklung von #672; nie in einem Release, aber
 * auf Test-Stacks moeglich. Sie werden einmal entfernt, gelesen wird nichts mehr.
 */
const ALTE_MERKER = 'gutgesagt-letzter-besuch';

/** Entfernt die alten Browser-Merker; ohne Speicher passiert nichts. */
export function alteBesuchMerkerEntfernen(): void {
  try {
    const schluessel: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const name = localStorage.key(i);
      if (name?.startsWith(ALTE_MERKER)) {
        schluessel.push(name);
      }
    }
    schluessel.forEach((name) => localStorage.removeItem(name));
  } catch {
    // Ohne Speicher gibt es nichts aufzuraeumen.
  }
}

/**
 * „Seit deinem letzten Besuch“ auf der Startseite (Nutzerfuehrung 13.11.): Die Zahlen
 * kommen alle vom Server, aus der Antwort des Besuchs beim App-Start (Zaehlerstaende am
 * Konto, kein Zeitpunkt, kein Browser-Speicher). Hier steht nur, welche Links in diesem
 * App-Start schon angeklickt wurden; beim Kontowechsel faengt das neu an.
 */
@Injectable({ providedIn: 'root' })
export class SeitLetztemBesuchService {
  private kennung: string | null = null;
  readonly erledigt$ = new BehaviorSubject<ReadonlySet<NeuesArt>>(new Set());
  /**
   * Ob „Dein nächster Schritt“ einen Vorschlag hat, gemeldet von dessen Karte, sobald ihre
   * Antwort da ist; null, solange noch keine kam. Bleibt beim Verlassen der Startseite
   * stehen: Bei der Rückkehr gilt der letzte Stand, bis die neue Antwort ihn bestätigt.
   */
  readonly naechsterSchrittDa$ = new BehaviorSubject<boolean | null>(null);
  /**
   * Die letzten Vorschläge der Karte in diesem App-Start; null, solange keine kamen. Die
   * Karte zeigt sie bei der Rückkehr sofort und fragt im Hintergrund neu.
   */
  naechsterSchrittGemerkt: Vorschlag[] | null = null;
  /**
   * Ob die Karte „Heute im Saal gehört:“ heute einen Spruch hat. false ohne die Karte (dann
   * wartet nichts auf sie); die Karte setzt null, solange ihre Antwort aussteht, und dann
   * true oder false. Bei der Rückkehr gilt der letzte Stand, wie beim Vorschlag.
   */
  readonly saalSpruchDa$ = new BehaviorSubject<boolean | null>(false);
  /** Der letzte Saal-Spruch dieses App-Starts mit seinem Tag; null, solange keiner kam. */
  saalSpruchGemerkt: { tag: string; spruch: string | null } | null = null;

  /**
   * Die eine Stelle, die über den Vorrang auf der Startseite entscheidet (Review
   * Spielgefühl 25.11., Reihenfolge in docs/ARCHITECTURE.md). Block und Karte lesen beide
   * nur hier, damit die Regel nicht an zwei Orten auseinanderläuft.
   */
  readonly start$: Observable<StartStand> = combineLatest([
    mitZeitgrenze(inject(UsageTrackingService).besuchStand$),
    this.erledigt$,
    mitZeitgrenze(this.naechsterSchrittDa$).pipe(map((da) => (da === null ? false : da))),
    mitZeitgrenze(this.saalSpruchDa$).pipe(map((da) => (da === undefined ? 'offen' : da === null ? false : da))),
  ]).pipe(
    map(([stand, erledigt, da, spruch]) => {
      const vorrang = startVorrang(stand, erledigt, da, spruch);
      return { vorrang, kacheln: startKacheln(stand, erledigt, vorrang) };
    }),
    distinctUntilChanged((a, b) => a.vorrang === b.vorrang && gleicheKacheln(a.kacheln, b.kacheln)),
    shareReplay({ bufferSize: 1, refCount: true }),
  );

  private aufgeraeumt = false;

  /** Einmal je App-Start die alten Merker entfernen; bei neuer Kennung die Klicks vergessen. */
  fuer(kennung: string): void {
    if (!this.aufgeraeumt) {
      this.aufgeraeumt = true;
      alteBesuchMerkerEntfernen();
    }
    if (kennung !== this.kennung) {
      this.kennung = kennung;
      this.erledigt$.next(new Set());
    }
  }

  /** Nach dem Klick auf einen Link: Er verschwindet, die Sache ist gesehen. */
  erledigen(art: NeuesArt): void {
    this.erledigt$.next(new Set([...this.erledigt$.value, art]));
  }
}

function gleicheKacheln(a: NeuesEintrag[], b: NeuesEintrag[]): boolean {
  return a.length === b.length && a.every((e, i) => e.art === b[i].art && e.zahl === b[i].zahl);
}
