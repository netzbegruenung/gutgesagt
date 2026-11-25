import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import {
  FUNKTIONEN_FEHLER_PAUSE_MS,
  FUNKTIONEN_FRISCH_WARTEN_MS,
  FUNKTIONEN_NACHLADEN_MS,
  FunktionenService,
} from './funktionen.service';

describe('FunktionenService', () => {
  const URL = `${environment.baseUrl}/api/v1/funktionen`;
  let service: FunktionenService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(FunktionenService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('gilt bis zur Antwort als aus und folgt dann dem Server', () => {
    const an = service.an('beispiel');
    expect(an()).toBeFalse();

    http.expectOne(URL).flush({ funktionen: { beispiel: true } });

    expect(an()).toBeTrue();
  });

  it('bleibt aus, wenn der Server aus meldet oder den Schalter nicht kennt', () => {
    const an = service.an('beispiel');
    http.expectOne(URL).flush({ funktionen: {} });

    expect(an()).toBeFalse();
  });

  it('fragt nur einmal, solange der Stand frisch ist', () => {
    service.an('beispiel');
    service.an('beispiel');
    http.expectOne(URL).flush({ funktionen: { beispiel: false } });

    service.an('beispiel');
    http.expectNone(URL);
  });

  it('fragt neu, wenn der Stand alt ist, und schaltet dann um', () => {
    const jetzt = Date.now();
    const uhr = spyOn(Date, 'now').and.returnValue(jetzt);
    const an = service.an('beispiel');
    http.expectOne(URL).flush({ funktionen: { beispiel: true } });

    uhr.and.returnValue(jetzt + FUNKTIONEN_NACHLADEN_MS + 1);
    service.an('beispiel');
    http.expectOne(URL).flush({ funktionen: { beispiel: false } });

    expect(an()).toBeFalse();
  });

  it('behaelt nach einem Fehler den letzten Stand', () => {
    const jetzt = Date.now();
    const uhr = spyOn(Date, 'now').and.returnValue(jetzt);
    const an = service.an('beispiel');
    http.expectOne(URL).flush({ funktionen: { beispiel: true } });

    uhr.and.returnValue(jetzt + FUNKTIONEN_NACHLADEN_MS + 1);
    service.an('beispiel');
    http.expectOne(URL).flush('weg', { status: 503, statusText: 'Service Unavailable' });

    expect(an()).toBeTrue();
  });
});

describe('FunktionenService.stand$ (Saal: Abrufe hinter Schaltern nur, wenn nicht sicher aus)', () => {
  const URL = `${environment.baseUrl}/api/v1/funktionen`;
  let service: FunktionenService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(FunktionenService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('wartet auf den Server und meldet an oder aus, mehrere Karten teilen eine Abfrage', () => {
    const gemeldet: (boolean | null)[] = [];
    service.stand$('a').subscribe((an) => gemeldet.push(an));
    service.stand$('b').subscribe((an) => gemeldet.push(an));
    // an() haengt sich an dieselbe Abfrage
    const signal = service.an('a');
    expect(gemeldet).toEqual([]);

    http.expectOne(URL).flush({ funktionen: { a: true, b: false } });

    expect(gemeldet).toEqual([true, false]);
    expect(signal()).toBeTrue();
  });

  it('antwortet aus dem frischen Stand ohne neue Abfrage', () => {
    service.stand$('a').subscribe();
    http.expectOne(URL).flush({ funktionen: { a: false } });

    let gemeldet: boolean | null | undefined;
    service.stand$('a').subscribe((an) => (gemeldet = an));
    http.expectNone(URL);
    expect(gemeldet).toBeFalse();
  });

  it('meldet unbekannt (null), wenn der Server nie geantwortet hat', () => {
    let gemeldet: boolean | null | undefined;
    service.stand$('a').subscribe((an) => (gemeldet = an));
    http.expectOne(URL).flush('weg', { status: 503, statusText: 'Service Unavailable' });
    expect(gemeldet).toBeNull();
  });

  it('meldet nach einem Fehler unbekannt, nicht den alten Stand (alt ist nicht sicher aus)', () => {
    const jetzt = Date.now();
    const uhr = spyOn(Date, 'now').and.returnValue(jetzt);
    service.stand$('a').subscribe();
    http.expectOne(URL).flush({ funktionen: { a: false } });

    uhr.and.returnValue(jetzt + FUNKTIONEN_NACHLADEN_MS + 1);
    let gemeldet: boolean | null | undefined;
    service.stand$('a').subscribe((an) => (gemeldet = an));
    http.expectOne(URL).flush('weg', { status: 503, statusText: 'Service Unavailable' });
    expect(gemeldet).toBeNull();
  });

  it('fragt nach einem Fehler eine Weile nicht neu, dann wieder', () => {
    const jetzt = Date.now();
    const uhr = spyOn(Date, 'now').and.returnValue(jetzt);
    service.stand$('a').subscribe();
    http.expectOne(URL).flush('weg', { status: 503, statusText: 'Service Unavailable' });

    let gemeldet: boolean | null | undefined;
    service.stand$('a').subscribe((an) => (gemeldet = an));
    http.expectNone(URL);
    expect(gemeldet).toBeNull();

    uhr.and.returnValue(jetzt + FUNKTIONEN_FEHLER_PAUSE_MS + 1);
    service.stand$('a').subscribe((an) => (gemeldet = an));
    http.expectOne(URL).flush({ funktionen: { a: true } });
    expect(gemeldet).toBeTrue();
  });

  it('meldet einen Namen, den der Server nicht kennt, als unbekannt', () => {
    let gemeldet: boolean | null | undefined;
    service.stand$('nicht_oeffentlich').subscribe((an) => (gemeldet = an));
    http.expectOne(URL).flush({ funktionen: { a: false } });
    expect(gemeldet).toBeNull();
  });

});

describe('FunktionenService.frisch (#757)', () => {
  const URL = `${environment.baseUrl}/api/v1/funktionen`;
  let service: FunktionenService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(FunktionenService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('fragt den Server und meldet den Stand', () => {
    let an: boolean | undefined;
    service.frisch('beispiel').subscribe((wert) => (an = wert));
    http.expectOne(URL).flush({ funktionen: { beispiel: true } });

    expect(an).toBeTrue();
    // Der Stand gilt danach auch fuer an(): kein zweiter Abruf
    expect(service.an('beispiel')()).toBeTrue();
    http.expectNone(URL);
  });

  it('gilt bei Fehler als aus', () => {
    let an: boolean | undefined;
    service.frisch('beispiel').subscribe((wert) => (an = wert));
    http.expectOne(URL).flush('weg', { status: 500, statusText: 'Server Error' });

    expect(an).toBeFalse();
  });

  it('gilt als aus, wenn der Server zu lange braucht', fakeAsync(() => {
    let an: boolean | undefined;
    service.frisch('beispiel').subscribe((wert) => (an = wert));
    const anfrage = http.expectOne(URL);

    tick(FUNKTIONEN_FRISCH_WARTEN_MS + 1);

    expect(an).toBeFalse();
    expect(anfrage.cancelled).toBeTrue();
  }));
});
