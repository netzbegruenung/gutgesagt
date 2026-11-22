import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, UrlTree, convertToParamMap, provideRouter } from '@angular/router';
import { Observable, firstValueFrom, of } from 'rxjs';

import { FunktionenService } from '../services/funktionen.service';
import { ABKUERZUNGEN_SCHALTER, abkuerzungGuard } from './abkuerzung.guard';

describe('abkuerzungGuard (#757)', () => {
  let frisch: jasmine.Spy;

  beforeEach(() => {
    frisch = jasmine.createSpy('frisch');
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: FunktionenService, useValue: { frisch } }],
    });
  });

  async function ziel(name: string): Promise<string> {
    const route = { paramMap: convertToParamMap({ name }) } as ActivatedRouteSnapshot;
    const ergebnis = TestBed.runInInjectionContext(() =>
      abkuerzungGuard(route, {} as RouterStateSnapshot),
    ) as Observable<UrlTree>;
    return TestBed.inject(Router).serializeUrl(await firstValueFrom(ergebnis));
  }

  describe('Schalter an', () => {
    beforeEach(() => frisch.and.returnValue(of(true)));

    it('fuehrt jede Abkuerzung zu ihrem Ziel', async () => {
      expect(await ziel('einwerfen')).toBe('/einwerfen');
      expect(await ziel('suchen')).toBe('/search');
      expect(await ziel('fangkorb')).toBe('/fangkorb');
      expect(frisch).toHaveBeenCalledWith(ABKUERZUNGEN_SCHALTER);
    });

    it('fuehrt unbekannte Namen auf die Startseite', async () => {
      expect(await ziel('admin')).toBe('/search');
    });
  });

  describe('Schalter aus', () => {
    beforeEach(() => frisch.and.returnValue(of(false)));

    it('oeffnet jede Abkuerzung als normale Startseite', async () => {
      expect(await ziel('einwerfen')).toBe('/search');
      expect(await ziel('fangkorb')).toBe('/search');
    });
  });
});
