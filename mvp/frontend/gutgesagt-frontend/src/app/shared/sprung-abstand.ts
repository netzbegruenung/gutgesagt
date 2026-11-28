/**
 * Abstand für Sprünge zu einem Anker (/impressum#melden, /search#recent-content): so viel,
 * wie `scroll-padding-top` am <html> freihält (styles.css: klebender Kopf am Handy, klebende
 * Suche im Album). Der Router scrollt mit `window.scrollTo` und kennt `scroll-padding` nicht;
 * ohne diesen Abstand verschwand am Handy die Überschrift des Ziels unter dem klebenden Kopf
 * (Rundgang 28.11., „Kontakt“ im Fuß, WCAG 2.4.11).
 */
export function sprungAbstand(doc: Document = document): [number, number] {
  const wert = parseFloat(getComputedStyle(doc.documentElement).scrollPaddingTop);
  return [0, Number.isFinite(wert) && wert > 0 ? wert : 0];
}
