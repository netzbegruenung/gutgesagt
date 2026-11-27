// Grenzen und Motive wie im Backend (domain/teams.py, api/v1/einladungen.py).
export const TEAM_NAME_MAX = 40;
export const TEAM_SAISON_MAX = 20;
// Teamname und Saison stehen an Namen und in Pillen: kein Markup, keine Schraegstriche,
// keine Steuerzeichen (TEAM_VERBOTEN im Backend).
// eslint-disable-next-line no-control-regex
const TEAM_VERBOTEN = /[<>&"\\/\x00-\x1f\x7f]/;

/** Hinweis zum Teamnamen, falls der Server keinen mitschickt (teamname_hinweis); wie TEAMNAME_HINWEIS im Backend. */
export const TEAMNAME_HINWEIS =
  'Anlass, Ort, Saison oder öffentliche Gruppe mit schriftlicher Zustimmung; keine Namen zu Religion, Gesundheit, sexueller Orientierung, Herkunft oder Gewerkschaft.';

/** Teamart an der Einladung (TEAM_ARTEN in domain/teams.py). */
export type TeamArt = 'anlass' | 'gruppe';

/** Die Auswahl im Admin-Formular; „anlass“ ist der Standard. */
export const TEAM_ARTEN: readonly { schluessel: TeamArt; name: string }[] = [
  { schluessel: 'anlass', name: 'Team nach Anlass, Ort oder Saison' },
  { schluessel: 'gruppe', name: 'Team nach Gruppe' },
];

/**
 * Bei „Team nach Gruppe“ ist der Teamname genau der Gruppenname: Die Begrüßung setzt ihn
 * als {gruppe} in den Satz zur Zustimmung (teamGruppeSatz). Beschriftung und Hinweis des Felds.
 */
export const TEAM_GRUPPENNAME_LABEL = 'Name der Gruppe (genau so, wie sie öffentlich heißt)';
export const TEAM_GRUPPENNAME_HINWEIS =
  'Ohne Zusätze wie Ort oder Jahr: Die Begrüßung nennt die Gruppe mit genau diesem Namen.';

/** Beschriftung des Pflichtfelds bei „Team nach Gruppe“. */
export const TEAM_ZUSTIMMUNG_LABEL = 'Zustimmung der Gruppenleitung liegt schriftlich vor (Datum)';

/** Ein Motiv: Schlüssel (Datei unter public/meilensteine) und Name, der immer daneben steht. */
export interface TeamMotiv {
  schluessel: string;
  name: string;
}

/** Die sechs Meilenstein-Motive (Fluent Emoji, MIT), vorerst auch die Teammotive. */
export const TEAM_MOTIVE: readonly TeamMotiv[] = [
  { schluessel: 'vogel', name: 'Vogel' },
  { schluessel: 'sprechblase', name: 'Sprechblase' },
  { schluessel: 'handschlag', name: 'Handschlag' },
  { schluessel: 'laufschuh', name: 'Laufschuh' },
  { schluessel: 'waage', name: 'Waage' },
  { schluessel: 'lautsprecher', name: 'Lautsprecher' },
];

/**
 * Bildadresse eines Motivs; nur bekannte Schlüssel, sonst null (dann kein Bild, der
 * Teamname steht trotzdem da).
 */
export function motivBild(schluessel: string | null | undefined): string | null {
  return TEAM_MOTIVE.some((m) => m.schluessel === schluessel) ? `/meilensteine/${schluessel}.svg` : null;
}

/** Name eines Motivs zum Schlüssel, für Beschriftungen ohne Namen vom Server. */
export function motivName(schluessel: string | null | undefined): string | null {
  return TEAM_MOTIVE.find((m) => m.schluessel === schluessel)?.name ?? null;
}

/** Ob Teamname bzw. Saison so durchgehen, wie das Backend sie prüft; leer zählt nicht. */
export function teamTextGueltig(text: string, max: number): boolean {
  const t = text.trim().split(/\s+/).join(' ');
  return t.length > 0 && t.length <= max && !TEAM_VERBOTEN.test(text);
}

/**
 * Die Saison an einem Teamlink: wie beim Anlegen der Saison nur ohne Steuerzeichen, damit ein
 * Name wie „Winter 26/27“ geht (Befund 6, backend api/v1/einladungen.py). Ob es die Saison
 * gibt, prüft der Server.
 */
// eslint-disable-next-line no-control-regex
const SAISON_STEUERZEICHEN = /[\x00-\x1f\x7f]/;

export function saisonTextGueltig(text: string, max: number): boolean {
  const t = text.trim().split(/\s+/).join(' ');
  return t.length > 0 && t.length <= max && !SAISON_STEUERZEICHEN.test(text);
}

/** Ein Team am Anzeigenamen (autor_teams): nur aktuelle Saison, ohne Nummer. */
export interface TeamAmNamen {
  name: string;
  motiv: string | null;
  motiv_name: string | null;
}

/** So viele Team-Pillen stehen am Namen, der Rest als „+N“. */
export const TEAMS_AM_NAMEN = 2;
