import { HttpClient } from '@angular/common/http';
import { Injectable, Signal, computed, inject, signal } from '@angular/core';
import { Observable, of, throwError } from 'rxjs';
import { catchError, map, tap } from 'rxjs/operators';

import { environment } from '../../environments/environment';
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
 * ist er aus, fragt der Dienst den Server nicht.
 */
@Injectable({ providedIn: 'root' })
export class MerklisteService {
  // Optional: Ohne HttpClient (Komponenten-Tests ohne Backend) bleibt die Liste leer.
  private readonly http = inject(HttpClient, { optional: true });
  private readonly funktionen = inject(FunktionenService);
  private readonly url = `${environment.baseUrl}/api/v1/merkliste`;
  private readonly stand = signal<Gemerkt[]>([]);
  private geladen = false;
  private unterwegs = false;

  /** Ob der Schalter an ist. */
  readonly an: Signal<boolean> = this.funktionen.an(MERKLISTE_SCHALTER);
  /** Die Einträge, zuletzt gemerkt zuerst. */
  readonly eintraege: Signal<Gemerkt[]> = this.stand.asReadonly();
  private readonly ids = computed(() => new Set(this.stand().map((e) => e.content_id)));

  istGemerkt(id: string): boolean {
    return this.ids().has(id);
  }

  /** Einmal laden, sobald es jemand braucht (Karten mit Merken-Knopf). */
  sicherstellen(): void {
    if (this.geladen || this.unterwegs || !this.an()) {
      return;
    }
    this.laden().subscribe({ error: () => undefined });
  }

  /** Frisch vom Server; der Reiter „Gemerkt“ ruft das beim Öffnen. */
  laden(): Observable<Gemerkt[]> {
    if (!this.http || !this.an()) {
      return of([]);
    }
    this.unterwegs = true;
    return this.http.get<MerklisteAntwort>(this.url).pipe(
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

  /** Merken (oben einreihen) oder entfernen; sofort sichtbar, bei Fehler zurück. */
  umschalten(id: string): Observable<boolean> {
    if (!this.http) {
      return of(false);
    }
    const vorher = this.stand();
    const merken = !this.istGemerkt(id);
    this.stand.set(
      merken
        ? [{ content_id: id, gemerkt_am: new Date().toISOString() }, ...vorher]
        : vorher.filter((e) => e.content_id !== id),
    );
    const anfrage = merken
      ? this.http.put<void>(`${this.url}/${encodeURIComponent(id)}`, null)
      : this.http.delete<void>(`${this.url}/${encodeURIComponent(id)}`);
    return anfrage.pipe(
      map(() => merken),
      catchError((fehler) => {
        this.stand.set(vorher);
        return throwError(() => fehler);
      }),
    );
  }
}
