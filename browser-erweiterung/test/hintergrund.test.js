// hintergrund.js mit Attrappen fuer die Browser-API (vm, ohne Paket): Menue, Klick, Tab, Ziel.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ORDNER = path.join(__dirname, '..');

/** Laedt adressen.js und hintergrund.js wie Firefox (background.scripts) in einen Kontext. */
function laden({ ziel, storageWirft = false } = {}) {
  const hoerer = {};
  const protokoll = { menue: [], tabs: [], removeAll: 0 };
  const ereignis = (name) => ({ addListener: (f) => { hoerer[name] = f; } });
  const browser = {
    runtime: { onInstalled: ereignis('installiert'), onStartup: ereignis('start') },
    contextMenus: {
      removeAll: async () => { protokoll.removeAll += 1; protokoll.menue = []; },
      create: (eintrag) => { protokoll.menue.push(eintrag); },
      onClicked: ereignis('klick'),
    },
    storage: {
      local: {
        get: async () => {
          if (storageWirft) throw new Error('kein Speicher');
          return ziel ? { ziel } : {};
        },
      },
    },
    tabs: { create: (neu) => { protokoll.tabs.push(neu); } },
  };
  const kontext = vm.createContext({ browser, URL, console });
  for (const datei of ['adressen.js', 'hintergrund.js']) {
    vm.runInContext(fs.readFileSync(path.join(ORDNER, datei), 'utf8'), kontext, { filename: datei });
  }
  return { hoerer, protokoll };
}

const QUELLE = { id: 7, index: 2, windowId: 3 };

test('Menue: zwei Eintraege fuer Markierungen, bei Installation und Start ohne Doppelte', async () => {
  const { hoerer, protokoll } = laden();
  await hoerer.installiert();
  await hoerer.start();
  assert.equal(protokoll.removeAll, 2);
  assert.deepEqual(
    protokoll.menue.map((e) => [e.id, e.title, e.contexts.join()]),
    [
      ['gutgesagt-suchen', 'In Gut gesagt suchen', 'selection'],
      ['gutgesagt-einwerfen', 'In Gut gesagt einwerfen', 'selection'],
    ],
  );
});

test('Klick Suchen: neuer Tab direkt neben der Quelle, Prod als Standard', async () => {
  const { hoerer, protokoll } = laden();
  await hoerer.klick({ menuItemId: 'gutgesagt-suchen', selectionText: 'Grüne', pageUrl: 'https://a.example/' }, QUELLE);
  // Objekte aus dem vm-Kontext haben ein anderes Object.prototype: als JSON vergleichen
  assert.deepEqual(JSON.parse(JSON.stringify(protokoll.tabs)), [
    { url: 'https://gutgesagt.netzbegruenung.de/result?searchQuery=Gr%C3%BCne', index: 3, windowId: 3 },
  ]);
});

test('Klick Einwerfen mit Testziel', async () => {
  const { hoerer, protokoll } = laden({ ziel: 'test' });
  await hoerer.klick({ menuItemId: 'gutgesagt-einwerfen', selectionText: 'x', pageUrl: 'https://a.example/b' }, QUELLE);
  assert.equal(
    protokoll.tabs[0].url,
    'https://gutgesagt-test.netzbegruenung.de/teilen?text=x&url=https%3A%2F%2Fa.example%2Fb',
  );
});

test('Ohne Tab oder mit Tab-id -1 (z. B. PDF-Ansicht): Tab ohne Platzierung', async () => {
  const { hoerer, protokoll } = laden();
  await hoerer.klick({ menuItemId: 'gutgesagt-suchen', selectionText: 'a' }, undefined);
  await hoerer.klick({ menuItemId: 'gutgesagt-suchen', selectionText: 'b' }, { id: -1, index: 0, windowId: 1 });
  assert.deepEqual(Object.keys(protokoll.tabs[0]), ['url']);
  assert.deepEqual(Object.keys(protokoll.tabs[1]), ['url']);
});

test('Speicher wirft: Prod; fremde Menue-id und leere Markierung: kein Tab', async () => {
  const { hoerer, protokoll } = laden({ storageWirft: true });
  await hoerer.klick({ menuItemId: 'gutgesagt-suchen', selectionText: 'a' }, QUELLE);
  assert.ok(protokoll.tabs[0].url.startsWith('https://gutgesagt.netzbegruenung.de/'));
  await hoerer.klick({ menuItemId: 'fremd', selectionText: 'a' }, QUELLE);
  await hoerer.klick({ menuItemId: 'gutgesagt-suchen', selectionText: '  ' }, QUELLE);
  assert.equal(protokoll.tabs.length, 1);
});
