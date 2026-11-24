import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, UrlTree, provideRouter } from '@angular/router';
import { firstValueFrom, Observable } from 'rxjs';
import { AuthGuard, MIT_KONTO_VORSCHAU } from './auth.guard';
import { AuthService } from './auth.service';
import { routes } from '../app.routes';

describe('AuthGuard', () => {
  let guard: AuthGuard;
  let http: HttpTestingController;
  let router: Router;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    guard = TestBed.inject(AuthGuard);
    http = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
  });

  afterEach(() => http.verify());

  function pruefen(data: Record<string, unknown>, url: string, angemeldet: boolean): Promise<boolean | UrlTree> {
    const ergebnis = firstValueFrom(
      guard.canActivate({ data } as unknown as ActivatedRouteSnapshot, { url } as RouterStateSnapshot) as Observable<boolean | UrlTree>,
    );
    const anfrage = http.expectOne((r) => r.url.endsWith('/api/check-session'));
    anfrage.flush({ isAuthenticated: angemeldet });
    return ergebnis;
  }

  it('lässt Angemeldete durch, auch an den Einstiegen ins Mitmachen', async () => {
    expect(await pruefen({ [MIT_KONTO_VORSCHAU]: true }, '/einwerfen', true)).toBeTrue();
  });

  it('zeigt Besuchern an den Einstiegen erst die Vorschau, mit dem Ziel', async () => {
    const baum = (await pruefen({ [MIT_KONTO_VORSCHAU]: true }, '/einwerfen?von=fangkorb', false)) as UrlTree;
    expect(router.serializeUrl(baum)).toBe('/mit-konto?ziel=%2Feinwerfen%3Fvon%3Dfangkorb');
  });

  it('führt Besucher auf anderen geschützten Seiten weiter direkt zur Anmeldung', async () => {
    const baum = (await pruefen({}, '/contributions', false)) as UrlTree;
    expect(router.serializeUrl(baum)).toBe('/login?returnUrl=%2Fcontributions');
  });

  it('wertet das Feld, nicht den Status: 200 mit isAuthenticated = false führt zur Anmeldung', async () => {
    const ergebnis = firstValueFrom(
      guard.canActivate({ data: {} } as unknown as ActivatedRouteSnapshot, { url: '/contributions' } as RouterStateSnapshot) as Observable<boolean | UrlTree>,
    );
    const anfrage = http.expectOne((r) => r.url.endsWith('/api/check-session'));
    expect(anfrage.request.method).toBe('GET');
    anfrage.flush({ isAuthenticated: false });
    expect(router.serializeUrl((await ergebnis) as UrlTree)).toBe('/login?returnUrl=%2Fcontributions');
  });

  it('wertet eine 401 (älteres BFF) und einen Netzfehler weiter als Besucher', async () => {
    const ergebnis = firstValueFrom(
      guard.canActivate({ data: {} } as unknown as ActivatedRouteSnapshot, { url: '/contributions' } as RouterStateSnapshot) as Observable<boolean | UrlTree>,
    );
    http.expectOne((r) => r.url.endsWith('/api/check-session')).flush(null, { status: 401, statusText: 'Unauthorized' });
    expect(router.serializeUrl((await ergebnis) as UrlTree)).toBe('/login?returnUrl=%2Fcontributions');

    const nochmal = firstValueFrom(
      guard.canActivate({ data: {} } as unknown as ActivatedRouteSnapshot, { url: '/contributions' } as RouterStateSnapshot) as Observable<boolean | UrlTree>,
    );
    http.expectOne((r) => r.url.endsWith('/api/check-session')).error(new ProgressEvent('Netzfehler'));
    expect(router.serializeUrl((await nochmal) as UrlTree)).toBe('/login?returnUrl=%2Fcontributions');
  });

  it('setzt eine beendete Sitzung in der Kopfzeile auf Besucher', async () => {
    const auth = TestBed.inject(AuthService);
    auth.setUserInfo({ isAuthenticated: true, userId: 'u1', userName: 'Jo', claims: null });
    await pruefen({}, '/contributions', false);
    expect(auth.getUserInfo()?.isAuthenticated).toBeFalse();
    expect(auth.getUserInfo()?.userId).toBeNull();
  });

  it('markiert genau Einwerfen, Beitragen und Fangkorb als Einstiege mit Vorschau', () => {
    const markiert = routes.filter((r) => r.data?.[MIT_KONTO_VORSCHAU]).map((r) => r.path);
    expect(markiert.sort()).toEqual(['contribute', 'einwerfen', 'fangkorb']);
  });
});
