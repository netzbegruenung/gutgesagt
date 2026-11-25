/**
 * Die Texte der Rückmeldung „Gepostet?“ im Erfolgskasten nach dem Kopieren (#643), an einer Stelle.
 * Der Dank nennt eine echte Zahl: verschiedene Personen dieser Kalenderwoche, wie der
 * Server sie gezählt hat (CODING_STANDARDS.md „Visible numbers are real“).
 */
/**
 * Die Frage im Erfolgskasten nach dem Kopieren. Sie steht ohne Frist da, bis die Person
 * den Kasten schließt oder eine andere Karte kopiert: Posten dauert länger als eine
 * Snackbar (Review Spielgefühl 25.11., WCAG 2.2.1).
 */
export const GEPOSTET_FRAGE = 'Gepostet? Dann zählt dein Konter mit.';
export const JA_GEPOSTET = 'Ja, gepostet';
/** Der Knopf nach dem Tippen: Er bleibt stehen (Fokus), tut aber nichts mehr. */
export const GEPOSTET_GEMELDET = 'Gepostet';
/** Melden nicht angekommen: Der Knopf steht wieder bereit (Review 25.11.). */
export const GEPOSTET_NICHT_GEZAEHLT = 'Danke! Zählen hat gerade nicht geklappt. Versuch es gleich noch einmal.';
/**
 * Der Dank ohne Konto (#799): ohne Zahl, denn gezählt werden dort nur Meldungen, keine
 * Menschen; und ohne Aufforderung, sich anzumelden.
 */
export const GEPOSTET_OHNE_KONTO_DANK = 'Danke! Schön, dass du öffentlich konterst.';

/**
 * Der Dank nach „Ja, gepostet“; ``personen`` schließt die Person selbst ein. Die Zahl
 * ist eine Selbstauskunft, deshalb „gemeldet“.
 */
export function gepostetDank(personen: number | null): string {
  if (personen === null) {
    return GEPOSTET_NICHT_GEZAEHLT;
  }
  if (personen <= 1) {
    return 'Danke! Du bist diese Woche die erste Person, die meldet, dass sie öffentlich kontert.';
  }
  return `Danke! Diese Woche haben ${personen} Menschen gemeldet, dass sie öffentlich gekontert haben. Du bist dabei.`;
}
