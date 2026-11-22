import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { stillerKontext } from '../../shared/selbst-nachladen';

/** Ergebnis je Link (utils/sicherer_abruf.py im Suchdienst). */
export type HerkunftErgebnis = 'ok' | 'umgezogen' | 'tot' | 'fehler' | 'nicht_erreichbar' | 'gesperrt';

export interface AuffaelligeHerkunft {
  herkunft_id: string;
  adresse: string;
  ergebnis: HerkunftErgebnis;
  http_status: number | null;
  ziel: string | null;
  geprueft_am: string;
  auffaellig_seit: string | null;
}

export interface HerkunftPruefenStand {
  /** Schalter „herkunft_pruefen“ wirksam; sonst ist alles andere leer. */
  aktiv: boolean;
  laeuft: boolean;
  geprueft: number;
  letzter_lauf: string | null;
  /** Alle auffälligen; die Liste zeigt höchstens 200 davon. */
  auffaellig_gesamt: number;
  auffaellig: AuffaelligeHerkunft[];
}

/** Herkunft prüfen (#759), nur für Admins. */
@Injectable({ providedIn: 'root' })
export class HerkunftPruefenService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.baseUrl}/api/v1/herkunft-pruefen`;

  stand(still = false): Observable<HerkunftPruefenStand> {
    return this.http.get<HerkunftPruefenStand>(this.url, { context: still ? stillerKontext() : undefined });
  }

  anstossen(): Observable<void> {
    return this.http.post<void>(`${this.url}/lauf`, null);
  }
}
