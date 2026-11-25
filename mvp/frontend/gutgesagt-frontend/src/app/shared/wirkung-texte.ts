/**
 * Die Texte zu Wirkungs-Echo (#790) und Danke (#791), an einer Stelle. Zahlen ehrlich:
 * Gezählt werden Meldungen und Danke, nicht Menschen („3-mal öffentlich gepostet“).
 */

export const DANKE_KNOPF = 'Danke an die Autorin';
export const DANKE_ANGEKOMMEN = 'Dein Danke ist angekommen.';
export const DANKE_SCHON_HEUTE = 'Dein Danke von heute ist schon angekommen.';
export const DANKE_FEHLER = 'Das Danke hat gerade nicht geklappt. Versuch es gleich noch einmal.';

/** „3-mal öffentlich gepostet“; null bei 0 oder ohne Zahl: dann steht nichts da. */
export function oeffentlichGepostetText(anzahl: number | null | undefined): string | null {
  if (!anzahl || anzahl < 1) {
    return null;
  }
  return `${anzahl}-mal öffentlich gepostet`;
}

/** „5 Danke“ (auch „1 Danke“); null bei 0 oder ohne Zahl. */
export function dankeText(anzahl: number | null | undefined): string | null {
  if (!anzahl || anzahl < 1) {
    return null;
  }
  return `${anzahl} Danke`;
}
