import { APIRequestContext, Browser, Page, expect, test } from '@playwright/test';
import { KONTO } from './konto';

/**
 * Saal-Test (BDK): Seitenaufrufe erzeugen kein 401 und kein 404 an /api, weder fuer Besucher
 * noch fuer Angemeldete, bei allen Schaltern aus und bei allen an. Am Gateway sperrt fail2ban
 * eine IP nach 20 × 401 oder 50 × 404 in 5 Minuten, und im Saal-WLAN teilen sich hunderte
 * Handys eine IP (docs/ARCHITECTURE.md, "Automatically requested endpoints").
 *
 * Ohne E2E_SCHALTER_UMSCHALTEN laeuft nur der Fall, der zum Stand des Stacks passt; erkannt an
 * den oeffentlichen Schaltern (GET /api/v1/funktionen; alle aus wie im Dev-Stack von Haus aus,
 * oder alle an), die nicht oeffentlichen (Punkte, Rangliste, Gepostet) prueft dann niemand. Mit
 * E2E_SCHALTER_UMSCHALTEN=1 schaltet die Spec als Admin selbst um und am Ende alles aus:
 * nur gegen den Saal-Stack (mvp/docker-compose.saal-stack.yml, alle Obergrenzen an), nie gegen
 * den geteilten Dev-Stack.
 */

const UMSCHALTEN = process.env['E2E_SCHALTER_UMSCHALTEN'] === '1';
const ADMIN = { email: process.env['E2E_ADMIN_EMAIL'] ?? 'admin@example.com', passwort: process.env['E2E_ADMIN_PASSWORT'] ?? KONTO.passwort };

/** Seiten fuer Besucher; geschuetzte fuehren zur Anmeldung oder zur Vorschau mit Konto. */
const BESUCHER_SEITEN = [
  '/search',
  // Mit Kampagnenwort: Begruessung und POST /api/v1/ankunft (Schalter k_begruessung, k_ankuenfte)
  '/search?k=sticker',
  `/result?searchQuery=${encodeURIComponent('Windräder töten Vögel')}`,
  '/garten',
  '/konter-probe',
  '/hier-fehlt-eine-antwort',
  '/contributions',
];

/** Seiten fuer Angemeldete: Startseite, Meine Beitraege (Punkte, Rangliste, Teams), Einstellungen. */
const ANGEMELDET_SEITEN = [
  '/search',
  '/search?k=sticker',
  `/result?searchQuery=${encodeURIComponent('Windräder töten Vögel')}`,
  '/contributions',
  '/garten',
  '/konter-probe',
  '/hier-fehlt-eine-antwort',
  '/einwilligung',
];

type Lage = 'aus' | 'an' | 'gemischt';

async function lage(request: APIRequestContext): Promise<Lage> {
  const antwort = await request.get('/api/v1/funktionen');
  expect(antwort.status()).toBe(200);
  // Not-Aus der Basisfunktionen (Standard an, kein Admin-Wert) zählen nicht mit
  const NOTAUS = ['gepostet_ohne_konto', 'null_treffer_anzahl', 'feedback_gestoert'];
  const werte = Object.entries((await antwort.json()).funktionen as Record<string, boolean>)
    .filter(([name]) => !NOTAUS.includes(name))
    .map(([, wert]) => wert);
  if (werte.every((w) => w === false)) return 'aus';
  if (werte.every((w) => w === true)) return 'an';
  return 'gemischt';
}

async function anmelden(request: APIRequestContext, email: string, passwort: string): Promise<void> {
  const antwort = await request.post('/api/auth/login/managed', { data: { email, password: passwort } });
  expect(antwort.status(), `Anmeldung ${email}`).toBe(200);
}

/** Wie anmelden.setup.ts: ohne Art.-9-Einwilligung fuehrte die App auf /einwilligung. */
async function einwilligen(request: APIRequestContext): Promise<void> {
  const stand = await request.get('/api/v1/art9-einwilligung');
  expect(stand.status()).toBe(200);
  const { aktueller_wortlaut, nutzungsbedingungen, eingewilligt } = await stand.json();
  if (eingewilligt) return;
  expect(
    (await request.post('/api/v1/nutzungsbedingungen', { data: { stand: nutzungsbedingungen.aktueller_stand.kennung } })).status(),
  ).toBe(204);
  expect((await request.post('/api/v1/art9-einwilligung', { data: { wortlaut: aktueller_wortlaut.kennung } })).status()).toBe(204);
}

/** Alle Admin-Werte der Schalter auf ``an`` (ausser herkunft_pruefen, das nach aussen ruft). */
async function alleSchalter(browser: Browser, an: boolean): Promise<void> {
  const kontext = await browser.newContext();
  try {
    await anmelden(kontext.request, ADMIN.email, ADMIN.passwort);
    const liste = await kontext.request.get('/api/v1/moderation/schalter');
    expect(liste.status()).toBe(200);
    for (const s of (await liste.json()).schalter as { name: string }[]) {
      if (s.name === 'herkunft_pruefen') continue;
      const antwort = await kontext.request.put(`/api/v1/moderation/schalter/${s.name}`, { data: { an } });
      expect(antwort.status(), `Schalter ${s.name} (Obergrenze an? Saal-Stack)`).toBe(200);
    }
  } finally {
    await kontext.close();
  }
}

/**
 * Ruft die Seiten auf, wartet je auf Ruhe im Netz und sammelt jedes 401 und 404 an /api. Alle
 * Abrufe an /api haengen als Anhang „api-abrufe“ am Report, zum Nachsehen, was gefragt wurde.
 */
async function abgewieseneBeiSeitenaufrufen(page: Page, seiten: string[], vorher?: () => Promise<void>): Promise<string[]> {
  const abgewiesen: string[] = [];
  const alle: string[] = [];
  page.on('response', (r) => {
    const adresse = new URL(r.url());
    if (!adresse.pathname.startsWith('/api/')) return;
    const zeile = `${r.status()} ${r.request().method()} ${adresse.pathname} (Seite ${new URL(page.url()).pathname})`;
    alle.push(zeile);
    if (r.status() === 401 || r.status() === 404) abgewiesen.push(zeile);
  });
  // Was davor geschieht (etwa die Anmeldung auf der Startseite), zaehlt mit.
  if (vorher) await vorher();
  for (const seite of seiten) {
    await page.goto(seite);
    await page.waitForLoadState('networkidle');
  }
  await test.info().attach('api-abrufe', { body: alle.join('\n'), contentType: 'text/plain' });
  return abgewiesen;
}

for (const gewollt of ['aus', 'an'] as const) {
  test.describe(`Saal: alle Schalter ${gewollt}`, () => {
    test.beforeAll(async ({ browser, request }) => {
      if (UMSCHALTEN) {
        await alleSchalter(browser, gewollt === 'an');
        // Der Suchdienst liest die Admin-Werte mit kurzem Cache; erst warten, bis er sie meldet.
        await expect.poll(() => lage(request), { timeout: 60_000, intervals: [2_000] }).toBe(gewollt);
      }
    });

    test.afterAll(async ({ browser }) => {
      if (UMSCHALTEN && gewollt === 'an') await alleSchalter(browser, false);
    });

    test(`Besucher: null 401/404 bei Seitenaufrufen, Schalter ${gewollt}`, async ({ page, request }) => {
      test.skip((await lage(request)) !== gewollt, `Oeffentliche Schalter nicht alle ${gewollt} (E2E_SCHALTER_UMSCHALTEN=1 gegen den Saal-Stack)`);
      expect(await abgewieseneBeiSeitenaufrufen(page, BESUCHER_SEITEN)).toEqual([]);
    });

    test(`Angemeldet: null 401/404 bei Seitenaufrufen, Schalter ${gewollt}`, async ({ page, request }) => {
      test.skip((await lage(request)) !== gewollt, `Oeffentliche Schalter nicht alle ${gewollt} (E2E_SCHALTER_UMSCHALTEN=1 gegen den Saal-Stack)`);
      const abgewiesen = await abgewieseneBeiSeitenaufrufen(page, ANGEMELDET_SEITEN, async () => {
        await page.goto('/search');
        await page.waitForLoadState('networkidle');
        await anmelden(page.request, KONTO.email, KONTO.passwort);
        await einwilligen(page.request);
      });
      expect(abgewiesen).toEqual([]);
    });
  });
}
