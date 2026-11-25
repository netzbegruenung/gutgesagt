import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';

import { environment } from '../../../environments/environment';
import { LoggingService } from '../../services/logging.service';
import { EinwilligungsBudgetService } from './einwilligungs-budget.service';

/** Ob der Schalter einwilligung_im_gewinn sicher aus ist (#788, Jura 25.11.). */
describe('EinwilligungsBudgetService.schalterAus', () => {
  const URL = `${environment.baseUrl}/api/v1/usage/users/me/einwilligungs-moment`;
  let service: EinwilligungsBudgetService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [{ provide: LoggingService, useValue: jasmine.createSpyObj('LoggingService', ['error']) }],
    });
    service = TestBed.inject(EinwilligungsBudgetService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('ist nach einem 404 sicher aus', () => {
    let antwort: unknown = 'offen';
    service.moment().subscribe((m) => (antwort = m));
    http.expectOne(URL).flush(null, { status: 404, statusText: 'Not Found' });

    expect(antwort).toBeNull();
    expect(service.schalterAus).toBeTrue();
  });

  it('ist bei einem Fehler nicht sicher aus', () => {
    service.moment().subscribe();
    http.expectOne(URL).flush(null, { status: 500, statusText: 'Server Error' });

    expect(service.schalterAus).toBeFalse();
  });

  it('ist mit Antwort nicht aus', () => {
    service.moment().subscribe();
    http.expectOne(URL).flush({ abgestimmt: false, beantwortet: 0, konto_seit: null });

    expect(service.schalterAus).toBeFalse();
  });
});
