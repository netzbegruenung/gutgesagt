import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, of } from 'rxjs';
import { map, timeout } from 'rxjs/operators';

import { environment } from '../../environments/environment';
import { KartenDaten, ausSuchergebnis } from '../beitragskarte/karten-daten';
import { LADE_TIMEOUT_MS } from '../shared/lade-wiederholung';
import { STIL_LABEL, Stil } from '../shared/zweck-stil';

/** Name des Schalters (services/schalter_service.py, SPIEL_SCHALTER). */
export const KONTER_PROBE_SCHALTER = 'konter_probe';

/** Pfad im Suchdienst; nur lesend, der Tipp geht nie an den Server. */
export const KONTER_PROBE_PFAD = '/api/v1/konter-probe';

/** Eine Probe, wie GET /api/v1/konter-probe sie liefert. */
export interface KonterProbeAntwort {
  aussage: { id: string; text: string };
  /** Karten wie bei „Diese Woche oft genutzt“, je mit result_type, style und usage_count. */
  antworten: Record<string, any>[];
}

/** Eine Antwort der Probe, wie die Seite sie zeigt. */
export interface ProbeAntwort {
  karte: KartenDaten;
  stil: Stil;
  /** Sichtbarer Name der Tonlage, etwa „freundlich“ für brueckenbauend. */
  stilName: string;
  nutzung: number;
  /** Was vor dem Tipp zu lesen ist: die kurze Fassung, sonst der Text. */
  vorschau: string;
}

export interface KonterProbe {
  aussageId: string;
  spruch: string;
  antworten: ProbeAntwort[];
}

/** Aus der Antwort des Servers; Antworten ohne bekannten Stil fallen weg, Proben mit weniger als drei auch. */
export function ausAntwort(antwort: KonterProbeAntwort): KonterProbe | null {
  const antworten = antwort.antworten.flatMap((roh): ProbeAntwort[] => {
    const stil = roh['style'];
    if (typeof stil !== 'string' || !Object.hasOwn(STIL_LABEL, stil)) {
      return [];
    }
    // Kein Suchtreffer: ohne Aussage, Aehnlichkeit und Relevanz (wie „Diese Woche oft genutzt“).
    const karte = ausSuchergebnis({
      score: 1.0,
      statement_text: null,
      statement_similarity_score: null,
      reply_relevance: null,
      content_type: 'commentary',
      commentary_result: roh,
    });
    return [{
      karte,
      stil: stil as Stil,
      stilName: STIL_LABEL[stil as Stil],
      nutzung: Number(roh['usage_count']) || 0,
      vorschau: karte.extra?.kurz || karte.text || '',
    }];
  });
  if (antworten.length < 3) {
    return null;
  }
  return { aussageId: antwort.aussage.id, spruch: antwort.aussage.text, antworten };
}

/** Die meistgenutzte Antwort (der Server liefert nur Proben mit klarem Spitzenreiter). */
export function besteAntwort(probe: KonterProbe): ProbeAntwort {
  return probe.antworten.reduce((beste, a) => (a.nutzung > beste.nutzung ? a : beste));
}

/** „14-mal genutzt“, ehrlich und ohne Personen; 0 als „noch nicht genutzt“. */
export function nutzungText(nutzung: number): string {
  return nutzung > 0 ? `${nutzung}-mal genutzt` : 'noch nicht genutzt';
}

/**
 * Der Satz nach dem Tipp: „Getroffen, die humorvolle läuft am besten.“ oder ohne
 * Wertung „Diesmal läuft die sachliche am besten.“ Ausgewertet nur hier im Browser.
 */
export function ergebnisSatz(probe: KonterProbe, tipp: ProbeAntwort): string {
  const beste = besteAntwort(probe);
  const welche = `die ${beste.stilName}e`;
  return tipp === beste ? `Getroffen, ${welche} läuft am besten.` : `Diesmal läuft ${welche} am besten.`;
}

/**
 * Holt die Proben. Der Server mischt Auswahl und Reihenfolge; gespeichert wird nichts,
 * auch nicht im Browser.
 */
@Injectable({ providedIn: 'root' })
export class KonterProbeService {
  // Optional wie im FunktionenService: Komponenten-Tests der Startseite ohne Backend.
  private readonly http = inject(HttpClient, { optional: true });

  proben(): Observable<KonterProbe[]> {
    if (!this.http) {
      return of([]);
    }
    return this.http
      .get<{ proben: KonterProbeAntwort[] }>(`${environment.baseUrl}${KONTER_PROBE_PFAD}`)
      .pipe(
        timeout({ first: LADE_TIMEOUT_MS }),
        map((antwort) =>
          (antwort?.proben ?? []).map(ausAntwort).filter((p): p is KonterProbe => p !== null),
        ),
      );
  }
}
