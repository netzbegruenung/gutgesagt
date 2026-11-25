import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { stillerKontext } from '../shared/selbst-nachladen';

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
}

export interface MeineTeams {
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

  /** 404: Schalter teams aus; ``still``: Hintergrund-Abfrage (STILLE_ABFRAGE). */
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
