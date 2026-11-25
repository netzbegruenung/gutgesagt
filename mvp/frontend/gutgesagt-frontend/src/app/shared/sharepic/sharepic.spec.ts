import {
  SHAREPIC_FARBEN,
  SHAREPIC_MASSE,
  SHAREPIC_ZEITGRENZE_MS,
  SharepicDaten,
  SharepicLader,
  SharepicZeitueberschreitung,
  kartenText,
  kuerzen,
  kurzeAdresse,
  mitZeitgrenze,
  motivAdresse,
  sharepicDatei,
  umbrechen,
} from './sharepic';

const DATEN: SharepicDaten = {
  titel: 'Windkraft schafft Arbeitsplätze',
  text: 'In der Windbranche arbeiten heute mehr Menschen als in der Kohle. '.repeat(3),
  aussage: 'Windräder kosten nur Jobs.',
  thema: { name: 'Klima', motiv: 'themen/klima.svg' },
  link: 'https://gut-gesagt.example/beitrag/11111111-1111-4111-8111-111111111111',
};

/**
 * Lader ohne Netz und ohne Schriftladen (#819): Logo und Motiv sind ein im Test gemaltes
 * Canvas, die Schriften gelten sofort als geladen. So hängt das Malen nur am Canvas selbst.
 */
function testLader(): SharepicLader & { bild: jasmine.Spy } {
  const bild = document.createElement('canvas');
  bild.width = bild.height = 192;
  const ctx = bild.getContext('2d')!;
  ctx.fillStyle = SHAREPIC_FARBEN.tanne;
  ctx.fillRect(0, 0, 192, 192);
  return { bild: jasmine.createSpy('bild').and.resolveTo(bild), schriften: () => Promise.resolve() };
}

/** Jedes Zeichen ist 10 breit: Umbruch ohne Canvas nachrechenbar. */
const messen = (text: string) => text.length * 10;

/** Kontrast nach WCAG 2.x aus zwei Hex-Farben. */
function kontrast(a: string, b: string): number {
  const hell = (hex: string) => {
    const [r, g, bl] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(bl);
  };
  const [x, y] = [hell(a), hell(b)].sort((m, n) => n - m);
  return (x + 0.05) / (y + 0.05);
}

describe('Sharepic (#756)', () => {
  describe('umbrechen', () => {
    it('bricht an Leerzeichen und haelt Absaetze', () => {
      expect(umbrechen('eins zwei drei\nvier', 90, messen)).toEqual(['eins zwei', 'drei', 'vier']);
    });

    it('teilt ein Wort, das allein zu breit ist', () => {
      expect(umbrechen('Klimaschutzgesetz', 60, messen)).toEqual(['Klimas', 'chutzg', 'esetz']);
    });

    it('teilt nicht mitten im Emoji', () => {
      expect(umbrechen('😀😀😀', 20, messen).every((z) => !/[\uD800-\uDBFF]$/.test(z))).toBeTrue();
    });

    it('laesst keine Leerzeile am Ende', () => {
      expect(umbrechen('eins\n\n', 100, messen)).toEqual(['eins']);
    });
  });

  it('kuerzt mit Auslassungszeichen', () => {
    expect(kuerzen(['aaaa', 'bbbb', 'cccc'], 2, 50, messen)).toEqual(['aaaa', 'bbbb…']);
    expect(kuerzen(['aaaa'], 2, 50, messen)).toEqual(['aaaa']);
  });

  it('waehlt fuer kurzen Text die groesste Schrift und kuerzt zu langen', () => {
    const messenIn = () => messen;
    const kurz = kartenText('Titel', 'kurz', 500, 800, messenIn, 60, 30);
    expect(kurz.text.groesse).toBe(60);

    const lang = kartenText(null, 'wort '.repeat(500), 500, 300, messenIn, 60, 30);
    expect(lang.text.groesse).toBe(30);
    expect(lang.text.zeilen.length * lang.text.zeilenhoehe).toBeLessThanOrEqual(300);
    expect(lang.text.zeilen[lang.text.zeilen.length - 1].endsWith('…')).toBeTrue();
  });

  it('zeigt die Adresse ohne Schema', () => {
    expect(kurzeAdresse('https://www.gut-gesagt.de/beitrag/abc')).toBe('gut-gesagt.de/beitrag/abc');
  });

  it('malt nur eigene Motive', () => {
    expect(motivAdresse('themen/klima.svg')).toBe('/themen/klima.svg');
    expect(motivAdresse('/themen/klima.svg')).toBe('/themen/klima.svg');
    expect(motivAdresse('https://example.org/x.svg')).toBeNull();
    expect(motivAdresse('//example.org/x.svg')).toBeNull();
    expect(motivAdresse('data:image/svg+xml,<svg/>')).toBeNull();
    expect(motivAdresse('/\\evil.example/x.svg')).toBeNull();
    expect(motivAdresse('\\\\evil.example\\x.svg')).toBeNull();
    expect(motivAdresse('themen/../x.svg')).toBeNull();
    expect(motivAdresse(undefined)).toBeNull();
  });

  it('haelt die Farbpaare bei mindestens 4,5:1 (WCAG AA)', () => {
    expect(kontrast(SHAREPIC_FARBEN.tanne, SHAREPIC_FARBEN.grund)).toBeGreaterThanOrEqual(4.5);
    expect(kontrast(SHAREPIC_FARBEN.tanne, SHAREPIC_FARBEN.karte)).toBeGreaterThanOrEqual(4.5);
    expect(kontrast(SHAREPIC_FARBEN.text, SHAREPIC_FARBEN.karte)).toBeGreaterThanOrEqual(4.5);
  });

  for (const format of ['quadrat', 'story'] as const) {
    it(`malt ein PNG im Format ${format}`, async () => {
      const lader = testLader();
      // Zeitgrenze unter dem Jasmine-Timeout (5 s): Haengt toBlob, nennt der Fehler den Schritt.
      const datei = await sharepicDatei(DATEN, format, lader, 3000);
      expect(lader.bild.calls.allArgs()).toEqual([['/marke/icon-192-v3.png'], ['/themen/klima.svg']]);
      expect(datei.type).toBe('image/png');
      expect(datei.size).toBeGreaterThan(1000);
      const bild = await createImageBitmap(datei);
      expect([bild.width, bild.height]).toEqual([SHAREPIC_MASSE[format].breite, SHAREPIC_MASSE[format].hoehe]);
    });
  }

  it('laesst einen rechtzeitigen Schritt der Zeitgrenze unveraendert durch und raeumt die Uhr ab (#819)', async () => {
    // Ohne jasmine.clock: die Spione umhuellen die echten Timer, nicht die der Test-Uhr
    const setzen = spyOn(window, 'setTimeout').and.callThrough();
    const abraeumen = spyOn(window, 'clearTimeout').and.callThrough();
    await expectAsync(mitZeitgrenze(Promise.resolve('fertig'), 'Test')).toBeResolvedTo('fertig');
    expect(abraeumen).toHaveBeenCalledWith(setzen.calls.mostRecent().returnValue);
  });

  describe('Zeitgrenze (#819)', () => {
    beforeEach(() => jasmine.clock().install());
    afterEach(() => jasmine.clock().uninstall());

    it('bricht ab, wenn ein Bild nie fertig laedt', async () => {
      const lader: SharepicLader = { bild: () => new Promise(() => undefined), schriften: () => Promise.resolve() };
      const datei = sharepicDatei(DATEN, 'story', lader);
      let fertig = false;
      datei.catch(() => undefined).finally(() => (fertig = true));

      jasmine.clock().tick(SHAREPIC_ZEITGRENZE_MS - 1);
      await Promise.resolve();
      expect(fertig).toBeFalse();

      jasmine.clock().tick(1);
      await expectAsync(datei).toBeRejectedWithError(SharepicZeitueberschreitung, /Logo laden/);
    });

    it('bricht ab, wenn die Schriften nie fertig laden', async () => {
      const lader: SharepicLader = { bild: () => Promise.resolve(null), schriften: () => new Promise(() => undefined) };
      const datei = sharepicDatei(DATEN, 'quadrat', lader);

      jasmine.clock().tick(SHAREPIC_ZEITGRENZE_MS);
      await expectAsync(datei).toBeRejectedWithError(SharepicZeitueberschreitung, /Schriften laden/);
    });

  });
});
