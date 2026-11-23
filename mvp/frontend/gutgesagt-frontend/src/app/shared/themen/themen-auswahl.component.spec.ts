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

    function zeile(): HTMLElement | null {
      return fixture.nativeElement.querySelector('.themen-vorschlag');
    }

    function vorschlagChips(): HTMLButtonElement[] {
      return Array.from(fixture.nativeElement.querySelectorAll('.vorschlag-chip')) as HTMLButtonElement[];
    }

    function alleKnopf(): HTMLButtonElement | null {
      return fixture.nativeElement.querySelector('.vorschlag-alle');
    }

    it('zeigt Vorschlaege in einer eigenen Zeile mit +, Motiv und zugaenglichem Namen', () => {
      vorschlagen(['klima']);

      expect(zeile()!.getAttribute('role')).toBe('group');
      expect(zeile()!.getAttribute('aria-label')).toBe('Vorgeschlagene Themen');
      expect(zeile()!.querySelector('.vorschlag-titel')!.textContent).toBe('Vorschlag:');
      const [chip] = vorschlagChips();
      expect(chip.getAttribute('aria-label')).toBe('Klima übernehmen');
      expect(chip.querySelector('.vorschlag-plus')!.textContent).toBe('+');
      expect(chip.querySelector('img.thema-motiv')!.getAttribute('src')).toBe('themen/klima.svg');
      expect(alleKnopf()!.textContent!.trim()).toBe('Übernehmen');
    });

    it('hebt in der Liste nichts hervor und nennt die Vorschlaege nicht im Hinweis', () => {
      vorschlagen(['verkehr', 'klima']);

      expect(knopf('Verkehr').getAttribute('aria-pressed')).toBe('false');
      expect(knopf('Verkehr').className).toBe(knopf('Europa').className);
      expect(hinweis()).toBe('Bis zu drei Themen, optional.');
    });

    it('ein Tipp auf einen Vorschlag waehlt ihn; danach ist er aus der Zeile weg', () => {
      vorschlagen(['verkehr', 'klima']);
      expect(alleKnopf()!.textContent!.trim()).toBe('Beide übernehmen');

      vorschlagChips()[0].click();
      expect(gemeldet).toEqual([['verkehr']]);

      setzen(['verkehr']);
      expect(vorschlagChips().map((c) => c.getAttribute('aria-label'))).toEqual(['Klima übernehmen']);
      expect(alleKnopf()!.textContent!.trim()).toBe('Übernehmen');
    });

    it('waehlt nichts von selbst', () => {
      vorschlagen(['verkehr']);

      expect(gemeldet).toEqual([]);
    });

    it('Alle uebernehmen waehlt der Reihe nach, soweit die Grenze reicht', () => {
      setzen(['soziales']);
      vorschlagen(['verkehr', 'klima', 'europa']);
      expect(alleKnopf()!.textContent!.trim()).toBe('Alle übernehmen');

      alleKnopf()!.click();

      expect(gemeldet).toEqual([['soziales', 'verkehr', 'klima']]);
    });

    it('beim Einwerfen (hoechstens 2) nur bis zur Grenze', () => {
      fixture.componentRef.setInput('hoechstens', 2);
      vorschlagen(['verkehr', 'klima']);

      setzen(['europa']);
      alleKnopf()!.click();

      expect(gemeldet).toEqual([['europa', 'verkehr']]);
    });

    it('sind alle gewaehlt oder ist die Grenze erreicht, fehlt die Zeile', () => {
      vorschlagen(['verkehr', 'klima']);
      setzen(['verkehr', 'klima']);
      expect(zeile()).toBeNull();

      fixture.componentRef.setInput('hoechstens', 2);
      vorschlagen(['europa']);
      expect(zeile()).toBeNull();
    });

    it('uebergeht unbekannte Schluessel', () => {
      vorschlagen(['gibt-es-nicht']);

      expect(zeile()).toBeNull();
      expect(hinweis()).toBe('Bis zu drei Themen, optional.');
    });
  });
});
