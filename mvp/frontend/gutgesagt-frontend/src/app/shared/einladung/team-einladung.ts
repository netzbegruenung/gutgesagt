import { TEAM_MOTIVE as MOTIV_LISTE, motivBild } from '../teams/teams';

/**
 * Teams über Einladungen beim Einlösen (api/v1/einladungen.py): was /pruefen zum Team
 * sagt, was /beitreten antwortet. Die Texte der Einwilligungen kommen vom Backend
 * (domain/teams.py), damit gezeigter und gespeicherter Wortlaut nie auseinanderlaufen.
 */

/**
 * Das Team an einer einlösbaren Einladung, nur bei wirksamem Schalter teams. Ist die
 * Einladung nicht mehr einlösbar, kommt es nur für ein angemeldetes Mitglied (mit
 * eigene_nummer), damit es „Du bist schon dabei“ sieht.
 */
export interface TeamBeimPruefen {
  name: string;
  /** Schlüssel des Motivs (public/meilensteine/<motiv>.svg), siehe TEAM_MOTIVE. */
  motiv: string | null;
  saison: string;
  mitglieder: number;
  /** Die Nummer, die als nächste vergeben wird; fest erst beim Speichern. */
  naechste_nummer: number;
  /** Nummer der angemeldeten Person, wenn sie schon im Team ist. */
  eigene_nummer: number | null;
  einwilligung_kennung: string;
  einwilligung_text: string;
  knopf_ja: string;
  knopf_nein: string;
  /** Zweite Frage „Team öffentlich am Namen zeigen“; null: nicht fragen. */
  oeffentlich_kennung: string | null;
  oeffentlich_text: string | null;
}

/** Antwort von POST /einladungen/pruefen. */
export interface PruefenAntwort {
  einloesbar: boolean;
  team: TeamBeimPruefen | null;
}

/** Was beim Einlösen ohne Konto oder beim Beitreten zum Team mitgeht. */
export interface TeamAntwort {
  /** Knopf „Ja, speichert, dass ich im Team X bin“ */
  einwilligung: boolean;
  /** Kennung des gezeigten Wortlauts (aus /pruefen); gespeichert wird genau diese. */
  einwilligungKennung: string;
  /** Zweite Frage, zählt nur mit einwilligung */
  oeffentlich: boolean;
  /** Kennung des gezeigten Wortlauts der zweiten Frage; null, wenn sie nicht gestellt wurde. */
  oeffentlichKennung: string | null;
}

/** Antwort von POST /einladungen/beitreten. */
export interface BeitretenAntwort {
  team: { name: string; motiv: string | null; saison: string };
  nummer: number;
  /** false: schon dabei, nichts gezählt */
  neu: boolean;
}

/** Motive der Teams, Schlüssel → Name; eine Quelle mit shared/teams/teams.ts. */
export const TEAM_MOTIVE: Record<string, string> = Object.fromEntries(
  MOTIV_LISTE.map((m) => [m.schluessel, m.name]),
);

/** Pfad des Motivbilds oder null, wenn das Motiv unbekannt ist (dann nur der Name). */
export function teamMotivBild(motiv: string | null | undefined): string | null {
  return motivBild(motiv);
}
