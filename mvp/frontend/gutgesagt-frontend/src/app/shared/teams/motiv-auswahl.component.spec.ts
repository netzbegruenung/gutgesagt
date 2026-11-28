import { Component } from '@angular/core';
import { ComponentFixture, TestBed, fakeAsync, flush } from '@angular/core/testing';
import { OverlayContainer } from '@angular/cdk/overlay';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

import { MotivAuswahlComponent } from './motiv-auswahl.component';
import { TeamMotivEintrag, TeamMotivKategorie } from './teams';

const MOTIVE: TeamMotivEintrag[] = [
  { schluessel: '🐝', name: 'Biene', kategorie: 'tiere-natur', stichworte: 'insekt honig' },
  { schluessel: '🌻', name: 'Sonnenblume', kategorie: 'tiere-natur', stichworte: 'blume sonne' },
  { schluessel: '🚲', name: 'Fahrrad', kategorie: 'reisen-orte', stichworte: 'rad' },
  { schluessel: '⚖️', name: 'Waage', kategorie: 'gegenstaende', stichworte: 'gerechtigkeit' },
];
const KATEGORIEN: TeamMotivKategorie[] = [
  { schluessel: 'tiere-natur', name: 'Tiere & Natur' },
  { schluessel: 'reisen-orte', name: 'Reisen & Orte' },
  { schluessel: 'gegenstaende', name: 'Gegenstände' },
];

@Component({
  standalone: true,
  imports: [MotivAuswahlComponent],
  template: `<app-motiv-auswahl [motive]="motive" [kategorien]="kategorien" [(motiv)]="motiv"></app-motiv-auswahl>`,
})
class GastComponent {
  motive = MOTIVE;
  kategorien = KATEGORIEN;
  motiv = '🌻';
}

describe('MotivAuswahlComponent', () => {
  let fixture: ComponentFixture<GastComponent>;
  let overlay: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GastComponent],
      providers: [provideNoopAnimations()],
    }).compileComponents();
    fixture = TestBed.createComponent(GastComponent);
    fixture.detectChanges();
    overlay = TestBed.inject(OverlayContainer).getContainerElement();
  });

  const el = () => fixture.nativeElement as HTMLElement;
  const suche = () => el().querySelector('[data-testid="motiv-suche"]') as HTMLInputElement;
  const auswahl = () =>
    fixture.debugElement.query((d) => d.name === 'app-motiv-auswahl').componentInstance as MotivAuswahlComponent;

  function tippen(text: string) {
    suche().focus();
    suche().dispatchEvent(new Event('focusin'));
    suche().value = text;
    suche().dispatchEvent(new Event('input'));
    fixture.detectChanges();
    flush();
    fixture.detectChanges();
  }

  /** Material liest noch keyCode; den setzt der Konstruktor von KeyboardEvent nicht. */
  function taste(key: 'ArrowDown' | 'Enter') {
    const ereignis = new KeyboardEvent('keydown', { key, code: key, bubbles: true, cancelable: true });
    Object.defineProperty(ereignis, 'keyCode', { get: () => (key === 'Enter' ? 13 : 40) });
    suche().dispatchEvent(ereignis);
    fixture.detectChanges();
    flush();
    fixture.detectChanges();
  }

  it('zeigt das gewählte Motiv mit Namen in einer Live-Region', () => {
    const gewaehlt = el().querySelector('[data-testid="motiv-gewaehlt"]')!;
    expect(gewaehlt.getAttribute('aria-live')).toBe('polite');
    expect(gewaehlt.textContent).toContain('Gewählt: Sonnenblume');
    expect(gewaehlt.textContent).toContain('🌻');
  });

  it('listet die Treffer nach Kategorien gruppiert, jedes Motiv mit Namen', fakeAsync(() => {
    tippen('');

    const gruppen = Array.from(overlay.querySelectorAll('mat-optgroup'));
    expect(gruppen.map((g) => g.querySelector('.mat-mdc-optgroup-label')!.textContent!.trim())).toEqual([
      'Tiere & Natur',
      'Reisen & Orte',
      'Gegenstände',
    ]);
    const optionen = Array.from(overlay.querySelectorAll('[data-testid="motiv-option"]'));
    expect(optionen.map((o) => o.textContent!.replace(/\s+/g, ''))).toEqual([
      '🐝Biene',
      '🌻Sonnenblume',
      '🚲Fahrrad',
      '⚖️Waage',
    ]);
  }));

  it('filtert mit der Suche und sagt, wenn nichts passt', fakeAsync(() => {
    tippen('rad');
    expect(Array.from(overlay.querySelectorAll('[data-testid="motiv-option"]')).length).toBe(1);

    tippen('gibtesnicht');
    expect(overlay.querySelector('[data-testid="motiv-option"]')).toBeNull();
    expect(overlay.querySelector('[data-testid="motiv-leer"]')!.textContent).toContain('Kein Motiv gefunden');
  }));

  it('filtert nach Kategorie', () => {
    const k = auswahl();
    k.kategorie = 'gegenstaende';
    k.aktualisieren();

    expect(k.gruppen.map((g) => g.name)).toEqual(['Gegenstände']);
    expect(k.gruppen[0].motive.map((m) => m.name)).toEqual(['Waage']);
  });

  it('wählt mit der Tastatur: Pfeil nach unten und Enter', fakeAsync(() => {
    tippen('fahr');
    taste('ArrowDown');
    taste('Enter');

    expect(fixture.componentInstance.motiv).toBe('🚲');
    expect(el().querySelector('[data-testid="motiv-gewaehlt"]')!.textContent).toContain('Gewählt: Fahrrad');
    // Danach ist das Suchfeld wieder leer
    expect(suche().value).toBe('');
  }));
});
