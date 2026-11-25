import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, UrlTree, provideRouter } from '@angular/router';
import { Observable, firstValueFrom, of } from 'rxjs';

import { FunktionenService } from '../services/funktionen.service';
import { KONTER_PROBE_SCHALTER } from './konter-probe';
import { konterProbeGuard } from './konter-probe.guard';

describe('konterProbeGuard (#786)', () => {
  let frisch: jasmine.Spy;

  beforeEach(() => {
    frisch = jasmine.createSpy('frisch');
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: FunktionenService, useValue: { frisch } }],
    });
  });

  function pruefen(): Promise<boolean | UrlTree> {
    const ergebnis = TestBed.runInInjectionContext(() =>
      konterProbeGuard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot),
    ) as Observable<boolean | UrlTree>;
    return firstValueFrom(ergebnis);
  }

  it('laesst bei eingeschaltetem Schalter durch', async () => {
    frisch.and.returnValue(of(true));
    expect(await pruefen()).toBeTrue();
    expect(frisch).toHaveBeenCalledWith(KONTER_PROBE_SCHALTER);
  });

  it('fuehrt bei ausgeschaltetem Schalter auf die Startseite', async () => {
    frisch.and.returnValue(of(false));
    const ziel = await pruefen();
    expect(ziel instanceof UrlTree).toBeTrue();
    expect(TestBed.inject(Router).serializeUrl(ziel as UrlTree)).toBe('/search');
  });
});
