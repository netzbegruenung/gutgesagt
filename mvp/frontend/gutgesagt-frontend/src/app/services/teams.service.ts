import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { stillerKontext } from '../shared/selbst-nachladen';

/**
 * Team-Fortschritt der letzten abgeschlossenen Woche (nie der laufenden). Nur gerundete
 * Texte vom Server („weniger als 10“, „rund 45“), nie die genaue Zahl; unter 5 Mitgliedern
 * mit Einwilligung nur `waechst_noch`.
 */
export interface TeamWirkung {
  /** Montag der abgeschlossenen Woche, ISO-Datum. */
  woche: string;
  waechst_noch: boolean;
  beitraege: string | null;
  bewertungen: string | null;
  gepostet: string | null;
}

/** Team-Quest: das Ziel der laufenden Woche ohne Stand und ob die vorige geschafft ist. */
export interface TeamQuest {
  /** Montag der laufenden Woche; null, wenn es keine Quest gibt. */
  woche: string | null;
  ziel: number | null;
  thema: string | null;
  thema_name: string | null;
  /** Pfad des Motivs unter public/, rein dekorativ; der Name steht daneben. */
  thema_motiv: string | null;
  vorige_geschafft: boolean;
  vorige_thema_name: string | null;
}

/** Eine eigene Mitgliedschaft (GET /api/v1/teams/meine). */
export interface MeinTeam {
  /** Zum Verlassen: DELETE /api/v1/teams/meine/{id}. */
  id: string;
  team_name: string;
  motiv: string | null;
  motiv_name: string | null;
  saison: string;
  nummer: number;
  /** ISO-Datum (JJJJ-MM-TT). */
  eingetreten_am: string;
  /** Gehört zur aktuellen Saison; sonst ein Abzeichen einer vergangenen. */
  aktuelle_saison: boolean;
  /** Nur mit Schalter team_fortschritt; fehlt oder null: nichts zeigen. */
  wirkung?: TeamWirkung | null;
  /** Nur mit Schalter team_quests und ab 5 Mitgliedern; fehlt oder null: nichts zeigen. */
  quest?: TeamQuest | null;
}

export interface MeineTeams {
  /**
   * Schalter teams: false heißt, es gehen keine neuen Beitritte; die eigenen Teams stehen
   * trotzdem da, damit „Team verlassen“ (Widerruf) erreichbar bleibt. Fehlt: wie true.
   */
  teams_aktiv?: boolean;
  aktuelle_saison: string;
  /** Schalter teams_oeffentlich wirkt: nur dann den Umschalter zeigen. */
  oeffentlich_verfuegbar: boolean;
  /** Jüngste Antwort auf „Team öffentlich am Namen zeigen“; null: nie gefragt. */
  oeffentlich_zeigen: boolean | null;
  oeffentlich_kennung: string | null;
  oeffentlich_text: string | null;
  /** Alle Saisons, neueste zuerst. */
  teams: MeinTeam[];
}

/**
 * Die eigenen Teams (Glossar „Team“): lesen, verlassen und die Einwilligung „Team
 * öffentlich am Namen zeigen“. Nur für die angemeldete Person selbst; fremde
 * Mitgliedschaften gibt keine Schnittstelle heraus, auch nicht für Admins.
 */
@Injectable({ providedIn: 'root' })
export class TeamsService {
  private readonly baseUrl = `${environment.baseUrl}/api/v1/teams`;

  constructor(private http: HttpClient) {}

  /** Ohne Schalter teams und ohne eigene Teams `teams: []`, `teams_aktiv: false` (200, nie 404); ``still``: Hintergrund-Abfrage (STILLE_ABFRAGE). */
  meine(still = false): Observable<MeineTeams> {
    return this.http.get<MeineTeams>(`${this.baseUrl}/meine`, { context: still ? stillerKontext() : undefined });
  }

  /** „Team verlassen“: löscht die eigene Mitgliedschaft sofort (Widerruf). */
  verlassen(id: string): Observable<unknown> {
    return this.http.delete(`${this.baseUrl}/meine/${encodeURIComponent(id)}`);
  }

  /** Einwilligung geben (``zeigen`` true, mit der Kennung des gezeigten Wortlauts) oder zurücknehmen. */
  oeffentlich(zeigen: boolean, wortlaut: string): Observable<unknown> {
    return this.http.put(`${this.baseUrl}/oeffentlich`, { zeigen, wortlaut });
  }
}
