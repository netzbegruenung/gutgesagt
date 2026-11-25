import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { SAISON_NACHLADEN_MS, SaisonZielComponent } from './saison-ziel.component';
import { environment } from '../../environments/environment';

const URL = `${environment.baseUrl}/api/v1/saisons/aktuell`;

describe('SaisonZielComponent', () => {
  let fixture: ComponentFixture<SaisonZielComponent>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SaisonZielComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
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

  it('zeigt nichts, solange der Schalter aus ist (404)', () => {
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
    expect(balken.getAttribute('aria-labelledby')).toBe('saison-ziel-titel');
    expect(balken.getAttribute('aria-describedby')).toBe('saison-ziel-stand');
  });

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
