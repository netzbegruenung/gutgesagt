import { BESTAND_MINDEST_ANTWORTEN, abgerundet, bestandszahl } from './bestandszahl';

describe('Bestandszahl', () => {
  it('rundet nach unten auf runde Stufen, nie nach oben', () => {
    expect(abgerundet(7)).toBe(7);
    expect(abgerundet(19)).toBe(10);
    expect(abgerundet(99)).toBe(90);
    expect(abgerundet(100)).toBe(100);
    expect(abgerundet(149)).toBe(100);
    expect(abgerundet(263)).toBe(250);
    expect(abgerundet(799)).toBe(750);
    expect(abgerundet(1042)).toBe(1000);
    expect(abgerundet(1999)).toBe(1900);
    expect(abgerundet(12345)).toBe(12000);
  });

  it('zuckt nicht bei jedem neuen Beitrag', () => {
    expect(abgerundet(751)).toBe(abgerundet(799));
  });

  it('nie negativ und ohne Nachkommastellen', () => {
    expect(abgerundet(-3)).toBe(0);
    expect(abgerundet(12.9)).toBe(10);
  });

  it('zeigt nichts bei zu wenig Bestand oder fehlender Zählung', () => {
    expect(bestandszahl(BESTAND_MINDEST_ANTWORTEN - 1, 5)).toBeNull();
    expect(bestandszahl(800, 0)).toBeNull();
    expect(bestandszahl(Number.NaN, 5)).toBeNull();
    expect(bestandszahl(BESTAND_MINDEST_ANTWORTEN, 1)).toEqual({ antworten: 10, sprueche: 1 });
  });

  it('liefert beide Zahlen abgerundet', () => {
    expect(bestandszahl(812, 263)).toEqual({ antworten: 800, sprueche: 250 });
  });
});
