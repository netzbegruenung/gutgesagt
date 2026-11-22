import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';

import { AllesZumThemaComponent } from './alles-zum-thema.component';
import { PassendesThema } from '../services/dtos/searchDtos';

const THEMA: PassendesThema = {
  schluessel: 'energie-heizen',
  name: 'Energie und Heizen',
  motiv: 'themen/energie-heizen.svg',
  aussagen: [
    { statement_id: 'a-1', text: 'Die Wärmepumpe funktioniert im Altbau nicht', antworten: 3 },
    { statement_id: 'a-2', text: 'Das Heizungsgesetz ist Enteignung', antworten: 1 },
  ],
  anzahl_aussagen: 3,
};

describe('AllesZumThemaComponent', () => {
  let fixture: ComponentFixture<AllesZumThemaComponent>;
  let http: HttpTestingController;

  function oeffnen(themen: PassendesThema[], filterbar: string[] = [], aktiv: string | null = null): HTMLElement {
    TestBed.configureTestingModule({
      imports: [AllesZumThemaComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(AllesZumThemaComponent);
    fixture.componentRef.setInput('themen', themen);
    fixture.componentRef.setInput('filterbar', filterbar);
    fixture.componentRef.setInput('aktiv', aktiv);
    fixture.detectChanges();
    return fixture.nativeElement;
  }

  function aussagen(seite: HTMLElement): string[] {
    return Array.from(seite.querySelectorAll('.kasten-aussage')).map((a) => a.textContent!.trim());
  }

  afterEach(() => http.verify());

  it('verlinkt jede Aussage als Suche und nennt ihre Antworten', () => {
    const seite = oeffnen([THEMA]);

    const link = seite.querySelector<HTMLAnchorElement>('.kasten-aussage')!;
    expect(link.getAttribute('href')).toBe('/result?searchQuery=Die%20W%C3%A4rmepumpe%20funktioniert%20im%20Altbau%20nicht');
    expect(Array.from(seite.querySelectorAll('.kasten-zahl')).map((z) => z.textContent!.trim())).toEqual([
      '3 Antworten',
      '1 Antwort',
    ]);
    // Das Motiv ist Zierde, der Name steht daneben.
    const motiv = seite.querySelector('img.kasten-motiv')!;
    expect(motiv.getAttribute('alt')).toBe('');
    expect(motiv.getAttribute('aria-hidden')).toBe('true');
  });

  it('laedt mit "Alle … Aussagen zum Thema" die uebrigen in den Kasten', () => {
    const seite = oeffnen([THEMA]);
    const knopf = seite.querySelector<HTMLButtonElement>('.kasten-alle')!;
    expect(knopf.textContent!.trim()).toBe('Alle 3 Aussagen zum Thema');

    knopf.click();
    fixture.detectChanges();
    expect(knopf.disabled).toBeTrue();
    http.expectOne('/api/v1/search/thema/energie-heizen').flush({
      thema: {
        ...THEMA,
        aussagen: [...THEMA.aussagen, { statement_id: 'a-3', text: 'Windräder töten Vögel', antworten: 2 }],
      },
    });
    fixture.detectChanges();

    expect(aussagen(seite).length).toBe(3);
    expect(aussagen(seite)[2]).toBe('„Windräder töten Vögel“');
    expect(seite.querySelector('.kasten-alle')).toBeNull();
    expect(seite.querySelector('[aria-live="polite"]')!.textContent).toContain('3 Aussagen zum Thema Energie und Heizen');
    // Der Knopf ist weg; der Fokus steht auf der ersten neuen Aussage.
    expect(document.activeElement).toBe(seite.querySelectorAll('.kasten-aussage')[2]);
  });

  it('verspricht bei mehr als 50 Aussagen nur die 50 meistgenutzten', () => {
    const seite = oeffnen([{ ...THEMA, anzahl_aussagen: 73 }]);

    expect(seite.querySelector('.kasten-alle')!.textContent!.trim()).toBe(
      'Die 50 meistgenutzten von 73 Aussagen zeigen',
    );
  });

  it('meldet einen Fehler beim Nachladen und laesst die Liste stehen', () => {
    const seite = oeffnen([THEMA]);

    seite.querySelector<HTMLButtonElement>('.kasten-alle')!.click();
    http.expectOne('/api/v1/search/thema/energie-heizen').flush('kaputt', { status: 500, statusText: 'Fehler' });
    fixture.detectChanges();

    expect(seite.querySelector('[role="alert"]')).toBeTruthy();
    expect(aussagen(seite).length).toBe(2);
    expect(seite.querySelector<HTMLButtonElement>('.kasten-alle')!.disabled).toBeFalse();
  });

  it('ohne weitere Aussagen und ohne Filter keine Aktionen', () => {
    const seite = oeffnen([{ ...THEMA, anzahl_aussagen: 2 }]);

    expect(seite.querySelector('.kasten-aktionen')).toBeNull();
  });

  it('schaltet den Themenfilter nur, wenn das Thema dort steht', () => {
    const seite = oeffnen([THEMA], ['energie-heizen'], 'energie-heizen');
    const gemeldet: Array<string | null> = [];
    fixture.componentInstance.filtern.subscribe((s) => gemeldet.push(s));

    const knopf = seite.querySelector<HTMLButtonElement>('.kasten-filter')!;
    expect(knopf.getAttribute('aria-pressed')).toBe('true');
    knopf.click();
    fixture.componentRef.setInput('aktiv', null);
    fixture.detectChanges();
    knopf.click();

    expect(gemeldet).toEqual([null, 'energie-heizen']);
  });

  it('zeigt hoechstens die Themen, die kommen, je mit eigenem Kasten', () => {
    const seite = oeffnen([THEMA, { ...THEMA, schluessel: 'klima', name: 'Klima', motiv: 'themen/klima.svg', anzahl_aussagen: 2 }]);

    expect(Array.from(seite.querySelectorAll('h2')).map((h) => h.textContent!.replace(/\s+/g, ' ').trim())).toEqual([
      'Alles zum Thema Energie und Heizen',
      'Alles zum Thema Klima',
    ]);
  });
});
