import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface AntwortAufAussage {
  id: string;
  content_type: string;
  titel: string;
  verknuepft_am: string;
  /** Die Antwort stammt von der Person selbst. */
  von_dir: boolean;
  /** Von jemand anderem und in den letzten ``zeitraum_tage`` Tagen verknüpft. */
  neu: boolean;
}

export interface EigeneAussage {
  id: string;
  text: string;
  created: string;
  antworten: AntwortAufAussage[];
}

export interface EigeneAussagen {
  zeitraum_tage: number;
  aussagen: EigeneAussage[];
}

/** „Meine Aussagen“ (#760): eigene Aussagen mit ihren Antworten; nur mit dem Schalter „antworten_hinweis“. */
@Injectable({ providedIn: 'root' })
export class MeineAussagenService {
  private readonly http = inject(HttpClient);

  laden(): Observable<EigeneAussagen> {
    return this.http.get<EigeneAussagen>(`${environment.baseUrl}/api/v1/usage/users/me/aussagen`);
  }
}
