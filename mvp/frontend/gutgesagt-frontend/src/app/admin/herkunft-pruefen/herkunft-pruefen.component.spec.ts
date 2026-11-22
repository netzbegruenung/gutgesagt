import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { HerkunftPruefenComponent } from './herkunft-pruefen.component';
import { HerkunftPruefenStand } from './herkunft-pruefen.service';
import { environment } from '../../../environments/environment';

const URL = `${environment.baseUrl}/api/v1/herkunft-pruefen`;

const AUS: HerkunftPruefenStand = { aktiv: false, laeuft: false, geprueft: 0, letzter_lauf: null, auffaellig_gesamt: 0, auffaellig: [] };

const AN: HerkunftPruefenStand = {
  aktiv: true,
  laeuft: false,
  geprueft: 12,
  letzter_lauf: '2026-11-22T03:00:00Z',
  auffaellig_gesamt: 2,
  auffaellig: [
    {
      herkunft_id: 'a',
      adresse: 'https://quelle.example/weg',
      ergebnis: 'tot',
      http_status: 404,
      ziel: null,
      geprueft_am: '2026-11-22T03:00:00Z',
      auffaellig_seit: '2026-11-20T03:00:00Z',
    },
    {
      herkunft_id: 'b',
      adresse: 'https://quelle.example/alt',
      ergebnis: 'umgezogen',
      http_status: 200,
      ziel: 'https://neu.example/seite',
      geprueft_am: '2026-11-22T03:00:00Z',
      auffaellig_seit: '2026-11-22T03:00:00Z',
    },
  ],
};

describe('HerkunftPruefenComponent', () => {
  let fixture: ComponentFixture<HerkunftPruefenComponent>;
  let http: HttpTestingController;

  beforeEach(async () => {
    spyOnProperty(document, 'visibilityState', 'get').and.returnValue('hidden');
    await TestBed.configureTestingModule({
      imports: [HerkunftPruefenComponent, NoopAnimationsModule],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(HerkunftPruefenComponent);
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

  it('zeigt bei ausgeschaltetem Schalter gar nichts, auch keine leere Karte', () => {
    http.expectOne(URL).flush(AUS);
    fixture.detectChanges();

    expect(el().querySelector('mat-card')).toBeNull();
    expect(el().textContent?.trim()).toBe('');
  });

  it('listet auffällige Links mit Symbol und Wort, Status und neuem Ziel', () => {
    http.expectOne(URL).flush(AN);
    fixture.detectChanges();

    const eintraege = Array.from(el().querySelectorAll('[data-testid="auffaellig"]'));
    expect(eintraege.length).toBe(2);
    expect(eintraege[0].textContent).toContain('Nicht gefunden (HTTP 404)');
    expect(eintraege[0].querySelector('mat-icon')?.textContent).toContain('link_off');
    expect(eintraege[1].textContent).toContain('Umgezogen');
    expect(eintraege[1].textContent).toContain('Jetzt: https://neu.example/seite');
    const link = eintraege[0].querySelector('a') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe('https://quelle.example/weg');
    expect(link.rel).toContain('noopener');
    expect(el().querySelector('[data-testid="zusammenfassung"]')?.textContent).toContain('12 Links geprüft, 2 auffällig');
  });

  it('sagt es, wenn alle Links gehen', () => {
    http.expectOne(URL).flush({ ...AN, auffaellig_gesamt: 0, auffaellig: [] });
    fixture.detectChanges();

    expect(el().textContent).toContain('Alle geprüften Links gehen.');
  });

  it('verlinkt ein gesperrtes Weiterleitungsziel nicht', () => {
    http.expectOne(URL).flush({
      ...AN,
      auffaellig_gesamt: 1,
      auffaellig: [{ ...AN.auffaellig[0], ergebnis: 'gesperrt', http_status: null, ziel: 'http://10.0.0.7/' }],
    });
    fixture.detectChanges();

    const eintrag = el().querySelector('[data-testid="auffaellig"]') as HTMLElement;
    expect(eintrag.textContent).toContain('Leitet weiter auf: http://10.0.0.7/');
    expect(Array.from(eintrag.querySelectorAll('a')).map((a) => a.getAttribute('href'))).toEqual([
      'https://quelle.example/weg',
    ]);
  });

  it('stößt mit „Jetzt prüfen“ einen Lauf an und lädt gleich nach', () => {
    http.expectOne(URL).flush(AN);
    fixture.detectChanges();

    (el().querySelector('button') as HTMLButtonElement).click();
    const lauf = http.expectOne(`${URL}/lauf`);
    expect(lauf.request.method).toBe('POST');
    lauf.flush(null, { status: 202, statusText: 'Accepted' });
    http.expectOne(URL).flush({ ...AN, laeuft: true });
    fixture.detectChanges();

    expect(el().textContent).toContain('Prüfung läuft');
    expect((el().querySelector('button') as HTMLButtonElement).disabled).toBeTrue();
  });
});
