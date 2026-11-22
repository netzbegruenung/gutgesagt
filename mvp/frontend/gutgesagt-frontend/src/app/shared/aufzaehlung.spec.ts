import { mitPunkten } from './aufzaehlung';

describe('mitPunkten', () => {
  it('macht aus "- " und "* " am Zeilenanfang Punkte, Zeilenumbrueche und Leerraum bleiben', () => {
    expect(mitPunkten('Darum:\n- erstens\n* zweitens')).toBe('Darum:\n• erstens\n• zweitens');
    expect(mitPunkten('  -   eingerueckt')).toBe('  •   eingerueckt');
    expect(mitPunkten('-\tTab')).toBe('•\tTab');
    expect(mitPunkten('a\r\n- b')).toBe('a\r\n• b');
  });

  it('laesst alles andere stehen, wie das Backend', () => {
    for (const text of ['Minus - mitten im Satz', '-5 Grad', '**fett**', '--- Linie', '• schon ein Punkt', '-', '']) {
      expect(mitPunkten(text)).toBe(text);
    }
    expect(mitPunkten(null)).toBeNull();
    expect(mitPunkten(undefined)).toBeUndefined();
  });
});
