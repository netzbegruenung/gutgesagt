import { DOCUMENT } from '@angular/common';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { FunktionenService } from '../services/funktionen.service';
import { KampagnenwortService, kampagnenwortAus } from './kampagnenwort.service';
import { STILLE_ABFRAGE } from './selbst-nachladen';

describe('kampagnenwortAus', () => {
  it('liest ?k= klein geschrieben', () => {
    expect(kampagnenwortAus('?k=sticker')).toBe('sticker');
    expect(kampagnenwortAus('?searchQuery=x&k=BDK')).toBe('bdk');
    expect(kampagnenwortAus('?k=g1')).toBe('g1');
  });

  it('ignoriert fehlende und unpassende Wörter', () => {
    for (const suche of ['', '?', '?q=1', '?k=', '?k=a%20b', '?k=<b>', `?k=${'x'.repeat(21)}`, null, undefined]) {
      expect(kampagnenwortAus(suche)).withContext(String(suche)).toBeNull();
    }
  });
});

describe('KampagnenwortService', () => {
  let http: HttpTestingController;
  let stand: jasmine.Spy;

  function aufsetzen(suche: string, schalter: boolean | null): KampagnenwortService {
    stand = jasmine.createSpy('stand$').and.returnValue(of(schalter));
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: DOCUMENT, useValue: { location: { search: suche } } },
        { provide: FunktionenService, useValue: { stand$: stand } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
    return TestBed.inject(KampagnenwortService);
  }

  afterEach(() => http.verify());

  it('meldet die Ankunft mit dem Wort im Body, still und nur einmal je Seite', () => {
    const dienst = aufsetzen('?k=Sticker', true);

    dienst.ankunftMelden();
    dienst.ankunftMelden();

    const anfrage = http.expectOne((r) => r.url.endsWith('/api/v1/ankunft'));
    expect(anfrage.request.method).toBe('POST');
    expect(anfrage.request.body).toEqual({ k: 'sticker' });
    expect(anfrage.request.context.get(STILLE_ABFRAGE)).toBeTrue();
    expect(stand).toHaveBeenCalledOnceWith('k_ankuenfte');
    anfrage.flush({ gezaehlt: true });
  });

  it('fragt bei sicher ausgeschaltetem Schalter nicht', () => {
    const dienst = aufsetzen('?k=bdk', false);

    dienst.ankunftMelden();

    http.expectNone((r) => r.url.endsWith('/api/v1/ankunft'));
  });

  it('fragt bei unbekanntem Stand: der Endpunkt antwortet dann selbst mit 200', () => {
    const dienst = aufsetzen('?k=bdk', null);

    dienst.ankunftMelden();

    http.expectOne((r) => r.url.endsWith('/api/v1/ankunft')).flush({ gezaehlt: false });
  });

  it('ohne ?k= weder Schalter noch Endpunkt', () => {
    const dienst = aufsetzen('?searchQuery=x', true);

    dienst.ankunftMelden();

    expect(dienst.wort).toBeNull();
    expect(stand).not.toHaveBeenCalled();
    http.expectNone((r) => r.url.endsWith('/api/v1/ankunft'));
  });

  it('bleibt bei einem Fehler still', () => {
    const dienst = aufsetzen('?k=bdk', true);

    dienst.ankunftMelden();

    http
      .expectOne((r) => r.url.endsWith('/api/v1/ankunft'))
      .flush(null, { status: 429, statusText: 'Too Many Requests' });
  });

  it('speichert nichts im Browser', () => {
    const vorher = Object.keys(localStorage).length;
    const sitzung = Object.keys(sessionStorage).length;
    const dienst = aufsetzen('?k=sticker', true);

    dienst.ankunftMelden();
    http.expectOne((r) => r.url.endsWith('/api/v1/ankunft')).flush({ gezaehlt: true });

    expect(Object.keys(localStorage).length).toBe(vorher);
    expect(Object.keys(sessionStorage).length).toBe(sitzung);
  });
});
