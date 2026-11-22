import { HttpClient } from '@angular/common/http';
import { Injectable, Signal, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Observable, forkJoin, of, throwError } from 'rxjs';
import { catchError, map, tap } from 'rxjs/operators';

import { environment } from '../../environments/environment';
import { stillerKontext } from '../shared/selbst-nachladen';
import { Art9EinwilligungZustand } from './art9-einwilligung-zustand';
import { FunktionenService } from './funktionen.service';

/** Name des Schalters auf der Admin-Seite (#758). */
export const MERKLISTE_SCHALTER = 'merkliste';

/** Ein Eintrag der Merkliste, wie GET /api/v1/merkliste ihn liefert. */
export interface Gemerkt {
  content_id: string;
  gemerkt_am: string;
}

interface MerklisteAntwort {
  eintraege: Gemerkt[];
}

/**
 * Die eigene Merkliste (#758, Glossar „Merkliste“): welche Beiträge die angemeldete
 * Person gemerkt hat, zuletzt gemerkt zuerst. Ein Stand für alle Karten und den Reiter
 * „Gemerkt“; Merken und Entfernen ändern ihn sofort und nehmen das bei einem Fehler
 * zurück. Ob die Funktion an ist, sagt der Schalter `merkliste` (FunktionenService);
 * lesen und merken lässt das Backend nur mit Art.-9-Einwilligung zu, deshalb fragt der
 * Dienst ohne sie nicht (sonst käme der Hinweis zur Einwilligung ungefragt).
 */
@Injectable({ providedIn: 'root' })
export class MerklisteService {
  // Optional: Ohne HttpClient (Komponenten-Tests ohne Backend) bleibt die Liste leer.
  private readonly http = inject(HttpClient, { optional: true });
  private readonly funktionen = inject(FunktionenService);
  private readonly einwilligung = toSignal(inject(Art9EinwilligungZustand).zustand$, { initialValue: 'unbekannt' });
  private readonly url = `${environment.baseUrl}/api/v1/merkliste`;
  private readonly stand = signal<Gemerkt[]>([]);
  private geladen = false;
  private unterwegs = false;

  /** Die Einträge, zuletzt gemerkt zuerst. */
  readonly eintraege: Signal<Gemerkt[]> = this.stand.asReadonly();
  private readonly ids = computed(() => new Set(this.stand().map((e) => e.content_id)));

  /**
   * Ob der Schalter an ist. Jeder Aufruf darf den Stand auffrischen lassen (nach
   * FUNKTIONEN_NACHLADEN_MS): So kommt ein Umschalten auf der Admin-Seite ohne Neuladen an.
   */
  an(): boolean {
    return this.funktionen.an(MERKLISTE_SCHALTER)();
  }

  /** Ob die Person die Einwilligung gegeben hat, ohne die das Backend die Liste sperrt. */
  eingewilligt(): boolean {
    return this.einwilligung() === 'eingewilligt';
  }

  /** Schalter an und eingewilligt: Merken wird angeboten. */
  bereit(): boolean {
    return this.an() && this.eingewilligt();
  }

  istGemerkt(id: string): boolean {
    return this.ids().has(id);
  }

  /** Einmal still laden, sobald es jemand braucht (Karten mit Merken-Knopf). */
  sicherstellen(): void {
    if (this.geladen || this.unterwegs || !this.bereit()) {
      return;
    }
    this.laden(true).subscribe({ error: () => undefined });
  }

  /**
   * Frisch vom Server; der Reiter „Gemerkt“ ruft das beim Öffnen. ``still``: im
   * Hintergrund, ohne Umleitung auf die Anmeldung bei abgelaufener Sitzung.
   */
  laden(still = false): Observable<Gemerkt[]> {
    if (!this.http || !this.bereit()) {
      return of([]);
    }
    this.unterwegs = true;
    const optionen = still ? { context: stillerKontext() } : {};
    return this.http.get<MerklisteAntwort>(this.url, optionen).pipe(
      map((antwort) => antwort?.eintraege ?? []),
      tap({
        next: (eintraege) => {
          this.stand.set(eintraege);
          this.geladen = true;
          this.unterwegs = false;
        },
        error: () => (this.unterwegs = false),
      }),
    );
  }

  /** Merken (oben einreihen) oder entfernen; sofort sichtbar, bei Fehler nur dieser zurück. */
  umschalten(id: string): Observable<boolean> {
    if (!this.http) {
      return of(false);
    }
    const merken = !this.istGemerkt(id);
    const vorher = this.stand().find((e) => e.content_id === id);
    const position = this.stand().findIndex((e) => e.content_id === id);
    this.stand.update((liste) =>
      merken
        ? [{ content_id: id, gemerkt_am: new Date().toISOString() }, ...liste]
        : liste.filter((e) => e.content_id !== id),
    );
    const anfrage = merken
      ? this.http.put<void>(`${this.url}/${encodeURIComponent(id)}`, null)
      : this.http.delete<void>(`${this.url}/${encodeURIComponent(id)}`);
    return anfrage.pipe(
      map(() => merken),
      catchError((fehler) => {
        // Nur diesen Eintrag zuruecknehmen: Andere Karten koennen inzwischen umgeschaltet haben
        this.stand.update((liste) => {
          const ohne = liste.filter((e) => e.content_id !== id);
          if (merken || !vorher) {
            return ohne;
          }
          const wieder = [...ohne];
          wieder.splice(Math.min(position, wieder.length), 0, vorher);
          return wieder;
        });
        return throwError(() => fehler);
      }),
    );
  }

  /** Mehrere Einträge auf einmal entfernen (Beiträge, die nicht mehr da sind). */
  entfernen(ids: string[]): Observable<void> {
    if (!this.http || !ids.length) {
      return of(undefined);
    }
    const weg = new Set(ids);
    return forkJoin(ids.map((id) => this.http!.delete<void>(`${this.url}/${encodeURIComponent(id)}`))).pipe(
      tap(() => this.stand.update((liste) => liste.filter((e) => !weg.has(e.content_id)))),
      map(() => undefined),
    );
  }
}
