import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ThemenAuswahlComponent } from './themen-auswahl.component';
import { Thema } from '../../services/dtos/themenDtos';

const THEMEN: Thema[] = [
  { schluessel: 'klima', name: 'Klima', motiv: 'themen/klima.svg' },
  { schluessel: 'verkehr', name: 'Verkehr' },
  { schluessel: 'europa', name: 'Europa' },
  { schluessel: 'soziales', name: 'Soziales' },
];

describe('ThemenAuswahlComponent', () => {
  let fixture: ComponentFixture<ThemenAuswahlComponent>;
  let gemeldet: string[][];

  function setzen(gewaehlt: string[]): void {
    fixture.componentRef.setInput('gewaehlt', gewaehlt);
    fixture.detectChanges();
  }

  function knopf(name: string): HTMLButtonElement {
    const knoepfe = Array.from(fixture.nativeElement.querySelectorAll('button')) as HTMLButtonElement[];
    return knoepfe.find((k) => k.textContent?.trim() === name)!;
  }

  beforeEach(() => {
    fixture = TestBed.createComponent(ThemenAuswahlComponent);
    fixture.componentRef.setInput('themen', THEMEN);
    gemeldet = [];
    fixture.componentInstance.gewaehltChange.subscribe((g) => gemeldet.push(g));
    setzen([]);
  });

  it('waehlt ein Thema per Klick', () => {
    knopf('Verkehr').click();

    expect(gemeldet).toEqual([['verkehr']]);
  });

  it('zeigt gewaehlte Themen als gedrueckt und waehlt sie per Klick ab', () => {
    setzen(['klima']);

    expect(knopf('Klima').getAttribute('aria-pressed')).toBe('true');
    expect(knopf('Verkehr').getAttribute('aria-pressed')).toBe('false');
    knopf('Klima').click();
    expect(gemeldet).toEqual([[]]);
  });

  it('laesst ein drittes Thema zu', () => {
    setzen(['klima', 'verkehr']);

    expect(knopf('Europa').disabled).toBeFalse();
    knopf('Europa').click();
    expect(gemeldet).toEqual([['klima', 'verkehr', 'europa']]);
  });

  it('laesst hoechstens drei Themen zu, ein viertes nicht', () => {
    setzen(['klima', 'verkehr', 'europa']);

    expect(knopf('Soziales').disabled).toBeTrue();
    expect(knopf('Klima').disabled).toBeFalse();
    knopf('Soziales').click();
    expect(gemeldet).toEqual([]);
  });

  it('nennt die Grenze im Hinweis', () => {
    expect(fixture.nativeElement.querySelector('.themen-hinweis').textContent.trim()).toBe('Bis zu drei Themen, optional.');
  });

  it('laesst mit hoechstens 2 nur zwei Themen zu und sagt das', () => {
    fixture.componentRef.setInput('hoechstens', 2);
    setzen(['klima', 'verkehr']);

    expect(knopf('Europa').disabled).toBeTrue();
    expect(knopf('Verkehr').disabled).toBeFalse();
    knopf('Europa').click();
    expect(gemeldet).toEqual([]);
    expect(fixture.nativeElement.querySelector('.themen-hinweis').textContent.trim()).toBe('Bis zu zwei Themen, optional.');
  });

  it('zeigt das Motiv dekorativ links im Chip, der Name bleibt der Zugaengliche Name', () => {
    const bild = knopf('Klima').querySelector('img.thema-motiv') as HTMLImageElement;

    expect(bild.getAttribute('src')).toBe('themen/klima.svg');
    expect(bild.getAttribute('alt')).toBe('');
    expect(bild.getAttribute('aria-hidden')).toBe('true');
    expect(bild.getAttribute('width')).toBe('18');
    expect(bild.getAttribute('height')).toBe('18');
    expect(knopf('Klima').firstElementChild).toBe(bild);
    expect(knopf('Verkehr').querySelector('img')).toBeNull();
  });

  describe('Themenvorschlaege (#401)', () => {
    function hinweis(): string {
      return fixture.nativeElement.querySelector('.themen-hinweis').textContent.trim();
    }

    function vorschlagen(vorschlaege: string[]): void {
      fixture.componentRef.setInput('vorschlaege', vorschlaege);
      fixture.detectChanges();
    }

    it('markiert Vorschlaege sichtbar mit Text, nicht nur mit Farbe', () => {
      vorschlagen(['verkehr']);

      const chip = knopf('Verkehrvorgeschlagen');
      expect(chip.classList).toContain('vorgeschlagen');
      expect(chip.querySelector('.vorschlag-marke')?.textContent).toBe('vorgeschlagen');
      expect(chip.getAttribute('aria-pressed')).toBe('false');
      expect(knopf('Klima').classList).not.toContain('vorgeschlagen');
    });

    it('nennt die Vorschlaege auch im Hinweis darunter', () => {
      vorschlagen(['verkehr', 'klima']);

      expect(hinweis()).toBe('Bis zu drei Themen, optional. Vorgeschlagen: Verkehr und Klima.');
    });

    it('waehlt nichts von selbst; ein Tipp uebernimmt den Vorschlag', () => {
      vorschlagen(['verkehr']);
      expect(gemeldet).toEqual([]);

      knopf('Verkehrvorgeschlagen').click();

      expect(gemeldet).toEqual([['verkehr']]);
    });

    it('ein gewaehlter Vorschlag ist kein Vorschlag mehr', () => {
      vorschlagen(['verkehr', 'europa']);
      setzen(['verkehr']);

      expect(knopf('Verkehr').classList).not.toContain('vorgeschlagen');
      expect(knopf('Verkehr').getAttribute('aria-pressed')).toBe('true');
      expect(hinweis()).toBe('Bis zu drei Themen, optional. Vorgeschlagen: Europa.');
    });

    it('ist die Grenze erreicht, zeigt es keine Vorschlaege mehr', () => {
      fixture.componentRef.setInput('hoechstens', 2);
      vorschlagen(['europa']);
      setzen(['klima', 'verkehr']);

      expect(knopf('Europa').classList).not.toContain('vorgeschlagen');
      expect(hinweis()).toBe('Bis zu zwei Themen, optional.');
    });

    it('uebergeht unbekannte Schluessel', () => {
      vorschlagen(['gibt-es-nicht']);

      expect(hinweis()).toBe('Bis zu drei Themen, optional.');
      expect(fixture.nativeElement.querySelectorAll('.vorgeschlagen').length).toBe(0);
    });
  });
});
