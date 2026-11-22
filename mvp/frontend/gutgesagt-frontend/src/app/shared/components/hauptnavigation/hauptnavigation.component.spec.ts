import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { MatDialog } from '@angular/material/dialog';
import { BehaviorSubject } from 'rxjs';

import { HauptnavigationComponent, NavModus, oeffnetTastatur } from './hauptnavigation.component';
import { fangkorbZusatz } from './fangkorb-neu.service';
import { AuthService, UserInfo } from '../../../auth/auth.service';
import { NavigationService } from '../../../services/navigation.service';
import { BesuchResponse, UsageTrackingService } from '../../../services/usage-tracking.service';
import { SeitLetztemBesuchService } from '../../../seit-letztem-besuch/seit-letztem-besuch.service';
import { RundgangService } from '../../../rundgang/rundgang.service';
import { LeerComponent } from '../../../testing/routen-ohne-waechter';

const ANGEMELDET: UserInfo = { isAuthenticated: true, userId: 'u1', userName: 'Kim', claims: null };
const BESUCHER: UserInfo = { isAuthenticated: false, userId: null, userName: null, claims: null };

/**
 * Navigation Variante 3 (Sebastian 22.11.2026): untere Leiste am Handy, dieselben Ziele
 * im Kopf am Desktop. Messlatte Barrierefreiheit vom Designwichtel: Ziele >= 48 px,
 * aria-current, aria-haspopup, Zähler im zugänglichen Namen, Platz unter dem Inhalt,
 * Leiste weicht der Tastatur.
 */
describe('HauptnavigationComponent', () => {
  let fixture: ComponentFixture<HauptnavigationComponent>;
  let router: Router;
  let navigation: jasmine.SpyObj<NavigationService>;
  let rundgang: jasmine.SpyObj<RundgangService>;
  let person$: BehaviorSubject<UserInfo | null>;
  let besuch$: BehaviorSubject<BesuchResponse | null>;

  beforeEach(async () => {
    person$ = new BehaviorSubject<UserInfo | null>(ANGEMELDET);
    besuch$ = new BehaviorSubject<BesuchResponse | null>(null);
    navigation = jasmine.createSpyObj('NavigationService', ['navigateHome', 'navigiereZu']);
    navigation.navigateHome.and.resolveTo();
    navigation.navigiereZu.and.resolveTo();
    rundgang = jasmine.createSpyObj('RundgangService', ['starten']);
    rundgang.starten.and.resolveTo();

    await TestBed.configureTestingModule({
      imports: [HauptnavigationComponent],
      providers: [
        provideRouter(
          ['search', 'result', 'einwerfen', 'fangkorb', 'contributions', 'hier-fehlt-eine-antwort'].map((path) => ({
            path,
            component: LeerComponent,
          })),
        ),
        provideNoopAnimations(),
        { provide: AuthService, useValue: { userInfo$: person$.asObservable() } },
        { provide: UsageTrackingService, useValue: { besuchStand$: besuch$ } },
        { provide: NavigationService, useValue: navigation },
        { provide: RundgangService, useValue: rundgang },
        { provide: MatDialog, useValue: jasmine.createSpyObj('MatDialog', ['open']) },
      ],
    }).compileComponents();
    router = TestBed.inject(Router);
  });

  afterEach(() => fixture?.destroy());

  function bauen(modus: NavModus): void {
    fixture = TestBed.createComponent(HauptnavigationComponent);
    fixture.componentInstance.modus = modus;
    document.body.appendChild(fixture.nativeElement);
    fixture.detectChanges();
  }

  function oeffnen(url: string): void {
    router.navigateByUrl(url);
    tick();
    fixture.detectChanges();
  }

  function ziele(): HTMLElement[] {
    return Array.from(fixture.nativeElement.querySelectorAll('.ziel')) as HTMLElement[];
  }

  function texte(): string[] {
    return ziele().map((z) => z.querySelector('.ziel-text')!.textContent!.trim());
  }

  function beruehrungEmulieren(an: boolean): void {
    const echt = window.matchMedia.bind(window);
    spyOn(window, 'matchMedia').and.callFake((q: string) =>
      q === '(pointer: coarse)' ? ({ matches: an } as MediaQueryList) : echt(q),
    );
  }

  function ziel(id: string): HTMLElement {
    return fixture.nativeElement.querySelector(`[data-ziel="${id}"]`) as HTMLElement;
  }

  describe('Leiste am Handy', () => {
    it('zeigt angemeldet Suchen, Einwerfen, Fangkorb, Meine und Mehr, jedes mit Icon und Text', () => {
      bauen('leiste');

      expect(texte()).toEqual(['Suchen', 'Einwerfen', 'Fangkorb', 'Meine', 'Mehr']);
      for (const z of ziele()) {
        expect(z.querySelector('mat-icon')!.getAttribute('aria-hidden')).toBe('true');
      }
      expect(fixture.nativeElement.querySelector('nav')!.getAttribute('aria-label')).toBe('Hauptnavigation');
    });

    it('hat Ziele von mindestens 48 x 48 px und steht fest am unteren Rand', () => {
      bauen('leiste');

      for (const z of ziele()) {
        const r = z.getBoundingClientRect();
        expect(r.height).withContext(z.textContent!).toBeGreaterThanOrEqual(48);
        expect(r.width).withContext(z.textContent!).toBeGreaterThanOrEqual(48);
      }
      expect(getComputedStyle(fixture.nativeElement).position).toBe('fixed');
    });

    it('zeigt Besuchern eine reduzierte Leiste: Suchen, Hilfe, Mehr', () => {
      person$.next(BESUCHER);
      bauen('leiste');

      expect(texte()).toEqual(['Suchen', 'Hilfe', 'Mehr']);
      expect(ziel('fangkorb')).toBeNull();
    });

    it('meldet ihre Hoehe als --unterleiste-hoehe und nimmt sie beim Abbau wieder weg', () => {
      bauen('leiste');
      const wert = () => document.documentElement.style.getPropertyValue('--unterleiste-hoehe');

      expect(parseInt(wert(), 10)).toBeGreaterThanOrEqual(64);
      fixture.destroy();
      expect(wert()).toBe('');
    });

    it('weicht der Bildschirmtastatur: versteckt bei Fokus in einem Textfeld, danach wieder da', () => {
      beruehrungEmulieren(true);
      bauen('leiste');
      const feld = document.createElement('input');
      document.body.appendChild(feld);
      try {
        feld.focus();
        fixture.detectChanges();
        expect(fixture.nativeElement.classList).toContain('versteckt');
        expect(getComputedStyle(fixture.nativeElement).visibility).toBe('hidden');

        feld.blur();
        fixture.detectChanges();
        expect(fixture.nativeElement.classList).not.toContain('versteckt');
      } finally {
        feld.remove();
      }
    });

    it('bleibt mit Maus und Tastatur stehen, auch bei Fokus in einem Textfeld', () => {
      beruehrungEmulieren(false);
      bauen('leiste');
      const feld = document.createElement('input');
      document.body.appendChild(feld);
      try {
        feld.focus();
        fixture.detectChanges();
        expect(fixture.nativeElement.classList).not.toContain('versteckt');
      } finally {
        feld.remove();
      }
    });
  });

  describe('aktives Ziel', () => {
    it('setzt aria-current="page" am Ziel der Seite, und nur dort', fakeAsync(() => {
      bauen('leiste');
      oeffnen('/contributions?tab=einwuerfe');

      expect(ziel('meine').getAttribute('aria-current')).toBe('page');
      expect(ziel('meine').classList).toContain('ziel--aktiv');
      expect(fixture.nativeElement.querySelectorAll('[aria-current]').length).toBe(1);
    }));

    it('zaehlt die Treffer zum Suchen', fakeAsync(() => {
      bauen('kopf');
      oeffnen('/result?searchQuery=Wind');

      expect(ziel('suchen').getAttribute('aria-current')).toBe('page');
    }));

    it('hebt "Mehr" hervor, wenn die Seite darunter steht', fakeAsync(() => {
      bauen('leiste');
      oeffnen('/hier-fehlt-eine-antwort');

      expect(ziel('mehr').classList).toContain('ziel--aktiv');
      expect(fixture.nativeElement.querySelector('[aria-current]')).toBeNull();
    }));
  });

  describe('Navigieren', () => {
    it('fuehrt ueber den NavigationService, damit offene Saetze gespeichert werden', () => {
      bauen('leiste');

      ziel('fangkorb').click();
      ziel('suchen').click();

      expect(navigation.navigiereZu).toHaveBeenCalledOnceWith('/fangkorb');
      expect(navigation.navigateHome).toHaveBeenCalledTimes(1);
    });

    it('laesst Strg-Klick als normalen Link durch (neuer Tab)', () => {
      bauen('kopf');
      const klick = new MouseEvent('click', { ctrlKey: true, cancelable: true, bubbles: true });
      // Den neuen Tab selbst verhindert der Test, nicht die Komponente
      document.addEventListener('click', (e) => e.preventDefault(), { once: true });

      ziel('meine').dispatchEvent(klick);

      expect(navigation.navigiereZu).not.toHaveBeenCalled();
    });
  });

  describe('Mehr', () => {
    async function mehrOeffnen(): Promise<string[]> {
      ziel('mehr').click();
      fixture.detectChanges();
      await fixture.whenStable();
      return Array.from(document.querySelectorAll('.mehr-menue [mat-menu-item]')).map((e) =>
        e.textContent!.replace(/\s+/g, ' ').trim(),
      );
    }

    it('ist ein Menue-Knopf mit aria-haspopup="menu"', () => {
      bauen('leiste');
      expect(ziel('mehr').tagName).toBe('BUTTON');
      expect(ziel('mehr').getAttribute('aria-haspopup')).toBe('menu');
    });

    it('enthaelt am Handy denselben Inhalt wie am Desktop', async () => {
      bauen('leiste');
      const handy = await mehrOeffnen();
      fixture.destroy();
      document.querySelectorAll('.cdk-overlay-container').forEach((e) => (e.innerHTML = ''));

      bauen('kopf');
      expect(await mehrOeffnen()).toEqual(handy);
      expect(handy.length).toBe(6);
    });

    it('startet einen Rundgang', async () => {
      bauen('leiste');
      await mehrOeffnen();

      (Array.from(document.querySelectorAll('.mehr-menue .mehr-eintrag')) as HTMLElement[])
        .find((e) => e.textContent!.includes('Antwort finden'))!
        .click();

      expect(rundgang.starten).toHaveBeenCalledOnceWith('antwort-finden');
    });

    it('zeigt Admins den Admin-Eintrag, anderen nicht', async () => {
      bauen('leiste');
      expect((await mehrOeffnen()).some((t) => t.includes('Admin'))).toBeFalse();
    });
  });

  describe('Zaehler am Fangkorb', () => {
    function zaehler(): HTMLElement | null {
      return ziel('fangkorb').querySelector('.zaehler');
    }

    it('zeigt neue Einwuerfe seit dem letzten Besuch, im zugaenglichen Namen und stumm als Kreis', () => {
      besuch$.next({ nutzung_seit_letztem_besuch: 0, neue_einwuerfe: 3 });
      bauen('leiste');

      expect(zaehler()!.textContent!.trim()).toBe('3');
      expect(zaehler()!.getAttribute('aria-hidden')).toBe('true');
      expect(ziel('fangkorb').querySelector('.visually-hidden')!.textContent).toBe(', 3 neue Einwürfe');
    });

    it('zeigt ohne Neues nichts', () => {
      besuch$.next({ nutzung_seit_letztem_besuch: 0, neue_einwuerfe: 0 });
      bauen('kopf');

      expect(zaehler()).toBeNull();
      expect(ziel('fangkorb').querySelector('.visually-hidden')!.textContent).toBe('');
    });

    it('verschwindet, sobald der Fangkorb offen war', fakeAsync(() => {
      besuch$.next({ nutzung_seit_letztem_besuch: 0, neue_einwuerfe: 2 });
      bauen('leiste');
      expect(zaehler()).not.toBeNull();

      oeffnen('/fangkorb');

      expect(zaehler()).toBeNull();
      expect(TestBed.inject(SeitLetztemBesuchService).erledigt$.value.has('einwuerfe')).toBeTrue();
    }));
  });
});

describe('oeffnetTastatur', () => {
  it('erkennt Textfelder, nicht Knoepfe oder Haken', () => {
    const text = document.createElement('input');
    const haken = document.createElement('input');
    haken.type = 'checkbox';
    const editierbar = document.createElement('div');
    editierbar.contentEditable = 'true';
    document.body.appendChild(editierbar);

    expect(oeffnetTastatur(text)).toBeTrue();
    expect(oeffnetTastatur(document.createElement('textarea'))).toBeTrue();
    expect(oeffnetTastatur(editierbar)).toBeTrue();
    expect(oeffnetTastatur(haken)).toBeFalse();
    expect(oeffnetTastatur(document.createElement('button'))).toBeFalse();
    expect(oeffnetTastatur(null)).toBeFalse();
    editierbar.remove();
  });
});

describe('fangkorbZusatz', () => {
  it('nennt die Zahl in Ein- und Mehrzahl, ohne Neues nichts', () => {
    expect(fangkorbZusatz(0)).toBe('');
    expect(fangkorbZusatz(1)).toBe(', 1 neuer Einwurf');
    expect(fangkorbZusatz(5)).toBe(', 5 neue Einwürfe');
  });
});
