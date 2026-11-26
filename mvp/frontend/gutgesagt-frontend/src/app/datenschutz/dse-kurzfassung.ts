import { InjectionToken } from '@angular/core';

/**
 * Kasten „Kurz gesagt“ oben in der Datenschutzerklärung (Schalter dse_kurzfassung).
 *
 * Wortlaut Jura: Die drei Sätze liefert Jura (Paket 27.11.); hier stehen bis dahin nur
 * Platzhalter. Jeder Satz muss einem Absatz im Volltext entsprechen, auf den sein Sprunglink
 * zeigt (id an diesem Absatz in datenschutz.component.html). Solange ein Satz noch den
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

// Wortlaut Jura: die drei Texte unten ersetzen, Anker nur ändern, wenn Jura einen anderen
// Absatz als Entsprechung nennt (dann die id dort setzen; der Ankertest prüft sie).
// Keine eckigen Klammern im Wortlaut: kurzfassungFertig hält jeden Text mit […] für einen
// Platzhalter und lässt den Kasten dann still weg, auch bei eingeschaltetem Schalter.
export const KURZFASSUNG_SAETZE: readonly KurzfassungSatz[] = [
  {
    // Wer verantwortlich ist. Den Namen nicht fest schreiben, sondern aus LEGAL_ENTITY.NAME
    // einsetzen (Organisation-neutral), etwa `… ${LEGAL_ENTITY.NAME} …`; der Rest des
    // Satzes ist Wortlaut Jura.
    text: `${KURZFASSUNG_PLATZHALTER} Wer verantwortlich ist`,
    anker: KURZFASSUNG_ANKER.verantwortlich,
    linkText: 'Mehr dazu',
  },
  {
    // Was gespeichert wird
    text: `${KURZFASSUNG_PLATZHALTER} Was gespeichert wird`,
    anker: KURZFASSUNG_ANKER.gespeichert,
    linkText: 'Mehr dazu',
  },
  {
    // Wie man löscht und widerruft
    text: `${KURZFASSUNG_PLATZHALTER} Wie du löschst und widerrufst`,
    anker: KURZFASSUNG_ANKER.loeschen,
    linkText: 'Mehr dazu',
  },
];

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
