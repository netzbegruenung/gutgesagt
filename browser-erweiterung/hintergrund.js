/*
 * Kontextmenue "In Gut gesagt suchen/einwerfen" fuer markierten Text.
 *
 * Liest nur, was der Browser beim Klick uebergibt (selectionText, pageUrl), keine
 * Seiteninhalte, und ruft selbst nichts ab: Es oeffnet nur einen neuen Tab.
 */

// Chrome (Service Worker) laedt adressen.js hier; Firefox laedt es vorher ueber background.scripts.
if (typeof importScripts === 'function') {
  importScripts('adressen.js');
}

const api = globalThis.browser ?? globalThis.chrome;

const MENUE = {
  suchen: 'gutgesagt-suchen',
  einwerfen: 'gutgesagt-einwerfen',
};

// Beide Browser behalten die Eintraege ueber Neustarts; neu angelegt wird nur bei Installation
// und Update. removeAll vorher, sonst scheitert create an der schon vergebenen id.
api.runtime.onInstalled.addListener(async () => {
  await api.contextMenus.removeAll();
  api.contextMenus.create({ id: MENUE.suchen, title: 'In Gut gesagt suchen', contexts: ['selection'] });
  api.contextMenus.create({ id: MENUE.einwerfen, title: 'In Gut gesagt einwerfen', contexts: ['selection'] });
});

/** Gespeichertes Ziel (Optionen), sonst Prod. storage.local: nichts wird synchronisiert. */
async function basis() {
  try {
    const { ziel } = await api.storage.local.get('ziel');
    return zielBasis(ziel);
  } catch {
    return zielBasis(STANDARD_ZIEL);
  }
}

/** Klick auf einen der Eintraege: Adresse bilden, neuen Tab oeffnen. */
async function beimKlick(info, tab) {
  if (info.menuItemId !== MENUE.suchen && info.menuItemId !== MENUE.einwerfen) {
    return;
  }
  const ziel = await basis();
  const adresse =
    info.menuItemId === MENUE.suchen
      ? suchAdresse(ziel, info.selectionText)
      : einwurfAdresse(ziel, info.selectionText, info.pageUrl);
  if (!adresse) {
    return;
  }
  const neu = { url: adresse };
  // Direkt neben dem aktuellen Tab und im selben Fenster (privat bleibt privat).
  if (tab && tab.id !== undefined && tab.id >= 0) {
    neu.index = tab.index + 1;
    neu.windowId = tab.windowId;
  }
  api.tabs.create(neu);
}

api.contextMenus.onClicked.addListener(beimKlick);
