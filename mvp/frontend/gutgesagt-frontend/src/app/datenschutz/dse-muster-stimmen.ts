/**
 * Satz unter „Muster-Hinweise“ der Datenschutzerklärung, nur solange der Schalter
 * `muster_stimmen` wirkt (gegenseitige Zustimmungen als weiteres Merkmal; Wortlaut Jura
 * 27.11.). Das Datum ist der Tag, an dem ein Admin den Schalter zuletzt eingeschaltet hat
 * (GET /api/v1/funktionen/muster_stimmen/seit); ist es nicht zu lesen, steht „Seit dem
 * Einschalten“.
 */

const MONATE = [
  'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
  'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember',
];

/** „2026-11-28“ → „28. November 2026“; null bei allem, was kein Datum ist. */
export function dseDatum(iso: string | null | undefined): string | null {
  const treffer = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso ?? '');
  if (!treffer) {
    return null;
  }
  const monat = Number(treffer[2]);
  if (monat < 1 || monat > 12) {
    return null;
  }
  return `${Number(treffer[3])}. ${MONATE[monat - 1]} ${treffer[1]}`;
}

/** Der Satz mit dem Einschalttag, ohne lesbaren Tag mit „Seit dem Einschalten“. */
export function dseMusterStimmen(seit: string | null | undefined): string {
  const datum = dseDatum(seit);
  return (
    `Seit dem ${datum ?? 'Einschalten'} fließt auch ein, wessen Beiträgen du zustimmst, wenn ` +
    'du dafür eingewilligt hast. Die Hinweise bleiben höchstens 56 Tage und werden gelöscht, ' +
    'sobald einer von euch widerruft.'
  );
}
