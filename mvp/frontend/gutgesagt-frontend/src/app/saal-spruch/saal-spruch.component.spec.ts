import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { BehaviorSubject, of } from 'rxjs';

import { AuthService, UserInfo } from '../auth/auth.service';
import { RundgangService } from '../rundgang/rundgang.service';
import { FunktionenService } from '../services/funktionen.service';
import { SAAL_SPRUCH_HEUTE_URL } from '../services/saal-spruch.service';
import { BesuchResponse, UsageTrackingService } from '../services/usage-tracking.service';
import { SeitLetztemBesuchService } from '../seit-letztem-besuch/seit-letztem-besuch.service';
import { startKacheln, startVorrang } from '../seit-letztem-besuch/neues-liste';
import { SaalSpruchComponent, browserTag } from './saal-spruch.component';

const SPRUCH = 'Klimaschutz können wir uns gerade nicht leisten.';
const ANGEMELDET: UserInfo = { isAuthenticated: true, userId: 'kim', userName: null, claims: null };
const BESUCHER: UserInfo = { isAuthenticated: false, userId: null, userName: null, claims: null };

describe('Saal-Spruch (Schalter saal_spruch)', () => {
  describe('startVorrang mit Saal-Spruch', () => {
    const keins = new Set<never>();

    it('geht allgemeinen Zahlen und dem Vorschlag vor (Rundgang 2, 28.11.)', () => {
      const allgemein = { nutzung_seit_letztem_besuch: 0, neue_einwuerfe: 3, unbeantwortete_aussagen: 2 };
      expect(startVorrang(allgemein, keins, false, true)).toBe('spruch');
      expect(startVorrang(allgemein, keins, true, true)).toBe('spruch');
      // Ausdrücklich über die Kachel geholt: dann doch der Vorschlag
      expect(startVorrang(allgemein, keins, true, true, true)).toBe('karte');
      // Die allgemeinen Zahlen treten zurück
      expect(startKacheln(allgemein, keins, 'spruch')).toEqual([]);
    });

    it('tritt hinter eigenes Neues zurück', () => {
      expect(startVorrang({ nutzung_seit_letztem_besuch: 2 }, keins, true, true)).toBe('block');
    });

    it('wartet, solange seine Antwort aussteht; ohne Spruch wie bisher', () => {
      expect(startVorrang(null, keins, false, 'offen')).toBe('offen');
      // Auch mit Vorschlag: Der Spruch ginge vor, also kurz warten statt umspringen
      expect(startVorrang(null, keins, true, 'offen')).toBe('offen');
      expect(startVorrang(null, keins, true, false)).toBe('karte');
      expect(startVorrang(null, keins, true)).toBe('karte');
    });
  });

  describe('Karte', () => {
    let http: HttpTestingController;
    let schalter: boolean | null;
    let info: BehaviorSubject<UserInfo | null>;
    let besuch: BehaviorSubject<BesuchResponse | null>;
    let band: ReturnType<typeof signal<{ imInhalt?: boolean; schlank?: boolean; begruessung?: boolean } | null>>;

    function einrichten(an: boolean | null, wer: UserInfo) {
      schalter = an;
      info = new BehaviorSubject<UserInfo | null>(wer);
      besuch = new BehaviorSubject<BesuchResponse | null>(null);
      band = signal<{ imInhalt?: boolean; schlank?: boolean; begruessung?: boolean } | null>(null);
      TestBed.configureTestingModule({
        providers: [
          provideHttpClient(),
          provideHttpClientTesting(),
          provideRouter([]),
          { provide: AuthService, useValue: { userInfo$: info } },
          { provide: FunktionenService, useValue: { stand$: () => of(schalter) } },
          { provide: UsageTrackingService, useValue: { besuchStand$: besuch } },
          { provide: RundgangService, useValue: { band } },
        ],
      });
      http = TestBed.inject(HttpTestingController);
    }

    afterEach(() => http.verify());

    const karte = (el: HTMLElement) => el.querySelector('[data-testid="saal-spruch"]');

    it('Schalter aus: unsichtbar, kein Abruf, nichts wartet auf die Karte', () => {
      einrichten(false, BESUCHER);
      const fixture = TestBed.createComponent(SaalSpruchComponent);
      fixture.detectChanges();

      expect(karte(fixture.nativeElement)).toBeNull();
      http.expectNone(SAAL_SPRUCH_HEUTE_URL);
      expect(TestBed.inject(SeitLetztemBesuchService).saalSpruchDa$.value).toBeFalse();
    });

    it('Server meldet aus (aktiv: false): unsichtbar', () => {
      einrichten(null, BESUCHER);
      const fixture = TestBed.createComponent(SaalSpruchComponent);
      fixture.detectChanges();
      http.expectOne(SAAL_SPRUCH_HEUTE_URL).flush({ spruch: null, aktiv: false });
      fixture.detectChanges();

      expect(karte(fixture.nativeElement)).toBeNull();
      expect(TestBed.inject(SeitLetztemBesuchService).saalSpruchDa$.value).toBeFalse();
    });

    it('heute kein Spruch: unsichtbar', () => {
      einrichten(true, BESUCHER);
      const fixture = TestBed.createComponent(SaalSpruchComponent);
      fixture.detectChanges();
      http.expectOne(SAAL_SPRUCH_HEUTE_URL).flush({ spruch: null, aktiv: true });
      fixture.detectChanges();

      expect(karte(fixture.nativeElement)).toBeNull();
    });

    it('Besucher sehen den Spruch sofort, mit Frage und Knopf auf die Suche', () => {
      einrichten(true, BESUCHER);
      const fixture = TestBed.createComponent(SaalSpruchComponent);
      fixture.detectChanges();
      expect(TestBed.inject(SeitLetztemBesuchService).saalSpruchDa$.value).toBeNull();
      http.expectOne(SAAL_SPRUCH_HEUTE_URL).flush({ spruch: SPRUCH, aktiv: true });
      fixture.detectChanges();

      const el: HTMLElement = fixture.nativeElement;
      expect(karte(el)).not.toBeNull();
      expect(el.querySelector('h2')!.textContent).toContain('Heute im Netz zur BDK:');
      expect(el.querySelector('[data-testid="saal-spruch-text"]')!.textContent).toContain(SPRUCH);
      expect(el.textContent).toContain('Wie würdest du antworten?');
      const knopf = el.querySelector('[data-testid="saal-spruch-knopf"]') as HTMLAnchorElement;
      expect(knopf.textContent).toContain('Antworten ansehen');
      expect(knopf.getAttribute('href')).toBe(`/result?searchQuery=${encodeURIComponent(SPRUCH)}`);
      expect(TestBed.inject(SeitLetztemBesuchService).saalSpruchDa$.value).toBeTrue();
    });

    it('wartet, solange ein Rundgang-Angebot auf der Startseite steht', () => {
      einrichten(true, BESUCHER);
      band.set({ imInhalt: true });
      const fixture = TestBed.createComponent(SaalSpruchComponent);
      fixture.detectChanges();
      http.expectOne(SAAL_SPRUCH_HEUTE_URL).flush({ spruch: SPRUCH });
      fixture.detectChanges();
      expect(karte(fixture.nativeElement)).toBeNull();

      // Beantwortet: die Karte erscheint ohne Neuladen
      band.set(null);
      fixture.detectChanges();
      expect(karte(fixture.nativeElement)).not.toBeNull();
    });

    for (const [wie, angebot] of [
      ['„Neu hier?“', { imInhalt: true, schlank: true }],
      ['„Von der BDK?“', { imInhalt: true, schlank: true, begruessung: true }],
    ] as const) {
      it(`steht neben dem schlanken Willkommen ${wie} (UX-Review 26.11.)`, () => {
        einrichten(true, BESUCHER);
        band.set({ ...angebot });
        const fixture = TestBed.createComponent(SaalSpruchComponent);
        fixture.detectChanges();
        http.expectOne(SAAL_SPRUCH_HEUTE_URL).flush({ spruch: SPRUCH });
        fixture.detectChanges();
        expect(karte(fixture.nativeElement)).not.toBeNull();
      });
    }

    it('Angemeldete mit Vorschlag: der Saal-Spruch geht vor (Rundgang 2, 28.11.)', () => {
      einrichten(true, ANGEMELDET);
      const neues = TestBed.inject(SeitLetztemBesuchService);
      neues.naechsterSchrittDa$.next(true);
      besuch.next({ nutzung_seit_letztem_besuch: 0, neue_einwuerfe: 3 });
      const fixture = TestBed.createComponent(SaalSpruchComponent);
      fixture.detectChanges();
      http.expectOne(SAAL_SPRUCH_HEUTE_URL).flush({ spruch: SPRUCH });
      fixture.detectChanges();
      expect(karte(fixture.nativeElement)).not.toBeNull();

      // Ohne Vorschlag ebenso
      neues.naechsterSchrittDa$.next(false);
      fixture.detectChanges();
      expect(karte(fixture.nativeElement)).not.toBeNull();
    });

    for (const [wer, info, satz] of [
      ['Besucher', BESUCHER, 'Mit Konto schreibst du die erste.'],
      ['Angemeldete', ANGEMELDET, 'Schreib die erste!'],
    ] as const) {
      it(`ohne Antworten: ${wer} sehen „Antwort beitragen“ statt der Sackgasse`, () => {
        einrichten(true, info);
        TestBed.inject(SeitLetztemBesuchService).naechsterSchrittDa$.next(false);
        besuch.next({ nutzung_seit_letztem_besuch: 0 });
        const fixture = TestBed.createComponent(SaalSpruchComponent);
        fixture.detectChanges();
        http.expectOne(SAAL_SPRUCH_HEUTE_URL).flush({ spruch: SPRUCH, aktiv: true, antworten: false });
        fixture.detectChanges();

        const el: HTMLElement = fixture.nativeElement;
        const knopf = el.querySelector('[data-testid="saal-spruch-knopf"]') as HTMLAnchorElement;
        expect(knopf.textContent).toContain('Antwort beitragen');
        expect(knopf.getAttribute('href')).toBe(`/workflow/add-commentary?searchQuery=${encodeURIComponent(SPRUCH)}`);
        expect(el.querySelector('[data-testid="saal-spruch-ohne-antwort"]')!.textContent).toContain(satz);
        expect(el.textContent).not.toContain('Wie würdest du antworten?');
      });
    }

    it('Antwortstand unbekannt (null): bleibt bei „Antworten ansehen“', () => {
      einrichten(true, BESUCHER);
      const fixture = TestBed.createComponent(SaalSpruchComponent);
      fixture.detectChanges();
      http.expectOne(SAAL_SPRUCH_HEUTE_URL).flush({ spruch: SPRUCH, aktiv: true, antworten: null });
      fixture.detectChanges();
      const knopf = fixture.nativeElement.querySelector('[data-testid="saal-spruch-knopf"]') as HTMLAnchorElement;
      expect(knopf.textContent).toContain('Antworten ansehen');
    });

    it('Angemeldete: eigenes Neues geht vor, allgemeine Zahlen nicht', () => {
      einrichten(true, ANGEMELDET);
      const neues = TestBed.inject(SeitLetztemBesuchService);
      neues.naechsterSchrittDa$.next(false);
      besuch.next({ nutzung_seit_letztem_besuch: 3 });
      const fixture = TestBed.createComponent(SaalSpruchComponent);
      fixture.detectChanges();
      http.expectOne(SAAL_SPRUCH_HEUTE_URL).flush({ spruch: SPRUCH });
      fixture.detectChanges();
      expect(karte(fixture.nativeElement)).toBeNull();

      neues.erledigen('nutzung');
      fixture.detectChanges();
      expect(karte(fixture.nativeElement)).not.toBeNull();
    });

    it('bei der Rückkehr steht der Spruch sofort da und wird still neu gefragt', () => {
      einrichten(true, BESUCHER);
      TestBed.inject(SeitLetztemBesuchService).saalSpruchGemerkt = { tag: browserTag(), spruch: { spruch: SPRUCH, antworten: true } };
      const fixture = TestBed.createComponent(SaalSpruchComponent);
      fixture.detectChanges();
      expect(karte(fixture.nativeElement)).not.toBeNull();
      http.expectOne(SAAL_SPRUCH_HEUTE_URL).flush({ spruch: SPRUCH });
    });

    it('Fehler beim Abruf: keine Karte, nichts wartet', () => {
      einrichten(true, BESUCHER);
      const fixture = TestBed.createComponent(SaalSpruchComponent);
      fixture.detectChanges();
      http.expectOne(SAAL_SPRUCH_HEUTE_URL).flush('kaputt', { status: 500, statusText: 'Fehler' });
      fixture.detectChanges();

      expect(karte(fixture.nativeElement)).toBeNull();
      expect(TestBed.inject(SeitLetztemBesuchService).saalSpruchDa$.value).toBeFalse();
    });
  });
});
