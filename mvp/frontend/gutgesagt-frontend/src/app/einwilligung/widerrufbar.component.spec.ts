import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { BehaviorSubject, of } from 'rxjs';
import { provideRouter } from '@angular/router';

import { environment } from '../../environments/environment';
import { PunkteEinwilligungService, PunkteEinwilligungStand } from '../shared/punkte-einwilligung/punkte-einwilligung.service';
import { SpielgefuehlService, SpielgefuehlStand } from '../services/spielgefuehl.service';
import { NACHLADEN_MS, STILLE_ABFRAGE } from '../shared/selbst-nachladen';
import { Widerrufbar, WiderrufbarComponent } from './widerrufbar.component';

const BASIS = `${environment.baseUrl}/api/v1`;
const URL = `${BASIS}/usage/users/me/widerrufbar`;
const NICHTS: Widerrufbar = { spielgefuehl: null, punkte: null, rangliste: null, abzeichen: null, team_oeffentlich: null };
const ALLES: Widerrufbar = {
  spielgefuehl: { stufe: 'rangliste', titel: 'In der Saison-Rangliste mitspielen', wortlaut: 'spielgefuehl-2026-11-26' },
  punkte: { wortlaut: '2026-11-13' },
  rangliste: { wortlaut: 'rangliste-2026-11-25' },
  abzeichen: { wortlaut: '2026-11-09-b' },
  team_oeffentlich: { wortlaut: 'team-oeffentlich-2026-11-25' },
};

/** Widerruf jederzeit, auch bei ausgeschalteten Schaltern (Art. 7 Abs. 3 DSGVO). */
describe('WiderrufbarComponent', () => {
  let fixture: ComponentFixture<WiderrufbarComponent>;
  let http: HttpTestingController;
  let punkteStand: BehaviorSubject<PunkteEinwilligungStand | null | undefined>;
  let punkteLaden: jasmine.Spy;
  /** Stand der Spielgefühl-Karte (SpielgefuehlService); undefined: noch nicht geladen. */
  let spielStand: BehaviorSubject<SpielgefuehlStand | null | undefined>;
  let spielLaden: jasmine.Spy;

  function starten(stand: Widerrufbar, eingaben: Partial<WiderrufbarComponent> = {}) {
    punkteStand = new BehaviorSubject<PunkteEinwilligungStand | null | undefined>(null);
    punkteLaden = jasmine.createSpy('laden').and.returnValue(of(null));
    spielStand = new BehaviorSubject<SpielgefuehlStand | null | undefined>(undefined);
    spielLaden = jasmine.createSpy('spielLaden').and.returnValue(of(null));
    TestBed.configureTestingModule({
      imports: [WiderrufbarComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: PunkteEinwilligungService, useValue: { stand$: punkteStand, laden: punkteLaden } },
        { provide: SpielgefuehlService, useValue: { stand$: spielStand, laden: spielLaden } },
        provideRouter([]),
      ],
    });
    fixture = TestBed.createComponent(WiderrufbarComponent);
    Object.assign(fixture.componentInstance, eingaben);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne({ method: 'GET', url: URL }).flush(stand);
    fixture.detectChanges();
  }

  function el(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function zeile(art: string): HTMLElement | null {
    return el().querySelector(`[data-testid="widerruf-${art}"]`);
  }

  afterEach(() => http.verify());

  it('zeigt nichts, wenn nichts über „aus“ gespeichert ist', () => {
    starten(NICHTS);

    expect(el().querySelector('[data-testid="widerrufbar"]')).toBeNull();
  });

  it('zeigt je gespeicherter Einwilligung eine Zeile mit „Ausschalten“, ohne Ja-Knopf', () => {
    starten(ALLES);

    expect(zeile('spielgefuehl')?.textContent).toContain('Spielgefühl: In der Saison-Rangliste mitspielen');
    expect(zeile('punkte')?.textContent).toContain('Punkte und Meilensteine: an');
    expect(zeile('rangliste')?.textContent).toContain('Rangliste: dabei');
    expect(zeile('abzeichen')?.textContent).toContain('Abzeichen am Namen: sichtbar');
    expect(zeile('team_oeffentlich')?.textContent).toContain('Teams am Namen: sichtbar');
    // Jura 27.11.: neutral, weil darunter auch die Teams stehen
    expect(el().querySelector('[id^="widerrufbar-titel"]')?.textContent?.trim()).toBe('Einwilligungen ausschalten');
    const knoepfe = Array.from(el().querySelectorAll('button')).map((b) => b.textContent?.trim());
    expect(knoepfe).toEqual(['Ausschalten', 'Ausschalten', 'Ausschalten', 'Ausschalten', 'Ausschalten']);
  });

  it('lässt die Punkte-Zeile weg, solange das Häkchen den Widerruf anbietet', () => {
    starten(ALLES);

    punkteStand.next({ eingewilligt: true, wortlaut: '2026-11-13', aktueller_wortlaut: { kennung: '2026-11-13', text: '' } });
    fixture.detectChanges();

    expect(zeile('punkte')).toBeNull();
    expect(zeile('spielgefuehl')).not.toBeNull();
  });

  const FAELLE: Array<[keyof Widerrufbar, string, object]> = [
    ['spielgefuehl', `${BASIS}/usage/users/me/spielgefuehl`, { stufe: 'aus', mit_anzeigename: null, wortlaut: 'spielgefuehl-2026-11-26' }],
    ['punkte', `${BASIS}/usage/users/me/punkte-einwilligung`, { eingewilligt: false, wortlaut: '2026-11-13' }],
    ['rangliste', `${BASIS}/rangliste/einwilligung`, { teilnehmen: false, mit_anzeigename: false, wortlaut: 'rangliste-2026-11-25' }],
    ['abzeichen', `${BASIS}/usage/users/me/abzeichen-sichtbarkeit`, { zeigen: false, wortlaut: '2026-11-09-b' }],
    // Auch bei Schalter teams_oeffentlich aus: der Server nimmt ein Nein immer an.
    ['team_oeffentlich', `${BASIS}/teams/oeffentlich`, { zeigen: false, wortlaut: 'team-oeffentlich-2026-11-25' }],
  ];

  for (const [art, url, body] of FAELLE) {
    it(`„Ausschalten“ bei ${art} schickt das Nein mit dem gespeicherten Wortlaut und lädt neu`, () => {
      starten(ALLES);

      (zeile(art)?.querySelector('button') as HTMLButtonElement).click();
      const anfrage = http.expectOne({ method: 'PUT', url });
      expect(anfrage.request.body).toEqual(body);
      anfrage.flush(null, { status: 204, statusText: 'No Content' });
      http.expectOne({ method: 'GET', url: URL }).flush({ ...ALLES, [art]: null });
      fixture.detectChanges();

      expect(zeile(art)).toBeNull();
      expect(punkteLaden).toHaveBeenCalled();
      expect(el().querySelector('[data-testid="widerruf-status"]')?.textContent).toContain('Ausgeschaltet:');
    });
  }

  it('setzt den Fokus nach dem Ausschalten auf die nächste Zeile, nach der letzten auf die Meldung', () => {
    starten({ ...NICHTS, rangliste: ALLES.rangliste, abzeichen: ALLES.abzeichen });
    document.body.appendChild(el());

    (zeile('rangliste')?.querySelector('button') as HTMLButtonElement).click();
    http.expectOne({ method: 'PUT', url: `${BASIS}/rangliste/einwilligung` }).flush(null, { status: 204, statusText: 'No Content' });
    http.expectOne({ method: 'GET', url: URL }).flush({ ...NICHTS, abzeichen: ALLES.abzeichen });
    fixture.detectChanges();
    expect(document.activeElement).toBe(zeile('abzeichen')?.querySelector('button') ?? null);

    (zeile('abzeichen')?.querySelector('button') as HTMLButtonElement).click();
    http
      .expectOne({ method: 'PUT', url: `${BASIS}/usage/users/me/abzeichen-sichtbarkeit` })
      .flush(null, { status: 204, statusText: 'No Content' });
    http.expectOne({ method: 'GET', url: URL }).flush(NICHTS);
    fixture.detectChanges();
    expect(document.activeElement?.classList.contains('meldungen')).toBeTrue();
    expect(el().querySelector('[data-testid="widerruf-status"]')?.textContent).toContain('Abzeichen am Namen');
    el().remove();
  });

  it('nach dem Abwählen des Punkte-Häkchens keine Punkte-Zeile mit altem Stand', () => {
    starten(ALLES);
    punkteStand.next({ eingewilligt: true, wortlaut: '2026-11-13', aktueller_wortlaut: { kennung: '2026-11-13', text: '' } });
    fixture.detectChanges();

    punkteStand.next({ eingewilligt: false, wortlaut: '2026-11-13', aktueller_wortlaut: { kennung: '2026-11-13', text: '' } });
    fixture.detectChanges();

    expect(zeile('punkte')).toBeNull();
    // Der Server hat dabei auch das Spielgefühl ausgeschaltet: Stand frisch geholt.
    http.expectOne({ method: 'GET', url: URL }).flush({ ...ALLES, punkte: null, spielgefuehl: null });
    fixture.detectChanges();
    expect(zeile('spielgefuehl')).toBeNull();
    expect(zeile('punkte')).toBeNull();
  });

  it('nimmt die erledigte Zeile weg, auch wenn das Nachladen scheitert', () => {
    starten(ALLES);

    (zeile('rangliste')?.querySelector('button') as HTMLButtonElement).click();
    http.expectOne({ method: 'PUT', url: `${BASIS}/rangliste/einwilligung` }).flush(null, { status: 204, statusText: 'No Content' });
    http.expectOne({ method: 'GET', url: URL }).flush(null, { status: 500, statusText: 'Fehler' });
    fixture.detectChanges();

    expect(zeile('rangliste')).toBeNull();
    expect(zeile('abzeichen')).not.toBeNull();
  });

  it('neuLaden holt den Stand frisch (nach einem Widerruf auf der Seite)', () => {
    starten(ALLES);

    fixture.componentInstance.neuLaden();
    http.expectOne({ method: 'GET', url: URL }).flush(NICHTS);
    fixture.detectChanges();

    expect(el().querySelector('[data-testid="widerrufbar"]')).toBeNull();
  });

  it('meldet einen Fehler und lässt die Zeile stehen', () => {
    starten(ALLES);

    (zeile('abzeichen')?.querySelector('button') as HTMLButtonElement).click();
    http
      .expectOne({ method: 'PUT', url: `${BASIS}/usage/users/me/abzeichen-sichtbarkeit` })
      .flush(null, { status: 500, statusText: 'Fehler' });
    fixture.detectChanges();

    expect(el().querySelector('[data-testid="widerruf-fehler"]')).not.toBeNull();
    expect(zeile('abzeichen')).not.toBeNull();
    expect((zeile('abzeichen')?.querySelector('button') as HTMLButtonElement).disabled).toBeFalse();
  });

  it('zeigt bei einem Lesefehler nichts', () => {
    punkteStand = new BehaviorSubject<PunkteEinwilligungStand | null | undefined>(null);
    TestBed.configureTestingModule({
      imports: [WiderrufbarComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: PunkteEinwilligungService, useValue: { stand$: punkteStand, laden: () => of(null) } },
        provideRouter([]),
      ],
    });
    fixture = TestBed.createComponent(WiderrufbarComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne({ method: 'GET', url: URL }).flush(null, { status: 500, statusText: 'Fehler' });
    fixture.detectChanges();

    expect(el().querySelector('[data-testid="widerrufbar"]')).toBeNull();
  });

  describe('Einbindung auf anderen Seiten (Datenschutzseite, „Meine Beiträge“)', () => {
    function karte(stufe: SpielgefuehlStand['stufe']): SpielgefuehlStand {
      return { stufe, aktueller_wortlaut: {} } as unknown as SpielgefuehlStand;
    }

    it('nimmt die Ebene der Überschrift von der Seite', () => {
      starten(ALLES, { ebene: 4 });

      expect(el().querySelector('h4[id^="widerrufbar-titel"]')?.textContent).toContain('Einwilligungen ausschalten');
      expect(el().querySelector('h3')).toBeNull();
    });

    it('zeigt den Satz für „nichts zu widerrufen“ erst nach dem Laden', () => {
      punkteStand = new BehaviorSubject<PunkteEinwilligungStand | null | undefined>(null);
      TestBed.configureTestingModule({
        imports: [WiderrufbarComponent],
        providers: [
          provideHttpClient(),
          provideHttpClientTesting(),
          { provide: PunkteEinwilligungService, useValue: { stand$: punkteStand, laden: () => of(null) } },
          { provide: SpielgefuehlService, useValue: { stand$: new BehaviorSubject(undefined), laden: () => of(null) } },
          provideRouter([]),
        ],
      });
      fixture = TestBed.createComponent(WiderrufbarComponent);
      fixture.componentInstance.leerText = 'Nichts zu widerrufen.';
      http = TestBed.inject(HttpTestingController);
      fixture.detectChanges();
      expect(el().querySelector('[data-testid="widerrufbar-leer"]')).toBeNull();

      http.expectOne({ method: 'GET', url: URL }).flush(NICHTS);
      fixture.detectChanges();
      expect(el().querySelector('[data-testid="widerrufbar-leer"]')?.textContent).toContain('Nichts zu widerrufen.');
    });

    it('zeigt ohne Häkchen daneben die Punkte-Zeile, auch wenn der gemeinsame Stand eingewilligt hat', () => {
      starten(ALLES, { punkteHaekchenDaneben: false });

      punkteStand.next({ eingewilligt: true, wortlaut: '2026-11-13', aktueller_wortlaut: { kennung: '2026-11-13', text: '' } });
      fixture.detectChanges();

      expect(zeile('punkte')).not.toBeNull();
    });

    it('lässt neben der Spielgefühl-Karte die Spielgefühl-Zeile weg, solange die Karte die Stufe zeigt', () => {
      starten(ALLES, { spielgefuehlKarteDaneben: true });
      // Stand der Karte noch unbekannt: lieber doppelt als kein Weg.
      expect(zeile('spielgefuehl')).not.toBeNull();

      spielStand.next(karte('rangliste'));
      fixture.detectChanges();
      expect(zeile('spielgefuehl')).toBeNull();
      expect(zeile('rangliste')).not.toBeNull();
    });

    it('zeigt die Spielgefühl-Zeile, wenn die Karte leer ist (Schalter aus)', () => {
      starten(ALLES, { spielgefuehlKarteDaneben: true });

      spielStand.next(null);
      fixture.detectChanges();

      expect(zeile('spielgefuehl')?.textContent).toContain('Spielgefühl: In der Saison-Rangliste mitspielen');
    });

    it('fragt neu, wenn die Stufe auf der Karte wechselt', () => {
      starten(ALLES, { spielgefuehlKarteDaneben: true });
      spielStand.next(karte('rangliste'));

      spielStand.next(karte('aus'));
      http.expectOne({ method: 'GET', url: URL }).flush({ ...ALLES, spielgefuehl: null, rangliste: null });
      fixture.detectChanges();

      expect(zeile('rangliste')).toBeNull();
    });

    it('lädt im Takt selbst nach, ohne Neuladen der Seite (Widerruf in einem anderen Tab)', fakeAsync(() => {
      starten(ALLES);

      tick(NACHLADEN_MS);
      const anfrage = http.expectOne({ method: 'GET', url: URL });
      anfrage.flush({ ...ALLES, abzeichen: null });
      fixture.detectChanges();

      expect(zeile('abzeichen')).toBeNull();
      fixture.destroy();
    }));

    it('fragt still: nach abgelaufener Sitzung keine Umleitung, keine Knöpfe, kein Weiterfragen', fakeAsync(() => {
      starten(ALLES);

      tick(NACHLADEN_MS);
      const anfrage = http.expectOne({ method: 'GET', url: URL });
      expect(anfrage.request.context.get(STILLE_ABFRAGE)).toBeTrue();
      anfrage.flush(null, { status: 401, statusText: 'Unauthorized' });
      fixture.detectChanges();

      expect(el().querySelector('[data-testid="widerrufbar"]')).toBeNull();
      // Der Weg zum Widerruf bleibt sichtbar: neu anmelden, zurück an diese Stelle.
      const link = el().querySelector('[data-testid="widerrufbar-sitzung"] a') as HTMLAnchorElement;
      expect(link.textContent?.trim()).toBe('Sitzung abgelaufen – Anmelden');
      expect(link.getAttribute('href')).toContain('/login?returnUrl=');
      tick(NACHLADEN_MS * 8);
      http.expectNone({ method: 'GET', url: URL });
      fixture.destroy();
    }));
    it('meldet die Zahl der Zeilen bei jeder Änderung, auch die erste „0“', () => {
      const zahlen: number[] = [];
      punkteStand = new BehaviorSubject<PunkteEinwilligungStand | null | undefined>(null);
      TestBed.configureTestingModule({
        imports: [WiderrufbarComponent],
        providers: [
          provideHttpClient(),
          provideHttpClientTesting(),
          { provide: PunkteEinwilligungService, useValue: { stand$: punkteStand, laden: () => of(null) } },
          { provide: SpielgefuehlService, useValue: { stand$: new BehaviorSubject(undefined), laden: () => of(null) } },
          provideRouter([]),
        ],
      });
      fixture = TestBed.createComponent(WiderrufbarComponent);
      http = TestBed.inject(HttpTestingController);
      fixture.componentInstance.zeilenZahl.subscribe((n) => zahlen.push(n));
      fixture.detectChanges();
      expect(zahlen).toEqual([]);
      http.expectOne({ method: 'GET', url: URL }).flush(NICHTS);
      fixture.componentInstance.neuLaden();
      http.expectOne({ method: 'GET', url: URL }).flush({ ...NICHTS, rangliste: ALLES.rangliste });
      fixture.componentInstance.neuLaden();
      http.expectOne({ method: 'GET', url: URL }).flush(NICHTS);

      expect(zahlen).toEqual([0, 1, 0]);
      fixture.destroy();
    });

    it('gibt jeder Instanz eine eigene Überschrift-id für aria-labelledby', () => {
      starten(ALLES);

      const abschnitt = el().querySelector('[data-testid="widerrufbar"]') as HTMLElement;
      const id = abschnitt.getAttribute('aria-labelledby') as string;
      expect(id).toMatch(/^widerrufbar-titel-\d+$/);
      expect(el().querySelector(`#${id}`)?.textContent).toContain('Einwilligungen ausschalten');
    });

    it('frischt nach dem Ausschalten von Spielgefühl oder Punkten die Spielgefühl-Karte auf', () => {
      starten(ALLES, { punkteHaekchenDaneben: false });

      (zeile('punkte')?.querySelector('button') as HTMLButtonElement).click();
      http.expectOne({ method: 'PUT', url: `${BASIS}/usage/users/me/punkte-einwilligung` }).flush(null, { status: 204, statusText: 'No Content' });
      http.expectOne({ method: 'GET', url: URL }).flush({ ...ALLES, punkte: null, spielgefuehl: null });

      expect(spielLaden).toHaveBeenCalledWith(true);
    });

    it('Fokus nach dem Ausschalten auch dann richtig, wenn ein älteres Nachladen noch unterwegs war', fakeAsync(() => {
      starten({ ...NICHTS, rangliste: ALLES.rangliste, abzeichen: ALLES.abzeichen });
      document.body.appendChild(el());

      tick(NACHLADEN_MS);
      const alt = http.expectOne({ method: 'GET', url: URL });
      (zeile('rangliste')?.querySelector('button') as HTMLButtonElement).click();
      http.expectOne({ method: 'PUT', url: `${BASIS}/rangliste/einwilligung` }).flush(null, { status: 204, statusText: 'No Content' });
      // Der alte Lauf kommt mit der Zeile von vor dem Ausschalten zurück.
      alt.flush({ ...NICHTS, rangliste: ALLES.rangliste, abzeichen: ALLES.abzeichen });
      http.expectOne({ method: 'GET', url: URL }).flush({ ...NICHTS, abzeichen: ALLES.abzeichen });
      fixture.detectChanges();

      expect(zeile('rangliste')).toBeNull();
      expect(document.activeElement).toBe(zeile('abzeichen')?.querySelector('button') ?? null);
      el().remove();
      fixture.destroy();
    }));
  });

  it('kommt mit einem älteren Backend ohne team_oeffentlich zurecht', () => {
    const { team_oeffentlich: _weg, ...ohne } = ALLES;
    starten(ohne);

    expect(zeile('team_oeffentlich')).toBeNull();
    expect(zeile('abzeichen')).not.toBeNull();
  });
});
