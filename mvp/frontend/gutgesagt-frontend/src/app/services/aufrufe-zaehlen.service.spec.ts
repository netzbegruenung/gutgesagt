import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router, provideRouter } from '@angular/router';
import { Component } from '@angular/core';
import { AufrufeZaehlenService, seite } from './aufrufe-zaehlen.service';
import { STILLE_ABFRAGE } from '../shared/selbst-nachladen';
import { environment } from '../../environments/environment';

@Component({ standalone: true, template: '' })
class LeerComponent {}

const URL = `${environment.baseUrl}/api/v1/aufrufe/zaehlen`;

describe('AufrufeZaehlenService (#761)', () => {
  let http: HttpTestingController;
  let router: Router;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([
          { path: 'search', component: LeerComponent },
          { path: 'hilfe', component: LeerComponent },
          { path: 'admin/dashboard', component: LeerComponent },
        ]),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
    TestBed.inject(AufrufeZaehlenService).starten();
  });

  afterEach(() => http.verify());

  it('meldet je Seitenwechsel eine leere, stille Anfrage ohne Pfad', async () => {
    await router.navigateByUrl('/search');
    const anfrage = http.expectOne(URL);
    expect(anfrage.request.method).toBe('POST');
    expect(anfrage.request.body).toBeNull();
    expect(anfrage.request.context.get(STILLE_ABFRAGE)).toBeTrue();
    anfrage.flush(null, { status: 204, statusText: 'No Content' });

    await router.navigateByUrl('/hilfe');
    http.expectOne(URL).flush(null, { status: 204, statusText: 'No Content' });
  });

  it('zählt Abfrage und Anker auf derselben Seite nicht neu, Admin-Seiten gar nicht', async () => {
    await router.navigateByUrl('/search');
    http.expectOne(URL).flush(null, { status: 204, statusText: 'No Content' });
    await router.navigateByUrl('/search?q=wolf#treffer');
    await router.navigateByUrl('/admin/dashboard');
    http.expectNone(URL);
  });

  it('zählt dieselbe Seite nach einem Abstecher in den Admin-Bereich wieder', async () => {
    await router.navigateByUrl('/search');
    http.expectOne(URL).flush(null, { status: 204, statusText: 'No Content' });
    await router.navigateByUrl('/admin/dashboard');
    await router.navigateByUrl('/search');
    http.expectOne(URL).flush(null, { status: 204, statusText: 'No Content' });
  });

  it('hört nach 404 (Schalter aus) für diesen Start auf', async () => {
    await router.navigateByUrl('/search');
    http.expectOne(URL).flush(null, { status: 404, statusText: 'Not Found' });
    await router.navigateByUrl('/hilfe');
    http.expectNone(URL);
  });

  it('meldet nach einem anderen Fehler weiter', async () => {
    await router.navigateByUrl('/search');
    http.expectOne(URL).flush(null, { status: 500, statusText: 'Fehler' });
    await router.navigateByUrl('/hilfe');
    http.expectOne(URL).flush(null, { status: 204, statusText: 'No Content' });
  });

  it('seite() schneidet Abfrage und Anker ab', () => {
    expect(seite('/search?q=x#a')).toBe('/search');
    expect(seite('/beitrag/1')).toBe('/beitrag/1');
  });
});
