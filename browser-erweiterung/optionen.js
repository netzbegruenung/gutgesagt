/* Optionen: Ziel Prod oder Test, gespeichert in storage.local. */
const api = globalThis.browser ?? globalThis.chrome;
const felder = document.querySelectorAll('input[name="ziel"]');
const meldung = document.getElementById('gespeichert');

function zeigen(ziel) {
  const wert = Object.prototype.hasOwnProperty.call(ZIELE, ziel) ? ziel : STANDARD_ZIEL;
  for (const feld of felder) {
    feld.checked = feld.value === wert;
  }
}

// Ohne lesbaren Speicher gilt Prod, wie in hintergrund.js
api.storage.local
  .get('ziel')
  .then(({ ziel }) => zeigen(ziel))
  .catch(() => zeigen(STANDARD_ZIEL));

for (const feld of felder) {
  feld.addEventListener('change', () => {
    api.storage.local
      .set({ ziel: feld.value })
      .then(() => {
        meldung.textContent = 'Gespeichert.';
      })
      .catch(() => {
        meldung.textContent = 'Nicht gespeichert: Der Browser erlaubt keinen Speicher.';
      });
  });
}
