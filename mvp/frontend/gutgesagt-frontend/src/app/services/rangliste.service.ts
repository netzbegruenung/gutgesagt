import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { stillerKontext } from '../shared/selbst-nachladen';

/** Ein Platz in der Rangliste: Ranglistenname oder, nur auf eigene Wahl, Anzeigename. */
export interface RanglistenPlatz {
  platz: number;
  name: string;
  punkte: number;
  /** Der eigene Eintrag */
  ich: boolean;
}

export interface Rangliste {
  /** Die ersten zehn Plätze; gleiche Punkte teilen sich den Platz. */
  oben: RanglistenPlatz[];
  /** Der eigene Platz, wenn er nicht unter den ersten zehn steht. */
  eigener: RanglistenPlatz | null;
  teilnehmende: number;
}

/** GET /api/v1/rangliste (#793): nur für die angemeldete Person selbst. */
export interface RanglisteStand {
  gefragt: boolean;
  teilnehmen: boolean | null;
  mit_anzeigename: boolean;
  /** Art.-9-Einwilligung und „Punkte und Meilensteine“ gelten. */
  voraussetzungen: boolean;
  /** Erst mit dem ersten Ja vergeben. */
  ranglistenname: string | null;
  anzeigename: string | null;
  saison: { name: string; ende: string } | null;
  /** Nur für Teilnehmende mit laufender Saison. */
  eigene_punkte: number | null;
  /** null: nicht teilnehmend, keine laufende Saison oder unter min_teilnehmende. */
  rangliste: Rangliste | null;
  /** Vergangene Saisons nur als Summe der eigenen Punkte. */
  vergangene: { name: string; punkte: number }[];
  min_teilnehmende: number;
  aktueller_wortlaut: { kennung: string; text: string };
}

/**
 * Rangliste je Saison mit eigener Einwilligung (#793, Schalter „rangliste“). Ohne
 * wirksamen Schalter antwortet der Server mit 404. Kein teilbarer Link, kein Export.
 */
@Injectable({ providedIn: 'root' })
export class RanglisteService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.baseUrl}/api/v1/rangliste`;

  /** ``still``: Nachladen im Hintergrund, ohne Umleitung zur Anmeldung bei 401. */
  laden(still = false): Observable<RanglisteStand> {
    return this.http.get<RanglisteStand>(this.baseUrl, { context: still ? stillerKontext() : undefined });
  }

  /** Ja oder Nein, mit der Kennung des gezeigten Wortlauts; jederzeit änderbar. */
  antworten(teilnehmen: boolean, mitAnzeigename: boolean, wortlaut: string): Observable<unknown> {
    return this.http.put(`${this.baseUrl}/einwilligung`, {
      teilnehmen,
      mit_anzeigename: mitAnzeigename,
      wortlaut,
    });
  }
}
