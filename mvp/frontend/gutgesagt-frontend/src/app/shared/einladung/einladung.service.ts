import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../environments/environment';
import { stillerKontext } from '../selbst-nachladen';
import { BeitretenAntwort, PruefenAntwort, TeamAntwort } from './team-einladung';

// Grenzen wie im Backend (services/einladung_service.py).
export const EINLADUNG_NOTIZ_MAX = 200;
export const EINLADUNG_EINLOESUNGEN_MAX = 1000;
// Wie NAME_MAX und NAME_VERBOTEN in api/v1/einladungen.py: was das Benutzerprofil von
// Keycloak bei Vor- und Nachnamen ablehnt, dazu "@" (kein Anzeigename in der BFF).
export const EINLADUNG_NAME_MAX = 100;
// eslint-disable-next-line no-control-regex
const NAME_VERBOTEN = /[<>&"\v$%!#?§;*~/\\|^=[\]{}()@\x00-\x1f\x7f]/;

/** Ob Keycloak den Namen nimmt; leer zählt nicht als gültig. */
export function nameGueltig(name: string): boolean {
  const n = name.trim();
  return n.length > 0 && n.length <= EINLADUNG_NAME_MAX && !NAME_VERBOTEN.test(n);
}

export type EinladungZustand = 'aktiv' | 'abgeschaltet' | 'abgelaufen' | 'aufgebraucht';

/** Eine Einladung, wie Admins sie im Admin-Dashboard sehen. */
export interface Einladung {
  id: string;
  code: string;
  notiz: string;
  erlaubte_einloesungen: number;
  einloesungen: number;
  /** ISO-Datum (JJJJ-MM-TT), der letzte Tag, an dem sie gilt. */
  gueltig_bis: string;
  abgeschaltet: boolean;
  angelegt_am: string;
  zustand: EinladungZustand;
  /** Team an der Einladung, nur mit Schalter teams; ``mitglieder`` ist nur eine Zahl, nie wer. */
  team?: EinladungTeam | null;
}

export interface EinladungTeam {
  name: string;
  motiv: string | null;
  saison: string;
  mitglieder: number;
}

/** Team für eine neue Einladung (POST): Name nur nach Anlass, Ort oder Saison. */
export interface EinladungTeamFelder {
  team_name: string;
  team_motiv: string;
  team_saison: string;
}

export interface EinladungListe {
  einloesen_eingerichtet: boolean;
  einladungen: Einladung[];
  /** Schalter teams wirkt: nur dann der Block „Team (optional)“ im Formular. */
  teams_aktiv?: boolean;
  /** Vorschlag für die Saison neuer Teamlinks (Admin-Einstellung). */
  aktuelle_saison?: string | null;
  motive?: { schluessel: string; name: string }[];
  /** Hinweis zum Teamnamen fürs Formular. */
  teamname_hinweis?: string | null;
}

/** Der Link, den ein Admin weitergibt. Der Code steht hinter #, damit er in keinem Server-Log landet. */
export function einladungslink(code: string, origin = window.location.origin): string {
  return `${origin}/einladung#${code}`;
}

/**
 * Einladungen (#429). Verwalten duerfen nur Admins; pruefen und einloesen jede Person
 * mit dem Link, ohne Anmeldung.
 */
@Injectable({ providedIn: 'root' })
export class EinladungService {
  private baseUrl = `${environment.baseUrl}/api/v1/einladungen`;

  constructor(private http: HttpClient) {}

  /** ``still``: Hintergrund-Abfrage (STILLE_ABFRAGE). */
  liste(still = false): Observable<EinladungListe> {
    return this.http.get<EinladungListe>(this.baseUrl, { context: still ? stillerKontext() : undefined });
  }

  /** ``team``: optional; ohne Schalter teams ignoriert der Server die Teamfelder. */
  anlegen(
    notiz: string,
    erlaubteEinloesungen: number,
    gueltigBis: string,
    team?: EinladungTeamFelder,
  ): Observable<Einladung> {
    return this.http.post<Einladung>(this.baseUrl, {
      notiz,
      erlaubte_einloesungen: erlaubteEinloesungen,
      gueltig_bis: gueltigBis,
      ...(team ?? {}),
    });
  }

  schalten(id: string, abgeschaltet: boolean): Observable<Einladung> {
    return this.http.patch<Einladung>(`${this.baseUrl}/${id}`, { abgeschaltet });
  }

  /** Ob die Einladung gilt und, bei wirksamem Schalter teams, ihr Team (sonst null). */
  pruefen(code: string): Observable<PruefenAntwort> {
    return this.http
      .post<Partial<PruefenAntwort>>(`${this.baseUrl}/pruefen`, { code })
      .pipe(map((antwort) => ({ einloesbar: antwort?.einloesbar === true, team: antwort?.team ?? null })));
  }

  /** ``team``: nur bei einer Einladung mit Team; ohne bleibt der Aufruf wie vor den Teams. */
  einloesen(code: string, email: string, vorname: string, nachname: string, team?: TeamAntwort): Observable<unknown> {
    const teamfelder = team ? { team_einwilligung: team.einwilligung, team_oeffentlich: team.einwilligung && team.oeffentlich } : {};
    return this.http.post(`${this.baseUrl}/einloesen`, { code, email, vorname, nachname, ...teamfelder });
  }

  /** Angemeldet dem Team der Einladung beitreten, nach dem Knopf „Ja, speichert …“. */
  beitreten(code: string, oeffentlich: boolean): Observable<BeitretenAntwort> {
    return this.http.post<BeitretenAntwort>(`${this.baseUrl}/beitreten`, { code, einwilligung: true, oeffentlich });
  }
}
