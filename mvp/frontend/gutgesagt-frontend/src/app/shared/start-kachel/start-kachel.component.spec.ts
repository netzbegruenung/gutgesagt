import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { StartKachelComponent } from './start-kachel.component';

describe('StartKachelComponent (eine Kachelart für Aktionen, Startseite 28.11.)', () => {
  function kachel(mitKonto?: boolean): HTMLAnchorElement {
    TestBed.configureTestingModule({ imports: [StartKachelComponent], providers: [provideRouter([])] });
    const fixture = TestBed.createComponent(StartKachelComponent);
    fixture.componentRef.setInput('ziel', '/garten');
    fixture.componentRef.setInput('icon', '🗺️');
    fixture.componentRef.setInput('titel', 'Themen im Überblick');
    fixture.componentRef.setInput('satz', 'Wo es schon viele Antworten gibt und wo noch welche fehlen');
    if (mitKonto !== undefined) {
      fixture.componentRef.setInput('mitKonto', mitKonto);
    }
    fixture.detectChanges();
    return (fixture.nativeElement as HTMLElement).querySelector('a.start-kachel') as HTMLAnchorElement;
  }

  it('führt zum Ziel und zeigt Symbol, Titel, Halbsatz und Pfeil', () => {
    const a = kachel();
    expect(a.getAttribute('href')).toBe('/garten');
    expect(a.querySelector('.kachel-icon')!.getAttribute('aria-hidden')).toBe('true');
    expect(a.querySelector('.kachel-icon')!.textContent!.trim()).toBe('🗺️');
    expect(a.querySelector('.kachel-titel')!.textContent!.trim()).toBe('Themen im Überblick');
    expect(a.querySelector('.kachel-satz')!.textContent!.trim()).toBe('Wo es schon viele Antworten gibt und wo noch welche fehlen');
    expect(a.querySelector('.kachel-pfeil')!.getAttribute('aria-hidden')).toBe('true');
  });

  it('trägt die Marke „mit Konto“ nur auf Wunsch', () => {
    expect(kachel().querySelector('.kachel-konto')).toBeNull();
    TestBed.resetTestingModule();
    expect(kachel(true).querySelector('.kachel-konto')!.textContent!.trim()).toBe('mit Konto');
  });
});
