// Grenzen und Motive wie im Backend (domain/teams.py, domain/team_emoji.py, api/v1/einladungen.py).
export const TEAM_NAME_MAX = 40;
export const TEAM_SAISON_MAX = 20;
// Der Teamname steht an Namen und in Pillen: kein Markup, keine Schraegstriche, keine
// Steuerzeichen (TEAM_VERBOTEN im Backend).
// eslint-disable-next-line no-control-regex
const TEAM_VERBOTEN = /[<>&"\\/\x00-\x1f\x7f]/;
// Die Saison wie bei den Saisons (SAISON_VERBOTEN in domain/teams.py): der Schraegstrich
// geht („Winter 26/27“), damit jede angelegte Saison auch am Teamlink geht.
// eslint-disable-next-line no-control-regex
const SAISON_VERBOTEN = /[<>&"\\\x00-\x1f\x7f]/;

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

/** Ein Motiv: Schlüssel und Name, der immer daneben steht. */
export interface TeamMotiv {
  schluessel: string;
  name: string;
}

/**
 * Ein Eintrag der festen Emoji-Liste (domain/team_emoji.py), wie ihn GET /einladungen schickt:
 * das Emoji als Schlüssel, der deutsche CLDR-Kurzname, die Kategorie und Stichworte für die Suche.
 */
export interface TeamMotivEintrag extends TeamMotiv {
  kategorie: string;
  stichworte?: string;
}

/** Eine Kategorie der Emoji-Liste (Tiere & Natur, Essen & Trinken …). */
export interface TeamMotivKategorie {
  schluessel: string;
  name: string;
}

/**
 * Die sechs ersten Teammotive (Meilenstein-Motive, Fluent Emoji, MIT). Neue Teams wählen seit
 * 28.11.2026 ein Emoji aus der festen Liste; Teams mit diesen Schlüsseln gibt es weiter, sie
 * zeigen das Bild unter public/meilensteine.
 */
export const TEAM_MOTIVE: readonly TeamMotiv[] = [
  { schluessel: 'vogel', name: 'Vogel' },
  { schluessel: 'sprechblase', name: 'Sprechblase' },
  { schluessel: 'handschlag', name: 'Handschlag' },
  { schluessel: 'laufschuh', name: 'Laufschuh' },
  { schluessel: 'waage', name: 'Waage' },
  { schluessel: 'lautsprecher', name: 'Lautsprecher' },
];

/**
 * Bildadresse eines der sechs früheren Motive; sonst null (dann ein Emoji oder kein Bild, der
 * Teamname steht trotzdem da).
 */
export function motivBild(schluessel: string | null | undefined): string | null {
  return TEAM_MOTIVE.some((m) => m.schluessel === schluessel) ? `/meilensteine/${schluessel}.svg` : null;
}

/**
 * Das Emoji eines Motivs zum Zeichnen als Text, sonst null. Welche Emoji gelten, prüft der
 * Server (feste Liste); hier nur, dass es ein einzelnes Zeichen ohne ASCII ist, höchstens mit
 * Variantenwähler, damit nie ein früherer Schlüssel oder fremder Text als Motiv erscheint.
 */
export function motivEmoji(motiv: string | null | undefined): string | null {
  if (!motiv || motivBild(motiv)) {
    return null;
  }
  const zeichen = [...motiv];
  const einzeln = zeichen.length === 1 || (zeichen.length === 2 && zeichen[1] === '\uFE0F');
  // eslint-disable-next-line no-control-regex
  return einzeln && !/[\x00-\x7f]/.test(motiv) ? motiv : null;
}

/** Name eines der sechs früheren Motive, für Beschriftungen ohne Namen vom Server. */
export function motivName(schluessel: string | null | undefined): string | null {
  return TEAM_MOTIVE.find((m) => m.schluessel === schluessel)?.name ?? null;
}

/**
 * Treffer der Suche im Admin-Formular: jedes Wort der Suche steht im Namen, in den Stichworten
 * oder im Namen der Kategorie (ohne Groß/klein, ohne Akzente). Leere Suche: alle.
 */
export function motiveSuchen(
  motive: readonly TeamMotivEintrag[],
  suche: string,
  kategorien: readonly TeamMotivKategorie[] = [],
): TeamMotivEintrag[] {
  const norm = (t: string) => t.toLocaleLowerCase('de').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  const woerter = norm(suche).split(/\s+/).filter(Boolean);
  if (!woerter.length) {
    return [...motive];
  }
  const katName = new Map(kategorien.map((k) => [k.schluessel, k.name]));
  return motive.filter((m) => {
    const text = norm(`${m.name} ${m.stichworte ?? ''} ${katName.get(m.kategorie) ?? ''}`);
    return woerter.every((w) => text.includes(w)) || m.schluessel === suche.trim();
  });
}

/** Ob der Teamname so durchgeht, wie das Backend ihn prüft; leer zählt nicht. */
export function teamTextGueltig(text: string, max: number): boolean {
  const t = text.trim().split(/\s+/).join(' ');
  return t.length > 0 && t.length <= max && !TEAM_VERBOTEN.test(text);
}

/**
 * Ob die Saison am Teamlink so durchgeht, wie das Backend sie prüft (Schrägstrich erlaubt). Ob es
 * die Saison gibt, prüft der Server.
 */
export function teamSaisonGueltig(text: string, max: number): boolean {
  const t = text.trim().split(/\s+/).join(' ');
  return t.length > 0 && t.length <= max && !SAISON_VERBOTEN.test(text);
}

/** Ein Team am Anzeigenamen (autor_teams): nur aktuelle Saison, ohne Nummer. */
export interface TeamAmNamen {
  name: string;
  motiv: string | null;
  motiv_name: string | null;
}

/** So viele Team-Pillen stehen am Namen, der Rest als „+N“. */
export const TEAMS_AM_NAMEN = 2;
