import { TestBed } from '@angular/core/testing';
import { WritableSignal, signal } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { FunktionenService } from './funktionen.service';
import { MerklisteService } from './merkliste.service';

describe('MerklisteService (#758)', () => {
  const URL = `${environment.baseUrl}/api/v1/merkliste`;
  let an: WritableSignal<boolean>;
  let service: MerklisteService;
  let http: HttpTestingController;

  beforeEach(() => {
    an = signal(true);
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: FunktionenService, useValue: { an: () => an.asReadonly() } },
      ],
    });
    service = TestBed.inject(MerklisteService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('fragt bei ausgeschaltetem Schalter nichts', () => {
    an.set(false);
    service.sicherstellen();
    let ergebnis: unknown;
    service.laden().subscribe((e) => (ergebnis = e));

    http.expectNone(URL);
    expect(ergebnis).toEqual([]);
  });

  it('laedt einmal fuer alle Karten', () => {
    service.sicherstellen();
    service.sicherstellen();
    http.expectOne(URL).flush({ eintraege: [{ content_id: 'a', gemerkt_am: '2026-11-22T10:00:00Z' }] });

    service.sicherstellen();
    http.expectNone(URL);
    expect(service.istGemerkt('a')).toBeTrue();
    expect(service.istGemerkt('b')).toBeFalse();
  });

  it('merkt sofort oben und schickt PUT', () => {
    service.sicherstellen();
    http.expectOne(URL).flush({ eintraege: [{ content_id: 'a', gemerkt_am: '2026-11-22T10:00:00Z' }] });

    let gemerkt: boolean | undefined;
    service.umschalten('b').subscribe((g) => (gemerkt = g));
    expect(service.eintraege().map((e) => e.content_id)).toEqual(['b', 'a']);
    const put = http.expectOne(`${URL}/b`);
    expect(put.request.method).toBe('PUT');
    put.flush(null, { status: 204, statusText: 'No Content' });

    expect(gemerkt).toBeTrue();
  });

  it('entfernt sofort und nimmt das bei einem Fehler zurueck', () => {
    service.sicherstellen();
    http.expectOne(URL).flush({ eintraege: [{ content_id: 'a', gemerkt_am: '2026-11-22T10:00:00Z' }] });

    let fehler: unknown;
    service.umschalten('a').subscribe({ error: (f) => (fehler = f) });
    expect(service.istGemerkt('a')).toBeFalse();
    const del = http.expectOne(`${URL}/a`);
    expect(del.request.method).toBe('DELETE');
    del.flush('weg', { status: 500, statusText: 'Server Error' });

    expect(fehler).toBeTruthy();
    expect(service.istGemerkt('a')).toBeTrue();
  });
});
