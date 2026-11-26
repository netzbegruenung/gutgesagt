import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { BehaviorSubject, of } from 'rxjs';

import { environment } from '../../environments/environment';
import { PunkteEinwilligungService, PunkteEinwilligungStand } from '../shared/punkte-einwilligung/punkte-einwilligung.service';
import { Widerrufbar, WiderrufbarComponent } from './widerrufbar.component';

const BASIS = `${environment.baseUrl}/api/v1`;
const URL = `${BASIS}/usage/users/me/widerrufbar`;
const NICHTS: Widerrufbar = { spielgefuehl: null, punkte: null, rangliste: null, abzeichen: null };
const ALLES: Widerrufbar = {
  spielgefuehl: { stufe: 'rangliste', titel: 'In der Saison-Rangliste mitspielen', wortlaut: 'spielgefuehl-2026-11-26' },
  punkte: { wortlaut: '2026-11-13' },
  rangliste: { wortlaut: 'rangliste-2026-11-20' },
  abzeichen: { wortlaut: '2026-11-09' },
};

/** Widerruf jederzeit, auch bei ausgeschalteten Schaltern (Art. 7 Abs. 3 DSGVO). */
describe('WiderrufbarComponent', () => {
  let fixture: ComponentFixture<WiderrufbarComponent>;
  let http: HttpTestingController;
  let punkteStand: BehaviorSubject<PunkteEinwilligungStand | null | undefined>;
  let punkteLaden: jasmine.Spy;

  function starten(stand: Widerrufbar) {
    punkteStand = new BehaviorSubject<PunkteEinwilligungStand | null | undefined>(null);
    punkteLaden = jasmine.createSpy('laden').and.returnValue(of(null));
    TestBed.configureTestingModule({
      imports: [WiderrufbarComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: PunkteEinwilligungService, useValue: { stand$: punkteStand, laden: punkteLaden } },
      ],
    });
    fixture = TestBed.createComponent(WiderrufbarComponent);
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
    const knoepfe = Array.from(el().querySelectorAll('button')).map((b) => b.textContent?.trim());
    expect(knoepfe).toEqual(['Ausschalten', 'Ausschalten', 'Ausschalten', 'Ausschalten']);
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
    ['rangliste', `${BASIS}/rangliste/einwilligung`, { teilnehmen: false, mit_anzeigename: false, wortlaut: 'rangliste-2026-11-20' }],
    ['abzeichen', `${BASIS}/usage/users/me/abzeichen-sichtbarkeit`, { zeigen: false, wortlaut: '2026-11-09' }],
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
    });
  }

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
      ],
    });
    fixture = TestBed.createComponent(WiderrufbarComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne({ method: 'GET', url: URL }).flush(null, { status: 500, statusText: 'Fehler' });
    fixture.detectChanges();

    expect(el().querySelector('[data-testid="widerrufbar"]')).toBeNull();
  });
});
