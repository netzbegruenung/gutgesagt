/**
 * Das Einwilligungs-Budget (#788, GLOSSARY.md „Einwilligungs-Budget“): die eine Stelle,
 * die entscheidet, ob die App jetzt eine Einwilligungsfrage stellen darf. Nur mit dem
 * Schalter `einwilligung_im_gewinn`; ohne ihn fragt die App wie bisher.
 *
 * - Höchstens eine Frage je Besuch. Ein Besuch ist ein Laden der App in diesem Tab: Die
 *   App merkt sich nur im Arbeitsspeicher, was sie schon gefragt hat, nicht im Browser
 *   und nicht auf dem Server.
 * - Höchstens vier Fragen im ersten Monat. Gezählt werden die schon beantworteten
 *   Fragen, die der Server ohnehin kennt (GET /api/v1/usage/users/me/einwilligungs-moment).
 * - Art.-9-Einwilligung und Team beim Einlösen eines Teamlinks gehören zum Beitreten:
 *   Sie kommen immer, verbrauchen aber den Besuch.
 * - Die Frage nach Punkten und Meilensteinen kommt erst nach dem ersten Gewinn (eine
 *   Stimme oder „Ja, gepostet“) und nie direkt nach einem Lob: Lob und Frage stehen
 *   getrennt, damit die Freiwilligkeit nicht angreifbar wird.
 */

/** Die Einwilligungsfragen, die das Budget kennt. */
export type EinwilligungsFrage = 'art9' | 'team' | 'punkte' | 'sichtbarkeit';

/** Fragen, die zum Beitreten gehören und deshalb immer kommen. */
export const FRAGEN_BEIM_BEITRETEN: readonly EinwilligungsFrage[] = ['art9', 'team'];

export const FRAGEN_JE_BESUCH = 1;
export const FRAGEN_IM_ERSTEN_MONAT = 4;
export const ERSTER_MONAT_TAGE = 30;

/**
 * So lange nach einem Lob (Sofort-Dank nach einer Stimme, Dank nach „Ja, gepostet“)
 * kommt keine Frage: länger, als die Snackbar mit dem Dank steht.
 */
export const ABSTAND_NACH_LOB_MS = 10_000;

/** Antwort von GET /api/v1/usage/users/me/einwilligungs-moment. */
export interface EinwilligungsMoment {
  /** Mindestens eine eigene Stimme steht. */
  abgestimmt: boolean;
  /** Wie viele Einwilligungsfragen schon beantwortet sind. */
  beantwortet: number;
  /** Früheste Antwort auf Art. 9 oder die Nutzungsbedingungen (ISO), sonst null. */
  konto_seit: string | null;
}

export interface BudgetLage {
  /** Was in diesem Besuch schon gefragt wurde. */
  gezeigt: ReadonlySet<EinwilligungsFrage>;
  moment: EinwilligungsMoment;
  /** Wann in diesem Besuch zuletzt ein Gewinn mit Lob kam; null: keiner. */
  gewinnUm: number | null;
  jetzt: number;
}

/** Ob das Konto noch im ersten Monat ist; ohne bekannten Beginn gilt es als neu. */
export function imErstenMonat(kontoSeit: string | null, jetzt: number): boolean {
  if (!kontoSeit) {
    return true;
  }
  const beginn = Date.parse(kontoSeit);
  if (Number.isNaN(beginn)) {
    return true;
  }
  return jetzt - beginn < ERSTER_MONAT_TAGE * 24 * 60 * 60 * 1000;
}

/** Ob die Frage in dieser Lage gestellt werden darf. */
export function frageErlaubt(frage: EinwilligungsFrage, lage: BudgetLage): boolean {
  if (FRAGEN_BEIM_BEITRETEN.includes(frage)) {
    return true;
  }
  // Schon in diesem Besuch gefragt: Die Frage bleibt stehen, sie ist nicht neu.
  if (lage.gezeigt.has(frage)) {
    return true;
  }
  if (lage.gezeigt.size >= FRAGEN_JE_BESUCH) {
    return false;
  }
  if (imErstenMonat(lage.moment.konto_seit, lage.jetzt) && lage.moment.beantwortet >= FRAGEN_IM_ERSTEN_MONAT) {
    return false;
  }
  return true;
}

/**
 * Ob die Frage nach Punkten und Meilensteinen jetzt fällig ist: nach dem ersten Gewinn
 * (eine Stimme steht, oder in diesem Besuch „Ja, gepostet“), nicht direkt nach einem
 * Lob und nur, wenn das Budget es erlaubt.
 */
export function punkteFrageFaellig(lage: BudgetLage): boolean {
  if (lage.gezeigt.has('punkte')) {
    return true;
  }
  const gewinn = lage.moment.abgestimmt || lage.gewinnUm !== null;
  if (!gewinn) {
    return false;
  }
  if (lage.gewinnUm !== null && lage.jetzt - lage.gewinnUm < ABSTAND_NACH_LOB_MS) {
    return false;
  }
  return frageErlaubt('punkte', lage);
}
