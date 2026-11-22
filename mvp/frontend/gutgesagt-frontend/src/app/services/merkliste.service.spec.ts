import { TestBed } from '@angular/core/testing';
import { WritableSignal, signal } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { STILLE_ABFRAGE } from '../shared/selbst-nachladen';
import { BehaviorSubject } from 'rxjs';
import { Art9EinwilligungZustand, Art9Zustand } from './art9-einwilligung-zustand';
import { FunktionenService } from './funktionen.service';
import { MerklisteService } from './merkliste.service';

describe('MerklisteService (#758)', () => {
  const URL = `${environment.baseUrl}/api/v1/merkliste`;
  let an: WritableSignal<boolean>;
  let zustand: BehaviorSubject<Art9Zustand>;
  let service: MerklisteService;
  let http: HttpTestingController;

  beforeEach(() => {
    an = signal(true);
    zustand = new BehaviorSubject<Art9Zustand>('eingewilligt');
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: FunktionenService, useValue: { an: () => an.asReadonly() } },
        { provide: Art9EinwilligungZustand, useValue: { zustand$: zustand.asObservable() } },
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

  it('fragt ohne Art.-9-Einwilligung nichts (sonst kaeme der Hinweis ungefragt)', () => {
    zustand.next('fehlt');
    service.sicherstellen();

    http.expectNone(URL);
    expect(service.bereit()).toBeFalse();
  });

  it('laedt im Hintergrund still', () => {
    service.sicherstellen();
    const anfrage = http.expectOne(URL);
    anfrage.flush({ eintraege: [] });

    expect(anfrage.request.context.get(STILLE_ABFRAGE)).toBeTrue();
  });

  it('nimmt bei einem Fehler nur den einen Eintrag zurueck', () => {
    service.sicherstellen();
    http.expectOne(URL).flush({ eintraege: [{ content_id: 'a', gemerkt_am: '2026-11-22T10:00:00Z' }] });

    service.umschalten('b').subscribe({ error: () => undefined });
    service.umschalten('c').subscribe();
    http.expectOne(`${URL}/b`).flush('weg', { status: 500, statusText: 'Server Error' });
    http.expectOne(`${URL}/c`).flush(null, { status: 204, statusText: 'No Content' });

    expect(service.eintraege().map((e) => e.content_id)).toEqual(['c', 'a']);
  });

  it('entfernt mehrere Eintraege', () => {
    service.sicherstellen();
    http.expectOne(URL).flush({
      eintraege: [
        { content_id: 'a', gemerkt_am: '' },
        { content_id: 'b', gemerkt_am: '' },
      ],
    });

    service.entfernen(['a']).subscribe();
    http.expectOne(`${URL}/a`).flush(null, { status: 204, statusText: 'No Content' });

    expect(service.eintraege().map((e) => e.content_id)).toEqual(['b']);
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
