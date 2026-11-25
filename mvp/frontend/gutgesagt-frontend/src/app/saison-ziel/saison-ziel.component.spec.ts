import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { of } from 'rxjs';

import { SAISON_NACHLADEN_MS, SaisonZielComponent } from './saison-ziel.component';
import { environment } from '../../environments/environment';
import { FunktionenService } from '../services/funktionen.service';

const URL = `${environment.baseUrl}/api/v1/saisons/aktuell`;

describe('SaisonZielComponent', () => {
  let fixture: ComponentFixture<SaisonZielComponent>;
  let http: HttpTestingController;
  /** Was FunktionenService zum Schalter saison_ziel meldet; null: unbekannt. */
  let schalter: boolean | null;
  let gefragt: string[];

  beforeEach(async () => {
    schalter = true;
    gefragt = [];
    await TestBed.configureTestingModule({
      imports: [SaisonZielComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: FunktionenService,
          useValue: {
            stand$: (name: string) => {
              gefragt.push(name);
              return of(schalter);
            },
          },
        },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(SaisonZielComponent);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    fixture.destroy();
    http.verify();
  });

  function text(): string {
    return (fixture.nativeElement as HTMLElement).textContent?.replace(/\s+/g, ' ').trim() ?? '';
  }

  function bereich(): HTMLElement | null {
    return fixture.nativeElement.querySelector('[data-testid="saison-ziel"]');
  }

  it('fragt den Endpunkt nicht, solange der Schalter sicher aus ist (Saal, kein 404)', () => {
    schalter = false;
    fixture.detectChanges();
    http.expectNone(URL);
    expect(gefragt).toEqual(['saison_ziel']);
    expect(bereich()).toBeNull();
  });

  it('zeigt nichts, wenn der Server den Schalter als aus meldet (200, aktiv false)', () => {
    schalter = null;
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: null, aktiv: false });
    fixture.detectChanges();
    expect(bereich()).toBeNull();
  });

  it('zeigt nichts bei einem 404 eines älteren Backends', () => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ detail: 'Nicht gefunden' }, { status: 404, statusText: 'Not Found' });
    fixture.detectChanges();
    expect(bereich()).toBeNull();
  });

  it('zeigt nichts unter der Schwelle', () => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: null });
    fixture.detectChanges();
    expect(bereich()).toBeNull();
  });

  it('zeigt Widerspruchs-Wochen ehrlich, nie Menschen', () => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: { name: 'Frühjahr 27', ziel: 1000, erreicht: 312 } });
    fixture.detectChanges();

    expect(bereich()).not.toBeNull();
    expect(text()).toContain('Saison Frühjahr 27: Woche für Woche zusammen 312-mal öffentlich widersprochen.');
    expect(text()).toContain('312 von 1.000 Widerspruchs-Wochen');
    expect(text()).not.toContain('Menschen');
    const balken: HTMLProgressElement = fixture.nativeElement.querySelector('progress');
    expect(balken.max).toBe(1000);
    expect(balken.value).toBe(312);
    expect(balken.getAttribute('aria-label')).toBe('Gemeinschaftsziel der Saison Frühjahr 27');
    expect(balken.getAttribute('aria-describedby')).toBe('saison-ziel-stand');
  });

  it('am Saisonstart: Startsatz statt „0-mal“, kein leerer Balken', () => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: { name: 'Winter 26/27', ziel: 500, erreicht: 0 } });
    fixture.detectChanges();

    expect(bereich()).not.toBeNull();
    expect(text()).toContain(
      'Saison Winter 26/27 hat begonnen: Jede gepostete Antwort zeigt öffentlich, dass jemand widerspricht.',
    );
    // Ehrlich: ohne Konto zählt nichts, und je Person nur einmal je Woche
    expect(text()).toContain(
      'Wer nach dem Kopieren mit Konto „Ja, gepostet“ meldet, zählt diese Woche fürs gemeinsame Ziel: 500 Widerspruchs-Wochen.',
    );
    expect(text()).not.toMatch(/Jedes „Ja, gepostet“/);
    expect(text()).not.toMatch(/\b0-mal|\b0 von/);
    expect(text()).not.toMatch(/verfehlt|noch \d+ Tage|bis zum|endet/);
    expect(fixture.nativeElement.querySelector('progress')).toBeNull();
    // Die Überschrift benennt den Bereich weiter für Screenreader
    expect(bereich()!.getAttribute('aria-labelledby')).toBe('saison-ziel-titel');
  });

  it('wechselt nach der ersten gezählten Woche von selbst zum Balken', fakeAsync(() => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: { name: 'Winter 26/27', ziel: 500, erreicht: 0 } });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('progress')).toBeNull();

    tick(SAISON_NACHLADEN_MS);
    http.expectOne(URL).flush({ balken: { name: 'Winter 26/27', ziel: 500, erreicht: 1 } });
    fixture.detectChanges();
    expect(text()).toContain('Woche für Woche zusammen 1-mal öffentlich widersprochen.');
    const balken: HTMLProgressElement = fixture.nativeElement.querySelector('progress');
    expect(balken.value).toBe(1);
    fixture.destroy();
  }));

  it('nennt kein Ende und keine Frist', () => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: { name: 'Winter 26', ziel: 100, erreicht: 10 } });
    fixture.detectChanges();
    expect(text()).not.toMatch(/noch \d+ Tage|bis zum|endet/);
  });

  it('über dem Ziel: Balken voll, Dank statt Zahl über 100 %', () => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: { name: 'Winter 26', ziel: 100, erreicht: 130 } });
    fixture.detectChanges();
    const balken: HTMLProgressElement = fixture.nativeElement.querySelector('progress');
    expect(balken.value).toBe(100);
    expect(text()).toContain('Gemeinsames Ziel geschafft');
  });

  it('lädt selbst nach: Einschalten kommt ohne Neuladen an', fakeAsync(() => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: null });
    fixture.detectChanges();
    expect(bereich()).toBeNull();

    tick(SAISON_NACHLADEN_MS);
    http.expectOne(URL).flush({ balken: { name: 'Winter 26', ziel: 100, erreicht: 10 } });
    fixture.detectChanges();
    expect(bereich()).not.toBeNull();
    fixture.destroy();
  }));

  it('behält nach einem Fehler den letzten Stand', fakeAsync(() => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: { name: 'Winter 26', ziel: 100, erreicht: 10 } });
    tick(SAISON_NACHLADEN_MS);
    http.expectOne(URL).flush('kaputt', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    expect(bereich()).not.toBeNull();
    fixture.destroy();
  }));
});
