/* Optionen: Ziel Prod oder Test, gespeichert in storage.local. */
const api = globalThis.browser ?? globalThis.chrome;
const felder = document.querySelectorAll('input[name="ziel"]');
const meldung = document.getElementById('gespeichert');

api.storage.local.get('ziel').then(({ ziel }) => {
  const wert = Object.prototype.hasOwnProperty.call(ZIELE, ziel) ? ziel : STANDARD_ZIEL;
  for (const feld of felder) {
    feld.checked = feld.value === wert;
  }
});

for (const feld of felder) {
  feld.addEventListener('change', () => {
    api.storage.local.set({ ziel: feld.value }).then(() => {
      meldung.textContent = 'Gespeichert.';
    });
  });
}
