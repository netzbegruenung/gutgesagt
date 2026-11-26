import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';

import {
  BESTAND_NACHLADEN_MS,
  HERO_UNTERZEILE,
  HeroUnterzeileComponent,
  heuteInDeutschland,
  zuwachsText,
} from './hero-unterzeile.component';
import { environment } from '../../environments/environment';
import { STILLE_ABFRAGE } from '../shared/selbst-nachladen';

const METRICS = `${environment.baseUrl}/api/v1/metrics/getMetrics`;
/** Bestand wie /getMetrics ihn meldet */
const BESTAND = { content_count: 1200, statement_count: 263, commentary_count: 812, reference_count: 40 };
/** 26.11.2026, 10 Uhr in Deutschland */
const JETZT = new Date('2026-11-26T09:00:00Z');

describe('zuwachsText', () => {
  it('ab 3 neuen die genaue Zahl', () => {
    expect(zuwachsText({ neu_7_tage: 12, zuletzt_ergaenzt: null }, JETZT)).toBe('12 neu in 7 Tagen');
    expect(zuwachsText({ neu_7_tage: 3, zuletzt_ergaenzt: null }, JETZT)).toBe('3 neu in 7 Tagen');
    expect(zuwachsText({ neu_7_tage: 1200, zuletzt_ergaenzt: null }, JETZT)).toBe('1.200 neu in 7 Tagen');
  });

  it('nie „0 neu“ oder eine kleine Zahl, sondern der Tag', () => {
    expect(zuwachsText({ neu_7_tage: 2, zuletzt_ergaenzt: '2026-11-26' }, JETZT)).toBe('zuletzt ergänzt heute');
    expect(zuwachsText({ neu_7_tage: null, zuletzt_ergaenzt: '2026-11-25' }, JETZT)).toBe('zuletzt ergänzt gestern');
    expect(zuwachsText({ neu_7_tage: null, zuletzt_ergaenzt: '2026-11-24' }, JETZT)).toBe('zuletzt ergänzt am 24.11.');
    expect(zuwachsText({ neu_7_tage: null, zuletzt_ergaenzt: '2026-11-19' }, JETZT)).toBe('zuletzt ergänzt am 19.11.');
    // ohne führende Null
    expect(zuwachsText({ neu_7_tage: null, zuletzt_ergaenzt: '2026-09-04' }, new Date('2026-09-08T09:00:00Z'))).toBe(
      'zuletzt ergänzt am 4.9.',
    );
    expect(zuwachsText({ neu_7_tage: 0, zuletzt_ergaenzt: null }, JETZT)).toBeNull();
  });

  it('älter als 7 Tage, ohne Angabe oder unlesbar: nichts', () => {
    expect(zuwachsText({ neu_7_tage: null, zuletzt_ergaenzt: '2026-11-18' }, JETZT)).toBeNull();
    expect(zuwachsText(null, JETZT)).toBeNull();
    expect(zuwachsText(undefined, JETZT)).toBeNull();
    expect(zuwachsText({ neu_7_tage: null, zuletzt_ergaenzt: 'gestern' }, JETZT)).toBeNull();
  });

  it('Tag in deutscher Zeit, auch kurz nach Mitternacht', () => {
    // 23:30 UTC am 25.11. ist in Deutschland schon der 26.11.
    expect(heuteInDeutschland(new Date('2026-11-25T23:30:00Z'))).toBe('2026-11-26');
    expect(zuwachsText({ neu_7_tage: null, zuletzt_ergaenzt: '2026-11-26' }, new Date('2026-11-25T23:30:00Z'))).toBe(
      'zuletzt ergänzt heute',
    );
  });

  it('nie eine Uhrzeit', () => {
    expect(zuwachsText({ neu_7_tage: null, zuletzt_ergaenzt: '2026-11-24' }, JETZT)).not.toMatch(/\d:\d|Uhr/);
  });
});

describe('HeroUnterzeileComponent', () => {
  let fixture: ComponentFixture<HeroUnterzeileComponent>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HeroUnterzeileComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(HeroUnterzeileComponent);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    fixture.destroy();
    http.verify();
  });

  /** Sichtbarer Text, ohne den Linkzweck nur für Screenreader */
  function text(): string {
    const kopie = (fixture.nativeElement as HTMLElement).cloneNode(true) as HTMLElement;
    kopie.querySelectorAll('.visually-hidden').forEach((e) => e.remove());
    return kopie.textContent?.replace(/\s+/g, ' ').trim() ?? '';
  }

  function zuwachsLink(): HTMLAnchorElement | null {
    return fixture.nativeElement.querySelector('[data-testid="hero-zuwachs"]');
  }

  function laden(antwort: object): void {
    fixture.detectChanges();
    http.expectOne(METRICS).flush(antwort);
    fixture.detectChanges();
  }

  it('zeigt bis zur Antwort die bisherige Unterzeile', () => {
    fixture.detectChanges();
    expect(text()).toBe(HERO_UNTERZEILE);
    http.expectOne(METRICS);
  });

  it('Bestand und Zuwachs, verlinkt auf „Frisch aus der Community“, Pflänzchen nur für Augen', () => {
    fixture.detectChanges();
    const anfrage = http.expectOne(METRICS);
    // Erster Abruf darf aus dem Frontend-Cache kommen (Rückkehr auf die Startseite)
    expect(anfrage.request.context.get(STILLE_ABFRAGE)).toBeFalse();
    anfrage.flush({ ...BESTAND, zuwachs: { neu_7_tage: 12, zuletzt_ergaenzt: null } });
    fixture.detectChanges();

    expect(text()).toBe('800 Antworten auf 250 Sprüche – 12 neu in 7 Tagen 🌱');
    expect(text()).not.toContain('bewährte');
    const link = zuwachsLink()!;
    expect(link.getAttribute('href')).toBe('/search#recent-content');
    expect(link.querySelector('[aria-hidden="true"]')!.textContent!.trim()).toBe('🌱');
    // Linkzweck für Screenreader (WCAG 2.4.4)
    expect(link.querySelector('.visually-hidden')!.textContent).toContain('Frisch aus der Community');
    expect(text()).not.toMatch(/Menschen|Personen|Konten|Nutzer|genutzt/);
  });

  it('unter 3 neuen der Tag, ohne Uhrzeit', () => {
    jasmine.clock().install();
    jasmine.clock().mockDate(JETZT);
    try {
      laden({ ...BESTAND, zuwachs: { neu_7_tage: null, zuletzt_ergaenzt: '2026-11-25' } });
      expect(text()).toBe('800 Antworten auf 250 Sprüche – zuletzt ergänzt gestern 🌱');
    } finally {
      jasmine.clock().uninstall();
    }
  });

  it('ohne Zuwachs (Schalter aus, älterer Server, nichts Neues): „aus der Community.“ ohne Link', () => {
    laden(BESTAND);
    expect(text()).toBe('800 Antworten auf 250 Sprüche – aus der Community.');
    expect(zuwachsLink()).toBeNull();
  });

  it('Umbruch nur nach dem Gedankenstrich: beide Teile brechen selbst nicht um', () => {
    laden({ ...BESTAND, zuwachs: { neu_7_tage: 12, zuletzt_ergaenzt: null } });
    const teile = Array.from(fixture.nativeElement.querySelectorAll('.teil')) as HTMLElement[];
    teile.forEach((t) => t.querySelectorAll('.visually-hidden').forEach((e) => e.remove()));
    expect(teile.map((t) => t.textContent!.replace(/\s+/g, ' ').trim())).toEqual([
      '800 Antworten auf 250 Sprüche –',
      '12 neu in 7 Tagen 🌱',
    ]);
    expect(teile.every((t) => getComputedStyle(t).whiteSpace === 'nowrap')).toBeTrue();
  });

  it('der Sprung landet auf „Frisch aus der Community“ mit Fokus auf der Überschrift', () => {
    const ziel = document.createElement('section');
    ziel.id = 'recent-content';
    const titel = document.createElement('h2');
    titel.tabIndex = -1;
    ziel.appendChild(titel);
    document.body.appendChild(ziel);
    try {
      laden({ ...BESTAND, zuwachs: { neu_7_tage: 12, zuletzt_ergaenzt: null } });
      const klick = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 });
      zuwachsLink()!.dispatchEvent(klick);
      expect(klick.defaultPrevented).toBeTrue();
      expect(document.activeElement).toBe(titel);
    } finally {
      ziel.remove();
    }
  });

  it('bei zu wenig Bestand die bisherige Unterzeile', () => {
    laden({ ...BESTAND, commentary_count: 4, statement_count: 2 });
    expect(text()).toBe(HERO_UNTERZEILE);
  });

  it('bei einem Fehler ohne letzte Zahl die bisherige Unterzeile', () => {
    fixture.detectChanges();
    http.expectOne(METRICS).flush('kaputt', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    expect(text()).toBe(HERO_UNTERZEILE);
  });

  it('behält die letzte Zeile nach einer 0 oder einem Fehler (gescheiterte Zählung)', fakeAsync(() => {
    fixture.detectChanges();
    http.expectOne(METRICS).flush({ ...BESTAND, zuwachs: { neu_7_tage: 12, zuletzt_ergaenzt: null } });
    tick(BESTAND_NACHLADEN_MS);
    const nachladen = http.expectOne(METRICS);
    // Nachladen: still und frisch
    expect(nachladen.request.context.get(STILLE_ABFRAGE)).toBeTrue();
    nachladen.flush({ ...BESTAND, commentary_count: 0 });
    fixture.detectChanges();
    expect(text()).toContain('800 Antworten auf 250 Sprüche – 12 neu in 7 Tagen');
    tick(BESTAND_NACHLADEN_MS);
    http.expectOne(METRICS).flush({ ...BESTAND, statement_count: 0 });
    fixture.detectChanges();
    expect(text()).toContain('12 neu in 7 Tagen');
    tick(BESTAND_NACHLADEN_MS);
    http.expectOne(METRICS).flush('kaputt', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    expect(text()).toContain('12 neu in 7 Tagen');
    fixture.destroy();
  }));

  it('lädt selbst nach: neuer Zuwachs kommt ohne Neuladen an', fakeAsync(() => {
    fixture.detectChanges();
    http.expectOne(METRICS).flush(BESTAND);
    tick(BESTAND_NACHLADEN_MS);
    http.expectOne(METRICS).flush({ ...BESTAND, commentary_count: 1003, zuwachs: { neu_7_tage: 5, zuletzt_ergaenzt: null } });
    fixture.detectChanges();
    expect(text()).toBe('1.000 Antworten auf 250 Sprüche – 5 neu in 7 Tagen 🌱');
    fixture.destroy();
  }));
});
