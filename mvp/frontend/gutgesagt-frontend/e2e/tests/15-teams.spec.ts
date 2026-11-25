import type { Page, Route } from '@playwright/test';
import { expect, test } from './fixtures';

/**
 * Teams über Einladungslinks (Glossar „Team“, „Teamlink“, „Mitgliedschaft“), am Handy
 * (360 px). Ohne Stack: Jede Anfrage an /api beantwortet ein kleiner Nachbau des Servers
 * im Test, der Mitgliedschaften je Konto führt, also auch gegen `ng serve` ohne Backend
 * (E2E_BASE_URL). Legt nichts an.
 *
 * Geprüft wird, was die Seite schickt und zeigt:
 * - neu einlösen mit „Ja“: Kasten mit Nummer, „Ja“ geht beim Anlegen mit, nach Mail und
 *   Anmeldung zurück auf /einladung mit „Neu in deiner Sammlung … Nr. N“, Team unter „Meine Teams“;
 * - neu einlösen mit „Nein“: `team_einwilligung` false, keine Mitgliedschaft, kein Merker;
 * - ohne Wahl kein Anlegen (nichts vorausgewählt);
 * - angemeldet beitreten, zweimal = „Du bist schon dabei“ ohne zweiten Beitritt;
 * - „Team verlassen“ mit Rückfrage löscht sofort, die Karte lädt selbst nach;
 * - Schalter teams aus: die Seite wie vor den Teams, ohne Teamfelder in der Anfrage;
 * - Schalter teams_oeffentlich aus: keine zweite Frage, kein Umschalter in „Meine Teams“.
 */
const CODE = 'E2eTeamCode_42';
const TEAM = { name: 'BDK 26 Berlin', motiv: 'vogel', saison: '2026' };
const KENNUNG = 'team-2026-11-25';
const KNOPF_JA = `Ja, speichert, dass ich im Team ${TEAM.name} bin`;
const KNOPF_NEIN = 'Nein, ohne Team weiter';
const MERKER = 'gutgesagt-einladung-team';
/** Schon im Team, bevor der Test beginnt (andere Konten): die nächste Nummer ist 4. */
const ANDERE = 3;

interface Mitgliedschaft {
  id: string;
  konto: string;
  nummer: number;
  eingetreten_am: string;
}

interface Stand {
  /** Schalter teams wirkt (Admin-Wert und Env-Obergrenze). */
  teamsAn: boolean;
  /** Angemeldetes Konto oder null (Besucherin). */
  konto: string | null;
  mitgliedschaften: Mitgliedschaft[];
  /** Zuletzt vergebene Nummer; Nummern werden nie neu vergeben. */
  letzteNummer: number;
  einloesen: Array<Record<string, unknown>>;
  beitreten: Array<Record<string, unknown>>;
  verlassen: string[];
}

function eigene(stand: Stand): Mitgliedschaft | undefined {
  return stand.mitgliedschaften.find((m) => m.konto === stand.konto);
}

function mitgliedWerden(stand: Stand, konto: string): Mitgliedschaft {
  stand.letzteNummer += 1;
  const m = { id: `m-${stand.letzteNummer}`, konto, nummer: stand.letzteNummer, eingetreten_am: '2026-11-25' };
  stand.mitgliedschaften.push(m);
  return m;
}

/** Das Team in der Antwort von /pruefen, wie api/v1/einladungen.py es baut (teams_oeffentlich aus). */
function teamBeimPruefen(stand: Stand) {
  return {
    ...TEAM,
    mitglieder: stand.mitgliedschaften.length,
    naechste_nummer: stand.letzteNummer + 1,
    eigene_nummer: stand.konto ? (eigene(stand)?.nummer ?? null) : null,
    einwilligung_kennung: KENNUNG,
    einwilligung_text: `Ich willige ausdrücklich ein, dass Gut gesagt an meinem Konto speichert, dass ich im Team ${TEAM.name} bin (Testwortlaut).`,
    knopf_ja: KNOPF_JA,
    knopf_nein: KNOPF_NEIN,
    oeffentlich_kennung: null,
    oeffentlich_text: null,
  };
}

async function ohneStack(page: Page, start: Partial<Stand> = {}): Promise<Stand> {
  const stand: Stand = {
    teamsAn: true,
    konto: null,
    mitgliedschaften: Array.from({ length: ANDERE }, (_, i) => ({
      id: `m-${i + 1}`,
      konto: `anderes-konto-${i + 1}`,
      nummer: i + 1,
      eingetreten_am: '2026-11-20',
    })),
    letzteNummer: ANDERE,
    einloesen: [],
    beitreten: [],
    verlassen: [],
    ...start,
  };
  await page.route('**/api/**', (anfrage: Route) => {
    const url = new URL(anfrage.request().url());
    const methode = anfrage.request().method();
    const pfad = url.pathname;
    const angemeldet = stand.konto !== null;
    if (pfad === '/api/user-info') {
      return anfrage.fulfill({
        json: angemeldet
          ? { isAuthenticated: true, userId: stand.konto, userName: 'Testkonto', claims: {} }
          : { isAuthenticated: false, userId: null, userName: null, claims: null },
      });
    }
    if (pfad === '/api/check-session') {
      return anfrage.fulfill({ json: { isAuthenticated: angemeldet } });
    }
    if (pfad === '/api/auth/modes') {
      return anfrage.fulfill({ json: { keycloakEnabled: false, managedAuthEnabled: true } });
    }
    if (pfad === '/api/v1/funktionen') {
      return anfrage.fulfill({ json: { funktionen: { teams: stand.teamsAn } } });
    }
    if (pfad === '/api/v1/art9-einwilligung') {
      return anfrage.fulfill({
        json: {
          eingewilligt: true,
          wortlaut: '2026-11-05',
          eingewilligt_am: '2026-11-05T00:00:00Z',
          widerrufen_am: null,
          aktueller_wortlaut: { kennung: '2026-11-05', text: 'Ich willige ein (Testwortlaut).' },
        },
      });
    }
    if (pfad === '/api/v1/contribution/getContributionsOfUser') {
      // „Meine Beiträge“ ohne eigene Beiträge, damit die Seite keinen Ladefehler zeigt
      return anfrage.fulfill({ json: { results: [], total_records_count: 0 } });
    }
    if (pfad === '/api/v1/einladungen/pruefen') {
      const einloesbar = anfrage.request().postDataJSON().code === CODE;
      // Schalter aus: die Antwort wie vor den Teams, ohne Feld team
      if (!einloesbar || !stand.teamsAn) {
        return anfrage.fulfill({ json: { einloesbar } });
      }
      return anfrage.fulfill({ json: { einloesbar, team: teamBeimPruefen(stand) } });
    }
    if (pfad === '/api/v1/einladungen/einloesen') {
      const body = anfrage.request().postDataJSON();
      stand.einloesen.push(body);
      // Neues Konto "neu-konto"; Mitglied nur nach "Ja" und bei wirksamem Schalter
      if (stand.teamsAn && body.team_einwilligung === true) {
        mitgliedWerden(stand, 'neu-konto');
      }
      return anfrage.fulfill({ status: 202, json: { success: true } });
    }
    if (pfad === '/api/v1/einladungen/beitreten') {
      const body = anfrage.request().postDataJSON();
      stand.beitreten.push(body);
      if (!angemeldet) return anfrage.fulfill({ status: 401, json: {} });
      if (!stand.teamsAn) return anfrage.fulfill({ status: 404, json: {} });
      if (body.einwilligung !== true) return anfrage.fulfill({ status: 422, json: {} });
      const vorhanden = eigene(stand);
      const m = vorhanden ?? mitgliedWerden(stand, stand.konto!);
      return anfrage.fulfill({ json: { team: TEAM, nummer: m.nummer, neu: !vorhanden } });
    }
    if (pfad === '/api/v1/teams/meine' && methode === 'GET') {
      if (!angemeldet) return anfrage.fulfill({ status: 401, json: {} });
      if (!stand.teamsAn) return anfrage.fulfill({ status: 404, json: {} });
      const m = eigene(stand);
      return anfrage.fulfill({
        json: {
          aktuelle_saison: TEAM.saison,
          oeffentlich_verfuegbar: false,
          oeffentlich_zeigen: null,
          oeffentlich_kennung: null,
          oeffentlich_text: null,
          teams: m
            ? [
                {
                  id: m.id,
                  team_name: TEAM.name,
                  motiv: TEAM.motiv,
                  motiv_name: 'Vogel',
                  saison: TEAM.saison,
                  nummer: m.nummer,
                  eingetreten_am: m.eingetreten_am,
                  aktuelle_saison: true,
                },
              ]
            : [],
        },
      });
    }
    if (pfad.startsWith('/api/v1/teams/meine/') && methode === 'DELETE') {
      const id = decodeURIComponent(pfad.split('/').pop()!);
      stand.verlassen.push(id);
      const m = eigene(stand);
      if (!m || m.id !== id) return anfrage.fulfill({ status: 404, json: {} });
      stand.mitgliedschaften = stand.mitgliedschaften.filter((x) => x.id !== id);
      return anfrage.fulfill({ status: 204, body: '' });
    }
    return anfrage.fulfill({ status: 404, json: {} });
  });
  return stand;
}

async function formularAusfuellen(page: Page): Promise<void> {
  await page.getByLabel('Vorname').fill('Erika');
  await page.getByLabel('Nachname').fill('Muster');
  await page.getByLabel('Mail-Adresse').fill('neu@example.org');
}

/**
 * Der Link in der Mail führt nach Passwort und Anmeldung auf /einladung/anmelden; die
 * Anmeldung selbst (Keycloak) steht hier für sich: Danach ist das neue Konto angemeldet.
 */
async function nachMailAngemeldet(page: Page, stand: Stand): Promise<void> {
  stand.konto = 'neu-konto';
  await page.goto('/einladung/anmelden');
}

async function keinQuerscrollen(page: Page): Promise<void> {
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
}

test.describe('Teams über Einladungslinks', () => {
  test('neu einlösen mit „Ja“: Nummer sichtbar, danach unter „Meine Teams“', async ({ page, bild }) => {
    const stand = await ohneStack(page);
    await page.goto(`/einladung#${CODE}`);

    const kasten = page.getByTestId('team-kasten');
    await expect(kasten.getByRole('heading', { level: 2 })).toHaveText(
      `Herzlich willkommen im Team ${TEAM.name}! Du wärst Nr. ${ANDERE + 1}.`,
    );
    // Motiv nie allein: der Name steht als Text daneben; vor dem Ja kein Ticket, kein Medaillon
    await expect(kasten.getByTestId('team-motiv')).toContainText('Motiv: Vogel');
    await expect(kasten.getByTestId('team-motiv').locator('img')).toBeVisible();
    await expect(kasten).toContainText(`Team ${TEAM.name}`);
    await expect(kasten).toContainText(`Schon ${ANDERE} dabei.`);
    // Vor der Frage: was gespeichert wird, wer es sieht, wie man widerruft
    await expect(kasten).toContainText('Das siehst nur du, unter „Meine Teams“.');
    await expect(kasten).toContainText('mit „Team verlassen“ widerrufen');
    // teams_oeffentlich aus: keine zweite Frage
    await expect(page.getByTestId('team-oeffentlich')).toHaveCount(0);

    // Gleichwertig, nichts vorausgewählt
    const ja = kasten.getByRole('button', { name: KNOPF_JA });
    const nein = kasten.getByRole('button', { name: KNOPF_NEIN });
    await expect(ja).toHaveAttribute('aria-pressed', 'false');
    await expect(nein).toHaveAttribute('aria-pressed', 'false');
    await bild('teams-einladung-kasten', true);

    // Ohne Wahl kein Anlegen
    await formularAusfuellen(page);
    await page.getByRole('button', { name: 'Konto anlegen' }).click();
    await expect(page.getByTestId('team-wahl-fehlt')).toBeVisible();
    expect(stand.einloesen).toEqual([]);

    await ja.click();
    await expect(ja).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByTestId('team-gewaehlt')).toContainText('sobald dein Konto angelegt ist');
    await page.getByRole('button', { name: 'Konto anlegen' }).click();
    await expect(page.locator('app-einladung')).toContainText('Schau in dein Postfach');
    await expect(page.getByTestId('team-nach-mail')).toBeVisible();
    expect(stand.einloesen).toEqual([
      {
        code: CODE,
        email: 'neu@example.org',
        vorname: 'Erika',
        nachname: 'Muster',
        team_einwilligung: true,
        team_oeffentlich: false,
        team_einwilligung_kennung: KENNUNG,
      },
    ]);
    // Merker für den Rücksprung: Code und Kennung des Wortlauts, kein Teamname
    const merker = await page.evaluate((s) => localStorage.getItem(s), MERKER);
    expect(JSON.parse(merker!)).toMatchObject({ code: CODE, kennung: KENNUNG, oeffentlich: false });
    expect(merker).not.toContain(TEAM.name);

    await nachMailAngemeldet(page, stand);
    await expect(page).toHaveURL(/\/einladung$/);
    const ergebnis = page.getByTestId('team-ergebnis');
    // Ein Seitenaufruf, keine Handlung: der Fokus bleibt, wo der Browser ihn setzt
    await expect(ergebnis).toHaveText(`Neu in deiner Sammlung: Team ${TEAM.name}, Nr. ${ANDERE + 1}`);
    // Der Merker gilt einmal
    expect(await page.evaluate((s) => localStorage.getItem(s), MERKER)).toBeNull();
    // Beim Anlegen entstanden, kein zweiter Beitritt
    expect(stand.beitreten).toEqual([]);
    await keinQuerscrollen(page);
    await bild('teams-neu-in-der-sammlung');

    await page.getByRole('link', { name: 'Zu meinen Teams' }).click();
    const meine = page.getByTestId('meine-teams');
    await expect(meine.getByRole('heading', { name: /Meine Teams/ })).toBeVisible();
    const team = meine.getByTestId('team');
    await expect(team).toHaveCount(1);
    await expect(team).toContainText(TEAM.name);
    await expect(team).toContainText(`Nr. ${ANDERE + 1}`);
    await expect(team).toContainText('seit 25.11.2026');
    await expect(meine.getByTestId('sichtbarkeit')).toHaveText('Nur du siehst deine Teams.');
    // teams_oeffentlich aus: kein Umschalter
    await expect(meine.getByTestId('oeffentlich')).toHaveCount(0);
    await keinQuerscrollen(page);
    await bild('teams-meine-teams', true);
  });

  test('neu einlösen mit „Nein“: keine Mitgliedschaft', async ({ page, bild }) => {
    const stand = await ohneStack(page);
    await page.goto(`/einladung#${CODE}`);
    const kasten = page.getByTestId('team-kasten');
    await kasten.getByRole('button', { name: KNOPF_NEIN }).click();
    await expect(page.getByTestId('team-gewaehlt')).toContainText('ohne Team. Wir speichern nichts dazu.');
    await formularAusfuellen(page);
    await page.getByRole('button', { name: 'Konto anlegen' }).click();
    await expect(page.locator('app-einladung')).toContainText('Schau in dein Postfach');
    await expect(page.getByTestId('team-nach-mail')).toHaveCount(0);
    expect(stand.einloesen).toEqual([
      {
        code: CODE,
        email: 'neu@example.org',
        vorname: 'Erika',
        nachname: 'Muster',
        team_einwilligung: false,
        team_oeffentlich: false,
      },
    ]);
    expect(await page.evaluate((s) => localStorage.getItem(s), MERKER)).toBeNull();
    expect(stand.mitgliedschaften).toHaveLength(ANDERE);

    // Nach der Mail: kein Rücksprung auf die Einladung, keine Teams
    await nachMailAngemeldet(page, stand);
    await expect(page).not.toHaveURL(/\/einladung/);
    await page.goto('/contributions');
    const meine = page.getByTestId('meine-teams');
    await expect(meine.getByTestId('leer')).toBeVisible();
    await expect(meine.getByTestId('team')).toHaveCount(0);
    expect(stand.beitreten).toEqual([]);
    await bild('teams-ohne-team-meine-teams', true);
  });

  test('angemeldet beitreten, beim zweiten Mal „schon dabei“, dann Team verlassen', async ({ page, bild }) => {
    const stand = await ohneStack(page, { konto: 'e2e-konto' });
    await page.goto(`/einladung#${CODE}`);

    // Angemeldet: kein Formular, nur der Kasten mit der Frage
    const kasten = page.getByTestId('team-kasten');
    await expect(kasten).toContainText('Die Nummer steht erst fest, wenn du beitrittst.');
    await expect(page.getByLabel('Mail-Adresse')).toHaveCount(0);
    await expect(page.getByTestId('team-oeffentlich')).toHaveCount(0);
    await bild('teams-angemeldet-frage', true);
    expect(stand.beitreten).toEqual([]);

    await kasten.getByRole('button', { name: KNOPF_JA }).click();
    const ergebnis = page.getByTestId('team-ergebnis');
    await expect(ergebnis).toHaveText(`Neu in deiner Sammlung: Team ${TEAM.name}, Nr. ${ANDERE + 1}`);
    await expect(ergebnis).toBeFocused();
    expect(stand.beitreten).toEqual([
      { code: CODE, einwilligung: true, einwilligung_kennung: KENNUNG, oeffentlich: false },
    ]);
    await keinQuerscrollen(page);

    // Zweites Mal: schon dabei, ohne Frage und ohne zweiten Beitritt
    await page.goto('/');
    await page.goto(`/einladung#${CODE}`);
    await expect(page.getByTestId('team-ergebnis')).toHaveText(`Du bist schon dabei (Nr. ${ANDERE + 1})`);
    await expect(page.locator('app-einladung')).toContainText('Dieser Link zählt für dich nicht noch einmal.');
    await expect(page.getByTestId('team-kasten')).toHaveCount(0);
    expect(stand.beitreten).toHaveLength(1);
    await bild('teams-schon-dabei');

    // Team verlassen: Rückfrage, dann sofort gelöscht
    await page.getByRole('link', { name: 'Zu meinen Teams' }).click();
    const meine = page.getByTestId('meine-teams');
    await expect(meine.getByTestId('team')).toContainText(`Nr. ${ANDERE + 1}`);
    await meine.getByRole('button', { name: `Team verlassen: ${TEAM.name}, Saison ${TEAM.saison}` }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toContainText(`Team ${TEAM.name} verlassen?`);
    await expect(dialog).toContainText('Die Nummer vergeben wir nicht neu.');
    await bild('teams-verlassen-rueckfrage');
    // Abbrechen löscht nichts
    await dialog.getByRole('button', { name: 'Abbrechen' }).click();
    await expect(dialog).toHaveCount(0);
    expect(stand.verlassen).toEqual([]);

    await meine.getByRole('button', { name: /^Team verlassen/ }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Team verlassen' }).click();
    await expect(meine.getByTestId('team')).toHaveCount(0);
    await expect(meine.getByTestId('leer')).toBeVisible();
    expect(stand.verlassen).toEqual([`m-${ANDERE + 1}`]);
    expect(stand.mitgliedschaften.some((m) => m.konto === 'e2e-konto')).toBe(false);
    await bild('teams-verlassen-leer', true);

    // Danach fragt der Link wieder; die alte Nummer wird nicht neu vergeben
    await page.goto('/');
    await page.goto(`/einladung#${CODE}`);
    await expect(page.getByTestId('team-kasten').getByRole('heading', { level: 2 })).toHaveText(
      `Herzlich willkommen im Team ${TEAM.name}! Du wärst Nr. ${ANDERE + 2}.`,
    );
  });

  test('angemeldet mit „Nein“: ohne Team weiter, nichts gespeichert', async ({ page }) => {
    const stand = await ohneStack(page, { konto: 'e2e-konto' });
    await page.goto(`/einladung#${CODE}`);
    await page.getByTestId('team-kasten').getByRole('button', { name: KNOPF_NEIN }).click();
    const ueberschrift = page.getByRole('heading', { name: 'Ohne Team weiter' });
    await expect(ueberschrift).toBeVisible();
    await expect(ueberschrift).toBeFocused();
    expect(stand.beitreten).toEqual([]);
    expect(stand.mitgliedschaften).toHaveLength(ANDERE);
  });

  test('Schalter teams aus: die Seite wie vor den Teams', async ({ page, bild }) => {
    const stand = await ohneStack(page, { teamsAn: false });
    await page.goto(`/einladung#${CODE}`);
    await expect(page.getByLabel('Mail-Adresse')).toBeVisible();
    await expect(page.getByTestId('team-kasten')).toHaveCount(0);
    await expect(page.locator('app-einladung')).not.toContainText('Team');
    await formularAusfuellen(page);
    await page.getByRole('button', { name: 'Konto anlegen' }).click();
    await expect(page.locator('app-einladung')).toContainText('Schau in dein Postfach');
    // Keine Teamfelder in der Anfrage, kein Merker
    expect(stand.einloesen).toEqual([{ code: CODE, email: 'neu@example.org', vorname: 'Erika', nachname: 'Muster' }]);
    expect(await page.evaluate((s) => localStorage.getItem(s), MERKER)).toBeNull();
    await bild('teams-schalter-aus-einloesen');

    // Angemeldet: das Formular wie vorher, kein „Du hast schon ein Konto“, kein Beitritt
    stand.konto = 'e2e-konto';
    await page.goto('/');
    await page.goto(`/einladung#${CODE}`);
    await expect(page.getByLabel('Mail-Adresse')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Du hast schon ein Konto' })).toHaveCount(0);
    expect(stand.beitreten).toEqual([]);

    // Ohne Schalter keine Karte „Meine Teams“
    await page.goto('/contributions');
    await expect(page.locator('app-meine-teams')).toBeAttached();
    await expect(page.getByTestId('meine-teams')).toHaveCount(0);
  });
});
