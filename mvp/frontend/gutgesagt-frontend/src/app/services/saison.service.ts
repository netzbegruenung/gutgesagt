import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, of, throwError } from 'rxjs';
import { catchError, map, switchMap } from 'rxjs/operators';

import { environment } from '../../environments/environment';
import { stillerKontext } from '../shared/selbst-nachladen';
import { FunktionenService } from './funktionen.service';

/** Name des Schalters (services/schalter_service.py, SPIEL_SCHALTER). */
export const SAISON_SCHALTER = 'saison_ziel';

/** Der Balken der laufenden Saison (#782): nur Name, Ziel und Summe. */
export interface SaisonBalken {
  name: string;
  /** Gemeinschaftsziel in Widerspruchs-Wochen */
  ziel: number;
  /** Widerspruchs-Wochen aus abgeschlossenen Wochen der Saison */
  erreicht: number;
}

export type SaisonZustand = 'geplant' | 'laufend' | 'vorbei';

/** Eine Saison auf der Admin-Seite. */
export interface Saison {
  id: string;
  name: string;
  /** ISO-Datum JJJJ-MM-TT, erster Tag */
  beginn: string;
  /** ISO-Datum, letzter Tag */
  ende: string;
  ziel: number;
  zustand: SaisonZustand;
  erreicht: number;
  /** Nur die laufende Saison: verschiedene Menschen der laufenden Woche bisher */
  laufende_woche: number | null;
  /**
   * Meldungen ohne Konto (#799) aus abgeschlossenen Wochen der Saison: Klicks, keine
   * Menschen; nur daneben, nicht im Ziel und nicht in der Schwelle. Fehlt bei älterem Server.
   */
  meldungen_ohne_konto?: number;
  /** Nur die laufende Saison: Meldungen ohne Konto der laufenden Woche bisher. */
  laufende_woche_ohne_konto?: number | null;
}

export interface SaisonListe {
  saisons: Saison[];
  schalter_wirksam: boolean;
  schwelle_erreicht: boolean;
  schwelle_menschen: number;
  schwelle_wochen: number;
  name_max: number;
}

export interface SaisonEingabe {
  name: string;
  beginn: string;
  ende: string;
  ziel: number;
}

/**
 * Saisons mit Gemeinschaftsziel (#782, Schalter „saison_ziel“): der Balken für alle und
 * die Pflege für Admins (Seite „Schalter“).
 */
@Injectable({ providedIn: 'root' })
export class SaisonService {
  private readonly http = inject(HttpClient);
  private readonly funktionen = inject(FunktionenService);
  private readonly admin = `${environment.baseUrl}/api/v1/moderation/saisons`;

  /**
   * Der Balken der laufenden Saison; null, solange der Schalter aus ist, keine Saison
   * läuft oder die Schwelle nicht erreicht ist. Meldet FunktionenService den Schalter
   * sicher aus, fragt die Startseite den Endpunkt gar nicht; sonst antwortet er auch bei
   * Schalter aus mit 200 (`aktiv: false`), nie 404 (Gateway-fail2ban, Saal-WLAN). Ein 404
   * kommt nur noch von einem älteren Backend und gilt ebenso als aus. Andere Fehler gehen
   * weiter, damit das Nachladen den letzten Stand behält.
   */
  aktuell(): Observable<SaisonBalken | null> {
    return this.funktionen.stand$(SAISON_SCHALTER).pipe(
      switchMap((an) =>
        an === false
          ? of(null)
          : this.http
              .get<{ balken: SaisonBalken | null; aktiv?: boolean }>(`${environment.baseUrl}/api/v1/saisons/aktuell`, {
                context: stillerKontext(),
              })
              .pipe(
                map((antwort) => (antwort?.aktiv === false ? null : (antwort?.balken ?? null))),
                catchError((fehler: { status?: number }) =>
                  fehler?.status === 404 ? of(null) : throwError(() => fehler),
                ),
              ),
      ),
    );
  }

  liste(still = false): Observable<SaisonListe> {
    return this.http.get<SaisonListe>(this.admin, { context: still ? stillerKontext() : undefined });
  }

  anlegen(eingabe: SaisonEingabe): Observable<SaisonListe> {
    return this.http.post<SaisonListe>(this.admin, eingabe);
  }

  aendern(id: string, eingabe: SaisonEingabe): Observable<SaisonListe> {
    return this.http.put<SaisonListe>(`${this.admin}/${encodeURIComponent(id)}`, eingabe);
  }

  loeschen(id: string): Observable<void> {
    return this.http.delete<void>(`${this.admin}/${encodeURIComponent(id)}`);
  }
}
