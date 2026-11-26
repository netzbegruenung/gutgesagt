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

import { TeamArt } from './teams/teams';

/** Name der eigenen Sammlung, in „Meine Beiträge“ und in der Datenschutzerklärung. */
export const MEINE_TEAMS_TITEL = 'Meine Teams';

/** Der Widerruf der Einwilligung für ein Team; löscht die Mitgliedschaft sofort. */
export const TEAM_VERLASSEN = 'Team verlassen';

/** Kopf der Begrüßung vor dem Beitritt; die Nummer ist die voraussichtliche. */
export function teamBegruessungTitel(team: string, nummer: number): string {
  return `Herzlich willkommen im Team ${team}! Du wärst Nr. ${nummer}.`;
}

/**
 * Wie viele schon dabei sind, unter der Begrüßung (Leerzustände 26.11.): bei 0 bis 3 nach
 * Anfang statt „Noch ist niemand dabei.“, ab 4 die Zahl wie bisher. Steht nicht im
 * Wortlaut der Einwilligung.
 *
 * Die Nummern werden nach einem Austritt nicht neu vergeben (`naechste_nummer` zählt
 * weiter). „Anfang“ und „die ersten“ stehen deshalb nur, solange niemand ausgetreten ist,
 * also die nächste Nummer genau auf die Mitglieder folgt; sonst die Zahl ohne Wertung,
 * damit der Satz nicht „Du wärst Nr. 5.“ darüber widerspricht.
 */
export function teamDabeiSatz(mitglieder: number, naechsteNummer: number): string {
  const anzahl = Number.isFinite(mitglieder) ? Math.max(0, Math.floor(mitglieder)) : 0;
  const vonAnfang = naechsteNummer === anzahl + 1;
  if (anzahl === 0) {
    return vonAnfang ? 'Mit dir fängt das Team an.' : 'Gerade ist niemand dabei.';
  }
  if (anzahl === 1) {
    return vonAnfang ? 'Die erste Person ist schon dabei.' : '1 Person ist schon dabei.';
  }
  if (anzahl <= 3 && vonAnfang) {
    return `Die ersten ${anzahl} sind schon dabei.`;
  }
  return `Schon ${anzahl} dabei.`;
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

/**
 * Vertrauenssatz beim Teambeitritt (Schalter `teamlink_vertrauenssatz`), wortgleich nach der
 * vorläufigen juristischen Einschätzung vom 26.11.2026 für den internen Test: nennt die
 * Team-Summe (team_fortschritt), zu der Mitglieder mit Einwilligung beitragen.
 */
export const TEAM_VERTRAUENSSATZ = 'Beitreten heißt: Du zählst zu diesem Team und trägst zu seiner Summe bei.';

/** Zweiter Satz, nur bei einem Team nach Gruppe: Ein Team nach Anlass ist nach keiner Gruppe benannt. */
export const TEAM_VERTRAUENSSATZ_GRUPPE = 'Die Gruppe, nach der es benannt ist, bekommt keine Daten über dich.';

/**
 * Der Vertrauenssatz zur Teamart: bei „gruppe“ beide Sätze, sonst (Anlass, Ort, Saison,
 * auch ohne Art von einem älteren Server) nur der erste.
 */
export function teamVertrauenssatz(art: TeamArt | undefined): string {
  return art === 'gruppe' ? `${TEAM_VERTRAUENSSATZ} ${TEAM_VERTRAUENSSATZ_GRUPPE}` : TEAM_VERTRAUENSSATZ;
}

/** Verweis unter den Knöpfen auf den Abschnitt der Datenschutzerklärung. */
export const TEAM_DATENSCHUTZ_HINWEIS = 'Mehr dazu in der Datenschutzerklärung unter „Teams“.';

/**
 * Team-Fortschritt (#784) unter der Schwelle von 5 Mitgliedern mit Einwilligung. Die
 * Schwelle selbst prüft der Server (domain/team_fortschritt.py); der Text nennt sie.
 */
export const TEAM_WAECHST_NOCH = 'Euer Team wächst noch, ab 5 zeigen wir eure gemeinsame Wirkung.';

/** Kopf des Team-Fortschritts: die abgeschlossene Woche von Montag bis Sonntag. */
export function teamWocheTitel(montagIso: string): string {
  const [jahr, monat, tag] = montagIso.split('-').map(Number);
  const montag = new Date(Date.UTC(jahr, monat - 1, tag));
  const sonntag = new Date(montag.getTime() + 6 * 24 * 60 * 60 * 1000);
  const kurz = (d: Date) => `${d.getUTCDate()}.${d.getUTCMonth() + 1}.`;
  return `Letzte Woche gemeinsam (${kurz(montag)} bis ${kurz(sonntag)})`;
}

/**
 * Das Wochenziel einer Team-Quest (#792), ohne Stand und ohne Frist. Das Thema heißt hier
 * „Beet“, das einzige Gartenwort; der Name des Themas steht daneben im Motiv.
 */
export function teamQuestZiel(ziel: number): string {
  return `Euer Wochenziel: gemeinsam ${ziel}-mal beitragen, bewerten oder „Ja, gepostet“ melden.`;
}

/** Nach Wochenende, nur wenn geschafft; ein verfehltes Ziel erwähnt nichts. */
export function teamQuestGeschafft(thema: string | null): string {
  const ort = thema ? ` im Beet ${thema}` : '';
  return `Euer Wochenziel letzte Woche${ort} ist geschafft. Danke, dass du dabei bist.`;
}
