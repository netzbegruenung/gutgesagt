/**
 * Die Texte zu Wirkungs-Echo (#790) und Danke (#791), an einer Stelle. Zahlen ehrlich:
 * Gezählt werden Meldungen und Danke, nicht Menschen („3-mal öffentlich gepostet“).
 */

export const DANKE_KNOPF = 'Danke an die Autorin';
/** Beschriftung des Knopfs nach dem Klick; er bleibt stehen, damit der Fokus nicht verloren geht. */
export const DANKE_GESAGT = 'Danke gesagt';
export const DANKE_ANGEKOMMEN = 'Dein Danke ist angekommen.';
/**
 * Hat der Server nicht gezaehlt (heute schon ein Danke von hier, derselbe Anschluss ohne
 * Konto, Beitrag gerade nicht lesbar), nennt der Text nur die Regel und behauptet nichts
 * ueber diese Person.
 */
export const DANKE_NICHT_GEZAEHLT = 'Danke! Gezählt wird höchstens ein Danke am Tag.';
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
