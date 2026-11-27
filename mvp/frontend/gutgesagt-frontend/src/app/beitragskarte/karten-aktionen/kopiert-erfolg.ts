import { STIL_LABEL, Stil } from '../../shared/zweck-stil';

/**
 * Erfolgstext nach dem Kopieren (#785, Schalter `kopiert_erfolg`): ein kurzer Satz, die
 * Nutzung von der Karte und, wenn es zur selben Aussage eine Antwort in anderem Stil
 * gibt, ein Hinweis darauf. Nichts davon wird gespeichert oder neu gezaehlt.
 */

/** Der Erfolgssatz; das Pflänzchen ist das eine Gartenwort auf dem Bildschirm. */
export const KOPIERT_ERFOLG = 'Kopiert. Viel Erfolg da draußen!';
export const KOPIERT_ERFOLG_ZEICHEN = '🌱';

/**
 * Eine Antwort zur selben Aussage in anderem Stil, wie die Ergebnisseite sie kennt
 * (result-view/andere-tonlage.ts). Fehlt sie, gibt es keinen Hinweis.
 */
export interface AndereTonlage {
  /** Content-ID der anderen Antwort; der Link fuehrt auf ihre eigene Adresse. */
  id: string;
  stil: Stil;
}

/**
 * Die Nutzung vor dieser Kopie (GLOSSARY „Nutzung“): Kopiervorgaenge, nie Menschen. Die
 * Karte gibt den Stand von vor dem Kopieren mit (karten-aktionen, `nutzungBeimKopieren`).
 * Bei 0 ist diese Kopie die erste, bei 1 die zweite: ein Anfang, kein ironisches „schon
 * 1-mal“ (Leerzustaende 26.11.). Am eigenen Beitrag zaehlt die Kopie nicht (api/v1/usage.py),
 * dort bei 0 kein Satz (sonst stünde bei jeder eigenen Kopie „die erste“). Null bei unbekannter Nutzung, dann steht nur der Erfolgssatz da.
 */
export function nutzungSatz(nutzung: number | null | undefined, eigen = false): string | null {
  if (nutzung === null || nutzung === undefined || !Number.isFinite(nutzung) || nutzung < 0) {
    return null;
  }
  const vorher = Math.floor(nutzung);
  if (vorher === 0) {
    return eigen ? null : 'Deine Kopie ist die erste.';
  }
  if (vorher === 1) {
    return eigen ? 'Einmal genutzt.' : 'Deine Kopie ist die zweite.';
  }
  return `Schon ${vorher.toLocaleString('de-DE')}-mal genutzt.`;
}

/** Die Frage vor dem Link, je Stil der anderen Antwort. */
const FRAGE: Record<Stil, string> = {
  humorvoll: 'Lieber mit einem Augenzwinkern?',
  sachlich: 'Lieber nüchtern?',
  persoenlich: 'Lieber aus eigenem Erleben?',
  brueckenbauend: 'Lieber freundlich?',
  bissig: 'Lieber zugespitzt?',
};

/**
 * Das Wort fuer den Stil in „Es gibt noch eine …“: das Wort der Oberflaeche (STIL_LABEL,
 * „freundlich“ statt „brückenbauend“) in der Form nach „eine“.
 */
function stilWort(stil: Stil): string {
  return `${STIL_LABEL[stil]}e`;
}

/** Frage und Linktext des Tonlagen-Hinweises, etwa „Lieber mit einem Augenzwinkern?“ und „Es gibt noch eine humorvolle.“ */
export function tonlagenHinweis(andere: AndereTonlage | null | undefined): { frage: string; link: string } | null {
  if (!andere || !Object.hasOwn(FRAGE, andere.stil)) {
    return null;
  }
  return { frage: FRAGE[andere.stil], link: `Es gibt noch eine ${stilWort(andere.stil)}.` };
}
