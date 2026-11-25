import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { stillerKontext } from '../shared/selbst-nachladen';

/** Schalter der Gartenansicht (#783), wie im Backend (services/gartenansicht_service.py). */
export const GARTEN_SCHALTER = 'gartenansicht';

/** Ein Thema mit seinen Zahlen; Besucher wie Angemeldete bekommen nur Zahlen. */
export interface Beet {
  schluessel: string;
  name: string;
  /** Pfad eines SVG unter public/, rein dekorativ; der Name steht immer daneben. */
  motiv?: string | null;
  antworten: number;
  ohne_antwort: number;
}

export interface GartenAntwort {
  beete: Beet[];
}

/** GET /api/v1/search/garten: offen wie die Suche, ohne Schalter 404. */
@Injectable({ providedIn: 'root' })
export class GartenService {
  private readonly http = inject(HttpClient);

  beete(): Observable<GartenAntwort> {
    // Still: die Seite laedt selbst nach, ein Fehler soll nie auf /login umleiten
    return this.http.get<GartenAntwort>(`${environment.baseUrl}/api/v1/search/garten`, {
      context: stillerKontext(),
    });
  }
}

/** „12 Antworten“, „1 Antwort“, „noch keine Antwort“. */
export function antwortenText(anzahl: number): string {
  if (anzahl <= 0) {
    return 'noch keine Antwort';
  }
  return anzahl === 1 ? '1 Antwort' : `${anzahl} Antworten`;
}

/**
 * So viele Aussagen zeigt „Hier fehlt eine Antwort“ hoechstens (LIMIT_STANDARD im Backend,
 * services/unbeantwortete_aussagen_service.py). Darueber nennt die Kachel „50+“, damit die
 * Zahl zur Liste hinter „Jetzt antworten“ passt (wie „Seit deinem letzten Besuch“).
 */
export const OHNE_ANTWORT_GRENZE = 50;

/** „3 Sprüche ohne Antwort“, „1 Spruch ohne Antwort“, „50+ Sprüche ohne Antwort“; leer bei 0. */
export function ohneAntwortText(anzahl: number): string {
  if (anzahl <= 0) {
    return '';
  }
  if (anzahl > OHNE_ANTWORT_GRENZE) {
    return `${OHNE_ANTWORT_GRENZE}+ Sprüche ohne Antwort`;
  }
  return anzahl === 1 ? '1 Spruch ohne Antwort' : `${anzahl} Sprüche ohne Antwort`;
}
