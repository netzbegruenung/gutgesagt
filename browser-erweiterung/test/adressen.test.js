// Adress-Bildung der Erweiterung. Ohne Paket: node --test browser-erweiterung/test/
const { test } = require('node:test');
const assert = require('node:assert/strict');
const {
  ZIELE,
  TEXT_MAX,
  ADRESSE_MAX,
  zielBasis,
  textKuerzen,
  seitenLink,
  suchAdresse,
  einwurfAdresse,
} = require('../adressen.js');

const PROD = ZIELE.prod;

/** Liest einen Parameter so, wie ihn das Frontend liest (URLSearchParams wie Angular). */
function parameter(adresse, name) {
  return new URL(adresse).searchParams.get(name);
}

test('Ziele: Prod ist Standard, Unbekanntes faellt auf Prod', () => {
  assert.equal(zielBasis('prod'), 'https://gutgesagt.netzbegruenung.de');
  assert.equal(zielBasis('test'), 'https://gutgesagt-test.netzbegruenung.de');
  assert.equal(zielBasis(undefined), PROD);
  assert.equal(zielBasis('toString'), PROD);
  assert.equal(zielBasis('https://boese.example'), PROD);
});

test('Suche: /result?searchQuery= mit Umlauten, Anfuehrungszeichen und Sonderzeichen', () => {
  const text = 'Grüne „Verbotspartei“? "Nein" & 100 % <script> #1 + ß/€';
  const adresse = suchAdresse(PROD, text);
  assert.ok(adresse.startsWith(`${PROD}/result?searchQuery=`));
  assert.equal(parameter(adresse, 'searchQuery'), text);
  // Leerzeichen als %20, nicht +: beides liest Angular, %20 ist eindeutig
  assert.ok(!adresse.includes('+'));
  assert.ok(!/[\s"<>„“]/.test(adresse));
  assert.equal(new URL(adresse).searchParams.size, 1);
});

test('Suche: Leerraum zusammengefasst, leere Markierung ergibt keine Adresse', () => {
  assert.equal(parameter(suchAdresse(PROD, '  zwei\n\n  Zeilen\t '), 'searchQuery'), 'zwei Zeilen');
  assert.equal(suchAdresse(PROD, ''), null);
  assert.equal(suchAdresse(PROD, '   \n'), null);
  assert.equal(suchAdresse(PROD, undefined), null);
});

test('Kuerzen: hoechstens TEXT_MAX Zeichen, am Wortende', () => {
  const lang = 'Wort '.repeat(500);
  const kurz = textKuerzen(lang);
  assert.ok(kurz.length <= TEXT_MAX);
  assert.ok(kurz.endsWith('Wort'));
  const ohneLeerzeichen = 'a'.repeat(TEXT_MAX + 50);
  assert.equal(textKuerzen(ohneLeerzeichen).length, TEXT_MAX);
});

test('Kuerzen: Emojis werden nicht halbiert, die Adresse bleibt unter ADRESSE_MAX', () => {
  const emojis = '👍'.repeat(TEXT_MAX + 10);
  const adresse = suchAdresse(PROD, emojis);
  assert.ok(adresse.length <= ADRESSE_MAX, `${adresse.length}`);
  const text = parameter(adresse, 'searchQuery');
  assert.ok(text.length > 0);
  assert.ok(/^(👍)+$/u.test(text), 'nur ganze Emojis');
});

test('Kuerzen: lange Umlaut-Texte gehen bis TEXT_MAX vollstaendig mit', () => {
  const text = 'ä'.repeat(TEXT_MAX);
  assert.equal(parameter(suchAdresse(PROD, text), 'searchQuery'), text);
});

test('Einwurf: /teilen mit text und url, wie das Teilen-Ziel der PWA', () => {
  const adresse = einwurfAdresse(
    PROD,
    'Das „Heizungsgesetz“ & die Wärmepumpe',
    'https://www.instagram.com/p/ABC123/?utm_source=ig_web&x="1"#kommentare',
  );
  const url = new URL(adresse);
  assert.equal(url.origin + url.pathname, `${PROD}/teilen`);
  assert.equal(url.searchParams.get('text'), 'Das „Heizungsgesetz“ & die Wärmepumpe');
  // Die Seitenadresse kommt ganz an, auch & und #; Tracking-Parameter entfernt erst der Guard
  assert.equal(url.searchParams.get('url'), 'https://www.instagram.com/p/ABC123/?utm_source=ig_web&x=%221%22#kommentare');
  assert.equal(url.searchParams.has('title'), false);
  assert.equal(url.hash, '');
});

test('Einwurf: nur http(s)-Seiten gehen als Link mit', () => {
  for (const seite of ['file:///home/x/geheim.html', 'chrome://settings', 'about:blank', 'kein link', undefined]) {
    const adresse = einwurfAdresse(PROD, 'Text', seite);
    assert.equal(parameter(adresse, 'url'), null, String(seite));
    assert.equal(parameter(adresse, 'text'), 'Text');
  }
  assert.equal(seitenLink('http://example.org/a b'), 'http://example.org/a%20b');
});

test('Einwurf: ohne Markierung nur der Link, ohne beides nichts', () => {
  const nurLink = einwurfAdresse(PROD, '  ', 'https://example.org/');
  assert.equal(nurLink, `${PROD}/teilen?url=${encodeURIComponent('https://example.org/')}`);
  assert.equal(einwurfAdresse(PROD, '', 'chrome://newtab'), null);
});

test('Einwurf: lange Texte gekuerzt, Adresse unter ADRESSE_MAX, ueberlanger Link faellt weg', () => {
  const seite = 'https://example.org/artikel';
  const adresse = einwurfAdresse(PROD, 'ö'.repeat(5000), seite);
  assert.ok(adresse.length <= ADRESSE_MAX);
  assert.equal(parameter(adresse, 'text').length, TEXT_MAX);
  assert.equal(parameter(adresse, 'url'), seite);

  const riesig = `https://example.org/?q=${'x'.repeat(ADRESSE_MAX)}`;
  const ohneLink = einwurfAdresse(PROD, 'Text', riesig);
  assert.equal(parameter(ohneLink, 'url'), null);
  assert.equal(parameter(ohneLink, 'text'), 'Text');

  const emojis = einwurfAdresse(PROD, '🌻'.repeat(2000), seite);
  assert.ok(emojis.length <= ADRESSE_MAX);
  assert.equal(parameter(emojis, 'url'), seite);
});

test('Testziel: Adressen zeigen auf die Testinstanz', () => {
  assert.ok(suchAdresse(zielBasis('test'), 'x').startsWith('https://gutgesagt-test.netzbegruenung.de/result?'));
  assert.ok(einwurfAdresse(zielBasis('test'), 'x', null).startsWith('https://gutgesagt-test.netzbegruenung.de/teilen?'));
});
