import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { of } from 'rxjs';

import { SAISON_NACHLADEN_MS, SaisonZielComponent } from './saison-ziel.component';
import { environment } from '../../environments/environment';
import { FunktionenService } from '../services/funktionen.service';

const URL = `${environment.baseUrl}/api/v1/saisons/aktuell`;
const METRICS = `${environment.baseUrl}/api/v1/metrics/getMetrics`;
/** Bestand wie /getMetrics ihn meldet */
const BESTAND = { content_count: 1200, statement_count: 263, commentary_count: 812, reference_count: 40 };

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

  function bestandBereich(): HTMLElement | null {
    return fixture.nativeElement.querySelector('[data-testid="bestandszahl"]');
  }

  it('zeigt nichts, wenn der Server den Schalter als aus meldet (200, aktiv false)', () => {
    schalter = null;
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: null, aktiv: false });
    fixture.detectChanges();
    http.expectNone(METRICS);
    expect(bereich()).toBeNull();
    expect(bestandBereich()).toBeNull();
  });

  it('zeigt nichts bei einem 404 eines älteren Backends', () => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ detail: 'Nicht gefunden' }, { status: 404, statusText: 'Not Found' });
    fixture.detectChanges();
    http.expectNone(METRICS);
    expect(bereich()).toBeNull();
    expect(bestandBereich()).toBeNull();
  });

  it('fragt bei Schalter sicher aus auch den Bestand nicht', () => {
    schalter = false;
    fixture.detectChanges();
    http.expectNone(METRICS);
    expect(bestandBereich()).toBeNull();
  });

  it('unter der Schwelle: Bestandszahl statt Balken, abgerundet und ohne Personen', () => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: null });
    http.expectOne(METRICS).flush(BESTAND);
    fixture.detectChanges();

    expect(bereich()).toBeNull();
    expect(bestandBereich()).not.toBeNull();
    expect(text()).toContain('Schon 800 Antworten auf 250 Sprüche');
    expect(text()).toContain('Fertig zum Kopieren und Anpassen.');
    expect(text()).not.toMatch(/Menschen|Personen|Konten|Nutzer|genutzt|Woche/);
    expect(fixture.nativeElement.querySelector('progress')).toBeNull();
    expect(bestandBereich()!.getAttribute('aria-labelledby')).toBe('bestandszahl-titel');
  });

  it('zeigt bei zu wenig Bestand nichts statt einer kleinen Zahl', () => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: null });
    http.expectOne(METRICS).flush({ ...BESTAND, commentary_count: 4, statement_count: 2 });
    fixture.detectChanges();
    expect(bestandBereich()).toBeNull();
  });

  it('zeigt nichts, wenn der Bestand schon beim ersten Laden fehlschlägt', () => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: null });
    http.expectOne(METRICS).flush('kaputt', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    expect(bestandBereich()).toBeNull();
    expect(bereich()).toBeNull();
  });

  it('behält die Bestandszahl, wenn die Zählung einmal 0 meldet (gescheiterte Zählung)', fakeAsync(() => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: null });
    http.expectOne(METRICS).flush(BESTAND);
    tick(SAISON_NACHLADEN_MS);
    http.expectOne(URL).flush({ balken: null });
    http.expectOne(METRICS).flush({ ...BESTAND, commentary_count: 0 });
    fixture.detectChanges();
    expect(text()).toContain('Schon 800 Antworten auf 250 Sprüche');
    fixture.destroy();
  }));

  it('Saison vorbei und Bestand kaputt: kein veralteter Balken', fakeAsync(() => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: { name: 'Winter 26', ziel: 100, erreicht: 10 } });
    fixture.detectChanges();
    expect(bereich()).not.toBeNull();
    tick(SAISON_NACHLADEN_MS);
    http.expectOne(URL).flush({ balken: null });
    http.expectOne(METRICS).flush('kaputt', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    expect(bereich()).toBeNull();
    fixture.destroy();
  }));

  it('Einzahl bei einem Spruch', () => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: null });
    http.expectOne(METRICS).flush({ ...BESTAND, commentary_count: 12, statement_count: 1 });
    fixture.detectChanges();
    expect(text()).toContain('Schon 10 Antworten auf 1 Spruch');
  });

  it('mit öffentlichem Balken keine Bestandszahl und keine Abfrage dafür', () => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: { name: 'Winter 26', ziel: 100, erreicht: 10 } });
    http.expectNone(METRICS);
    fixture.detectChanges();
    expect(bestandBereich()).toBeNull();
    expect(bereich()).not.toBeNull();
  });

  it('wechselt von selbst von der Bestandszahl zum Balken, sobald die Schwelle erreicht ist', fakeAsync(() => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: null });
    http.expectOne(METRICS).flush(BESTAND);
    fixture.detectChanges();
    expect(bestandBereich()).not.toBeNull();

    tick(SAISON_NACHLADEN_MS);
    http.expectOne(URL).flush({ balken: { name: 'Winter 26', ziel: 100, erreicht: 10 } });
    fixture.detectChanges();
    expect(bestandBereich()).toBeNull();
    expect(bereich()).not.toBeNull();
    fixture.destroy();
  }));

  it('behält die Bestandszahl, wenn der Bestand einmal nicht lädt', fakeAsync(() => {
    fixture.detectChanges();
    http.expectOne(URL).flush({ balken: null });
    http.expectOne(METRICS).flush(BESTAND);
    tick(SAISON_NACHLADEN_MS);
    http.expectOne(URL).flush({ balken: null });
    http.expectOne(METRICS).flush('kaputt', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    expect(text()).toContain('Schon 800 Antworten auf 250 Sprüche');
    fixture.destroy();
  }));

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
    http.expectOne(URL).flush({ balken: null, aktiv: false });
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
