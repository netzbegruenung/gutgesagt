/**
 * Teilen als Bild (#756, Glossar „Teilen als Bild“): Die Beitragskarte als Bild im Stil der App,
 * gemalt im Browser auf ein Canvas. Kein Server, keine fremden Bilder: Schrift, Logo und
 * Motiv kommen von der eigenen Adresse. Das Bild ist immer hell, unabhängig vom
 * Dunkelmodus der App (es landet in fremden Apps).
 *
 * Aufbau von oben: Thema mit Motiv (falls bekannt), „Antwort auf“ mit der Aussage (falls
 * bekannt), die weiße Karte mit Titel und dem Text der gewählten Fassung, unten die Marke
 * „Gut gesagt“ und die Adresse des Beitrags ohne https://.
 */

/** Quadrat für den Feed, Story im Hochformat 9:16. */
export type SharepicFormat = 'quadrat' | 'story';

export const SHAREPIC_MASSE: Record<SharepicFormat, { breite: number; hoehe: number }> = {
  quadrat: { breite: 1080, hoehe: 1080 },
  story: { breite: 1080, hoehe: 1920 },
};

export const SHAREPIC_FORMAT_LABEL: Record<SharepicFormat, string> = {
  quadrat: 'Quadrat',
  story: 'Story',
};

/** Was ins Bild kommt. */
export interface SharepicDaten {
  titel: string | null;
  text: string;
  /** Die Aussage, auf die der Beitrag antwortet; null ohne. */
  aussage: string | null;
  /** Das erste Thema der Aussage; null ohne. */
  thema: { name: string; motiv?: string } | null;
  /** Volle Adresse des Beitrags; im Bild ohne Schema. */
  link: string;
}

/**
 * Farben des Bildes, fest und hell. Die Paare stehen mit ihrem Kontrast im Spec
 * (sharepic.spec.ts, mindestens 4,5:1).
 */
export const SHAREPIC_FARBEN = {
  grund: '#f6ff7c', // App-Gelb des Such-Bandes (Token kopf)
  tanne: '#005437', // Tannengrün: Marke, Aussage, Adresse auf Gelb
  karte: '#ffffff',
  text: '#1f1f1f',
} as const;

const RAND = 72;
const KARTE_INNEN = 56;
const KARTE_RADIUS = 36;
const SCHRIFT = 'PTSans, Roboto, sans-serif';
const SCHRIFT_FETT = 'PTSans-bold, Roboto, sans-serif';
const SCHRIFT_MARKE = 'GrueneType, Roboto, sans-serif';
// Das App-Symbol als PNG: Es traegt das Logo auf demselben Gelb wie der Grund. Ein SVG
// ohne eigene Breite und Hoehe (logo-v2.svg) malt Firefox nicht auf ein Canvas.
const LOGO = '/marke/icon-192-v3.png';

/** Die Adresse, wie sie im Bild steht: ohne Schema und ohne www. */
export function kurzeAdresse(link: string): string {
  return link.replace(/^https?:\/\//, '').replace(/^www\./, '');
}

/** Breite eines Textes in der aktuellen Schrift; in Tests ersetzbar. */
export type Messen = (text: string) => number;

/**
 * Bricht Text in Zeilen von höchstens `breite`, an Leerzeichen; Absätze bleiben.
 * Ein Wort, das allein zu breit ist, wird hart geteilt.
 */
export function umbrechen(text: string, breite: number, messen: Messen): string[] {
  const zeilen: string[] = [];
  for (const absatz of text.replace(/\r/g, '').split('\n')) {
    const woerter = absatz.split(/\s+/).filter(Boolean);
    if (!woerter.length) {
      if (zeilen.length) zeilen.push('');
      continue;
    }
    let zeile = '';
    for (const wort of woerter) {
      const versuch = zeile ? `${zeile} ${wort}` : wort;
      if (messen(versuch) <= breite) {
        zeile = versuch;
        continue;
      }
      if (zeile) zeilen.push(zeile);
      zeile = wort;
      // Nach Zeichen, nicht nach UTF-16-Einheiten: Emoji bleiben ganz
      let zeichen = Array.from(zeile);
      while (messen(zeile) > breite && zeichen.length > 1) {
        let n = zeichen.length - 1;
        while (n > 1 && messen(zeichen.slice(0, n).join('')) > breite) n--;
        zeilen.push(zeichen.slice(0, n).join(''));
        zeichen = zeichen.slice(n);
        zeile = zeichen.join('');
      }
    }
    if (zeile) zeilen.push(zeile);
  }
  while (zeilen.length && zeilen[zeilen.length - 1] === '') zeilen.pop();
  return zeilen;
}

/** Kürzt Zeilen auf `max`; die letzte endet dann mit „…“, solange sie passt. */
export function kuerzen(zeilen: string[], max: number, breite: number, messen: Messen): string[] {
  if (zeilen.length <= max) {
    return zeilen;
  }
  const rest = zeilen.slice(0, Math.max(1, max));
  const zeichen = Array.from(rest[rest.length - 1]);
  while (zeichen.length && messen(`${zeichen.join('')}…`) > breite) {
    zeichen.pop();
  }
  rest[rest.length - 1] = `${zeichen.join('').trimEnd()}…`;
  return rest;
}

/** Ein Textblock im Bild: Zeilen in einer Größe. */
export interface Block {
  zeilen: string[];
  groesse: number;
  zeilenhoehe: number;
}

/**
 * Wählt die größte Schrift zwischen `max` und `min`, bei der Titel und Text in die
 * Höhe passen; passt es auch klein nicht, wird der Text gekürzt.
 */
export function kartenText(
  titel: string | null,
  text: string,
  breite: number,
  hoehe: number,
  messenIn: (groesse: number, fett: boolean) => Messen,
  max = 60,
  min = 30,
): { titel: Block | null; text: Block } {
  for (let groesse = max; groesse >= min; groesse -= 2) {
    const titelBlock = titel ? block(titel, breite, groesse * 1.15, true, messenIn) : null;
    const textBlock = block(text, breite, groesse, false, messenIn);
    if (hoeheVon(titelBlock, textBlock) <= hoehe) {
      return { titel: titelBlock, text: textBlock };
    }
  }
  const titelBlock = titel ? block(titel, breite, min * 1.15, true, messenIn) : null;
  if (titelBlock) {
    titelBlock.zeilen = kuerzen(titelBlock.zeilen, 3, breite, messenIn(titelBlock.groesse, true));
  }
  const textBlock = block(text, breite, min, false, messenIn);
  const frei = hoehe - (titelBlock ? titelBlock.zeilen.length * titelBlock.zeilenhoehe + min : 0);
  const passen = Math.max(1, Math.floor(frei / textBlock.zeilenhoehe));
  textBlock.zeilen = kuerzen(textBlock.zeilen, passen, breite, messenIn(min, false));
  return { titel: titelBlock, text: textBlock };
}

function block(
  text: string,
  breite: number,
  groesse: number,
  fett: boolean,
  messenIn: (groesse: number, fett: boolean) => Messen,
): Block {
  const g = Math.round(groesse);
  return { zeilen: umbrechen(text, breite, messenIn(g, fett)), groesse: g, zeilenhoehe: Math.round(g * 1.3) };
}

function hoeheVon(titel: Block | null, text: Block): number {
  const titelHoehe = titel ? titel.zeilen.length * titel.zeilenhoehe + text.groesse : 0;
  return titelHoehe + text.zeilen.length * text.zeilenhoehe;
}

function schrift(groesse: number, fett = false): string {
  return `${groesse}px ${fett ? SCHRIFT_FETT : SCHRIFT}`;
}

function messerFuer(ctx: CanvasRenderingContext2D) {
  return (groesse: number, fett: boolean): Messen =>
    (text: string) => {
      ctx.font = schrift(groesse, fett);
      return ctx.measureText(text).width;
    };
}

/** Malt ein quadratisches Bild; wirft der Browser (etwa bei einem SVG ohne Groesse), ohne es. */
function sicherMalen(ctx: CanvasRenderingContext2D, bild: CanvasImageSource, x: number, y: number, groesse: number): boolean {
  try {
    ctx.drawImage(bild, x, y, groesse, groesse);
    return true;
  } catch {
    return false;
  }
}

/**
 * So lange darf jeder Schritt (Logo, Motiv, Schriften, PNG erzeugen) höchstens dauern (#819).
 * Normal braucht das ganze Bild unter einer Sekunde; hängt ein Schritt, meldet der Dialog
 * das, statt endlos zu warten.
 */
export const SHAREPIC_ZEITGRENZE_MS = 8000;

/** Ein Schritt brauchte länger als SHAREPIC_ZEITGRENZE_MS. */
export class SharepicZeitueberschreitung extends Error {
  constructor(readonly schritt: string) {
    super(`Sharepic: ${schritt} dauerte länger als ${SHAREPIC_ZEITGRENZE_MS} ms`);
    this.name = 'SharepicZeitueberschreitung';
  }
}

/** Wartet auf `versprechen`, höchstens `ms`; danach wirft es SharepicZeitueberschreitung. */
export function mitZeitgrenze<T>(versprechen: Promise<T>, schritt: string, ms = SHAREPIC_ZEITGRENZE_MS): Promise<T> {
  let uhr: ReturnType<typeof setTimeout> | undefined;
  const grenze = new Promise<never>((_, reject) => {
    uhr = setTimeout(() => reject(new SharepicZeitueberschreitung(schritt)), ms);
  });
  return Promise.race([versprechen, grenze]).finally(() => clearTimeout(uhr));
}

/**
 * Lädt, was das Bild von außen braucht. Im Browser `BROWSER_LADER`; Tests setzen einen
 * eigenen ein, damit sie nicht von Netz und Schriftladen abhängen.
 */
export interface SharepicLader {
  /** Ein Bild von der eigenen Adresse; null, wenn es sich nicht laden lässt. */
  bild(src: string): Promise<CanvasImageSource | null>;
  /** Die Schriften des Bildes; ein Fehler ist kein Abbruch. */
  schriften(): Promise<void>;
}

function bildLaden(src: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    // Mit Groesse: Firefox malt SVGs ohne eigene Breite und Hoehe sonst nicht
    const bild = new Image(192, 192);
    bild.onload = () => resolve(bild);
    bild.onerror = () => resolve(null);
    bild.src = src;
  });
}

async function schriftenLaden(): Promise<void> {
  const fonts = typeof document !== 'undefined' ? document.fonts : undefined;
  if (!fonts?.load) {
    return;
  }
  // Ohne geladene Schrift malte das Canvas in der Ersatzschrift; ein Fehler ist kein Abbruch.
  await Promise.all(
    [schrift(40), schrift(40, true), `56px ${SCHRIFT_MARKE}`].map((f) => fonts.load(f).catch(() => undefined)),
  );
}

export const BROWSER_LADER: SharepicLader = { bild: bildLaden, schriften: schriftenLaden };

function rundesRechteck(ctx: CanvasRenderingContext2D, x: number, y: number, b: number, h: number, r: number): void {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + b, y, x + b, y + h, r);
  ctx.arcTo(x + b, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + b, y, r);
  ctx.closePath();
}

/**
 * Malt das Bild auf ein neues Canvas; Logo, Motiv und Schriften werden vorher geladen, jedes
 * höchstens SHAREPIC_ZEITGRENZE_MS lang.
 */
export async function sharepicMalen(
  daten: SharepicDaten,
  format: SharepicFormat,
  lader: SharepicLader = BROWSER_LADER,
): Promise<HTMLCanvasElement> {
  const { breite, hoehe } = SHAREPIC_MASSE[format];
  const canvas = document.createElement('canvas');
  canvas.width = breite;
  canvas.height = hoehe;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    throw new Error('Canvas nicht verfügbar');
  }
  const motivSrc = motivAdresse(daten.thema?.motiv);
  const [logo, motiv] = await Promise.all([
    mitZeitgrenze(lader.bild(LOGO), 'Logo laden'),
    motivSrc ? mitZeitgrenze(lader.bild(motivSrc), 'Motiv laden') : Promise.resolve(null),
    mitZeitgrenze(lader.schriften(), 'Schriften laden'),
  ]);
  const messenIn = messerFuer(ctx);
  const innen = breite - 2 * RAND;
  const story = format === 'story';

  ctx.fillStyle = SHAREPIC_FARBEN.grund;
  ctx.fillRect(0, 0, breite, hoehe);
  ctx.textBaseline = 'top';

  let y = story ? RAND * 2 : RAND;

  // Thema als Marke mit Motiv
  if (daten.thema) {
    const g = 34;
    const motivGroesse = 48;
    ctx.font = schrift(g, true);
    const name = daten.thema.name;
    const textBreite = Math.min(ctx.measureText(name).width, innen - 120);
    const markeBreite = textBreite + 48 + (motiv ? motivGroesse + 14 : 0);
    const markeHoehe = 72;
    ctx.fillStyle = SHAREPIC_FARBEN.karte;
    rundesRechteck(ctx, RAND, y, markeBreite, markeHoehe, markeHoehe / 2);
    ctx.fill();
    let x = RAND + 24;
    if (motiv) {
      if (sicherMalen(ctx, motiv, x, y + (markeHoehe - motivGroesse) / 2, motivGroesse)) {
        x += motivGroesse + 14;
      }
    }
    ctx.fillStyle = SHAREPIC_FARBEN.tanne;
    ctx.fillText(name, x, y + (markeHoehe - g) / 2 + 2, textBreite);
    y += markeHoehe + 32;
  }

  // „Antwort auf“ mit der Aussage
  if (daten.aussage) {
    const g = story ? 40 : 34;
    ctx.font = schrift(g, true);
    ctx.fillStyle = SHAREPIC_FARBEN.tanne;
    ctx.fillText('Antwort auf:', RAND, y);
    y += Math.round(g * 1.35);
    const zeilen = kuerzen(umbrechen(`„${daten.aussage}“`, innen, messenIn(g, false)), story ? 4 : 2, innen, messenIn(g, false));
    ctx.font = schrift(g);
    for (const zeile of zeilen) {
      ctx.fillText(zeile, RAND, y);
      y += Math.round(g * 1.3);
    }
    y += 28;
  }

  // Fuss: Logo, Marke, Adresse
  const fussHoehe = 120;
  const fussY = hoehe - (story ? RAND * 2 : RAND) - fussHoehe;
  const logoGroesse = 104;
  const mitLogo = !!logo && sicherMalen(ctx, logo, RAND, fussY + (fussHoehe - logoGroesse) / 2, logoGroesse);
  const markeX = RAND + (mitLogo ? logoGroesse + 20 : 0);
  ctx.fillStyle = SHAREPIC_FARBEN.tanne;
  ctx.font = `56px ${SCHRIFT_MARKE}`;
  ctx.fillText('Gut gesagt', markeX, fussY + 8);
  let adresseGroesse = 30;
  const adresse = kurzeAdresse(daten.link);
  const adresseBreite = breite - RAND - markeX;
  while (adresseGroesse > 18 && messenIn(adresseGroesse, false)(adresse) > adresseBreite) {
    adresseGroesse -= 2;
  }
  ctx.font = schrift(adresseGroesse);
  ctx.fillText(adresse, markeX, fussY + 76, adresseBreite);

  // Die Karte mit Titel und Text dazwischen
  const karteY = y;
  const karteHoehe = fussY - 40 - karteY;
  const textBreite = innen - 2 * KARTE_INNEN;
  const inhalt = kartenText(
    daten.titel?.trim() || null,
    daten.text.trim(),
    textBreite,
    karteHoehe - 2 * KARTE_INNEN,
    messenIn,
    story ? 80 : 56,
    story ? 36 : 28,
  );
  const inhaltHoehe =
    (inhalt.titel ? inhalt.titel.zeilen.length * inhalt.titel.zeilenhoehe + inhalt.text.groesse : 0) +
    inhalt.text.zeilen.length * inhalt.text.zeilenhoehe;
  // Kurze Texte: die Karte so hoch wie ihr Inhalt, mittig im freien Raum
  const hoeheKarte = Math.min(karteHoehe, inhaltHoehe + 2 * KARTE_INNEN);
  const yKarte = karteY + Math.max(0, (karteHoehe - hoeheKarte) / 2);
  ctx.fillStyle = SHAREPIC_FARBEN.karte;
  rundesRechteck(ctx, RAND, yKarte, innen, hoeheKarte, KARTE_RADIUS);
  ctx.fill();

  let ty = yKarte + KARTE_INNEN;
  ctx.fillStyle = SHAREPIC_FARBEN.text;
  if (inhalt.titel) {
    ctx.font = schrift(inhalt.titel.groesse, true);
    for (const zeile of inhalt.titel.zeilen) {
      ctx.fillText(zeile, RAND + KARTE_INNEN, ty);
      ty += inhalt.titel.zeilenhoehe;
    }
    ty += inhalt.text.groesse;
  }
  ctx.font = schrift(inhalt.text.groesse);
  for (const zeile of inhalt.text.zeilen) {
    ctx.fillText(zeile, RAND + KARTE_INNEN, ty);
    ty += inhalt.text.zeilenhoehe;
  }
  return canvas;
}

/**
 * Motive liegen relativ unter public/ („themen/klima.svg“); im Bild von der Wurzel.
 * Fremde Adressen malt das Bild nicht (keine fremden Bilder, und sie sperrten das Canvas).
 */
export function motivAdresse(motiv: string | undefined): string | null {
  // Nur einfache Pfade unter public/: kein Schema, kein // oder \, keine Punkte-Ordner
  if (!motiv || !/^\/?(?:[a-z0-9_-]+\/)*[a-z0-9_-]+\.(?:svg|png)$/i.test(motiv)) {
    return null;
  }
  return motiv.startsWith('/') ? motiv : `/${motiv}`;
}

/** Das Bild als PNG-Datei zum Teilen oder Herunterladen. */
export async function sharepicDatei(
  daten: SharepicDaten,
  format: SharepicFormat,
  lader: SharepicLader = BROWSER_LADER,
): Promise<File> {
  const canvas = await sharepicMalen(daten, format, lader);
  const blob = await mitZeitgrenze(
    new Promise<Blob>((resolve, reject) =>
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Bild nicht erzeugt'))), 'image/png'),
    ),
    'PNG erzeugen',
  );
  return new File([blob], `gut-gesagt-${format}.png`, { type: 'image/png' });
}
