import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';

import { environment } from '../../../environments/environment';
import { LoggingService } from '../../services/logging.service';
import { PunkteEinwilligungService, PunkteEinwilligungStand } from './punkte-einwilligung.service';

/**
 * Die Antwort auf „Punkte und Meilensteine“ (#351, #788): Ein Nein ist wie ein Ja ein
 * Nachweis auf dem Server mit der Kennung des Wortlauts, nicht im Browser.
 */
describe('PunkteEinwilligungService', () => {
  const URL = `${environment.baseUrl}/api/v1/usage/users/me/punkte-einwilligung`;
  const NIE_GEANTWORTET: PunkteEinwilligungStand = {
    eingewilligt: false,
    wortlaut: null,
    aktueller_wortlaut: { kennung: '2026-11-13', text: 'Freiwillig: …' },
  };
  let service: PunkteEinwilligungService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [{ provide: LoggingService, useValue: jasmine.createSpyObj('LoggingService', ['error']) }],
    });
    service = TestBed.inject(PunkteEinwilligungService);
    http = TestBed.inject(HttpTestingController);
    service.laden().subscribe();
    http.expectOne(URL).flush(NIE_GEANTWORTET);
  });

  afterEach(() => http.verify());

  it('ein Nein geht mit der Kennung des Wortlauts an den Server, wie ein Ja', () => {
    const schreiben = spyOn(Storage.prototype, 'setItem').and.callThrough();
    let ok: boolean | undefined;
    service.setzen(false).subscribe((r) => (ok = r));

    const anfrage = http.expectOne(URL);
    expect(anfrage.request.method).toBe('PUT');
    expect(anfrage.request.body).toEqual({ eingewilligt: false, wortlaut: '2026-11-13' });
    anfrage.flush(null, { status: 204, statusText: 'No Content' });

    expect(ok).toBeTrue();
    // Nichts in localStorage oder sessionStorage: Das Nein steht nur auf dem Server.
    expect(schreiben).not.toHaveBeenCalled();
  });

  it('nach dem Nein ist der Stand beantwortet: eine Frage gilt dann nicht mehr als offen', () => {
    let stand: PunkteEinwilligungStand | null | undefined;
    service.stand$.subscribe((s) => (stand = s));

    service.setzen(false).subscribe();
    http.expectOne(URL).flush(null, { status: 204, statusText: 'No Content' });

    expect(stand?.eingewilligt).toBeFalse();
    expect(stand?.wortlaut).toBe('2026-11-13');
  });

  it('ein Ja sendet dieselbe Kennung', () => {
    service.setzen(true).subscribe();

    expect(http.expectOne(URL).request.body).toEqual({ eingewilligt: true, wortlaut: '2026-11-13' });
  });
});
