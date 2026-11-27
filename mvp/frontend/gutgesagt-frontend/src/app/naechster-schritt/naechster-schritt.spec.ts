import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { BehaviorSubject } from 'rxjs';

import { AuthService, UserInfo } from '../auth/auth.service';
import { FunktionenService } from '../services/funktionen.service';
import { BesuchResponse, UsageTrackingService } from '../services/usage-tracking.service';
import { START_WARTEZEIT_MS, SeitLetztemBesuchService } from '../seit-letztem-besuch/seit-letztem-besuch.service';
import { NAECHSTER_SCHRITT_URL, NaechsterSchrittComponent } from './naechster-schritt.component';
import {
  Vorschlag,
  WEGGEKLICKT_SCHLUESSEL,
  anzeige,
  offeneVorschlaege,
  tagVon,
  weggeklicktEntfernen,
  weggeklicktLesen,
  wegklicken,
  zahlAmSatzanfang,
} from './naechster-schritt';

const AUSSAGE = '11111111-1111-4111-8111-111111111111';
const KOMMENTAR = '22222222-2222-4222-8222-222222222222';

const BRACHE: Vorschlag = {
  art: 'brachflaeche',
  brachflaeche: { statement_id: AUSSAGE, statement_text: 'Windräder töten Vögel', personen_ohne_treffer: 4 },
};

describe('Dein nächster Schritt (#789)', () => {
  beforeEach(() => localStorage.removeItem(WEGGEKLICKT_SCHLUESSEL));
  afterEach(() => localStorage.removeItem(WEGGEKLICKT_SCHLUESSEL));

  describe('anzeige je Regel', () => {
    it('Regel 1: noch nie kopiert, zur Suche ohne Seitenwechsel', () => {
      const a = anzeige({ art: 'suchen' })!;
      expect(a.satz).toBe('Such den Spruch, der dich zuletzt geärgert hat.');
      expect(a.ziel).toBeUndefined();
    });

    it('Regel 2: noch kein Einwurf, zum Einwerfen', () => {
      const a = anzeige({ art: 'einwerfen' })!;
      expect(a.knopf).toBe('Einwerfen');
      expect(a.ziel).toBe('/einwerfen');
    });

    it('Regel 3: Stimmen, mit der Zahl vom Server als Wort', () => {
      expect(anzeige({ art: 'bewerten', anzahl: 3 })!.satz).toBe('Drei frische Antworten warten auf deine Einschätzung.');
      expect(anzeige({ art: 'bewerten', anzahl: 15 })!.satz).toBe('15 frische Antworten warten auf deine Einschätzung.');
      expect(anzeige({ art: 'bewerten', anzahl: 1 })!.satz).toBe('Eine frische Antwort wartet auf deine Einschätzung.');
      const a = anzeige({ art: 'bewerten', anzahl: 3 })!;
      expect([a.ziel, a.fragment]).toEqual(['/search', 'recent-content']);
      expect(zahlAmSatzanfang(5)).toBe('Fünf');
    });

    it('Regel 4 und 6: der Spruch ohne Antwort mit der Zahl der Suchenden, zum Kommentar', () => {
      const a = anzeige(BRACHE)!;
      expect(a.satz).toBe('Nach diesem Spruch haben 4 Leute gesucht. Magst du antworten?');
      expect(a.zitat).toBe('Windräder töten Vögel');
      expect(a.ziel).toBe('/workflow/add-commentary');
      expect(a.queryParams).toEqual({ aussage: AUSSAGE, von: 'hier-fehlt-eine-antwort', gesucht: '4' });
    });

    it('Regel 4 ohne Suchende: ohne Zahl und ohne ?gesucht=', () => {
      const a = anzeige({ ...BRACHE, brachflaeche: { ...BRACHE.brachflaeche!, personen_ohne_treffer: 0 } })!;
      expect(a.satz).toBe('Auf diesen Spruch gibt es noch keine Antwort. Magst du antworten?');
      expect(a.queryParams).toEqual({ aussage: AUSSAGE, von: 'hier-fehlt-eine-antwort' });
    });

    it('Regel 5: Kurzfassung ergänzen, ehrlich „-mal genutzt“, nach „Meine Beiträge“ mit dem Stift „Ändern“', () => {
      const a = anzeige({ art: 'kurzfassung', kommentar: { content_id: KOMMENTAR, titel: 'Windräder schützen Vögel', nutzung: 14 } })!;
      expect(a.satz).toContain('„Windräder schützen Vögel“ wurde 14-mal genutzt');
      expect(a.satz).not.toMatch(/Menschen|Leute/);
      expect(a.ziel).toBe('/contributions');
      expect(a.hinweis).toContain('„Ändern“');
    });

    it('ohne Daten oder bei unbekannter Art nichts', () => {
      expect(anzeige({ art: 'brachflaeche' })).toBeNull();
      expect(anzeige({ art: 'kurzfassung' })).toBeNull();
      expect(anzeige({ art: 'unbekannt' } as unknown as Vorschlag)).toBeNull();
    });

    it('nennt keine Frist, keinen Verlust und keine Serie', () => {
      const saetze = (['suchen', 'einwerfen', 'bewerten'] as const).map((art) => anzeige({ art, anzahl: 3 })!.satz);
      saetze.push(anzeige(BRACHE)!.satz);
      for (const satz of saetze) {
        expect(satz).not.toMatch(/verpasst|heute noch|Frist|Serie|verfällt|läuft ab/i);
      }
    });
  });

  describe('weggeklickt im Browser', () => {
    const heute = new Date(2026, 10, 25, 12);

    it('speichert unter dem festen Schlüssel nur Art und Tag', () => {
      wegklicken('einwerfen', heute);
      expect(JSON.parse(localStorage.getItem(WEGGEKLICKT_SCHLUESSEL)!)).toEqual({ einwerfen: '2026-11-25' });
    });

    it('gilt sieben Tage, danach kommt der Vorschlag wieder und der Eintrag ist weg', () => {
      wegklicken('einwerfen', heute);
      expect(weggeklicktLesen(new Date(2026, 11, 1, 23))).toEqual({ einwerfen: '2026-11-25' });
      expect(weggeklicktLesen(new Date(2026, 11, 2, 0, 1))).toEqual({});
      expect(localStorage.getItem(WEGGEKLICKT_SCHLUESSEL)).toBeNull();
    });

    it('verwirft Unlesbares, Unbekanntes und Tage in der Zukunft', () => {
      localStorage.setItem(WEGGEKLICKT_SCHLUESSEL, '{kaputt');
      expect(weggeklicktLesen(heute)).toEqual({});
      expect(localStorage.getItem(WEGGEKLICKT_SCHLUESSEL)).toBeNull();
      localStorage.setItem(WEGGEKLICKT_SCHLUESSEL, JSON.stringify({ kennung: 'x', suchen: '2027-01-01', bewerten: '2026-11-24' }));
      expect(weggeklicktLesen(heute)).toEqual({ bewerten: '2026-11-24' });
      expect(JSON.parse(localStorage.getItem(WEGGEKLICKT_SCHLUESSEL)!)).toEqual({ bewerten: '2026-11-24' });
    });

    it('löscht den Eintrag mit weggeklicktEntfernen (Abmelden)', () => {
      wegklicken('einwerfen', heute);
      weggeklicktEntfernen();
      expect(localStorage.getItem(WEGGEKLICKT_SCHLUESSEL)).toBeNull();
    });

    it('lässt weggeklickte Arten aus, Reihenfolge wie vom Server', () => {
      const liste: Vorschlag[] = [{ art: 'suchen' }, { art: 'einwerfen' }, BRACHE];
      expect(offeneVorschlaege(liste, { suchen: tagVon(heute) }).map((v) => v.art)).toEqual(['einwerfen', 'brachflaeche']);
    });
  });

  describe('Karte', () => {
    let http: HttpTestingController;
    let nutzer: BehaviorSubject<UserInfo | null>;
    let an: ReturnType<typeof signal<boolean>>;
    let besuch: BehaviorSubject<BesuchResponse | null>;

    function starten(angemeldet: boolean, schalter: boolean) {
      nutzer = new BehaviorSubject<UserInfo | null>({ isAuthenticated: angemeldet, userId: angemeldet ? 'kim' : null, userName: null, claims: null });
      an = signal(schalter);
      // Der Besuch ist gemeldet, ohne Neues: Sonst wartet die Karte bis START_WARTEZEIT_MS
      besuch = new BehaviorSubject<BesuchResponse | null>({ nutzung_seit_letztem_besuch: 0 });
      TestBed.configureTestingModule({
        imports: [NaechsterSchrittComponent],
        providers: [
          provideHttpClient(),
          provideHttpClientTesting(),
          provideRouter([]),
          { provide: AuthService, useValue: { userInfo$: nutzer } },
          { provide: FunktionenService, useValue: { an: () => an } },
          { provide: UsageTrackingService, useValue: { besuchStand$: besuch } },
        ],
      });
      http = TestBed.inject(HttpTestingController);
      const fixture = TestBed.createComponent(NaechsterSchrittComponent);
      fixture.detectChanges();
      return fixture;
    }

    afterEach(() => http.verify());

    it('fragt Besucher nichts und zeigt nichts', () => {
      const fixture = starten(false, true);
      http.expectNone(NAECHSTER_SCHRITT_URL);
      expect(fixture.nativeElement.querySelector('.naechster-schritt')).toBeNull();
    });

    it('fragt Angemeldete auch, wenn alle Schalter aus sind (Basisfunktion), und räumt Abgelaufenes auf', () => {
      localStorage.setItem(WEGGEKLICKT_SCHLUESSEL, JSON.stringify({ einwerfen: '2020-01-01' }));
      starten(true, false);
      http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [] });
      expect(localStorage.getItem(WEGGEKLICKT_SCHLUESSEL)).toBeNull();
    });

    it('zeigt genau einen Vorschlag und nach dem Wegklicken den nächsten', () => {
      const fixture = starten(true, true);
      http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [{ art: 'einwerfen' }, BRACHE] });
      fixture.detectChanges();
      const karte: HTMLElement = fixture.nativeElement.querySelector('.naechster-schritt');
      expect(karte.querySelector('h2')!.textContent).toContain('Dein nächster Schritt');
      expect(karte.textContent).toContain('Wirf ihn ein');
      expect(karte.textContent).not.toContain('Windräder');

      const weg: HTMLButtonElement = karte.querySelector('.naechster-schritt-weg')!;
      expect(weg.textContent!.trim()).toBe('Anderer Vorschlag');
      weg.click();
      fixture.detectChanges();

      expect(fixture.nativeElement.textContent).toContain('Nach diesem Spruch haben 4 Leute gesucht.');
      expect(fixture.nativeElement.querySelector('[aria-live]').textContent).toContain('Anderer Vorschlag: Nach diesem Spruch');
      expect(JSON.parse(localStorage.getItem(WEGGEKLICKT_SCHLUESSEL)!)).toEqual({ einwerfen: tagVon(new Date()) });
      expect((fixture.nativeElement.querySelector('.naechster-schritt-weg') as HTMLElement).textContent!.trim()).toBe('Ausblenden');

      const feld = document.createElement('input');
      feld.id = 'suche';
      document.body.appendChild(feld);
      try {
        (fixture.nativeElement.querySelector('.naechster-schritt-weg') as HTMLButtonElement).click();
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector('.naechster-schritt')).toBeNull();
        expect(fixture.nativeElement.querySelector('[aria-live]').textContent).toContain('Vorschlag ausgeblendet.');
        // Der Knopf ist weg: Der Fokus geht ins Suchfeld, nicht an den Seitenanfang
        expect(document.activeElement).toBe(feld);
      } finally {
        feld.remove();
      }
    });

    describe('nie zugleich mit „Seit deinem letzten Besuch“ (Review Spielgefühl 25.11.)', () => {
      it('meldet dem Block erst mit der Antwort, ob es einen Vorschlag gibt, und behält es beim Verlassen', () => {
        const fixture = starten(true, true);
        const neues = TestBed.inject(SeitLetztemBesuchService);
        // Vor der Antwort: unbekannt, nicht „kein Vorschlag“, sonst zeigte der Block kurz seine Kacheln
        expect(neues.naechsterSchrittDa$.value).toBeNull();
        http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [{ art: 'suchen' }] });
        fixture.detectChanges();
        expect(neues.naechsterSchrittDa$.value).toBeTrue();

        fixture.destroy();
        expect(neues.naechsterSchrittDa$.value).toBeTrue();
      });

      it('zeigt bei der Rückkehr auf die Startseite sofort den letzten Vorschlag und fragt still neu', () => {
        const erste = starten(true, true);
        http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [{ art: 'einwerfen' }] });
        erste.detectChanges();
        erste.destroy();

        const zweite = TestBed.createComponent(NaechsterSchrittComponent);
        zweite.detectChanges();
        expect(zweite.nativeElement.querySelector('.naechster-schritt')?.textContent).toContain('Wirf ihn ein');
        http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [] });
        zweite.detectChanges();
        expect(zweite.nativeElement.querySelector('.naechster-schritt')).toBeNull();
        expect(TestBed.inject(SeitLetztemBesuchService).naechsterSchrittDa$.value).toBeFalse();
      });

      it('meldet Besuchern sofort „kein Vorschlag“, damit der Block nicht wartet', () => {
        starten(false, true);
        expect(TestBed.inject(SeitLetztemBesuchService).naechsterSchrittDa$.value).toBeFalse();
      });

      it('wartet auf den Besuch, statt zu erscheinen und gleich wieder zu verschwinden', fakeAsync(() => {
        const fixture = starten(true, true);
        besuch.next(null);
        http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [{ art: 'einwerfen' }] });
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector('.naechster-schritt')).toBeNull();

        // Eigenes Neues kommt: Die Karte war nie zu sehen
        besuch.next({ nutzung_seit_letztem_besuch: 2 });
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector('.naechster-schritt')).toBeNull();

        // Kommt keine Antwort zum Besuch, steht die Karte nach der Wartezeit da
        besuch.next(null);
        tick(START_WARTEZEIT_MS);
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector('.naechster-schritt')).not.toBeNull();
        fixture.destroy();
      }));

      it('sagt beim Ausblenden an, dass darüber Neues steht', () => {
        const fixture = starten(true, true);
        besuch.next({ nutzung_seit_letztem_besuch: 0, neue_einwuerfe: 3 });
        http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [{ art: 'einwerfen' }] });
        fixture.detectChanges();
        (fixture.nativeElement.querySelector('.naechster-schritt-weg') as HTMLButtonElement).click();
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector('[aria-live]').textContent).toContain(
          'Vorschlag ausgeblendet. Neues seit deinem letzten Besuch steht darüber.',
        );
      });

      it('tritt hinter Neues zu eigenen Beiträgen zurück und kommt nach dessen Klick wieder', () => {
        const fixture = starten(true, true);
        http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [{ art: 'einwerfen' }] });
        besuch.next({ nutzung_seit_letztem_besuch: 2 });
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector('.naechster-schritt')).toBeNull();

        TestBed.inject(SeitLetztemBesuchService).erledigen('nutzung');
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector('.naechster-schritt')).not.toBeNull();
      });

      it('geht allgemeinen Zahlen und dem ersten Besuch vor', () => {
        const fixture = starten(true, true);
        http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [{ art: 'suchen' }] });
        besuch.next({ nutzung_seit_letztem_besuch: 0, neue_einwuerfe: 4, unbeantwortete_aussagen: 3 });
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector('.naechster-schritt')).not.toBeNull();

        besuch.next({ nutzung_seit_letztem_besuch: 5, erster_besuch: true });
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector('.naechster-schritt')).not.toBeNull();
      });
    });

    it('lässt schon Weggeklicktes beim Laden aus', () => {
      wegklicken('einwerfen');
      const fixture = starten(true, true);
      http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [{ art: 'einwerfen' }, BRACHE] });
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Windräder töten Vögel');
    });

    it('setzt bei „Zur Suche“ den Fokus ins Suchfeld', () => {
      const feld = document.createElement('input');
      feld.id = 'suche';
      document.body.appendChild(feld);
      try {
        const fixture = starten(true, true);
        http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [{ art: 'suchen' }] });
        fixture.detectChanges();
        (fixture.nativeElement.querySelector('.naechster-schritt-los') as HTMLButtonElement).click();
        expect(document.activeElement).toBe(feld);
      } finally {
        feld.remove();
      }
    });

    it('zeigt nach einem Fehler nichts', () => {
      const fixture = starten(true, true);
      http.expectOne(NAECHSTER_SCHRITT_URL).flush('weg', { status: 500, statusText: 'Fehler' });
      fixture.detectChanges();
      expect(fixture.nativeElement.querySelector('.naechster-schritt')).toBeNull();
    });
  });
});
