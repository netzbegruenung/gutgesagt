// Grenzen und Motive wie im Backend (domain/teams.py, api/v1/einladungen.py).
export const TEAM_NAME_MAX = 40;
export const TEAM_SAISON_MAX = 20;
// Teamname und Saison stehen an Namen und in Pillen: kein Markup, keine Schraegstriche,
// keine Steuerzeichen (TEAM_VERBOTEN im Backend).
// eslint-disable-next-line no-control-regex
const TEAM_VERBOTEN = /[<>&"\\/\x00-\x1f\x7f]/;

/** Hinweis zum Teamnamen, falls der Server keinen mitschickt (teamname_hinweis). */
export const TEAMNAME_HINWEIS =
  'Nur nach Anlass, Ort oder Saison benennen, etwa „BDK 26 Berlin“ oder „Bayreuth“. Nie nach Personen.';

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

/** Ein Team am Anzeigenamen (autor_teams): nur aktuelle Saison, ohne Nummer. */
export interface TeamAmNamen {
  name: string;
  motiv: string | null;
  motiv_name: string | null;
}

/** So viele Team-Pillen stehen am Namen, der Rest als „+N“. */
export const TEAMS_AM_NAMEN = 2;
