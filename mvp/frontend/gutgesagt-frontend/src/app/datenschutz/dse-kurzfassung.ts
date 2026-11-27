import { InjectionToken } from '@angular/core';

import { LEGAL_ENTITY } from '../shared/legal-entity';

/**
 * Kasten „Kurz gesagt“ oben in der Datenschutzerklärung (Schalter dse_kurzfassung).
 *
 * Wortlaut Jura: vorläufige Einschätzung vom 26.11.2026 (fünf Sätze, auf drei Punkte mit
 * Sprunglink und einen Schlusssatz verteilt). Jeder Satz muss einem Absatz im Volltext
 * entsprechen, auf den sein Sprunglink zeigt (id an diesem Absatz in datenschutz.component.html). Solange ein Satz noch den
 * Platzhalter trägt, bleibt der Kasten auch bei eingeschaltetem Schalter unsichtbar
 * (kurzfassungFertig), damit nie Platzhaltertext in der Erklärung steht.
 */

/** Kennzeichen eines noch nicht gelieferten Satzes; nie in einem echten Wortlaut verwenden. */
export const KURZFASSUNG_PLATZHALTER = '[Wortlaut Jura folgt]';

export interface KurzfassungSatz {
  /** Der Satz, wie er im Kasten steht. Wortlaut Jura. */
  readonly text: string;
  /** id des Absatzes im Volltext, auf den der Sprunglink zeigt. */
  readonly anker: string;
  /** Text des Sprunglinks, etwa „Mehr dazu“. */
  readonly linkText: string;
}

/** Sprunganker im Volltext; die ids stehen in datenschutz.component.html. */
export const KURZFASSUNG_ANKER = {
  verantwortlich: 'verantwortlicher',
  gespeichert: 'was-diese-erklaerung-abdeckt',
  loeschen: 'deine-rechte',
} as const;

// Wortlaut Jura (vorläufig 26.11.2026), auf die drei Sprunganker verteilt; der Schlusssatz
// steht in KURZFASSUNG_SCHLUSS. Anker nur ändern, wenn Jura einen anderen Absatz als
// Entsprechung nennt (dann die id dort setzen; der Ankertest prüft sie).
// Keine eckigen Klammern im Wortlaut: kurzfassungFertig hält jeden Text mit […] für einen
// Platzhalter und lässt den Kasten dann still weg, auch bei eingeschaltetem Schalter.
/** Der Text mit genau einem Punkt am Ende. */
function satzEnde(text: string): string {
  return text.endsWith('.') ? text : `${text}.`;
}

export const KURZFASSUNG_SAETZE: readonly KurzfassungSatz[] = [
  {
    // Wer verantwortlich ist. Bedingung Jura: der Name genau wie im Abschnitt
    // „Verantwortlicher“, deshalb aus LEGAL_ENTITY.NAME statt „die Netzbegrünung“. Der Name
    // endet auf „e. V.“; dessen Punkt schließt den Satz, sonst stünden zwei.
    text: `Verantwortlich für Gut gesagt ist ${satzEnde(LEGAL_ENTITY.NAME)}`,
    anker: KURZFASSUNG_ANKER.verantwortlich,
    linkText: 'Mehr dazu',
  },
  {
    // Was gespeichert wird
    text:
      'Suchen und Lesen geht ohne Konto. Wer mitmacht, gibt uns Beiträge und Bewertungen; was ' +
      'sich daraus über deine politische Haltung schließen lässt, verarbeiten wir nur mit ' +
      'deiner ausdrücklichen Einwilligung.',
    anker: KURZFASSUNG_ANKER.gespeichert,
    linkText: 'Mehr dazu',
  },
  {
    // Wie man löscht und widerruft
    text:
      'Jede Einwilligung kannst du unter „Meine Beiträge“ widerrufen und dein Konto jederzeit ' +
      'löschen.',
    anker: KURZFASSUNG_ANKER.loeschen,
    linkText: 'Mehr dazu',
  },
];

/** Schlusssatz des Kastens, unter den drei Sätzen (Wortlaut Jura). */
export const KURZFASSUNG_SCHLUSS = 'Alle Einzelheiten stehen unten.';

/** Sätze des Kastens; Standard KURZFASSUNG_SAETZE, in Tests per Provider ersetzbar. */
export const KURZFASSUNG = new InjectionToken<readonly KurzfassungSatz[]>('KURZFASSUNG', {
  providedIn: 'root',
  factory: () => KURZFASSUNG_SAETZE,
});

/**
 * Ob die Sätze gezeigt werden dürfen: genau drei, keiner leer, keiner mit Platzhalter und
 * jeder mit Anker. Sonst bleibt der Kasten weg, auch wenn der Schalter an ist.
 */
export function kurzfassungFertig(saetze: readonly KurzfassungSatz[]): boolean {
  return (
    saetze.length === 3 &&
    saetze.every(
      (satz) =>
        satz.text.trim().length > 0 &&
        !satz.text.includes(KURZFASSUNG_PLATZHALTER) &&
        !/\[[^\]]*\]/.test(satz.text) &&
        satz.anker.trim().length > 0 &&
        satz.linkText.trim().length > 0
    )
  );
}
