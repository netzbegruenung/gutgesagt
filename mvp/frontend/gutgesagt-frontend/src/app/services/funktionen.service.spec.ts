import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { FUNKTIONEN_NACHLADEN_MS, FunktionenService } from './funktionen.service';

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
