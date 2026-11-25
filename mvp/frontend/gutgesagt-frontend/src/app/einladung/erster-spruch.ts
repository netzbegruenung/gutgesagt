import { ROUTES } from '../shared/constants/app.constants';
import { SUCHFELD_FOKUS_FRAGMENT } from '../naechster-schritt/naechster-schritt';

/**
 * Der erste leichte Schritt nach dem Beitreten (UX-Review 25.11.2026, Vorschlag 5): nicht
 * schreiben, sondern den Spruch suchen, der einen zuletzt geärgert hat. Gleich nach dem
 * Teamergebnis auf /einladung und auf der Begrüßung nach einer Einladung ohne Team
 * (/willkommen). Kein Rechtstext: Er steht nach Beitritt und Konto, nicht vor einer Frage.
 */
export const ERSTER_SPRUCH = {
  satz:
    'Leg gleich los: Such den Spruch, der dich zuletzt geärgert hat. Meist findest du in ' +
    'Sekunden eine gute Antwort zum Kopieren.',
  knopf: 'Ersten Spruch suchen',
  /** Die Startseite; das Fragment setzt dort den Fokus ins Suchfeld (search-view). */
  ziel: ROUTES.SEARCH,
  fragment: SUCHFELD_FOKUS_FRAGMENT,
} as const;
