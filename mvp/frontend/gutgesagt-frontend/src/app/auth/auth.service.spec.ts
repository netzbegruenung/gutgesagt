import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';
import { environment } from '../../environments/environment';
import { MEILENSTEINE_GESEHEN_SCHLUESSEL } from '../meine-beitraege/meilenstein-merker';
import { KOMMENTAR_ENTWURF_SCHLUESSEL } from '../beitragsformular/kommentar-entwurf';

describe('AuthService', () => {
  let service: AuthService;
  let httpMock: HttpTestingController;
  let router: jasmine.SpyObj<Router>;

  const logoutUrl = `${environment.baseUrl}/api/auth/logout`;

  beforeEach(() => {
    const routerSpy = jasmine.createSpyObj('Router', ['navigate']);

    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [
        AuthService,
        { provide: Router, useValue: routerSpy }
      ]
    });

    service = TestBed.inject(AuthService);
    httpMock = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router) as jasmine.SpyObj<Router>;
  });

  afterEach(() => {
    httpMock.verify();
  });

  describe('logout', () => {
    it('entfernt den Kommentar-Entwurf des Tabs (E1)', () => {
      spyOn(console, 'error');
      sessionStorage.setItem(KOMMENTAR_ENTWURF_SCHLUESSEL, '{}');

      service.logout();
      httpMock.expectOne(logoutUrl).flush(null, { status: 500, statusText: 'Server Error' });

      expect(sessionStorage.getItem(KOMMENTAR_ENTWURF_SCHLUESSEL)).toBeNull();
    });

    it('entfernt den Merker der angezeigten Meilensteine des Kontos (#351)', () => {
      spyOn(console, 'error');
      service.setUserInfo({ isAuthenticated: true, userId: 'kim-1', userName: 'Kim', claims: null });
      localStorage.setItem(MEILENSTEINE_GESEHEN_SCHLUESSEL, '["einwurf-1"]');

      service.logout();
      httpMock.expectOne(logoutUrl).flush(null, { status: 500, statusText: 'Server Error' });

      expect(localStorage.getItem(MEILENSTEINE_GESEHEN_SCHLUESSEL)).toBeNull();
    });

    it('navigiert zur Startseite, wenn der Logout-Request fehlschlaegt', () => {
      spyOn(console, 'error');

      service.logout();

      httpMock.expectOne(logoutUrl).flush(
        { message: 'boom' },
        { status: 500, statusText: 'Server Error' }
      );

      expect(router.navigate).toHaveBeenCalledWith(['/']);
    });

    it('meldet den Nutzer im Fehlerfall auch lokal ab', () => {
      spyOn(console, 'error');

      service.logout();
      httpMock.expectOne(logoutUrl).flush(null, { status: 500, statusText: 'Server Error' });

      expect(service.getUserInfo()?.isAuthenticated).toBeFalse();
      expect(service.getUserInfo()?.userId).toBeNull();
    });

    it('fordert den Logout am BFF mit Cookies an', () => {
      service.logout();

      const req = httpMock.expectOne(logoutUrl);
      expect(req.request.method).toBe('POST');
      expect(req.request.withCredentials).toBeTrue();

      // Erfolgsfall nicht durchlaufen lassen: er setzt window.location.href und
      // wuerde den Karma-Runner navigieren.
      req.flush(null, { status: 500, statusText: 'Server Error' });
    });
  });

  describe('fetchUserInfo', () => {
    const userInfoUrl = `${environment.baseUrl}/api/user-info`;

    it('setzt Besucher aus 200 mit isAuthenticated = false, ohne Fehler', () => {
      let geliefert: unknown;
      let fehler = false;
      service.fetchUserInfo().subscribe({ next: (u) => (geliefert = u), error: () => (fehler = true) });

      httpMock.expectOne(userInfoUrl).flush({
        isAuthenticated: false, userId: null, userName: null, isAdmin: false, claims: null,
      });

      expect(fehler).toBeFalse();
      const besucher = { isAuthenticated: false, userId: null, userName: null, claims: null };
      expect(geliefert).toEqual(besucher);
      expect(service.getUserInfo()).toEqual(besucher);
    });

    it('nimmt bei isAuthenticated = true die Person wie geliefert', () => {
      const person = { isAuthenticated: true, userId: 'u1', userName: 'Jo', isAdmin: true, claims: { sub: 'u1' } };
      service.fetchUserInfo().subscribe();

      httpMock.expectOne(userInfoUrl).flush(person);

      expect(service.getUserInfo()).toEqual(person);
    });

    it('gibt einer Antwort ohne isAuthenticated keine Rechte, auch wenn Felder darin stehen', () => {
      service.fetchUserInfo().subscribe();

      httpMock.expectOne(userInfoUrl).flush({ userId: 'u1', isAdmin: true });

      expect(service.getUserInfo()?.isAuthenticated).toBeFalse();
      expect(service.getUserInfo()?.isAdmin).toBeUndefined();
      expect(service.getUserInfo()?.userId).toBeNull();
    });
  });
});
