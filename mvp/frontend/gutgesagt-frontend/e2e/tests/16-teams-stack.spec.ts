import { execFileSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import type { APIRequestContext, Page } from '@playwright/test';
import { expect, test } from './fixtures';

/**
 * Teams über Einladungslinks gegen den echten Stack (Frontend, BFF, Suchdienst, PostgreSQL),
 * am Handy (360 px). Anders als `15-teams` ist hier nichts nachgebaut außer der
 * Keycloak-Admin-Schnittstelle: Den Teil, der beim Einlösen ein Konto anlegt, übernimmt ein
 * kleiner Ersatz (`mvp/scripts/dev/teams-stack/keycloak-ersatz.py`), der die Kennungen der Direktanmeldung
 * vergibt, damit sich das neue Konto danach anmelden kann. Er schickt keine Mail.
 *
 * Braucht einen eigenen Stack mit Schalter-Obergrenze teams an und dem Ersatz
 * (`mvp/docker-compose.teams-stack.yml`, Anleitung in e2e/README.md). Läuft nur mit
 * `E2E_TEAMS_STACK=1`, sonst übersprungen. Prüft die Datenbank per `docker exec` im
 * Container `E2E_PG_CONTAINER`. Schreibt: Einladungen, Mitgliedschaften, Schalter; nur auf
 * frischer Datenbank aussagekräftig (Nummern ab 1).
 */
// Nur zusammen mit einer eigenen Adresse: Gegen den Dev-Stack (Standard 8080) schaltete die Spec dort teams an.
const AN = process.env['E2E_TEAMS_STACK'] === '1' && !!process.env['E2E_BASE_URL'];
const PG = process.env['E2E_PG_CONTAINER'] ?? 'gutgesagt-app-postgres-teams';
const PASSWORT = 'Liebe>Hass!';
const ADMIN = { email: 'admin@example.com', passwort: 'Liebe>Hass!' };
const TESTKONTO = { email: 'test.user@example.com', id: 'user-001' };
/** Kennungen in derselben Reihenfolge, in der der Keycloak-Ersatz sie vergibt. */
const NEU1 = { email: 'teams.neu1@example.com', id: 'teams-neu-1' };
const NEU2 = { email: 'teams.neu2@example.com', id: 'teams-neu-2' };
/** Geltender Wortlaut (domain/teams.py EINWILLIGUNG_KENNUNG); frühere nimmt der Server für neue Einwilligungen nicht an. */
const KENNUNG = 'team-2026-11-26';
const TEAM_A = { name: 'Stacktest Bayreuth', saison: '2026' };
const TEAM_B = { name: 'Stacktest Nordstand', saison: '2026' };

test.skip(!AN, 'nur gegen den Teams-Stack (E2E_TEAMS_STACK=1 und E2E_BASE_URL, e2e/README.md)');
test.describe.configure({ mode: 'serial' });

function sql(abfrage: string): string {
  return execFileSync('docker', ['exec', PG, 'psql', '-U', 'app_user', '-d', 'gutgesagt_app', '-tAc', abfrage], {
    encoding: 'utf8',
  }).trim();
}

function zeilen(konto: string): string[] {
  const aus = sql(
    `SELECT team_name || '|' || saison || '|' || nummer || '|' || einwilligung_kennung FROM team_mitgliedschaften ` +
      `WHERE konto_kennung = '${konto}' ORDER BY team_name`,
  );
  return aus ? aus.split('\n') : [];
}

function einloesungen(team: string): number {
  return Number(sql(`SELECT einloesungen FROM einladungen WHERE team_name = '${team}'`));
}

async function anmelden(page: Page, email: string, passwort = PASSWORT, zustimmen = true): Promise<void> {
  await page.goto('/search');
  const antwort = await page.request.post('/api/auth/login/managed', { data: { email, password: passwort } });
  expect(antwort.status()).toBe(200);
  if (zustimmen) await einwilligen(page.request);
}

async function abmelden(page: Page): Promise<void> {
  await page.context().clearCookies();
  await page.goto('/search');
}

/** Nutzungsbedingungen und Art.-9-Einwilligung wie anmelden.setup.ts, damit /contributions nicht umleitet. */
async function einwilligen(request: APIRequestContext): Promise<void> {
  const stand = await request.get('/api/v1/art9-einwilligung');
  expect(stand.status()).toBe(200);
  const { aktueller_wortlaut, nutzungsbedingungen } = await stand.json();
  expect(
    (await request.post('/api/v1/nutzungsbedingungen', { data: { stand: nutzungsbedingungen.aktueller_stand.kennung } })).status(),
  ).toBe(204);
  expect((await request.post('/api/v1/art9-einwilligung', { data: { wortlaut: aktueller_wortlaut.kennung } })).status()).toBe(204);
}

async function schalter(request: APIRequestContext, name: string, an: boolean): Promise<void> {
  const antwort = await request.put(`/api/v1/moderation/schalter/${name}`, { data: { an } });
  expect(antwort.status()).toBe(200);
}

async function formular(page: Page, email: string): Promise<void> {
  await page.getByLabel('Vorname').fill('Stack');
  await page.getByLabel('Nachname').fill('Test');
  await page.getByLabel('Mail-Adresse').fill(email);
}

const links: Record<string, string> = {};

test.describe('Teams gegen den echten Stack', () => {
  test('1 Admin legt einen Teamlink an, die Liste zeigt Team und Mitglieder', async ({ page, bild }) => {
    // Nummern ab 1 und die Kennungen des Keycloak-Ersatzes gelten nur auf einem frischen Stack
    expect(sql('SELECT count(*) FROM einladungen'), 'Stack nicht frisch: erst down -v, dann up (e2e/README.md)').toBe('0');
    await anmelden(page, ADMIN.email, ADMIN.passwort);
    await schalter(page.request, 'teams', true);
    await page.goto('/admin/dashboard');
    const karte = page.locator('app-einladungen');
    await expect(karte.getByTestId('team-block')).toBeVisible();
    await karte.getByLabel('Notiz').fill('Notiz Alpha');
    await karte.getByLabel('Erlaubte Einlösungen').fill('10');
    await karte.getByLabel('Teamname').fill(TEAM_A.name);
    await karte.getByLabel('Saison').fill(TEAM_A.saison);
    // Motiv über die Suche mit der Tastatur wählen (feste Emoji-Liste)
    await karte.getByTestId('motiv-suche').fill('fahrrad');
    // Der erste Treffer ist vorausgewählt: Enter übernimmt ihn
    await karte.getByTestId('motiv-suche').press('Enter');
    await expect(karte.getByTestId('motiv-gewaehlt')).toContainText('Gewählt: Fahrrad');
    await karte.getByRole('button', { name: 'Einladung anlegen' }).click();
    const zeile = karte.getByTestId('einladung').filter({ hasText: 'Notiz Alpha' });
    await expect(zeile).toHaveCount(1);
    await expect(karte.locator('th', { hasText: /^Team$/ })).toBeAttached();
    await expect(karte.locator('th', { hasText: /^Mitglieder$/ })).toBeAttached();
    await expect(zeile.getByTestId('team')).toContainText(TEAM_A.name);
    await expect(zeile.getByTestId('mitglieder')).toHaveText('0');
    links['A'] = (await zeile.locator('code').innerText()).trim();
    expect(links['A']).toContain('/einladung#');

    // Zweiter Teamlink über die Schnittstelle (Szenario 4)
    const liste = await (await page.request.get('/api/v1/einladungen')).json();
    const motiv = liste.motive[1].schluessel;
    const b = await page.request.post('/api/v1/einladungen', {
      data: {
        notiz: 'Notiz Beta',
        erlaubte_einloesungen: 10,
        gueltig_bis: new Date(Date.now() + 7 * 864e5).toISOString().slice(0, 10),
        team_name: TEAM_B.name,
        team_motiv: motiv,
        team_saison: TEAM_B.saison,
      },
    });
    expect(b.status()).toBe(201);
    // Admin-Liste am Desktop, damit die Tabelle Spalten zeigt statt Karten
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.reload();
    await expect(karte.getByTestId('einladung')).toHaveCount(2);
    await expect(karte.locator('th', { hasText: /^Mitglieder$/ })).toBeVisible();
    // Kopfzeile ohne Umbruch mitten im Wort: jede Kopfzelle eine Zeile hoch
    for (const kopf of ['Mitglieder', 'Zustand']) {
      const hoehe = (await karte.locator('th', { hasText: new RegExp(`^${kopf}$`) }).boundingBox())!.height;
      expect(hoehe, `Kopfzelle ${kopf}`).toBeLessThan(48);
    }
    links['B'] = (await karte.getByTestId('einladung').filter({ hasText: 'Notiz Beta' }).locator('code').innerText()).trim();
    await karte.locator('table').scrollIntoViewIfNeeded();
    await bild('admin-liste');
  });

  test('2 neues Konto über den Teamlink mit „Ja“', async ({ page, bild }) => {
    await page.goto(links['A']);
    const kasten = page.getByTestId('team-kasten');
    await expect(kasten.getByRole('heading', { level: 2 })).toContainText('Du wärst Nr. 1');
    await bild('begruessung', true);
    // Der Server liefert den geltenden Wortlaut: Kennung und Text mit Kommentaren und „Ja, gepostet“
    const pruefen = await page.request.post('/api/v1/einladungen/pruefen', { data: { code: links['A'].split('#')[1] } });
    expect(pruefen.status()).toBe(200);
    expect((await pruefen.json()).team.einwilligung_kennung).toBe(KENNUNG);
    const wortlaut = kasten.locator('details.team-wortlaut');
    await wortlaut.locator('summary').click();
    await expect(wortlaut).toContainText('Beiträge, Bewertungen und Kommentare');
    await expect(wortlaut).toContainText('Meldungen „Ja, gepostet“');
    await kasten.getByTestId('team-ja').click();
    await formular(page, NEU1.email);
    await page.getByRole('button', { name: 'Konto anlegen' }).click();
    await expect(page.locator('app-einladung')).toContainText('Schau in dein Postfach');
    expect(zeilen(NEU1.id)).toEqual([`${TEAM_A.name}|${TEAM_A.saison}|1|${KENNUNG}`]);
    // Kein Bezug zur Einladung: die Tabelle hat keine Spalte dafür
    expect(
      sql(`SELECT string_agg(column_name, ',' ORDER BY column_name) FROM information_schema.columns WHERE table_name = 'team_mitgliedschaften'`),
    ).toBe('eingetreten_am,einwilligung_kennung,einwilligung_zeitpunkt,id,konto_kennung,nummer,saison,team_motiv,team_name');
    expect(einloesungen(TEAM_A.name)).toBe(1);

    // Link aus der Mail: Passwort ist gesetzt, Anmeldung, zurück auf /einladung/anmelden
    // Erstes Anmelden ohne Nutzungsbedingungen und Art.-9-Einwilligung, wie bei einem echten neuen Konto
    await anmelden(page, NEU1.email, PASSWORT, false);
    await page.goto('/einladung/anmelden');
    // Der Merker führt zuerst zurück auf die Einladung, mit dem Ergebnis (nicht auf /einwilligung)
    await expect(page).toHaveURL(/\/einladung$/);
    await expect(page.getByTestId('team-ergebnis')).toHaveText(`Neu in deiner Sammlung: Team ${TEAM_A.name}, Nr. 1`);
    await bild('neu-in-der-sammlung', true);
    await page.getByRole('link', { name: 'Zu meinen Teams' }).click();
    await expect(page).toHaveURL(/\/contributions/);
    const team = page.getByTestId('meine-teams').getByTestId('team');
    await expect(team).toHaveCount(1);
    await expect(team).toContainText(TEAM_A.name);
    await expect(team).toContainText('Nr. 1');
    await bild('meine-teams', true);
    // Kein zweiter Eintrag durch den Rücksprung
    expect(zeilen(NEU1.id)).toHaveLength(1);
    expect(einloesungen(TEAM_A.name)).toBe(1);
  });

  test('3 zweites Konto mit „Nein“: keine Zeile, Einladung gezählt', async ({ page }) => {
    await page.goto(links['A']);
    const kasten = page.getByTestId('team-kasten');
    await expect(kasten.getByRole('heading', { level: 2 })).toContainText('Du wärst Nr. 2');
    await kasten.getByTestId('team-nein').click();
    await formular(page, NEU2.email);
    await page.getByRole('button', { name: 'Konto anlegen' }).click();
    await expect(page.locator('app-einladung')).toContainText('Schau in dein Postfach');
    expect(zeilen(NEU2.id)).toEqual([]);
    expect(einloesungen(TEAM_A.name)).toBe(2);
  });

  test('4 angemeldet zweiter Teamlink mit „Ja“, nochmal: schon dabei, nicht doppelt gezählt', async ({ page, bild }) => {
    await anmelden(page, NEU1.email);
    await page.goto(links['B']);
    await page.getByTestId('team-kasten').getByTestId('team-ja').click();
    await expect(page.getByTestId('team-ergebnis')).toHaveText(`Neu in deiner Sammlung: Team ${TEAM_B.name}, Nr. 1`);
    expect(zeilen(NEU1.id)).toEqual([
      `${TEAM_A.name}|${TEAM_A.saison}|1|${KENNUNG}`,
      `${TEAM_B.name}|${TEAM_B.saison}|1|${KENNUNG}`,
    ]);
    expect(einloesungen(TEAM_B.name)).toBe(1);

    await page.goto('/search');
    await page.goto(links['B']);
    await expect(page.getByTestId('team-ergebnis')).toHaveText('Du bist schon dabei (Nr. 1)');
    await bild('schon-dabei', true);
    expect(einloesungen(TEAM_B.name)).toBe(1);
    expect(zeilen(NEU1.id)).toHaveLength(2);
  });

  test('5 „Team verlassen“: die Zeile ist sofort weg', async ({ page, bild }) => {
    await anmelden(page, TESTKONTO.email);
    for (const link of [links['A'], links['B']]) {
      await page.goto('/search');
      await page.goto(link);
      await page.getByTestId('team-kasten').getByTestId('team-ja').click();
      await expect(page.getByTestId('team-ergebnis')).toContainText('Nr. 2');
    }
    expect(zeilen(TESTKONTO.id)).toHaveLength(2);

    await page.goto('/contributions');
    const meine = page.getByTestId('meine-teams');
    await meine.getByRole('button', { name: `Team verlassen: ${TEAM_B.name}, Saison ${TEAM_B.saison}` }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Team verlassen' }).click();
    await expect(meine.getByTestId('team')).toHaveCount(1);
    expect(zeilen(TESTKONTO.id)).toEqual([`${TEAM_A.name}|${TEAM_A.saison}|2|${KENNUNG}`]);
    // Die Nummer bleibt vergeben
    expect(sql(`SELECT letzte_nummer FROM team_nummern WHERE team_name = '${TEAM_B.name}'`)).toBe('2');
    await bild('nach-verlassen', true);
  });

  test('6 Kontolöschung (person_loeschen.sql): die Mitgliedschaften sind weg', async () => {
    expect(zeilen(NEU1.id)).toHaveLength(2);
    const skript = fs.readFileSync(path.join(__dirname, '../../../../scripts/manual/person_loeschen.sql'));
    execFileSync(
      'docker',
      ['exec', '-i', PG, 'psql', '-U', 'app_user', '-d', 'gutgesagt_app', '-v', 'ON_ERROR_STOP=1', '-v', `uid=${NEU1.id}`],
      { input: skript },
    );
    expect(zeilen(NEU1.id)).toEqual([]);
    expect(sql(`SELECT count(*) FROM team_oeffentlich WHERE konto_kennung = '${NEU1.id}'`)).toBe('0');
    // Andere bleiben
    expect(zeilen(TESTKONTO.id)).toHaveLength(1);
  });

  test('7 Schalter teams aus: Einladung wie vorher, „Meine Teams“ mit Verlassen', async ({ page, bild }) => {
    await anmelden(page, ADMIN.email, ADMIN.passwort);
    // Die Admin-Liste zählt nur die Mitglieder: A noch das Testkonto, B niemand mehr
    const liste = await (await page.request.get('/api/v1/einladungen')).json();
    const mitglieder = Object.fromEntries(liste.einladungen.map((e: { team: { name: string; mitglieder: number } }) => [e.team.name, e.team.mitglieder]));
    expect(mitglieder).toEqual({ [TEAM_A.name]: 1, [TEAM_B.name]: 0 });
    await schalter(page.request, 'teams', false);
    await abmelden(page);

    await page.goto(links['A']);
    await expect(page.getByLabel('Mail-Adresse')).toBeVisible();
    await expect(page.getByTestId('team-kasten')).toHaveCount(0);
    await expect(page.locator('app-einladung')).not.toContainText('Team');
    await bild('schalter-aus-einladung', true);

    await anmelden(page, TESTKONTO.email);
    await page.goto('/contributions');
    const meine = page.getByTestId('meine-teams');
    await expect(meine.getByTestId('teams-aus')).toBeVisible();
    await expect(meine.getByTestId('team')).toHaveCount(1);
    await expect(meine.getByRole('button', { name: `Team verlassen: ${TEAM_A.name}, Saison ${TEAM_A.saison}` })).toBeVisible();
    await bild('schalter-aus-meine-teams', true);

    // Beitreten ist zu: 404
    const code = links['B'].split('#')[1];
    const beitreten = await page.request.post('/api/v1/einladungen/beitreten', {
      data: { code, einwilligung: true, einwilligung_kennung: KENNUNG },
    });
    expect(beitreten.status()).toBe(404);

    // Verlassen geht auch bei Schalter aus
    await meine.getByRole('button', { name: /^Team verlassen/ }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Team verlassen' }).click();
    await expect(meine.getByTestId('team')).toHaveCount(0);
    expect(zeilen(TESTKONTO.id)).toEqual([]);
  });
});
