import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';

import { environment } from '../../../environments/environment';
import { FunktionenService } from '../../services/funktionen.service';
import { LoggingService } from '../../services/logging.service';
import { EinwilligungsMoment } from './einwilligungs-budget';
import { EinwilligungsBudgetService } from './einwilligungs-budget.service';

/** Ob der Schalter einwilligung_im_gewinn sicher aus ist (#788, Jura 25.11.). */
describe('EinwilligungsBudgetService.schalterAus', () => {
  const URL = `${environment.baseUrl}/api/v1/usage/users/me/einwilligungs-moment`;
  let service: EinwilligungsBudgetService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [
        { provide: LoggingService, useValue: jasmine.createSpyObj('LoggingService', ['error']) },
      ],
    });
    service = TestBed.inject(EinwilligungsBudgetService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('ist mit aktiv false vom Server sicher aus (200 statt 404, Saal)', () => {
    let antwort: unknown = 'offen';
    service.moment().subscribe((m) => (antwort = m));
    http.expectOne(URL).flush({ aktiv: false, abgestimmt: false, beantwortet: 0, konto_seit: null });

    expect(antwort).toBeNull();
    expect(service.schalterAus).toBeTrue();
  });

  it('ist nach einem 404 eines älteren Backends sicher aus', () => {
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

/**
 * Schalter-Umbau 27.11.: Einwilligung im passenden Moment ist Basisfunktion. Die Grenzen
 * (höchstens eine neue Frage je Besuch, vier im ersten Monat) gelten ohne Schalter: Der Dienst
 * fragt keinen FunktionenService, nur den Moment vom Server.
 */
describe('EinwilligungsBudgetService ohne Schalter (Schutzgrenzen)', () => {
  const URL = `${environment.baseUrl}/api/v1/usage/users/me/einwilligungs-moment`;
  let service: EinwilligungsBudgetService;
  let http: HttpTestingController;
  let funktionen: jasmine.SpyObj<FunktionenService>;

  beforeEach(() => {
    funktionen = jasmine.createSpyObj<FunktionenService>('FunktionenService', ['an', 'frisch', 'stand$']);
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [
        { provide: LoggingService, useValue: jasmine.createSpyObj('LoggingService', ['error']) },
        { provide: FunktionenService, useValue: funktionen },
      ],
    });
    service = TestBed.inject(EinwilligungsBudgetService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function moment(beantwortet: number): EinwilligungsMoment {
    let antwort: EinwilligungsMoment | null = null;
    service.moment().subscribe((m) => (antwort = m));
    // Wie der Server seit dem Umbau: immer angeboten, ohne aktiv false
    http.expectOne(URL).flush({ abgestimmt: true, beantwortet, konto_seit: new Date().toISOString() });
    return antwort!;
  }

  it('höchstens eine neue Frage je Besuch', () => {
    const m = moment(0);
    expect(service.darf('sichtbarkeit', m)).toBeTrue();

    service.gezeigt('sichtbarkeit');

    expect(service.darf('punkte', m)).toBeFalse();
    expect(funktionen.an).not.toHaveBeenCalled();
    expect(funktionen.frisch).not.toHaveBeenCalled();
    expect(funktionen.stand$).not.toHaveBeenCalled();
  });

  it('höchstens vier Fragen im ersten Monat', () => {
    expect(service.darf('sichtbarkeit', moment(3))).toBeTrue();
    expect(service.darf('sichtbarkeit', moment(4))).toBeFalse();
  });
});
