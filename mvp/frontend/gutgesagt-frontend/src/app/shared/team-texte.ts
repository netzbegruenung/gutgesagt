/**
 * Texte der Teams (GLOSSARY.md „Team“, „Teamlink“, „Mitgliedschaft“), an einer Stelle,
 * damit Begrüßung, „Meine Teams“ und Datenschutzerklärung nicht auseinanderlaufen.
 *
 * Der Wortlaut der Einwilligung selbst (Kennung `team-2026-11-26`) und die beiden
 * Knöpfe stehen nicht hier, sondern im Backend (`domain/teams.py`); das Frontend zeigt,
 * was `POST /api/v1/einladungen/pruefen` liefert (`einwilligung_text`, `knopf_ja`,
 * `knopf_nein`), wie bei der Art.-9-Einwilligung (docs/ART9_EINWILLIGUNG.md).
 *
 * Wer einen Text hier ändert, prüft die Datenschutzerklärung, Abschnitt „Teams“, mit:
 * Rechtstexte ändern sich nur nach juristischer Prüfung (CODING_STANDARDS.md).
 */

/** Name der eigenen Sammlung, in „Meine Beiträge“ und in der Datenschutzerklärung. */
export const MEINE_TEAMS_TITEL = 'Meine Teams';

/** Der Widerruf der Einwilligung für ein Team; löscht die Mitgliedschaft sofort. */
export const TEAM_VERLASSEN = 'Team verlassen';

/** Kopf der Begrüßung vor dem Beitritt; die Nummer ist die voraussichtliche. */
export function teamBegruessungTitel(team: string, nummer: number): string {
  return `Herzlich willkommen im Team ${team}! Du wärst Nr. ${nummer}.`;
}

/**
 * Was vor der Frage steht (juristische Vorprüfung 24.11.2026): was gespeichert wird,
 * wer es sieht und wie man widerruft. Erst danach die beiden gleichwertigen Knöpfe.
 */
export function teamBegruessungSaetze(team: string): readonly string[] {
  return [
    `Wenn du willst, speichern wir an deinem Konto, dass du im Team ${team} bist, mit deiner Nummer und dem Tag.`,
    `Das siehst nur du, unter „${MEINE_TEAMS_TITEL}“.`,
    'Weil Gut gesagt grüne Argumente sammelt, kann das zusammen mit dem Teamnamen auf deine politische Haltung und deinen Ort schließen lassen.',
    `Du kannst das jederzeit unter „${MEINE_TEAMS_TITEL}“ mit „${TEAM_VERLASSEN}“ widerrufen, dann löschen wir es sofort.`,
  ];
}

/**
 * Satz direkt über der Frage, nur bei einem Team nach Gruppe (Teamart „gruppe“,
 * Wortlaut aus der juristischen Prüfung vom 25.11.2026); ``gruppe`` ist der Teamname.
 */
export function teamGruppeSatz(gruppe: string): string {
  return `Dieses Team ist mit Zustimmung von ${gruppe} nach ihr benannt. Verantwortlich für Gut gesagt ist allein die Netzbegrünung; ${gruppe} bekommt keine Daten über dich.`;
}

/** Verweis unter den Knöpfen auf den Abschnitt der Datenschutzerklärung. */
export const TEAM_DATENSCHUTZ_HINWEIS = 'Mehr dazu in der Datenschutzerklärung unter „Teams“.';
