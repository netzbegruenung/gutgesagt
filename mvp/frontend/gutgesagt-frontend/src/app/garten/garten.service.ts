import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { stillerKontext } from '../shared/selbst-nachladen';

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
  /** false: nur von einem älteren Backend mit Schalter (dann 200 statt 404, Gateway-fail2ban). */
  aktiv?: boolean;
}

/**
 * GET /api/v1/search/garten: offen wie die Suche (Gartenansicht #783, Basisfunktion seit
 * dem Schalter-Umbau 27.11.).
 */
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

/** „12 Antworten“, „1 Antwort“; bei 0 nach Anfang: „wartet auf die erste Antwort“ (Leerzustände 26.11.). */
export function antwortenText(anzahl: number): string {
  if (anzahl <= 0) {
    return 'wartet auf die erste Antwort';
  }
  return anzahl === 1 ? '1 Antwort' : `${anzahl} Antworten`;
}

/**
 * Die Beete in zwei Gruppen, je in der Reihenfolge des Servers: erst die Themen mit
 * Antworten, dann die ohne (Leerzustände 26.11.). Viele leere Kacheln zwischen den vollen
 * wirken wie eine Brache; gesammelt unten heißen sie „Hier ist noch Platz“.
 */
export function beeteGruppieren(beete: readonly Beet[]): { mitAntworten: Beet[]; nochPlatz: Beet[] } {
  return {
    mitAntworten: beete.filter((beet) => beet.antworten > 0),
    nochPlatz: beete.filter((beet) => !(beet.antworten > 0)),
  };
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
