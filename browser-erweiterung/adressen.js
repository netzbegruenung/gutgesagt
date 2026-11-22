/*
 * Bildet die Adressen, die die Erweiterung oeffnet. Reine Funktionen ohne Browser-APIs,
 * damit node:test sie ohne Paket pruefen kann (test/adressen.test.js).
 *
 * Klassisches Skript statt ES-Modul: Chrome laedt es im Service Worker per importScripts,
 * Firefox ueber background.scripts vor hintergrund.js, die Optionsseite per <script>,
 * Node per require.
 */

/** Ziele zum Umschalten in den Optionen; Standard ist Prod. */
const ZIELE = {
  prod: 'https://gutgesagt.netzbegruenung.de',
  test: 'https://gutgesagt-test.netzbegruenung.de',
};
const STANDARD_ZIEL = 'prod';

/** Wie lang eine Markierung hoechstens mitgeht: die Eingabegrenze der Suche (AUSSAGE_MAX_ZEICHEN). */
const TEXT_MAX = 1000;

/*
 * Obergrenze fuer die ganze Adresse. nginx nimmt im Standard Anfragezeilen bis 8 KB an; ein
 * Umlaut wird kodiert zu 6 Zeichen, ein Emoji zu 12. 1000 Umlaute passen, 1000 Emojis werden
 * weiter gekuerzt.
 */
const ADRESSE_MAX = 7000;

/** Laengere Seitenadressen (kodiert) gehen nicht mit, damit fuer die Markierung Platz bleibt. */
const LINK_MAX = 1500;

/** Die Basisadresse fuer einen Zielnamen; Unbekanntes faellt auf Prod zurueck. */
function zielBasis(name) {
  return Object.prototype.hasOwnProperty.call(ZIELE, name) ? ZIELE[name] : ZIELE[STANDARD_ZIEL];
}

/**
 * Leerraum zusammenfassen und auf ``max`` Zeichen kuerzen, am letzten Wortende davor
 * (wie suchtextKuerzen im Frontend). Zaehlt Codepunkte, damit kein Emoji halbiert wird.
 */
function textKuerzen(text, max = TEXT_MAX) {
  const zeichen = Array.from(String(text ?? '').trim().replace(/\s+/g, ' '));
  if (zeichen.length <= max) {
    return zeichen.join('');
  }
  const schnitt = zeichen.slice(0, max).join('');
  const wortende = schnitt.lastIndexOf(' ');
  return (wortende > schnitt.length / 2 ? schnitt.slice(0, wortende) : schnitt).trimEnd();
}

/** Kuerzt ``text`` weiter, bis ``adresse(text)`` hoechstens ADRESSE_MAX Zeichen hat. */
function passendKuerzen(text, adresse) {
  let kurz = textKuerzen(text);
  while (kurz && adresse(kurz).length > ADRESSE_MAX) {
    kurz = textKuerzen(kurz, Math.floor(Array.from(kurz).length * 0.9));
  }
  return kurz;
}

/** Nur http(s)-Seiten gehen als Link mit; file://, about: und Browser-Seiten nicht. */
function seitenLink(seitenAdresse) {
  try {
    const url = new URL(String(seitenAdresse ?? ''));
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null;
  } catch {
    return null;
  }
}

/** /result?searchQuery=<Markierung> (SUCHTEXT_PARAM im Frontend), oder null ohne Markierung. */
function suchAdresse(basis, markierung) {
  const adresse = (text) => `${basis}/result?searchQuery=${encodeURIComponent(text)}`;
  const text = passendKuerzen(markierung, adresse);
  return text ? adresse(text) : null;
}

/**
 * /teilen?text=<Markierung>&url=<Seite>: derselbe Weg wie das Teilen-Ziel der PWA
 * (share_target im Manifest, ShareTargetGuard). Der Guard legt Link und Hinweis ab und leitet
 * auf /einwerfen; die Anmeldung uebernimmt dort der AuthGuard im normalen Tab.
 * Ein zu langer Seitenlink faellt weg, die Markierung bleibt.
 */
function einwurfAdresse(basis, markierung, seitenAdresse) {
  let link = seitenLink(seitenAdresse);
  if (link && encodeURIComponent(link).length > LINK_MAX) {
    link = null;
  }
  const linkTeil = link ? `&url=${encodeURIComponent(link)}` : '';
  const adresse = (text) => `${basis}/teilen?text=${encodeURIComponent(text)}${linkTeil}`;
  const text = passendKuerzen(markierung, adresse);
  if (text) {
    return adresse(text);
  }
  return link ? `${basis}/teilen?url=${encodeURIComponent(link)}` : null;
}

if (typeof module !== 'undefined') {
  module.exports = {
    ZIELE,
    STANDARD_ZIEL,
    TEXT_MAX,
    ADRESSE_MAX,
    LINK_MAX,
    zielBasis,
    textKuerzen,
    seitenLink,
    suchAdresse,
    einwurfAdresse,
  };
}
