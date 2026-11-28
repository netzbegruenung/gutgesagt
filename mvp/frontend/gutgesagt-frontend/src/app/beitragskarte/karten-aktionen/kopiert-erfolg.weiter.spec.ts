import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { KopiertErfolgComponent } from './kopiert-erfolg.component';
import { GEPOSTET_OHNE_KONTO_DANK } from './gepostet-texte';

/**
 * Erfolgskasten nach dem Kopieren (UX-Review 26.11.2026): nach „Ja, gepostet“ ein nächster
 * Schritt (Befund 5) und der Kasten kommt ins Bild, statt unter der Bildschirmkante zu
 * liegen (Befund 6).
 */
describe('KopiertErfolgComponent: nächster Schritt und ins Bild', () => {
  let fixture: ComponentFixture<KopiertErfolgComponent>;
  let scrollen: jasmine.Spy;
  let ruhig: boolean;

  beforeEach(() => {
    ruhig = false;
    scrollen = spyOn(HTMLElement.prototype, 'scrollIntoView');
    const echt = window.matchMedia.bind(window);
    // Nur „Bewegung reduzieren“ nachstellen; andere Abfragen (Material, CDK) wie echt
    spyOn(window, 'matchMedia').and.callFake((query: string) => {
      const mql = echt(query);
      if (!query.includes('prefers-reduced-motion')) {
        return mql;
      }
      return {
        matches: ruhig,
        media: query,
        onchange: null,
        addListener: () => undefined,
        removeListener: () => undefined,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        dispatchEvent: () => false,
      } as MediaQueryList;
    });
    TestBed.configureTestingModule({ imports: [KopiertErfolgComponent], providers: [provideRouter([])] });
    fixture = TestBed.createComponent(KopiertErfolgComponent);
    fixture.detectChanges();
  });

  function weiter(): HTMLElement | null {
    return fixture.nativeElement.querySelector('[data-testid="gepostet-weiter"]');
  }

  it('bietet nach „Ja, gepostet“ noch einen Spruch an, mit Link ins Suchfeld der Startseite', () => {
    fixture.componentRef.setInput('sichtbar', true);
    fixture.componentRef.setInput('gepostet', 'frage');
    fixture.detectChanges();
    expect(weiter()).withContext('vor dem Tippen nicht').toBeNull();

    fixture.componentRef.setInput('gepostet', 'gemeldet');
    fixture.componentRef.setInput('gepostetDank', GEPOSTET_OHNE_KONTO_DANK);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent.replace(/\s+/g, ' ');
    expect(text).toContain('Danke! Schön, dass du öffentlich konterst.');
    expect(weiter()!.textContent!.replace(/\s+/g, ' ').trim()).toBe('Noch ein Spruch, der dich ärgert? Spruch suchen');
    const link = weiter()!.querySelector('a')!;
    expect(link.getAttribute('href')).toBe('/search#suchen');
  });

  for (const ohneKonto of [true, false]) {
    it(`nach „Ja, gepostet“ ${ohneKonto ? 'ohne Konto der Weg „Einladung einlösen“' : 'mit Konto kein Einladungsweg'} (Rundgang 2)`, () => {
      fixture.componentRef.setInput('sichtbar', true);
      fixture.componentRef.setInput('ohneKonto', ohneKonto);
      fixture.componentRef.setInput('gepostet', 'gemeldet');
      fixture.detectChanges();

      const einladung = fixture.nativeElement.querySelector('[data-testid="gepostet-einladung"]') as HTMLElement | null;
      if (!ohneKonto) {
        expect(einladung).toBeNull();
        return;
      }
      expect(einladung!.textContent!.replace(/\s+/g, ' ').trim()).toBe(
        'Schon einen Einladungslink? Mit Konto schreibst du selbst Antworten. Einladung einlösen',
      );
      expect(einladung!.querySelector('a')!.getAttribute('href')).toBe('/einladung');
    });
  }

  it('holt den Kasten beim Erscheinen ins Bild, sanft und nur so weit wie nötig', () => {
    fixture.componentRef.setInput('sichtbar', true);
    fixture.componentRef.setInput('kopierLauf', 1);
    fixture.detectChanges();

    expect(scrollen).toHaveBeenCalledTimes(1);
    expect(scrollen.calls.mostRecent().args[0]).toEqual({ block: 'nearest', behavior: 'smooth' });

    // Ein weiterer Durchlauf ohne neues Kopieren scrollt nicht noch einmal
    fixture.componentRef.setInput('gepostet', 'frage');
    fixture.detectChanges();
    expect(scrollen).toHaveBeenCalledTimes(1);

    // Neu kopiert: wieder einmal
    fixture.componentRef.setInput('kopierLauf', 2);
    fixture.detectChanges();
    expect(scrollen).toHaveBeenCalledTimes(2);
  });

  it('mit „Bewegung reduzieren“ ohne Animation', () => {
    ruhig = true;
    fixture.componentRef.setInput('sichtbar', true);
    fixture.componentRef.setInput('kopierLauf', 1);
    fixture.detectChanges();
    expect(scrollen.calls.mostRecent().args[0]).toEqual({ block: 'nearest', behavior: 'auto' });
  });

  it('scrollt nicht, solange der Kasten zu ist', () => {
    fixture.componentRef.setInput('kopierLauf', 1);
    fixture.detectChanges();
    expect(scrollen).not.toHaveBeenCalled();
  });
});
