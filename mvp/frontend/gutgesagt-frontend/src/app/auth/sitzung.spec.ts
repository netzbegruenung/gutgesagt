import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';
import { meldetAnmeldung, sitzungPruefen } from './sitzung';

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

  it('wertet Fehler (401 eines älteren BFF, 5xx) als Besucher', async () => {
    const alt = pruefen();
    http.expectOne(`${environment.baseUrl}/api/check-session`).flush(null, { status: 401, statusText: 'Unauthorized' });
    expect(await alt).toBeFalse();

    const kaputt = pruefen();
    http.expectOne(`${environment.baseUrl}/api/check-session`).flush('x', { status: 502, statusText: 'Bad Gateway' });
    expect(await kaputt).toBeFalse();
  });
});
