import { TestBed, ComponentFixture } from '@angular/core/testing';
import { BreakpointObserver } from '@angular/cdk/layout';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideAnimations } from '@angular/platform-browser/animations';
import { ActivatedRoute, Router } from '@angular/router';
import { By } from '@angular/platform-browser';
import { MatDialog } from '@angular/material/dialog';
import { BehaviorSubject, of, throwError } from 'rxjs';
import { AppComponent } from './app.component';
import { AuthService, UserInfo } from './auth/auth.service';
import { NavigationService } from './services/navigation.service';
import { FeedbackDialogComponent } from './shared/feedback/feedback-dialog.component';
import {
  ALTE_PROFILBILD_SCHLUESSEL,
  ANONYMES_PROFILBILD,
  PROFILBILD_SCHLUESSEL,
  ProfilbildService,
} from './services/profilbild.service';
import { ProfilbildDialogComponent } from './shared/profilbild/profilbild-dialog.component';
import { RUECKKEHRZIEL_SCHLUESSEL } from './login/rueckkehrziel';
import { RundgangService } from './rundgang/rundgang.service';
import { MatTooltip } from '@angular/material/tooltip';
import { ZuTunService } from './services/zu-tun.service';
import { ModerationService } from './services/moderation.service';

/**
 * Der Desktop-Kopf: ein Weg zum Anmelden (#343), und seit der Navigation Variante 3
 * (22.11.2026) die Ziele sichtbar mit Icon und Text. Das Profilbild oeffnet nur das
 * Konto, Hilfe, Feedback und Co. stehen unter "Mehr".
 */
describe('AppComponent - Desktop-Kopf', () => {
  let fixture: ComponentFixture<AppComponent>;
  let router: jasmine.SpyObj<Router>;
  let navigation: jasmine.SpyObj<NavigationService>;
  let dialog: jasmine.SpyObj<MatDialog>;
  let userInfo$: BehaviorSubject<UserInfo | null>;

  const ANGEMELDET: UserInfo = {
    isAuthenticated: true,
    userId: 'user-001',
    userName: 'Test User',
    claims: {},
  };
  const BESUCHER: UserInfo = { isAuthenticated: false, userId: null, userName: null, claims: null };

  function starten(person: UserInfo) {
    const auth = TestBed.inject(AuthService) as jasmine.SpyObj<AuthService>;
    auth.fetchUserInfo.and.returnValue(
      person.isAuthenticated ? of(person) : throwError(() => new Error('401'))
    );
    auth.setUserInfo.and.callFake((u: UserInfo) => userInfo$.next(u));
    userInfo$.next(person);
    fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
  }

  function kopf(): HTMLElement {
    return fixture.nativeElement.querySelector('.header') as HTMLElement;
  }

  function konto(): HTMLElement {
    return kopf().querySelector('[data-testid="konto-knopf"]') as HTMLElement;
  }

  beforeEach(async () => {
    userInfo$ = new BehaviorSubject<UserInfo | null>(null);
    router = jasmine.createSpyObj('Router', ['navigate', 'navigateByUrl', 'createUrlTree', 'serializeUrl'], {
      events: of({}),
      url: '/search',
    });
    navigation = jasmine.createSpyObj('NavigationService', [
      'navigateToMeineBeitraege',
      'navigateToContribute',
      'navigateToEinwerfen',
      'navigateToFangkorb',
      'navigateHome',
      'navigiereZu',
      'goBack',
    ]);
    dialog = jasmine.createSpyObj('MatDialog', ['open']);

    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideAnimations(),
        {
          provide: AuthService,
          useValue: jasmine.createSpyObj('AuthService', ['fetchUserInfo', 'setUserInfo', 'logout', 'getCurrentUserId'], {
            userInfo$: userInfo$.asObservable(),
          }),
        },
        { provide: NavigationService, useValue: navigation },
        { provide: Router, useValue: router },
        { provide: ActivatedRoute, useValue: { params: of({}), queryParams: of({}), snapshot: {} } },
        // Desktop, unabhaengig von der Fenstergroesse des Testbrowsers.
        { provide: BreakpointObserver, useValue: { observe: () => of({ matches: false, breakpoints: {} }) } },
      ],
    })
      // MatDialog sitzt im Standalone-Import von AppComponent; der Override ersetzt ihn dort.
      .overrideProvider(MatDialog, { useValue: dialog })
      .compileComponents();
  });

  /** Sichtbarer Text ohne die Namen der Material-Icons, Leerraum zusammengezogen. */
  function text(e: Element): string {
    const kopie = e.cloneNode(true) as HTMLElement;
    kopie.querySelectorAll('mat-icon, .visually-hidden').forEach((i) => i.remove());
    return kopie.textContent!.replace(/\s+/g, ' ').trim();
  }

  /** Einträge eines offenen Menüs (Overlay). */
  function menueTexte(selektor: string): string[] {
    return Array.from(document.querySelectorAll(`${selektor} [mat-menu-item]`)).map(text);
  }

  async function klickUndWarten(element: HTMLElement): Promise<void> {
    element.click();
    fixture.detectChanges();
    await fixture.whenStable();
  }

  function mehrKnopf(): HTMLElement {
    return kopf().querySelector('app-hauptnavigation .mehr-knopf') as HTMLElement;
  }

  /** Sichtbarer Text der Navigation im Kopf, in der Reihenfolge der Anzeige. */
  function navigationTexte(): string[] {
    return Array.from(
      kopf().querySelectorAll('app-hauptnavigation .ziel-text, app-hauptnavigation .dark-green-button'),
    ).map(text);
  }

  describe('Besucher', () => {
    beforeEach(() => starten(BESUCHER));

    it('hat genau einen Weg zum Anmelden: den Knopf, und kein Profilbild (#599)', () => {
      const anmelden = Array.from(kopf().querySelectorAll('button, [role="button"]')).filter(
        (e) => e.textContent?.includes('Anmelden') || e.getAttribute('aria-label') === 'Anmelden'
      );
      expect(anmelden.length).toBe(1);
      expect(anmelden[0].tagName).toBe('BUTTON');

      expect(konto()).toBeNull();
      expect(kopf().textContent).not.toContain('Nicht angemeldet');
    });

    it('meldet nur ueber einen Klick im Kopf an, egal wie das Element beschriftet ist', () => {
      const komponente = fixture.componentInstance;
      const anmelden = spyOn(komponente, 'login');

      const klickbar = kopf().querySelectorAll('button, a, [role="button"], [tabindex], img');
      klickbar.forEach((e) => (e as HTMLElement).click());

      expect(anmelden.calls.count()).toBe(1);
    });

    // #620: Das Logo ist der Weg zur Startseite, "Start" im Kopf entfaellt
    it('fuehrt mit dem Logo "Startseite" zur Startseite; die Ueberschrift nennt nur die Seite', () => {
      const link = kopf().querySelector('a.logo-link') as HTMLAnchorElement;
      expect(link.getAttribute('aria-label')).toBe('Startseite');
      expect(link.querySelector('img')!.getAttribute('alt')).toBe('');
      expect(kopf().querySelector('h1 a')).toBeNull();
      expect(kopf().querySelector('[data-testid="start-knopf"]')).toBeNull();

      link.click();

      expect(navigation.navigateHome).toHaveBeenCalledTimes(1);
    });

    // Navigation Variante 3 (22.11.2026): reduziert, aber dieselbe Ordnung wie angemeldet
    it('zeigt Suchen, Hilfe, Anmelden und Mehr, ohne die Ziele fuer Angemeldete', () => {
      expect(navigationTexte()).toEqual(['Suchen', 'Hilfe', 'Anmelden', 'Mehr']);
    });

    it('oeffnet die Hilfe direkt und Feedback unter "Mehr"', async () => {
      (kopf().querySelector('app-hauptnavigation .hilfe-knopf') as HTMLElement).click();
      expect(dialog.open).toHaveBeenCalledTimes(1);

      await klickUndWarten(mehrKnopf());
      expect(menueTexte('.mehr-menue')).toEqual([
        jasmine.stringContaining('Rundgang Antwort finden'),
        jasmine.stringContaining('Rundgang Selbst beitragen'),
        'Feedback',
        jasmine.stringMatching(/Dunkel anzeigen|Hell anzeigen/),
      ]);
      (Array.from(document.querySelectorAll('.mehr-menue .mehr-eintrag')) as HTMLElement[])
        .find((e) => e.textContent!.includes('Feedback'))!
        .click();

      expect(dialog.open).toHaveBeenCalledWith(FeedbackDialogComponent, jasmine.anything());
    });
  });

  describe('auf der Anmeldeseite (#645)', () => {
    function aufSeite(url: string) {
      (Object.getOwnPropertyDescriptor(router, 'url')!.get as jasmine.Spy).and.returnValue(url);
      starten(BESUCHER);
    }

    function anmeldenKnopf(): Element | undefined {
      return Array.from(kopf().querySelectorAll('button')).find((e) => e.textContent?.trim() === 'Anmelden');
    }

    it('blendet den Kopfknopf "Anmelden" auf /login und /login/managed aus', () => {
      aufSeite('/login/managed?returnUrl=%2Fcontribute');
      expect(anmeldenKnopf()).toBeUndefined();
      expect(kopf().querySelector('h1')!.textContent!.trim()).toBe('Anmelden');
    });

    it('zeigt ihn auf anderen Seiten weiter', () => {
      aufSeite('/hier-fehlt-eine-antwort');
      expect(anmeldenKnopf()).toBeDefined();
    });
  });

  describe('Angemeldet', () => {
    beforeEach(() => starten(ANGEMELDET));

    function kontoEintrag(text: string): HTMLElement {
      return (Array.from(document.querySelectorAll('.konto-menue .profilmenue-eintrag')) as HTMLElement[]).find((e) =>
        e.textContent?.includes(text),
      )!;
    }

    // Anlass (Sebastian 22.11.2026): Wie man zu „Meine Beiträge“ kommt, musste man jedes Mal ueberlegen
    it('zeigt die Ziele sichtbar mit Icon und Text: Suchen, Einwerfen, Fangkorb, Meine Beitraege, Beitragen, Mehr', () => {
      expect(navigationTexte()).toEqual(['Suchen', 'Einwerfen', 'Fangkorb', 'Meine Beiträge', 'Beitragen', 'Mehr']);
      for (const ziel of Array.from(kopf().querySelectorAll('app-hauptnavigation .ziel'))) {
        expect(ziel.querySelector('.ziel-text')!.textContent!.trim()).not.toBe('');
      }
      const icons = Array.from(kopf().querySelectorAll('app-hauptnavigation .ziel-icon'));
      expect(icons.length).toBe(4);
      icons.forEach((icon) => expect(icon.getAttribute('aria-hidden')).toBe('true'));
    });

    it('markiert das aktive Ziel mit aria-current="page"', () => {
      const aktuell = Array.from(kopf().querySelectorAll('[aria-current="page"]'));
      expect(aktuell.length).toBe(1);
      expect(aktuell[0].textContent).toContain('Suchen');
    });

    it('fuehrt mit einem Klick zu Meine Beitraege, ueber den NavigationService', () => {
      const link = kopf().querySelector('app-hauptnavigation [data-ziel="meine"]') as HTMLAnchorElement;
      expect(link.getAttribute('href')).toBe('/contributions');

      link.click();

      expect(navigation.navigiereZu).toHaveBeenCalledOnceWith('/contributions');
    });

    it('zeigt das Profilbild mit Namen und ▾, als Menue-Knopf', () => {
      expect(konto().tagName).toBe('BUTTON');
      expect(konto().getAttribute('aria-haspopup')).toBe('menu');
      expect(konto().textContent).toContain('Profilmenü');
      expect(konto().querySelector('.konto-name')!.textContent!.trim()).toBe('Test User');
      expect(konto().querySelector('img')!.getAttribute('alt')).toBe('');
    });

    it('oeffnet am Profilbild nur das Konto und wuerfelt kein neues Bild', async () => {
      const vorher = fixture.componentInstance.selectedProfilePictureUrl;

      await klickUndWarten(konto());

      expect(menueTexte('.konto-menue')).toEqual([
        jasmine.stringContaining('Profilbild wählen'),
        jasmine.stringContaining('Datenschutz-Einstellungen'),
        jasmine.stringContaining('Abmelden'),
      ]);
      expect(fixture.componentInstance.selectedProfilePictureUrl).toBe(vorher);
      expect(sessionStorage.getItem('profilePicture')).toBeNull();
    });

    it('oeffnet das Profilmenue mit der Tastatur, Fokus auf dem ersten Eintrag', async () => {
      konto().focus();
      konto().dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      await klickUndWarten(konto()); // Enter auf einem <button> loest im Browser den Klick aus

      expect(document.activeElement).toBe(kontoEintrag('Profilbild wählen'));
    });

    it('meldet ueber das Profilmenue ab', async () => {
      const auth = TestBed.inject(AuthService) as jasmine.SpyObj<AuthService>;
      await klickUndWarten(konto());

      kontoEintrag('Abmelden').click();

      expect(auth.logout).toHaveBeenCalledTimes(1);
    });

    it('fuehrt ueber das Profilmenue zur Art.-9-Einwilligung (#489)', async () => {
      await klickUndWarten(konto());

      kontoEintrag('Datenschutz-Einstellungen').click();

      expect(router.navigate).toHaveBeenCalledWith(['/einwilligung']);
    });

    it('oeffnet ueber das Profilmenue den Dialog Profilbild waehlen', async () => {
      await klickUndWarten(konto());

      kontoEintrag('Profilbild wählen').click();

      expect(dialog.open).toHaveBeenCalledWith(ProfilbildDialogComponent, jasmine.anything());
    });

    it('zeigt das gewaehlte Profilbild sofort im Kopf', () => {
      const service = TestBed.inject(ProfilbildService);
      const option = service.auswahl[4];

      service.waehlen(option.id);
      fixture.detectChanges();

      expect(konto().querySelector('img')?.getAttribute('src')).toBe(option.url);
      localStorage.removeItem(PROFILBILD_SCHLUESSEL);
    });

    it('stellt Hilfe, Rundgaenge, Feedback, Hier fehlt eine Antwort und Hell/Dunkel unter "Mehr"', async () => {
      expect(mehrKnopf().getAttribute('aria-haspopup')).toBe('menu');

      await klickUndWarten(mehrKnopf());

      expect(menueTexte('.mehr-menue')).toEqual([
        'Hier fehlt eine Antwort',
        'Hilfe',
        jasmine.stringContaining('Rundgang Antwort finden'),
        jasmine.stringContaining('Rundgang Selbst beitragen'),
        'Feedback',
        jasmine.stringMatching(/Dunkel anzeigen|Hell anzeigen/),
      ]);
    });

    it('oeffnet Feedback unter "Mehr"', async () => {
      await klickUndWarten(mehrKnopf());
      (Array.from(document.querySelectorAll('.mehr-menue .mehr-eintrag')) as HTMLElement[])
        .find((e) => e.textContent!.includes('Feedback'))!
        .click();

      expect(dialog.open).toHaveBeenCalledWith(FeedbackDialogComponent, jasmine.anything());
    });

    // Design-Audit A1/B4 (#512): Abmelden nur im Profilmenue.
    it('hat Abmelden nur im Profilmenue, nicht als eigenen Link im Kopf', () => {
      const abmelden = Array.from(kopf().querySelectorAll('button, a, [role="button"]')).filter((e) =>
        e.textContent?.includes('Abmelden')
      );
      expect(abmelden.length).toBe(0);
    });

    // Grundsatz „Immer alles auch visuell lesbar“: kein Knopf nur mit Symbol (ausser Zurueck)
    it('hat keine unbeschrifteten Symbol-Knoepfe im Kopf', () => {
      expect(kopf().querySelectorAll('button[mat-icon-button]:not(.back-button-header)').length).toBe(0);
      expect(kopf().querySelector('.farbschema-knopf')).toBeNull();
    });

    it('setzt lange Titel kleiner, kurze nicht', () => {
      const komponente = fixture.componentInstance;
      komponente.pageTitle = 'Hintergrundinfo verfassen';
      fixture.detectChanges();
      expect(kopf().classList).toContain('header--titel-lang');
      expect(kopf().querySelector('.desktop-header-title')!.classList).toContain('desktop-header-title--lang');

      komponente.pageTitle = 'Fangkorb';
      fixture.detectChanges();
      expect(kopf().classList).not.toContain('header--titel-lang');
    });
  });

  // R55 (#644): Nach 4x Tab stand der Fokus auf "Hilfe", nicht im Suchfeld
  describe('Skip-Link "Zur Suche"', () => {
    beforeEach(() => starten(BESUCHER));

    it('steht auf dem Start als erstes fokussierbares Element', () => {
      const erstes = fixture.nativeElement.querySelector('a[href], button') as HTMLElement;
      expect(erstes.textContent!.trim()).toBe('Zur Suche');
      expect(erstes.getAttribute('href')).toBe('#suche');
    });

    it('setzt den Fokus ins Suchfeld, ohne die Adresse zu aendern', () => {
      const feld = document.createElement('input');
      feld.id = 'suche';
      document.body.appendChild(feld);
      try {
        const link = fixture.nativeElement.querySelector('[data-testid="skip-link"]') as HTMLAnchorElement;
        const klick = new MouseEvent('click', { cancelable: true, bubbles: true });
        link.dispatchEvent(klick);

        expect(document.activeElement).toBe(feld);
        expect(klick.defaultPrevented).toBeTrue();
      } finally {
        feld.remove();
      }
    });
  });

  // R59 (#644): Der gelbe Punkt an "Beitragen" stand ohne Erklaerung da
  describe('Neu-Punkt an Beitragen', () => {
    beforeEach(() => starten(ANGEMELDET));

    it('erklaert den Punkt per Tooltip und fuer Screenreader', () => {
      (TestBed.inject(RundgangService) as any).mitmachenOffen.set(true);
      fixture.detectChanges();
      const knopf = fixture.nativeElement.querySelector('.beitragen-knopf') as HTMLElement;

      expect(knopf.querySelector('.neu-punkt')).not.toBeNull();
      const tooltip = fixture.debugElement.query(By.css('.beitragen-knopf')).injector.get(MatTooltip);
      expect(tooltip.message).toBe('Neu: so geht Beitragen');
      expect(tooltip.disabled).toBeFalse();
    });
  });

  describe('Profilbild ohne Wahl nicht im Browser gespeichert (#437)', () => {
    function gespeichert(): string[][] {
      return [Object.keys(localStorage), Object.keys(sessionStorage)];
    }

    afterEach(() => ALTE_PROFILBILD_SCHLUESSEL.forEach((s: string) => sessionStorage.removeItem(s)));

    it('zeigt Besuchern das anonyme Profilbild und legt nichts im Browser ab', () => {
      const vorher = gespeichert();
      starten(BESUCHER);

      expect(fixture.componentInstance.selectedProfilePictureUrl).toBe(ANONYMES_PROFILBILD);
      expect(gespeichert()).toEqual(vorher);
    });

    it('zeigt Mitwirkenden ein festes Profilbild und legt nichts im Browser ab', () => {
      const vorher = gespeichert();
      starten(ANGEMELDET);

      const urls = TestBed.inject(ProfilbildService).auswahl.map((o) => o.url);
      expect(urls).toContain(fixture.componentInstance.selectedProfilePictureUrl);
      expect(gespeichert()).toEqual(vorher);
    });

    it('raeumt die Eintraege frueherer Versionen beim Start weg', () => {
      sessionStorage.setItem('profilePicture', '/avatars/female1.svg');
      sessionStorage.setItem('anonymousAvatar', '/avatars/anon-question.svg');
      sessionStorage.setItem('userAvatar', '/avatars/male2.svg');

      starten(BESUCHER);

      ALTE_PROFILBILD_SCHLUESSEL.forEach((s: string) => expect(sessionStorage.getItem(s)).toBeNull());
    });
  });

  describe('Rueckkehrziel nach dem Anmelden (Befund 10 aus dem Review zu PR 458)', () => {
    afterEach(() => sessionStorage.removeItem(RUECKKEHRZIEL_SCHLUESSEL));

    it('fuehrt angemeldet zum gemerkten Ziel und loescht es', () => {
      sessionStorage.setItem(RUECKKEHRZIEL_SCHLUESSEL, '/contribute');

      starten(ANGEMELDET);

      expect(router.navigateByUrl).toHaveBeenCalledWith('/contribute');
      expect(sessionStorage.getItem(RUECKKEHRZIEL_SCHLUESSEL)).toBeNull();
    });

    it('startet auch, wenn der Browser den sessionStorage sperrt', () => {
      const spione = [
        spyOn(Storage.prototype, 'getItem').and.throwError('SecurityError'),
        spyOn(Storage.prototype, 'removeItem').and.throwError('SecurityError'),
      ];

      expect(() => starten(ANGEMELDET)).not.toThrow();
      expect(router.navigateByUrl).not.toHaveBeenCalled();
      spione.forEach((spion) => spion.and.callThrough());
    });
  });
  // Nutzerfuehrung 13.11.2026: offene Meldungen sieht man schon im Kopf.
  describe('Admin', () => {
    it('fragt fuer Nicht-Admins nie nach offenen Meldungen', () => {
      const moderation = jasmine.createSpyObj('ModerationService', ['getReports', 'getLoeschauftraege']);
      TestBed.overrideProvider(ModerationService, { useValue: moderation });
      starten(ANGEMELDET);

      expect(document.querySelector('app-offene-meldungen-zahl')).toBeNull();
      expect(moderation.getReports).not.toHaveBeenCalled();
    });

    it('zeigt unter "Mehr" am Admin-Eintrag die Zahl offener Meldungen', async () => {
      TestBed.overrideProvider(ZuTunService, {
        useValue: {
          meldungen$: of({ daten: { anzahl: 3, mehr: false, aelteste: null }, fehler: false }),
          suchanfragen$: of({ daten: { anzahl: 0 }, fehler: false }),
        },
      });
      starten({ ...ANGEMELDET, isAdmin: true });

      await klickUndWarten(mehrKnopf());

      const admin = document.querySelector('.mehr-menue .mehr-admin') as HTMLElement;
      expect(admin.querySelector('.zahl')!.textContent!.trim()).toBe('3');
      expect(admin.textContent).toContain('3 offene Meldungen');
    });
  });
});
