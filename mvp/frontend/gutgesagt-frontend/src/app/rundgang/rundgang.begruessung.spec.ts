import { DestroyRef, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { NavigationEnd, Router } from '@angular/router';
import { BehaviorSubject, Subject } from 'rxjs';
import { AuthService, UserInfo } from '../auth/auth.service';
import { Art9EinwilligungService } from '../services/art9-einwilligung.service';
import { FunktionenService } from '../services/funktionen.service';
import { KampagnenwortService } from '../shared/kampagnenwort.service';
import { RundgangService } from './rundgang.service';
import { K_BEGRUESSUNG, MITMACHEN_ANGEBOT, WILLKOMMEN, WILLKOMMEN_ANGEMELDET, mitBegruessung } from './rundgang-daten';
import { MITMACHEN_SCHLUESSEL, WILLKOMMEN_SCHLUESSEL } from './rundgang-merker';

/**
 * Begrüßung nach dem Kampagnenwort (?k=, Schalter `k_begruessung`): Mit Schalter an ersetzt sie
 * Titel und Satz des Willkommens, mit Schalter aus ist sie unsichtbar. Nur Anzeige: Gespeichert
 * wird nichts außer dem Vermerk, den das Willkommen ohnehin hat.
 */
describe('RundgangService: Begrüßung nach ?k=', () => {
  let events: Subject<unknown>;
  let router: jasmine.SpyObj<Router> & { url: string };
  let userInfo: BehaviorSubject<UserInfo | null>;
  let schalter: ReturnType<typeof signal<boolean>>;
  let gefragt: string[];

  const besucher: UserInfo = { isAuthenticated: false, userId: null, userName: null, claims: null };
  const angemeldet: UserInfo = { isAuthenticated: true, userId: 'u1', userName: 'Test', claims: null };

  function aufsetzen(wort: string | null, info: UserInfo = besucher, geklaert: string | null = null): RundgangService {
    localStorage.removeItem(WILLKOMMEN_SCHLUESSEL);
    localStorage.removeItem(MITMACHEN_SCHLUESSEL);
    events = new Subject();
    userInfo = new BehaviorSubject<UserInfo | null>(info);
    schalter = signal(false);
    gefragt = [];
    router = Object.assign(jasmine.createSpyObj<Router>('Router', ['navigate', 'navigateByUrl']), {
      url: '/search',
      events,
    });
    TestBed.configureTestingModule({
      providers: [
        { provide: Router, useValue: router },
        { provide: AuthService, useValue: { userInfo$: userInfo, getUserInfo: () => userInfo.value } },
        {
          provide: Art9EinwilligungService,
          useValue: { geklaert$: new BehaviorSubject(geklaert), geklaert: () => geklaert },
        },
        { provide: KampagnenwortService, useValue: { wort } },
        {
          provide: FunktionenService,
          useValue: {
            an: (name: string) => {
              gefragt.push(name);
              return schalter.asReadonly();
            },
          },
        },
      ],
    });
    const service = TestBed.inject(RundgangService);
    service.beobachten({ onDestroy: () => undefined } as unknown as DestroyRef);
    return service;
  }

  function navigiert(url: string): void {
    router.url = url;
    events.next(new NavigationEnd(1, url, url));
  }

  afterEach(() => {
    localStorage.removeItem(WILLKOMMEN_SCHLUESSEL);
    localStorage.removeItem(MITMACHEN_SCHLUESSEL);
  });

  it('zeigt mit Schalter an über den Sticker die Begrüßung statt der allgemeinen Zeile', () => {
    const service = aufsetzen('sticker');
    schalter.set(true);
    navigiert('/search');

    const band = service.band()!;
    expect(band.titel).toBe('Vom Sticker?');
    expect(band.satz).toBe('Probier’s direkt aus – das Beispiel steht schon drin.');
    expect(band.begruessung).toBeTrue();
    // Rundgang, Vermerk und Ausblenden wie beim Willkommen
    expect(band.rundgang).toBe(WILLKOMMEN.rundgang);
    expect(band.schluessel).toBe(WILLKOMMEN.schluessel);
    expect(band.ja).toBe(WILLKOMMEN.ja);
  });

  it('hat für die BDK eine eigene Fassung', () => {
    const service = aufsetzen('bdk');
    schalter.set(true);
    navigiert('/search');

    expect(service.band()!.titel).toBe('Von der BDK?');
    expect(service.band()!.satz).toBe(K_BEGRUESSUNG['bdk'].satz);
  });

  it('ist mit Schalter aus unsichtbar: das allgemeine Willkommen', () => {
    const service = aufsetzen('sticker');
    navigiert('/search');

    expect(service.band()).toBe(WILLKOMMEN);
  });

  it('kommt beim Umschalten ohne Neuladen an', () => {
    const service = aufsetzen('sticker');
    navigiert('/search');
    expect(service.band()).toBe(WILLKOMMEN);

    schalter.set(true);
    expect(service.band()!.titel).toBe('Vom Sticker?');

    schalter.set(false);
    expect(service.band()).toBe(WILLKOMMEN);
  });

  it('fragt den Schalter nur bei einem Wort mit Begrüßung', () => {
    aufsetzen('g1');
    expect(gefragt).toEqual([]);
    TestBed.resetTestingModule();
    aufsetzen(null);
    expect(gefragt).toEqual([]);
    TestBed.resetTestingModule();
    aufsetzen('bdk');
    expect(gefragt).toEqual(['k_begruessung']);
  });

  it('ändert bei anderen Wörtern nichts', () => {
    const service = aufsetzen('g1');
    schalter.set(true);
    navigiert('/search');

    expect(service.band()).toBe(WILLKOMMEN);
  });

  it('begrüßt auch Angemeldete statt „In Sekunden zur Antwort“', () => {
    const service = aufsetzen('sticker', angemeldet, 'u1');
    schalter.set(true);
    navigiert('/search');

    expect(service.band()!.titel).toBe('Vom Sticker?');
    expect(service.band()!.satz).not.toBe(WILLKOMMEN_ANGEMELDET.satz);
  });

  it('speichert nichts zusätzlich: nach „Ausblenden“ nur der Vermerk des Willkommens', () => {
    const service = aufsetzen('sticker');
    schalter.set(true);
    navigiert('/search');
    const vorher = Object.keys(localStorage);

    service.bandBeantworten(false);

    expect(service.band()).toBeNull();
    const neu = Object.keys(localStorage).filter((k) => !vorher.includes(k));
    expect(neu).toEqual([WILLKOMMEN_SCHLUESSEL]);
  });

  it('lässt andere Angebote unverändert', () => {
    expect(mitBegruessung(MITMACHEN_ANGEBOT, 'sticker')).toBe(MITMACHEN_ANGEBOT);
    expect(mitBegruessung(WILLKOMMEN, null)).toBe(WILLKOMMEN);
  });
});
