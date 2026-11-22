/**
 * Aufzaehlungszeichen wie im Backend (utils/aufzaehlung.py): Steht am Zeilenanfang
 * "*" oder "-" vor einem Leerzeichen oder Tab, wird das Zeichen zu "•". Nur dieses
 * eine Zeichen wechselt, Laenge und Leerraum bleiben. Das Backend schreibt das beim
 * Speichern; die Vorschau im Formular zeigt dasselbe. Kein weiteres Markdown: Die
 * Zielplattformen zeigen keins. Anders als Python beginnt in JS mit dem Flag m eine
 * Zeile auch nach einem einzelnen "\r" oder U+2028; aus Textfeldern kommt "\n".
 */
const AUFZAEHLUNG = /^([ \t]*)[*-](?=[ \t])/gm;

/** Hinweis am Textfeld (nur Text, kein Symbol); der Strich in Anfuehrungszeichen, damit Screenreader ihn lesen. */
export const AUFZAEHLUNG_HINWEIS = 'Aufzählung: Zeile mit „-“ beginnen';

export function mitPunkten(text: string): string;
export function mitPunkten(text: string | null | undefined): string | null | undefined;
export function mitPunkten(text: string | null | undefined): string | null | undefined {
  return text ? text.replace(AUFZAEHLUNG, '$1•') : text;
}
