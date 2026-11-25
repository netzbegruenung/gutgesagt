/**
 * Bestandszahl auf der Startseite (Entscheidung des Maintainers vom 25.11.2026): Solange der
 * Saisonbalken nicht öffentlich ist, zeigt sein Platz, wie viel schon da ist, etwa „Schon 750
 * Antworten auf 250 Sprüche“. Nur Inhalte, keine Personen, keine Nutzung, keine Konten.
 *
 * Gezählt wird, was /getMetrics ohnehin für alle liefert: sichtbare Kommentare und Aussagen ohne
 * unbeantwortete Suchanfragen (Vormoderation). Abgerundet auf runde Stufen, damit die Zahl nicht
 * täglich zuckt; nie aufgerundet, die Zahl ist also nie größer als der Bestand.
 */

/** Darunter zeigt der Platz nichts: „Schon 3 Antworten“ zeigt noch keinen Gewinn. */
export const BESTAND_MINDEST_ANTWORTEN = 10;

export interface Bestandszahl {
  /** Kommentare, abgerundet */
  antworten: number;
  /** Aussagen, abgerundet */
  sprueche: number;
}

/**
 * Nach unten auf eine runde Stufe: unter 10 genau, bis 99 auf Zehner, bis 999 auf 50er,
 * bis 9.999 auf Hunderter, darüber auf Tausender.
 */
export function abgerundet(wert: number): number {
  const n = Math.max(0, Math.floor(wert));
  const stufe = n < 10 ? 1 : n < 100 ? 10 : n < 1000 ? 50 : n < 10000 ? 100 : 1000;
  return n - (n % stufe);
}

/** null: zu wenig Bestand oder eine Zählung fehlt (0 heißt bei /getMetrics auch „Fehler“). */
export function bestandszahl(kommentare: number | undefined, aussagen: number | undefined): Bestandszahl | null {
  if (kommentare === undefined || aussagen === undefined || !(kommentare >= BESTAND_MINDEST_ANTWORTEN) || !(aussagen >= 1)) {
    return null;
  }
  return { antworten: abgerundet(kommentare), sprueche: abgerundet(aussagen) };
}
