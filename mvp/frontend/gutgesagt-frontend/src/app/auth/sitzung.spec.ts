import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';
import { meldetAnmeldung, sitzungPruefen, sitzungsstand } from './sitzung';

describe('Sitzung (Anmelde-Pruefungen ohne 401 für Besucher)', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function pruefen(): Promise<boolean> {
    return firstValueFrom(sitzungPruefen(TestBed.inject(HttpClient)));
  }

  it('meldet nur bei isAuthenticated === true eine Anmeldung', () => {
    expect(meldetAnmeldung({ isAuthenticated: true })).toBeTrue();
    expect(meldetAnmeldung({ isAuthenticated: false })).toBeFalse();
    expect(meldetAnmeldung({})).toBeFalse();
    expect(meldetAnmeldung(null)).toBeFalse();
    expect(meldetAnmeldung(undefined)).toBeFalse();
  });

  it('fragt /api/check-session und liest das Feld', async () => {
    const angemeldet = pruefen();
    http.expectOne(`${environment.baseUrl}/api/check-session`).flush({ isAuthenticated: true });
    expect(await angemeldet).toBeTrue();

    const besucher = pruefen();
    http.expectOne(`${environment.baseUrl}/api/check-session`).flush({ isAuthenticated: false });
    expect(await besucher).toBeFalse();
  });

  it('unterscheidet Besucher (200 false, 401) von unbekannt (Netz, 5xx)', async () => {
    const stand = () => firstValueFrom(sitzungsstand(TestBed.inject(HttpClient)));
    const url = `${environment.baseUrl}/api/check-session`;

    const besucher = stand();
    http.expectOne(url).flush({ isAuthenticated: false });
    expect(await besucher).toBe('besucher');

    const alt = stand();
    http.expectOne(url).flush(null, { status: 401, statusText: 'Unauthorized' });
    expect(await alt).toBe('besucher');

    const kaputt = stand();
    http.expectOne(url).flush('x', { status: 502, statusText: 'Bad Gateway' });
    expect(await kaputt).toBe('unbekannt');

    const netz = stand();
    http.expectOne(url).error(new ProgressEvent('Netzfehler'));
    expect(await netz).toBe('unbekannt');

    const angemeldet = stand();
    http.expectOne(url).flush({ isAuthenticated: true });
    expect(await angemeldet).toBe('angemeldet');
  });

  it('wertet Fehler (401 eines älteren BFF, 5xx) als Besucher', async () => {
    const alt = pruefen();
    http.expectOne(`${environment.baseUrl}/api/check-session`).flush(null, { status: 401, statusText: 'Unauthorized' });
    expect(await alt).toBeFalse();

    const kaputt = pruefen();
    http.expectOne(`${environment.baseUrl}/api/check-session`).flush('x', { status: 502, statusText: 'Bad Gateway' });
    expect(await kaputt).toBeFalse();
  });
});
