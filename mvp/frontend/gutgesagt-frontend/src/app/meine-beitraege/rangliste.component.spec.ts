import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import { RANGLISTE_JA, RANGLISTE_NEIN, RanglisteComponent } from './rangliste.component';
import { RanglisteStand, RanglistenPlatz } from '../services/rangliste.service';
import { environment } from '../../environments/environment';

const URL = `${environment.baseUrl}/api/v1/rangliste`;
const WORTLAUT = 'Ich willige ausdrücklich ein, dass ich in der Rangliste der laufenden Saison erscheine …';

function stand(teil: Partial<RanglisteStand> = {}): RanglisteStand {
  return {
    gefragt: false,
    teilnehmen: null,
    mit_anzeigename: false,
    voraussetzungen: true,
    ranglistenname: 'Flinke Amsel 42',
    anzeigename: 'Kim B.',
    saison: { name: 'Winter 26', ende: '2027-02-28' },
    eigene_punkte: null,
    rangliste: null,
    vergangene: [],
    min_teilnehmende: 10,
    aktueller_wortlaut: { kennung: 'rangliste-2026-11-25', text: WORTLAUT },
    ...teil,
  };
}

function plaetze(ich = 3): RanglistenPlatz[] {
  return Array.from({ length: 10 }, (_, i) => ({ platz: i + 1, name: `Name ${i + 1}`, punkte: 100 - i, ich: i + 1 === ich }));
}

describe('RanglisteComponent', () => {
  let fixture: ComponentFixture<RanglisteComponent>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RanglisteComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideNoopAnimations(), provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(RanglisteComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => {
    fixture.destroy();
    http.verify();
  });

  function el(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function laden(daten: RanglisteStand): void {
    http.expectOne(URL).flush(daten);
    fixture.detectChanges();
  }

  function knopf(testid: string): HTMLButtonElement {
    return el().querySelector(`[data-testid="${testid}"]`) as HTMLButtonElement;
  }

  it('fragt einmal mit vollem Wortlaut und zwei gleichwertigen Knöpfen', () => {
    laden(stand());

    expect(el().querySelector('#rangliste-wortlaut')!.textContent).toContain(WORTLAUT);
    expect(knopf('ja').textContent!.trim()).toBe(RANGLISTE_JA);
    expect(knopf('nein').textContent!.trim()).toBe(RANGLISTE_NEIN);
    // Gleichwertig: dieselbe Art Knopf, keiner hervorgehoben
    expect(knopf('ja').className).toBe(knopf('nein').className);
    expect(el().querySelector('[data-testid="platz"]')).toBeNull();
  });

  it('zeigt nichts ohne Schalter (404)', () => {
    http.expectOne(URL).flush('', { status: 404, statusText: 'Not Found' });
    fixture.detectChanges();

    expect(el().querySelector('[data-testid="rangliste"]')).toBeNull();
  });

  it('fragt nicht ohne Voraussetzungen und nicht ohne laufende Saison', () => {
    laden(stand({ voraussetzungen: false }));
    expect(el().querySelector('[data-testid="frage"]')).toBeNull();

    fixture.componentInstance.stand = stand({ saison: null });
    fixture.componentInstance['cdr'].markForCheck();
    fixture.detectChanges();
    expect(el().querySelector('[data-testid="frage"]')).toBeNull();
  });

  it('Ja speichert mit der Kennung, ohne Anzeigename, und lädt nach', () => {
    laden(stand());

    knopf('ja').click();
    const anfrage = http.expectOne((r) => r.method === 'PUT' && r.url === `${URL}/einwilligung`);
    expect(anfrage.request.body).toEqual({ teilnehmen: true, mit_anzeigename: false, wortlaut: 'rangliste-2026-11-25' });
    anfrage.flush(null);
    fixture.detectChanges();

    expect(el().querySelector('[data-testid="frage"]')).toBeNull();
    expect(el().querySelector('.rangliste-status')!.textContent).toContain('Du bist in der Rangliste.');
    http.expectOne(URL).flush(stand({ gefragt: true, teilnehmen: true }));
  });

  it('zeigt Top 10 mit eigenem Platz und Namen erst ab zehn', () => {
    laden(stand({ gefragt: true, teilnehmen: true, eigene_punkte: 98, rangliste: { oben: plaetze(3), eigener: null, teilnehmende: 12 } }));

    const eintraege = el().querySelectorAll('[data-testid="platz"]');
    expect(eintraege.length).toBe(10);
    expect(eintraege[2].classList).toContain('ich');
    expect(eintraege[2].textContent).toContain('(du)');
    expect(el().textContent).toContain('12 machen mit');
  });

  it('zeigt den eigenen Platz unter den ersten zehn extra', () => {
    laden(
      stand({
        gefragt: true,
        teilnehmen: true,
        rangliste: { oben: plaetze(0), eigener: { platz: 14, name: 'Flinke Amsel 42', punkte: 3, ich: true }, teilnehmende: 20 },
      }),
    );

    expect(knopf('eigener').textContent).toContain('14.');
    expect(knopf('eigener').textContent).toContain('Flinke Amsel 42');
  });

  it('unter zehn Teilnehmenden nur der Hinweis und die eigenen Punkte', () => {
    laden(stand({ gefragt: true, teilnehmen: true, eigene_punkte: 30 }));

    expect(el().querySelector('[data-testid="platz"]')).toBeNull();
    expect(knopf('zu-wenige').textContent).toContain('sobald 10 mitmachen');
    expect(knopf('zu-wenige').textContent).toContain('Deine Punkte in dieser Saison: 30');
  });

  it('Anzeigename nur auf aktive Wahl, standardmäßig der Ranglistenname', () => {
    laden(stand({ gefragt: true, teilnehmen: true }));
    const radios = el().querySelectorAll<HTMLInputElement>('input[type="radio"]');
    expect(radios[0].checked).toBeTrue();
    expect(radios[1].checked).toBeFalse();

    radios[1].click();
    const anfrage = http.expectOne((r) => r.method === 'PUT');
    expect(anfrage.request.body).toEqual({ teilnehmen: true, mit_anzeigename: true, wortlaut: 'rangliste-2026-11-25' });
    anfrage.flush(null);
    http.expectOne(URL).flush(stand({ gefragt: true, teilnehmen: true, mit_anzeigename: true }));
  });

  it('setzt die Namenswahl zurück, wenn das Speichern scheitert', () => {
    laden(stand({ gefragt: true, teilnehmen: true }));
    const zufall = knopf('name-zufall') as unknown as HTMLInputElement;
    const anzeigename = knopf('name-anzeigename') as unknown as HTMLInputElement;

    anzeigename.click();
    expect(anzeigename.checked).toBeTrue();
    http.expectOne((r) => r.method === 'PUT').flush('', { status: 500, statusText: 'Fehler' });
    fixture.detectChanges();

    expect(el().querySelector('.rangliste-fehler')).not.toBeNull();
    expect(zufall.checked).toBeTrue();
    expect(anzeigename.checked).toBeFalse();
  });

  it('setzt auch die Rückkehr zum Ranglistennamen zurück, wenn das Speichern scheitert', () => {
    laden(stand({ gefragt: true, teilnehmen: true, mit_anzeigename: true }));
    const zufall = knopf('name-zufall') as unknown as HTMLInputElement;
    const anzeigename = knopf('name-anzeigename') as unknown as HTMLInputElement;
    expect(anzeigename.checked).toBeTrue();

    zufall.click();
    http.expectOne((r) => r.method === 'PUT').flush('', { status: 500, statusText: 'Fehler' });
    fixture.detectChanges();

    expect(anzeigename.checked).toBeTrue();
    expect(zufall.checked).toBeFalse();
  });

  it('zeigt einen Platzhalter, solange der Ranglistenname noch nicht vergeben ist', () => {
    laden(stand({ gefragt: true, teilnehmen: true, ranglistenname: null }));

    expect(el().querySelector('.rangliste-name')!.textContent).toContain('wird gerade vergeben');
  });

  it('„Aus der Rangliste nehmen“ wirkt sofort ohne Rückfrage', () => {
    laden(stand({ gefragt: true, teilnehmen: true, mit_anzeigename: true }));

    knopf('raus').click();
    const anfrage = http.expectOne((r) => r.method === 'PUT');
    expect(anfrage.request.body).toEqual({ teilnehmen: false, mit_anzeigename: false, wortlaut: 'rangliste-2026-11-25' });
    anfrage.flush(null);
    fixture.detectChanges();

    expect(knopf('ohne').textContent).toContain('Du bist nicht in der Rangliste.');
    http.expectOne(URL).flush(stand({ gefragt: true, teilnehmen: false }));
  });

  it('nach einem Nein erneut nur mit dem Wortlaut vor Augen', () => {
    laden(stand({ gefragt: true, teilnehmen: false }));
    expect(el().querySelector('[data-testid="frage"]')).toBeNull();

    (el().querySelector('.rangliste-doch') as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(el().querySelector('#rangliste-wortlaut')!.textContent).toContain(WORTLAUT);
  });

  it('ohne Voraussetzung nicht in der Liste, Widerruf bleibt erreichbar', () => {
    laden(stand({ gefragt: true, teilnehmen: true, voraussetzungen: false }));

    expect(el().querySelector('[data-testid="platz"]')).toBeNull();
    expect(knopf('ruhend').textContent).toContain('stehst aber gerade nicht darin');
    knopf('raus-ruhend').click();
    const anfrage = http.expectOne((r) => r.method === 'PUT');
    expect(anfrage.request.body.teilnehmen).toBeFalse();
    anfrage.flush(null);
    http.expectOne(URL).flush(stand({ gefragt: true, teilnehmen: false, voraussetzungen: false }));
  });

  it('vergangene Saisons nur als Summe', () => {
    laden(stand({ gefragt: true, teilnehmen: true, vergangene: [{ name: 'Herbst 26', punkte: 40 }] }));

    expect(knopf('vergangene').textContent).toContain('Herbst 26: 40 Punkte');
  });

  it('meldet einen Fehler beim Speichern', () => {
    laden(stand());

    knopf('nein').click();
    http.expectOne((r) => r.method === 'PUT').flush('', { status: 500, statusText: 'Fehler' });
    fixture.detectChanges();

    expect(el().querySelector('.rangliste-fehler')).not.toBeNull();
    expect(el().querySelector('[data-testid="frage"]')).not.toBeNull();
  });
});
