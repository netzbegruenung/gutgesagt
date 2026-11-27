import { lohntWiederholung } from '../shared/lade-wiederholung';

/**
 * Texte, wenn die Suche scheitert (UX-Review 26.11.2026, Befund 1): nie der rohe HTTP-Text
 * („Http failure response for …: 503“), der wirkt im Saal-WLAN wie kaputt.
 */

/** Überschrift des Fehlerkastens, nur wenn die Seite es selbst noch einmal versucht. */
export const SUCHE_HAKT_TITEL = 'Einen Moment';

/**
 * Vorübergehend (kein Netz, Timeout, 429, 5xx): Die Ergebnisseite versucht es selbst noch
 * einmal (LadeWiederholung), deshalb verspricht der Satz das.
 */
export const SUCHE_HAKT = 'Die Suche hakt gerade, vermutlich ist das Netz voll. Wir versuchen es gleich noch einmal.';

/** Alles andere (etwa 400, 422): Warten hilft nicht, es bleibt der Knopf. */
export const SUCHE_GESCHEITERT = 'Die Suche hat gerade nicht geklappt. Tipp unten auf „Noch einmal suchen“.';

/** Der Knopf im Fehlerkasten. */
export const NOCHMAL_SUCHEN = 'Noch einmal suchen';

/** Die Überschrift zum Satz: „Einen Moment“ nur beim Neuversuch, sonst die übliche (leer). */
export function suchFehlerTitel(text: string | null | undefined): string {
  return text === SUCHE_HAKT ? SUCHE_HAKT_TITEL : '';
}

/** Der Satz zum Fehler: vorübergehend oder nicht, wie LadeWiederholung entscheidet. */
export function suchFehlerText(fehler: unknown): string {
  return lohntWiederholung(fehler) ? SUCHE_HAKT : SUCHE_GESCHEITERT;
}
