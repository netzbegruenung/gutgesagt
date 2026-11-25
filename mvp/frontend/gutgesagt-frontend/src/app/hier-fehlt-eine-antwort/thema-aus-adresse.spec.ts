import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

import { environment } from '../../environments/environment';
import { HierFehltEineAntwortComponent } from './hier-fehlt-eine-antwort.component';

const LISTE_URL = `${environment.baseUrl}/api/v1/statement/unbeantwortet`;
const THEMEN_URL = `${environment.baseUrl}/api/v1/statement/themen`;
const THEMEN = [
  { schluessel: 'klima', name: 'Klima' },
  { schluessel: 'verkehr', name: 'Verkehr' },
];

/** ?thema= aus der Gartenansicht (#783): die Liste steht gleich auf dem Thema. */
describe('Hier fehlt eine Antwort mit ?thema=', () => {
  let http: HttpTestingController;

  function starten(thema: string) {
    TestBed.configureTestingModule({
      imports: [HierFehltEineAntwortComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        provideNoopAnimations(),
        { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: convertToParamMap({ thema }) } } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(HierFehltEineAntwortComponent);
    fixture.detectChanges();
    return fixture;
  }

  afterEach(() => http.verify());

  it('filtert auf ein bekanntes Thema', () => {
    const fixture = starten('verkehr');
    http.expectOne(THEMEN_URL).flush({ themen: THEMEN });
    // Der erste Abruf ohne Filter wird abgebrochen, es gilt der mit Thema
    const ohne = http.expectOne(LISTE_URL);
    expect(ohne.cancelled).toBeTrue();
    http.expectOne(`${LISTE_URL}?thema=verkehr`).flush({ aussagen: [] });
    expect(fixture.componentInstance.aktivesThema).toBe('verkehr');
  });

  it('übergeht ein unbekanntes Thema', () => {
    const fixture = starten('gibt-es-nicht');
    http.expectOne(THEMEN_URL).flush({ themen: THEMEN });
    http.expectOne(LISTE_URL).flush({ aussagen: [] });
    expect(fixture.componentInstance.aktivesThema).toBeNull();
  });
});
