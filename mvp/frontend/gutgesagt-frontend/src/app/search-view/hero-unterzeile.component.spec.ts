import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { MatDialog } from '@angular/material/dialog';
import { BehaviorSubject } from 'rxjs';
import { AuthService, UserInfo } from '../auth/auth.service';
import { HILFE_MITMACHEN } from '../help-dialog/help-dialog.component';

import {
  BESTAND_NACHLADEN_MS,
  HERO_UNTERZEILE,
  HeroUnterzeileComponent,
  NAECHSTE_FRAGE,
  zuwachsZahl,
} from './hero-unterzeile.component';
import { abgerundet } from './bestandszahl';
import { environment } from '../../environments/environment';
import { STILLE_ABFRAGE } from '../shared/selbst-nachladen';

const METRICS = `${environment.baseUrl}/api/v1/metrics/getMetrics`;
/** Bestand wie /getMetrics ihn meldet */
const BESTAND = { content_count: 1200, statement_count: 263, commentary_count: 812, reference_count: 40 };

describe('zuwachsZahl', () => {
  it('ab 3 neuen die Zahl, gerundet wie der Bestand', () => {
    expect(zuwachsZahl({ neu_7_tage: 12, zuletzt_ergaenzt: null })).toBe(10);
    expect(zuwachsZahl({ neu_7_tage: 3, zuletzt_ergaenzt: null })).toBe(3);
    expect(zuwachsZahl({ neu_7_tage: 1234, zuletzt_ergaenzt: null })).toBe(1200);
  });

  it('nie mehr neu als Bestand, auch nach einem Neustart mit Startbestand', () => {
    expect(zuwachsZahl({ neu_7_tage: 98, zuletzt_ergaenzt: null }, 98)).toBe(90);
    expect(zuwachsZahl({ neu_7_tage: 199, zuletzt_ergaenzt: null }, 250)).toBe(150);
    for (const [neu, bestand] of [[3, 10], [9, 12], [55, 70], [790, 999], [4000, 5001]]) {
      expect(zuwachsZahl({ neu_7_tage: neu, zuletzt_ergaenzt: null }, bestand)!).toBeLessThanOrEqual(abgerundet(bestand));
    }
  });

  it('nie „0 neu“: unter 3 neuen oder ohne Angabe nichts, auch nicht der Tag', () => {
    expect(zuwachsZahl({ neu_7_tage: 2, zuletzt_ergaenzt: '2026-11-26' })).toBeNull();
    expect(zuwachsZahl({ neu_7_tage: 0, zuletzt_ergaenzt: null })).toBeNull();
    expect(zuwachsZahl({ neu_7_tage: null, zuletzt_ergaenzt: '2026-11-25' })).toBeNull();
    expect(zuwachsZahl(null)).toBeNull();
    expect(zuwachsZahl(undefined)).toBeNull();
  });
});

describe('HeroUnterzeileComponent', () => {
  let fixture: ComponentFixture<HeroUnterzeileComponent>;
  let http: HttpTestingController;
  let nutzer: BehaviorSubject<UserInfo | null>;
  let dialog: jasmine.SpyObj<MatDialog>;

  beforeEach(async () => {
    // Die meisten Fälle angemeldet: dann führt die Frage auf Beitragen
    nutzer = new BehaviorSubject<UserInfo | null>({ isAuthenticated: true, userId: 'kim', userName: null, claims: null });
    dialog = jasmine.createSpyObj<MatDialog>('MatDialog', ['open']);
    await TestBed.configureTestingModule({
      imports: [HeroUnterzeileComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: AuthService, useValue: { userInfo$: nutzer } },
        { provide: MatDialog, useValue: dialog },
      ],
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

  function beitragenLink(): HTMLAnchorElement | null {
    return fixture.nativeElement.querySelector('[data-testid="hero-beitragen"]');
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

  it('Antworten und Zuwachs „diese Woche“, die Frage verlinkt auf Beitragen, ohne Emoji (Rundgang 28.11.)', () => {
    fixture.detectChanges();
    const anfrage = http.expectOne(METRICS);
    // Erster Abruf darf aus dem Frontend-Cache kommen (Rückkehr auf die Startseite)
    expect(anfrage.request.context.get(STILLE_ABFRAGE)).toBeFalse();
    anfrage.flush({ ...BESTAND, zuwachs: { neu_7_tage: 12, zuletzt_ergaenzt: null } });
    fixture.detectChanges();

    expect(text()).toBe('800 Antworten, 10 neu diese Woche – ist deine die nächste?');
    // Die Zahl der Sprüche fällt weg, das Pflänzchen auch
    expect(text()).not.toMatch(/Spr(u|ü)ch/);
    expect(text()).not.toContain('\u{1F331}');
    const link = beitragenLink()!;
    expect(link.textContent!.trim()).toBe(NAECHSTE_FRAGE);
    expect(link.getAttribute('href')).toBe('/contribute');
    expect(text()).not.toMatch(/Menschen|Personen|Konten|Nutzer|genutzt/);
  });

  it('abgemeldet: die Frage öffnet die Hilfe beim Abschnitt „Mitmachen“ statt der Anmeldung (Sebastian 28.11.)', () => {
    nutzer.next({ isAuthenticated: false, userId: null, userName: null, claims: null });
    laden({ ...BESTAND, zuwachs: { neu_7_tage: 12, zuletzt_ergaenzt: null } });

    expect(text()).toBe('800 Antworten, 10 neu diese Woche – ist deine die nächste?');
    expect(beitragenLink()).toBeNull();
    const knopf = fixture.nativeElement.querySelector('[data-testid="hero-mitmachen"]') as HTMLButtonElement;
    expect(knopf.tagName).toBe('BUTTON');
    expect(knopf.textContent!.trim()).toBe(NAECHSTE_FRAGE);
    expect(getComputedStyle(knopf).whiteSpace).toBe('nowrap');
    knopf.click();
    expect(dialog.open).toHaveBeenCalledTimes(1);
    expect(dialog.open.calls.mostRecent().args[1]!.data).toEqual({ abschnitt: HILFE_MITMACHEN });

    // Meldet sich jemand an, wird daraus der Link auf Beitragen
    nutzer.next({ isAuthenticated: true, userId: 'kim', userName: null, claims: null });
    fixture.detectChanges();
    expect(beitragenLink()!.getAttribute('href')).toBe('/contribute');
  });

  it('auch nach dem Startbestand-Import nie mehr neu als Antworten', () => {
    laden({ content_count: 98, statement_count: 38, commentary_count: 98, reference_count: 0, zuwachs: { neu_7_tage: 98, zuletzt_ergaenzt: null } });
    expect(text()).toBe('90 Antworten, 90 neu diese Woche – ist deine die nächste?');
  });

  it('unter 3 neuen „aus der Community“, auch wenn der letzte Kommentar von gestern ist', () => {
    laden({ ...BESTAND, zuwachs: { neu_7_tage: 2, zuletzt_ergaenzt: '2026-11-25' } });
    expect(text()).toBe('800 Antworten aus der Community – ist deine die nächste?');
    expect(text()).not.toContain('0 neu');
  });

  it('ohne Zuwachswert (älterer Server): „aus der Community“, die Frage bleibt verlinkt', () => {
    laden(BESTAND);
    expect(text()).toBe('800 Antworten aus der Community – ist deine die nächste?');
    expect(beitragenLink()).not.toBeNull();
  });

  it('Umbruch nur nach dem Gedankenstrich: beide Teile brechen selbst nicht um', () => {
    laden({ ...BESTAND, zuwachs: { neu_7_tage: 12, zuletzt_ergaenzt: null } });
    const teile = Array.from(fixture.nativeElement.querySelectorAll('.teil')) as HTMLElement[];
    expect(teile.map((t) => t.textContent!.replace(/\s+/g, ' ').trim())).toEqual([
      '800 Antworten, 10 neu diese Woche –',
      'ist deine die nächste?',
    ]);
    expect(teile.every((t) => getComputedStyle(t).whiteSpace === 'nowrap')).toBeTrue();
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
    expect(text()).toContain('800 Antworten, 10 neu diese Woche');
    tick(BESTAND_NACHLADEN_MS);
    http.expectOne(METRICS).flush({ ...BESTAND, statement_count: 0 });
    fixture.detectChanges();
    expect(text()).toContain('10 neu diese Woche');
    tick(BESTAND_NACHLADEN_MS);
    http.expectOne(METRICS).flush('kaputt', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    expect(text()).toContain('10 neu diese Woche');
    fixture.destroy();
  }));

  it('lädt selbst nach: neuer Zuwachs kommt ohne Neuladen an', fakeAsync(() => {
    fixture.detectChanges();
    http.expectOne(METRICS).flush(BESTAND);
    tick(BESTAND_NACHLADEN_MS);
    http.expectOne(METRICS).flush({ ...BESTAND, commentary_count: 1003, zuwachs: { neu_7_tage: 5, zuletzt_ergaenzt: null } });
    fixture.detectChanges();
    expect(text()).toBe('1.000 Antworten, 5 neu diese Woche – ist deine die nächste?');
    fixture.destroy();
  }));
});
