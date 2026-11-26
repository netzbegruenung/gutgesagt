import { DOCUMENT } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { environment } from '../../environments/environment';
import { FunktionenService } from '../services/funktionen.service';
import { stillerKontext } from './selbst-nachladen';

/** Name des Adresszusatzes: gutgesagt.de/?k=sticker (GLOSSARY.md „Kampagnenwort“). */
export const KAMPAGNENWORT_PARAM = 'k';

/** Was als Kampagnenwort gilt; alles andere wird ignoriert, nicht gemeldet. */
const WORT_MUSTER = /^[a-z0-9-]{1,20}$/;

/** Das Kampagnenwort aus einem Adresszusatz („?k=BDK“ → „bdk“), sonst null. */
export function kampagnenwortAus(suche: string | null | undefined): string | null {
  let wert: string | null;
  try {
    wert = new URLSearchParams(suche ?? '').get(KAMPAGNENWORT_PARAM);
  } catch {
    return null;
  }
  const wort = wert?.trim().toLowerCase() ?? '';
  return WORT_MUSTER.test(wort) ? wort : null;
}

/**
 * Das Kampagnenwort, mit dem die App geöffnet wurde (?k=sticker, ?k=bdk, ?k=g1 …). Gelesen
 * einmal beim Start aus der Adresse und nur im Arbeitsspeicher gehalten: kein Speicher im
 * Browser, kein Cookie. Zwei Funktionen hängen daran, je hinter ihrem Schalter (Standard aus,
 * vorläufige Jura-Einschätzung 26.11.2026):
 *
 * - Begrüßung nach dem Wort (`k_begruessung`, RundgangService): nur Anzeige.
 * - Ankunft melden (`k_ankuenfte`): einmal je geöffneter Seite `POST /api/v1/ankunft` mit dem
 *   Wort im Body, ohne Kennung; der Server zählt nur Wörter seiner Positivliste je Tag.
 */
@Injectable({ providedIn: 'root' })
export class KampagnenwortService {
  private readonly http = inject(HttpClient, { optional: true });
  private readonly funktionen = inject(FunktionenService);
  /** Das Wort aus der Adresse beim Start, klein geschrieben; null ohne ?k=. */
  readonly wort: string | null = kampagnenwortAus(inject(DOCUMENT).location?.search);
  private gemeldet = false;

  /**
   * Einmal je geöffneter Seite: die Ankunft melden, wenn ein Wort da ist und der Server den
   * Schalter als an meldet. Bei unbekanntem Stand (Server kennt den Schalter nicht, etwa ein
   * neues Frontend vor dem neuen Suchdienst, oder /funktionen scheitert) wird nicht gefragt:
   * sonst drohten 401/404 (docs/ARCHITECTURE.md „Automatically requested endpoints“). Eine
   * verpasste Ankunft ist der kleinere Preis. Fehler bleiben still: Für die Person ändert sich
   * dadurch nichts.
   */
  ankunftMelden(): void {
    const wort = this.wort;
    if (!wort || this.gemeldet || !this.http) return;
    this.gemeldet = true;
    this.funktionen.stand$('k_ankuenfte').subscribe((an) => {
      if (an !== true) return;
      this.http!
        .post(`${environment.baseUrl}/api/v1/ankunft`, { k: wort }, { context: stillerKontext() })
        .subscribe({ error: () => undefined });
    });
  }
}
