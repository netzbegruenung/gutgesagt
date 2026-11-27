import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, UrlTree, convertToParamMap, provideRouter } from '@angular/router';

import { FunktionenService } from '../services/funktionen.service';
import { abkuerzungGuard } from './abkuerzung.guard';

describe('abkuerzungGuard (#757)', () => {
  let funktionen: jasmine.SpyObj<FunktionenService>;

  beforeEach(() => {
    funktionen = jasmine.createSpyObj<FunktionenService>('FunktionenService', ['an', 'frisch', 'stand$']);
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: FunktionenService, useValue: funktionen }],
    });
  });

  function ziel(name: string): string {
    const route = { paramMap: convertToParamMap({ name }) } as ActivatedRouteSnapshot;
    const ergebnis = TestBed.runInInjectionContext(() =>
      abkuerzungGuard(route, {} as RouterStateSnapshot),
    ) as UrlTree;
    return TestBed.inject(Router).serializeUrl(ergebnis);
  }

  it('fuehrt jede Abkuerzung ohne Schalter zu ihrem Ziel (Basisfunktion)', () => {
    expect(ziel('einwerfen')).toBe('/einwerfen');
    expect(ziel('suchen')).toBe('/search');
    expect(ziel('fangkorb')).toBe('/fangkorb');
    expect(funktionen.frisch).not.toHaveBeenCalled();
    expect(funktionen.an).not.toHaveBeenCalled();
  });

  it('fuehrt unbekannte Namen auf die Startseite', () => {
    expect(ziel('admin')).toBe('/search');
    expect(ziel('constructor')).toBe('/search');
    expect(ziel('__proto__')).toBe('/search');
  });
});
