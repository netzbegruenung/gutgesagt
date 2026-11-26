import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { Subject, of } from 'rxjs';

import { SpielgefuehlComponent } from './spielgefuehl.component';
import { SpielgefuehlStand } from '../services/spielgefuehl.service';
import { EinwilligungsBudgetService } from '../shared/einwilligungs-budget/einwilligungs-budget.service';
import { EinwilligungsMoment } from '../shared/einwilligungs-budget/einwilligungs-budget';
import { environment } from '../../environments/environment';
import { FunktionenService } from '../services/funktionen.service';

const URL = `${environment.baseUrl}/api/v1/usage/users/me/spielgefuehl`;
const KENNUNG = 'spielgefuehl-2026-11-26';

function stand(teil: Partial<SpielgefuehlStand> = {}): SpielgefuehlStand {
  return {
    stufe: null,
    mit_anzeigename: null,
    ranglistenname: null,
    anzeigename: 'Kim B.',
    abzeichen_hinweis: null,
    aktueller_wortlaut: {
      kennung: KENNUNG,
      ueberschrift: 'Spielgefühl: Wie möchtest du mitspielen?',
      einleitung: 'Aus deiner Mitwirkung …',
      stufen: [
        { stufe: 'rangliste', titel: 'In der Saison-Rangliste mitspielen', text: 'Ich willige ausdrücklich ein … Rangliste' },
        { stufe: 'fuer_mich', titel: 'Nur für mich', text: 'Ich willige ausdrücklich ein … nur ich' },
        { stufe: 'aus', titel: 'Aus', text: 'Wir berechnen nichts für dich und zeigen nichts.' },
      ],
      absprachen: 'Für ‚Nur für mich‘ und ‚In der Saison-Rangliste mitspielen‘ willige ich außerdem ein: … Absprachen …',
      namenswahl: {
        frage: 'In der Rangliste als:',
        anzeigename: 'mein Anzeigename',
        zufallsname: 'ein Zufallsname',
        tipp: 'Datenschutz-Tipp: …',
        vorbelegung_anzeigename: null,
      },
      fuss: 'Verantwortlich ist …',
    },
    ...teil,
  };
}

describe('SpielgefuehlComponent', () => {
  let fixture: ComponentFixture<SpielgefuehlComponent>;
  let http: HttpTestingController;
  let moment: EinwilligungsMoment | null;
  let faellig: boolean;
  let budget: jasmine.SpyObj<EinwilligungsBudgetService> & { gewinn$: Subject<void> };
  /** Stand des Schalters laut FunktionenService: null unbekannt, false sicher aus. */
  let schalter: boolean | null;

  function erstellen(): void {
    fixture = TestBed.createComponent(SpielgefuehlComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  }

  beforeEach(async () => {
    moment = null;
    faellig = false;
    schalter = null;
    budget = Object.assign(jasmine.createSpyObj<EinwilligungsBudgetService>('Budget', ['moment', 'punkteFaellig', 'gezeigt']), {
      gewinn$: new Subject<void>(),
    });
    budget.moment.and.callFake(() => of(moment));
    budget.punkteFaellig.and.callFake(() => faellig);
    await TestBed.configureTestingModule({
      imports: [SpielgefuehlComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
        provideRouter([]),
        { provide: EinwilligungsBudgetService, useValue: budget },
        { provide: FunktionenService, useValue: { stand$: () => of(schalter) } },
      ],
    }).compileComponents();
  });

  afterEach(() => {
    fixture.destroy();
    http.verify();
  });

  function el(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function laden(daten: SpielgefuehlStand | (SpielgefuehlStand & { aktiv: false })): void {
    http.expectOne((r) => r.method === 'GET' && r.url === URL).flush(daten);
    fixture.detectChanges();
  }

  function knopf(testid: string): HTMLButtonElement {
    return el().querySelector(`[data-testid="${testid}"]`) as HTMLButtonElement;
  }

  function radio(testid: string): HTMLInputElement {
    return el().querySelector(`[data-testid="${testid}"]`) as HTMLInputElement;
  }

  it('zeigt nichts ohne Schalter (aktiv false)', () => {
    erstellen();
    laden({ ...stand(), aktiv: false });

    expect(el().querySelector('[data-testid="spielgefuehl"]')).toBeNull();
  });

  it('fragt den Endpunkt nicht, wenn der Schalter sicher aus ist', () => {
    schalter = false;
    erstellen();

    http.expectNone(URL);
    expect(el().querySelector('[data-testid="spielgefuehl"]')).toBeNull();
  });

  it('setzt die Namenswahl nach einem Fehler auf die gespeicherte zurück und behält den Fokus', () => {
    erstellen();
    laden(stand({ stufe: 'rangliste', mit_anzeigename: false, ranglistenname: 'Kluge Eule 11' }));

    radio('name-anzeigename').focus();
    radio('name-anzeigename').click();
    http.expectOne((r) => r.method === 'PUT' && r.url === URL).flush('', { status: 500, statusText: 'Fehler' });
    fixture.detectChanges();

    expect(radio('name-anzeigename').checked).toBeFalse();
    expect(radio('name-zufallsname').checked).toBeTrue();
    expect(document.activeElement).toBe(radio('name-anzeigename'));
    expect(el().textContent).toContain('Das hat nicht geklappt');
  });

  it('fragt mit drei gleich großen Knöpfen ohne Vorauswahl, Gemeinschaft zuerst', () => {
    erstellen();
    laden(stand());

    const knoepfe = Array.from(el().querySelectorAll<HTMLButtonElement>('.spielgefuehl-stufe > button'));
    expect(knoepfe.map((k) => k.getAttribute('data-testid'))).toEqual(['stufe-rangliste', 'stufe-fuer_mich', 'stufe-aus']);
    // Gleich gewichtet: dieselbe Art Knopf, keiner hervorgehoben
    expect(new Set(knoepfe.map((k) => k.className)).size).toBe(1);
    expect(el().textContent).toContain('Wir berechnen nichts für dich und zeigen nichts.');
    // Der Satz zu Absprachen direkt unter den drei Stufen
    const stufen = el().querySelector('.spielgefuehl-stufen')!;
    expect(stufen.nextElementSibling!.getAttribute('data-testid')).toBe('absprachen');
    expect(el().textContent).not.toContain('empfohlen');
    expect(el().querySelector('[data-testid="namenswahl"]')).toBeNull();
  });

  it('nennt einmal den Hinweis zu den Abzeichen', () => {
    erstellen();
    laden(stand({ abzeichen_hinweis: 'Abzeichen zeigen wir jetzt nur noch in der Rangliste.' }));

    expect(knopf('abzeichen-hinweis').textContent).toContain('nur noch in der Rangliste');
  });

  it('„Nur für mich“ speichert mit einem Klick', () => {
    erstellen();
    laden(stand());

    knopf('stufe-fuer_mich').click();
    const put = http.expectOne((r) => r.method === 'PUT' && r.url === URL);
    expect(put.request.body).toEqual({ stufe: 'fuer_mich', mit_anzeigename: null, wortlaut: KENNUNG });
    put.flush(null);
    http.expectOne((r) => r.method === 'GET' && r.url === URL).flush(stand({ stufe: 'fuer_mich' }));
    fixture.detectChanges();

    expect(knopf('stand').textContent).toContain('Nur für mich');
  });

  it('Rangliste verlangt die Namenswahl ohne Vorauswahl, Anzeigename zuerst', () => {
    erstellen();
    laden(stand());

    knopf('stufe-rangliste').click();
    fixture.detectChanges();
    http.expectNone((r) => r.method === 'PUT');

    const wahl = el().querySelector('[data-testid="namenswahl"]')!;
    const optionen = Array.from(wahl.querySelectorAll('input[type="radio"]')) as HTMLInputElement[];
    expect(optionen.map((o) => o.getAttribute('data-testid'))).toEqual(['wahl-anzeigename', 'wahl-zufallsname']);
    expect(optionen.some((o) => o.checked)).toBeFalse();
    expect(wahl.textContent).toContain('Datenschutz-Tipp');
    // Ohne Wahl nicht absendbar
    expect(knopf('mitspielen').disabled).toBeTrue();

    radio('wahl-zufallsname').click();
    fixture.detectChanges();
    expect(knopf('mitspielen').disabled).toBeFalse();
    knopf('mitspielen').click();
    const put = http.expectOne((r) => r.method === 'PUT' && r.url === URL);
    expect(put.request.body).toEqual({ stufe: 'rangliste', mit_anzeigename: false, wortlaut: KENNUNG });
    put.flush(null);
    http
      .expectOne((r) => r.method === 'GET' && r.url === URL)
      .flush(stand({ stufe: 'rangliste', mit_anzeigename: false, ranglistenname: 'Kluge Eule 11' }));
    fixture.detectChanges();

    expect(radio('name-zufallsname').checked).toBeTrue();
    expect(el().textContent).toContain('Kluge Eule 11');
    expect(knopf('wuerfeln')).not.toBeNull();
  });

  it('herabstufen wirkt mit einem Klick, heraufstufen zeigt erst den Wortlaut', () => {
    erstellen();
    laden(stand({ stufe: 'fuer_mich' }));

    knopf('wechsel-rangliste').click();
    fixture.detectChanges();
    http.expectNone((r) => r.method === 'PUT');
    expect(knopf('stufe-rangliste')).not.toBeNull();
    expect(el().querySelector('[data-testid="namenswahl"]')).not.toBeNull();
    knopf('abbrechen').click();
    fixture.detectChanges();

    knopf('wechsel-aus').click();
    const put = http.expectOne((r) => r.method === 'PUT' && r.url === URL);
    expect(put.request.body.stufe).toBe('aus');
    put.flush(null);
    http.expectOne((r) => r.method === 'GET' && r.url === URL).flush(stand({ stufe: 'aus' }));
    fixture.detectChanges();
    expect(knopf('stand').textContent).toContain('Aus');
  });

  it('stellt den Namen mit einem Klick um und würfelt neu', () => {
    erstellen();
    laden(stand({ stufe: 'rangliste', mit_anzeigename: false, ranglistenname: 'Kluge Eule 11' }));

    radio('name-anzeigename').click();
    const put = http.expectOne((r) => r.method === 'PUT' && r.url === URL);
    expect(put.request.body).toEqual({ stufe: 'rangliste', mit_anzeigename: true, wortlaut: KENNUNG });
    put.flush(null);
    http
      .expectOne((r) => r.method === 'GET' && r.url === URL)
      .flush(stand({ stufe: 'rangliste', mit_anzeigename: true, ranglistenname: 'Kluge Eule 11' }));
    fixture.detectChanges();

    knopf('wuerfeln').click();
    http.expectOne((r) => r.method === 'POST' && r.url === `${URL}/ranglistenname`).flush({ ranglistenname: 'Mutige Biene 12' });
    fixture.detectChanges();
    expect(el().textContent).toContain('Mutige Biene 12');
    expect(el().textContent).not.toContain('Kluge Eule 11');
  });

  it('mit Einwilligungs-Budget erst, wenn die Frage fällig ist', () => {
    moment = { abgestimmt: false, beantwortet: 0, konto_seit: null };
    faellig = false;
    erstellen();
    laden(stand());
    expect(el().querySelector('[data-testid="spielgefuehl"]')).toBeNull();

    faellig = true;
    budget.gewinn$.next();
    fixture.detectChanges();
    expect(knopf('stufe-aus')).not.toBeNull();
    expect(budget.gezeigt).toHaveBeenCalledWith('punkte');
  });
});
