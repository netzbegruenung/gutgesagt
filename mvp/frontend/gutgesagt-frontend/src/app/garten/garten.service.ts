import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, of } from 'rxjs';
import { switchMap } from 'rxjs/operators';

import { environment } from '../../environments/environment';
import { FunktionenService } from '../services/funktionen.service';
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
  /** false: Schalter aus (der Server antwortet dann 200 statt 404, Gateway-fail2ban). */
  aktiv?: boolean;
}

/**
 * GET /api/v1/search/garten: offen wie die Suche. Meldet FunktionenService den Schalter
 * sicher aus, fragt die Seite den Endpunkt nicht; sonst antwortet er ohne Schalter 200 mit
 * `aktiv: false`.
 */
@Injectable({ providedIn: 'root' })
export class GartenService {
  private readonly http = inject(HttpClient);
  private readonly funktionen = inject(FunktionenService);

  beete(): Observable<GartenAntwort> {
    return this.funktionen.stand$(GARTEN_SCHALTER).pipe(
      switchMap((an) =>
        an === false
          ? of<GartenAntwort>({ beete: [], aktiv: false })
          : // Still: die Seite laedt selbst nach, ein Fehler soll nie auf /login umleiten
            this.http.get<GartenAntwort>(`${environment.baseUrl}/api/v1/search/garten`, {
              context: stillerKontext(),
            }),
      ),
    );
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
