/**
 * Trägt eine Einladung mit Team über den Umweg Mail → Passwort → Anmeldung zurück auf
 * /einladung (einladung-anmelden), damit die Person dort ihr Team sieht. Der Code steht
 * nur hier im Browser, nie in einer Adresse, die BFF oder Keycloak protokollieren.
 *
 * Abgelegt wird nur, was die Person selbst gewählt hat: nach dem Knopf „Ja, speichert …“
 * die Kennung des gezeigten Wortlauts (und die Antwort auf die zweite Frage), oder ohne
 * jede Einwilligung nur der Code, wenn sie sich zum Beitreten erst anmelden will. Kein
 * Teamname, keine Nummer. Der Merker trägt nur, dass gefragt wurde: Er löst nie selbst
 * einen Beitritt aus, denn angemeldet kann auf einem geteilten Gerät jemand anderes sein;
 * ohne Mitgliedschaft kommt die Frage nach dem Anmelden noch einmal.
 * Gelesen wird einmal; danach ist der Eintrag weg. Er gilt so
 * lange wie der Link in der Mail (MAIL_GUELTIG_SEKUNDEN in keycloak_konten.py).
 *
 * localStorage statt sessionStorage: Der Link in der Mail öffnet meist einen neuen Tab.
 * Ein gesperrter Speicher wirft nicht; dann bleibt es beim Stand auf dem Server.
 */
export const TEAM_MERKER_SCHLUESSEL = 'gutgesagt-einladung-team';
export const TEAM_MERKER_DAUER_MS = 3 * 24 * 60 * 60 * 1000;

export interface TeamMerker {
  code: string;
  /** Kennung des Wortlauts, dem die Person mit „Ja“ zugestimmt hat; null: noch nicht gefragt. */
  kennung: string | null;
  /** Zweite Frage „Team öffentlich am Namen zeigen“, nur mit kennung. */
  oeffentlich: boolean;
}

interface Abgelegt extends TeamMerker {
  bis: number;
}

export function teamMerkerAblegen(merker: TeamMerker, jetzt = Date.now()): void {
  const abgelegt: Abgelegt = {
    code: merker.code,
    kennung: merker.kennung,
    oeffentlich: merker.kennung !== null && merker.oeffentlich,
    bis: jetzt + TEAM_MERKER_DAUER_MS,
  };
  try {
    localStorage.setItem(TEAM_MERKER_SCHLUESSEL, JSON.stringify(abgelegt));
  } catch {
    // Ohne Speicher kein Rücksprung; die Mitgliedschaft entsteht trotzdem beim Anlegen.
  }
}

export function teamMerkerLoeschen(): void {
  try {
    localStorage.removeItem(TEAM_MERKER_SCHLUESSEL);
  } catch {
    // Ohne Zugriff liegt dort auch nichts.
  }
}

/** Der gültige Eintrag, ohne ihn zu entfernen; abgelaufene oder kaputte werden verworfen. */
export function teamMerkerLesen(jetzt = Date.now()): TeamMerker | null {
  let roh: string | null;
  try {
    roh = localStorage.getItem(TEAM_MERKER_SCHLUESSEL);
  } catch {
    return null;
  }
  if (!roh) {
    return null;
  }
  try {
    const m = JSON.parse(roh) as Partial<Abgelegt>;
    const gueltig =
      typeof m.code === 'string' &&
      m.code.length > 0 &&
      typeof m.bis === 'number' &&
      m.bis > jetzt &&
      (m.kennung === null || typeof m.kennung === 'string');
    if (gueltig) {
      return { code: m.code!, kennung: m.kennung ?? null, oeffentlich: m.oeffentlich === true };
    }
  } catch {
    // kaputt: wie abgelaufen
  }
  teamMerkerLoeschen();
  return null;
}

/** Liest den Eintrag und entfernt ihn (einmal verwenden). */
export function teamMerkerNehmen(jetzt = Date.now()): TeamMerker | null {
  const merker = teamMerkerLesen(jetzt);
  teamMerkerLoeschen();
  return merker;
}
