/**
 * Aufzaehlungszeichen wie im Backend (utils/aufzaehlung.py): Zeilen, die mit "* " oder
 * "- " beginnen, werden zu "• ". Das Backend schreibt das beim Speichern; die Vorschau
 * im Formular zeigt dasselbe. Kein weiteres Markdown: Die Zielplattformen zeigen keins.
 */
const AUFZAEHLUNG = /^([ \t]*)[*-][ \t]+/gm;

/** Hinweis am Textfeld (nur Text, kein Symbol). */
export const AUFZAEHLUNG_HINWEIS = 'Aufzählung: Zeile mit - beginnen';

export function mitPunkten(text: string): string;
export function mitPunkten(text: string | null | undefined): string | null | undefined;
export function mitPunkten(text: string | null | undefined): string | null | undefined {
  return text ? text.replace(AUFZAEHLUNG, '$1• ') : text;
}
