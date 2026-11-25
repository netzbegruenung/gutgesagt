import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { BESTAND_NACHLADEN_MS, HERO_UNTERZEILE, HeroUnterzeileComponent } from './hero-unterzeile.component';
import { environment } from '../../environments/environment';
import { STILLE_ABFRAGE } from '../shared/selbst-nachladen';

const METRICS = `${environment.baseUrl}/api/v1/metrics/getMetrics`;
/** Bestand wie /getMetrics ihn meldet */
const BESTAND = { content_count: 1200, statement_count: 263, commentary_count: 812, reference_count: 40 };

describe('HeroUnterzeileComponent', () => {
  let fixture: ComponentFixture<HeroUnterzeileComponent>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HeroUnterzeileComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(HeroUnterzeileComponent);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    fixture.destroy();
    http.verify();
  });

  function text(): string {
    return (fixture.nativeElement as HTMLElement).textContent?.replace(/\s+/g, ' ').trim() ?? '';
  }

  it('zeigt bis zur Antwort die bisherige Unterzeile', () => {
    fixture.detectChanges();
    expect(text()).toBe(HERO_UNTERZEILE);
    http.expectOne(METRICS);
  });

  it('zeigt die Bestandszahl abgerundet, ohne Personen', () => {
    fixture.detectChanges();
    const anfrage = http.expectOne(METRICS);
    // Hintergrund-Abfrage: frisch statt aus dem Cache, nie Umleitung
    expect(anfrage.request.context.get(STILLE_ABFRAGE)).toBeTrue();
    anfrage.flush(BESTAND);
    fixture.detectChanges();
    expect(text()).toBe('800 bewährte Antworten auf 250 Sprüche – aus der Community.');
    expect(text()).not.toMatch(/Menschen|Personen|Konten|Nutzer|genutzt|Woche/);
  });

  it('Tausenderpunkt und Einzahl', () => {
    fixture.detectChanges();
    http.expectOne(METRICS).flush({ ...BESTAND, commentary_count: 1042, statement_count: 1 });
    fixture.detectChanges();
    expect(text()).toBe('1.000 bewährte Antworten auf 1 Spruch – aus der Community.');
  });

  it('bei zu wenig Bestand die bisherige Unterzeile', () => {
    fixture.detectChanges();
    http.expectOne(METRICS).flush({ ...BESTAND, commentary_count: 4, statement_count: 2 });
    fixture.detectChanges();
    expect(text()).toBe(HERO_UNTERZEILE);
  });

  it('bei einem Fehler ohne letzte Zahl die bisherige Unterzeile', () => {
    fixture.detectChanges();
    http.expectOne(METRICS).flush('kaputt', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    expect(text()).toBe(HERO_UNTERZEILE);
  });

  it('behält die letzte Zahl nach einem Fehler oder einer 0 (gescheiterte Zählung)', fakeAsync(() => {
    fixture.detectChanges();
    http.expectOne(METRICS).flush(BESTAND);
    tick(BESTAND_NACHLADEN_MS);
    http.expectOne(METRICS).flush({ ...BESTAND, commentary_count: 0 });
    fixture.detectChanges();
    expect(text()).toContain('800 bewährte Antworten');
    tick(BESTAND_NACHLADEN_MS);
    http.expectOne(METRICS).flush('kaputt', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    expect(text()).toContain('800 bewährte Antworten');
    fixture.destroy();
  }));

  it('lädt selbst nach: ein gewachsener Bestand kommt ohne Neuladen an', fakeAsync(() => {
    fixture.detectChanges();
    http.expectOne(METRICS).flush(BESTAND);
    tick(BESTAND_NACHLADEN_MS);
    http.expectOne(METRICS).flush({ ...BESTAND, commentary_count: 1003 });
    fixture.detectChanges();
    expect(text()).toContain('1.000 bewährte Antworten');
    fixture.destroy();
  }));
});
