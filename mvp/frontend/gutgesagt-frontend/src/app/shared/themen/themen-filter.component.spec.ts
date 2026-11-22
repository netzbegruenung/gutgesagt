import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ThemenFilterComponent } from './themen-filter.component';

describe('ThemenFilterComponent', () => {
  let fixture: ComponentFixture<ThemenFilterComponent>;
  let gemeldet: Array<string | null>;

  function knopf(name: string): HTMLButtonElement {
    const knoepfe = Array.from(fixture.nativeElement.querySelectorAll('button')) as HTMLButtonElement[];
    return knoepfe.find((k) => k.textContent?.trim() === name)!;
  }

  beforeEach(() => {
    fixture = TestBed.createComponent(ThemenFilterComponent);
    fixture.componentRef.setInput('themen', [
      { schluessel: 'klima', name: 'Klima', motiv: 'themen/klima.svg' },
      { schluessel: 'verkehr', name: 'Verkehr' },
    ]);
    gemeldet = [];
    fixture.componentInstance.aktivChange.subscribe((a) => gemeldet.push(a));
    fixture.detectChanges();
  });

  it('zeigt das Motiv dekorativ im Chip, "Alle Themen" ohne', () => {
    const bild = knopf('Klima').querySelector('img.thema-motiv') as HTMLImageElement;

    expect(bild.getAttribute('src')).toBe('themen/klima.svg');
    expect(bild.getAttribute('alt')).toBe('');
    expect(bild.getAttribute('aria-hidden')).toBe('true');
    expect(knopf('Alle Themen').querySelector('img')).toBeNull();
  });

  it('steht ohne Wahl auf "Alle Themen"', () => {
    expect(knopf('Alle Themen').getAttribute('aria-pressed')).toBe('true');
    expect(knopf('Klima').getAttribute('aria-pressed')).toBe('false');
  });

  it('meldet das gewaehlte Thema und "Alle" als null', () => {
    knopf('Verkehr').click();
    fixture.componentRef.setInput('aktiv', 'verkehr');
    fixture.detectChanges();
    knopf('Alle Themen').click();

    expect(gemeldet).toEqual(['verkehr', null]);
  });

  it('meldet nichts, wenn das aktive Thema noch einmal gewaehlt wird', () => {
    fixture.componentRef.setInput('aktiv', 'klima');
    fixture.detectChanges();

    knopf('Klima').click();

    expect(gemeldet).toEqual([]);
  });
});
