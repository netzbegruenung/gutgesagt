import { HttpClient } from '@angular/common/http';
import { Injectable, Signal, computed, inject, signal } from '@angular/core';
import { Observable, of } from 'rxjs';
import { catchError, map, tap, timeout } from 'rxjs/operators';

import { environment } from '../../environments/environment';

/**
 * Antwort von GET /api/v1/funktionen: je oeffentlichem Schalter (Name wie auf der
 * Admin-Seite, etwa „sharepic“), ob er wirkt.
 */
export interface FunktionenAntwort {
  funktionen: Record<string, boolean>;
}

/** So lange wartet frisch() auf den Server, dann gilt aus. */
export const FUNKTIONEN_FRISCH_WARTEN_MS = 3000;

/** So alt darf der Stand werden; danach fragt die nächste Karte, die ihn braucht, neu. */
export const FUNKTIONEN_NACHLADEN_MS = 5 * 60 * 1000;

/**
 * Welche Funktionen hinter einem Schalter an sind (Glossar „Schalter“, #708), für
 * Funktionen, die nur im Browser laufen oder die die App ohne eigenen Abruf ausblendet. Gefragt wird beim ersten
 * Zugriff und wieder, wenn der Stand älter als FUNKTIONEN_NACHLADEN_MS ist und eine
 * Komponente ihn braucht: So kommt ein Umschalten auf der Admin-Seite an, ohne dass
 * jemand neu lädt, und ohne dauernd laufenden Takt. Bis zur ersten Antwort gilt aus: Eine
 * Funktion, die nicht sicher an ist, zeigt die App nicht. Nach einem Fehler bleibt der
 * letzte bekannte Stand.
 */
@Injectable({ providedIn: 'root' })
export class FunktionenService {
  // Optional: Ohne HttpClient (Komponenten-Tests ohne Backend) bleibt alles aus.
  private readonly http = inject(HttpClient, { optional: true });
  private readonly stand = signal<FunktionenAntwort['funktionen']>({});
  private gefragtUm: number | null = null;
  private unterwegs = false;

  /** Ob die Funktion an ist; als Signal, damit OnPush-Vorlagen beim Umschalten neu zeichnen. */
  an(name: string): Signal<boolean> {
    this.auffrischen();
    return computed(() => this.stand()[name] === true);
  }

  /**
   * Der Stand dieser Funktion direkt vom Server, für Entscheidungen beim Laden einer
   * Adresse (App-Abkürzungen, #757). Antwortet der Server nicht binnen
   * FUNKTIONEN_FRISCH_WARTEN_MS oder mit Fehler, gilt aus.
   */
  frisch(name: string): Observable<boolean> {
    if (!this.http) {
      return of(false);
    }
    return this.http.get<FunktionenAntwort>(`${environment.baseUrl}/api/v1/funktionen`).pipe(
      timeout(FUNKTIONEN_FRISCH_WARTEN_MS),
      tap((antwort) => {
        this.gefragtUm = Date.now();
        this.stand.set(antwort?.funktionen ?? {});
      }),
      map((antwort) => antwort?.funktionen?.[name] === true),
      catchError(() => of(false)),
    );
  }

  private auffrischen(): void {
    if (!this.http || this.unterwegs) {
      return;
    }
    if (this.gefragtUm !== null && Date.now() - this.gefragtUm < FUNKTIONEN_NACHLADEN_MS) {
      return;
    }
    this.unterwegs = true;
    this.gefragtUm = Date.now();
    this.http.get<FunktionenAntwort>(`${environment.baseUrl}/api/v1/funktionen`).subscribe({
      next: (antwort) => {
        this.unterwegs = false;
        this.stand.set(antwort?.funktionen ?? {});
      },
      error: () => {
        this.unterwegs = false;
      },
    });
  }
}
