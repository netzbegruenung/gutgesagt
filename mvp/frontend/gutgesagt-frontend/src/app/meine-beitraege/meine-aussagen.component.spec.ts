import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { MeineAussagenComponent } from './meine-aussagen.component';
import { EigeneAussagen } from './meine-aussagen.service';
import { environment } from '../../environments/environment';

const URL = `${environment.baseUrl}/api/v1/usage/users/me/aussagen`;

const DATEN: EigeneAussagen = {
  zeitraum_tage: 7,
  aussagen: [
    {
      id: 'a1',
      text: 'Windräder töten Vögel',
      created: '2026-11-01T10:00:00Z',
      antworten: [
        { id: 'k1', content_type: 'commentary', titel: 'Katzen töten mehr', verknuepft_am: '2026-11-21T10:00:00Z', von_dir: false, neu: true },
        { id: 'k2', content_type: 'generic_text', titel: 'Zahlen zum Vogelschlag', verknuepft_am: '2026-11-02T10:00:00Z', von_dir: true, neu: false },
      ],
    },
    { id: 'a2', text: 'Zweite Aussage', created: '2026-11-03T10:00:00Z', antworten: [] },
  ],
};

describe('MeineAussagenComponent (#760)', () => {
  let fixture: ComponentFixture<MeineAussagenComponent>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MeineAussagenComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(MeineAussagenComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function el(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  it('zeigt die eigenen Aussagen mit Antworten, neue mit Symbol und Text „Neu“', () => {
    http.expectOne(URL).flush(DATEN);
    fixture.detectChanges();

    const aussagen = el().querySelectorAll('[data-testid="eigene-aussage"]');
    expect(aussagen.length).toBe(2);
    const antworten = Array.from(aussagen[0].querySelectorAll('[data-testid="antwort"]')) as HTMLElement[];
    expect(antworten.length).toBe(2);
    expect(antworten[0].querySelector('[data-testid="neu"]')?.textContent).toContain('Neu');
    expect(antworten[0].querySelector('a')?.getAttribute('href')).toBe('/beitrag/k1');
    expect(antworten[0].textContent).toContain('Kommentar');
    expect(antworten[1].querySelector('[data-testid="neu"]')).toBeNull();
    expect(antworten[1].textContent).toContain('Hintergrundinfo · von dir');
    expect(aussagen[1].textContent).toContain('Noch keine Antwort.');
    expect(el().textContent).toContain('in den letzten 7 Tagen');
  });

  it('erklärt den leeren Zustand', () => {
    http.expectOne(URL).flush({ zeitraum_tage: 7, aussagen: [] });
    fixture.detectChanges();

    expect(el().querySelector('[data-testid="keine-aussagen"]')).not.toBeNull();
  });

  it('bietet nach einem Fehler einen neuen Versuch an', () => {
    http.expectOne(URL).flush(null, { status: 500, statusText: 'Fehler' });
    fixture.detectChanges();
    expect(el().textContent).toContain('gerade nicht erreichbar');

    (el().querySelector('button') as HTMLButtonElement).click();
    http.expectOne(URL).flush(DATEN);
    fixture.detectChanges();
    expect(el().querySelectorAll('[data-testid="eigene-aussage"]').length).toBe(2);
  });
});
