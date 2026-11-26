import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, Observable, of, throwError } from 'rxjs';
import { distinctUntilChanged, map, tap } from 'rxjs/operators';

import { environment } from '../../environments/environment';
import { stillerKontext } from '../shared/selbst-nachladen';

/** Die drei Stufen des Spielgefühls (GLOSSARY.md „Spielgefühl“). */
export type SpielgefuehlStufe = 'aus' | 'fuer_mich' | 'rangliste';

export interface SpielgefuehlStufenText {
  stufe: SpielgefuehlStufe;
  titel: string;
  text: string;
}

export interface SpielgefuehlWortlaut {
  kennung: string;
  ueberschrift: string;
  einleitung: string;
  /** In der Reihenfolge der Knöpfe: Gemeinschaft zuerst, Datenschutz danach. */
  stufen: SpielgefuehlStufenText[];
  namenswahl: {
    frage: string;
    anzeigename: string;
    zufallsname: string;
    tipp: string;
    /** null: keine Vorbelegung, die Person wählt aktiv (Jura 26.11.). */
    vorbelegung_anzeigename: boolean | null;
  };
  fuss: string;
}

/** GET /api/v1/usage/users/me/spielgefuehl, nur für die angemeldete Person selbst. */
export interface SpielgefuehlStand {
  /** false: Schalter aus (200 statt 404, Gateway-fail2ban); dann gilt das bisherige Modell. */
  aktiv?: boolean;
  /** null: noch keine Antwort im neuen Modell, die App fragt. */
  stufe: SpielgefuehlStufe | null;
  /** Nur bei Stufe rangliste: Anzeigename (true) oder Zufallsname (false). */
  mit_anzeigename: boolean | null;
  ranglistenname: string | null;
  anzeigename: string | null;
  /** Einmaliger Satz für Konten, die bisher Abzeichen am Namen gezeigt haben. */
  abzeichen_hinweis: string | null;
  aktueller_wortlaut: SpielgefuehlWortlaut;
}

/** Punkte und Meilensteine werden berechnet: ab Stufe „Nur für mich“. */
export function punkteWirksam(stufe: SpielgefuehlStufe | null | undefined): boolean {
  return stufe === 'fuer_mich' || stufe === 'rangliste';
}

/** Rang einer Stufe, um Herab- von Heraufstufen zu unterscheiden. */
export function stufenRang(stufe: SpielgefuehlStufe | null): number {
  return stufe === 'rangliste' ? 2 : stufe === 'fuer_mich' ? 1 : 0;
}

/**
 * Spielgefühl als eine Einstellung in drei Stufen (Schalter `spielgefuehl_buehne`): Aus,
 * Nur für mich, in der Saison-Rangliste mitspielen. Ohne wirksamen Schalter antwortet der
 * Server beim Lesen mit 200 und `aktiv: false`, dann ist der Stand null und es gilt das
 * bisherige Modell mit drei Einwilligungen.
 *
 * Ein gemeinsamer Stand (`stand$`) für die Frage, die Punkte und die Meilensteine: Ändert
 * die Person die Stufe, laden die anderen Karten selbst nach.
 */
@Injectable({ providedIn: 'root' })
export class SpielgefuehlService {
  // Optional wie im Einwilligungs-Budget: Karten, die nur auf die Stufe hören, laufen auch in
  // Tests ohne HttpClient; ohne ihn gilt der Schalter als aus.
  private readonly http = inject(HttpClient, { optional: true });
  private readonly url = `${environment.baseUrl}/api/v1/usage/users/me/spielgefuehl`;
  /** undefined: noch nicht geladen; null: Schalter aus. */
  private readonly stand = new BehaviorSubject<SpielgefuehlStand | null | undefined>(undefined);
  readonly stand$ = this.stand.asObservable();

  /** Der eigene Stand; null bei ausgeschaltetem Schalter. ``still``: ohne Umleitung bei 401. */
  laden(still = false): Observable<SpielgefuehlStand | null> {
    if (!this.http) {
      this.melden(null);
      return of(null);
    }
    return this.http.get<SpielgefuehlStand>(this.url, { context: still ? stillerKontext() : undefined }).pipe(
      map((stand) => (stand?.aktiv === false ? null : stand)),
      tap((stand) => this.melden(stand)),
    );
  }

  /** Eine Stufe wählen; bei Stufe rangliste mit der Namenswahl. */
  waehlen(stufe: SpielgefuehlStufe, mitAnzeigename: boolean | null, wortlaut: string): Observable<unknown> {
    if (!this.http) {
      return throwError(() => new Error('ohne HttpClient'));
    }
    return this.http.put(this.url, { stufe, mit_anzeigename: mitAnzeigename, wortlaut });
  }

  /** Einen neuen Zufallsnamen würfeln (nur mit Stufe rangliste). */
  wuerfeln(): Observable<{ ranglistenname: string }> {
    if (!this.http) {
      return throwError(() => new Error('ohne HttpClient'));
    }
    return this.http.post<{ ranglistenname: string }>(`${this.url}/ranglistenname`, {});
  }

  /** Einen neuen Stand an alle melden, die zuhören (etwa nach einer Wahl). */
  melden(stand: SpielgefuehlStand | null): void {
    this.stand.next(stand);
  }

  /**
   * Die wirksame Stufe für andere Karten: undefined solange unbekannt, null ohne Schalter
   * oder ohne Antwort. Meldet nur Änderungen.
   */
  readonly stufe$: Observable<SpielgefuehlStufe | null | undefined> = this.stand$.pipe(
    map((stand) => (stand === undefined ? undefined : (stand?.stufe ?? null))),
    distinctUntilChanged(),
  );
}
