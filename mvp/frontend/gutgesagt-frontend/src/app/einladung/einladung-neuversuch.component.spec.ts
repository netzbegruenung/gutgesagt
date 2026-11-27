import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { HttpHeaders, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { EINLOESEN_NEUVERSUCHE, EinladungComponent, PRUEFEN_LANGE_AB, VERBINDUNG_HAKT, VIEL_LOS } from './einladung.component';
import { environment } from '../../environments/environment';
import { TeamBeimPruefen } from '../shared/einladung/team-einladung';
import { NEUVERSUCH_START_MS } from '../shared/neuversuch';
import { teamMerkerLesen } from './team-merker';

const URL = `${environment.baseUrl}/api/v1/einladungen`;
const SITZUNG = `${environment.baseUrl}/api/check-session`;
const FUNKTIONEN = `${environment.baseUrl}/api/v1/funktionen`;

const TEAM: TeamBeimPruefen = {
  name: 'BDK 26 Berlin',
  motiv: 'vogel',
  saison: '2026',
  mitglieder: 36,
  naechste_nummer: 37,
  eigene_nummer: null,
  einwilligung_kennung: 'team-2026-11-26',
  einwilligung_text: 'Ich willige ausdrücklich ein, dass Gut gesagt an meinem Konto speichert, dass ich im Team BDK 26 Berlin bin …',
  knopf_ja: 'Ja, speichert, dass ich im Team BDK 26 Berlin bin',
  knopf_nein: 'Nein, ohne Team weiter',
  oeffentlich_kennung: null,
  oeffentlich_text: null,
};

const ZU_VIELE = { status: 429, statusText: 'Too Many Requests' };

/**
 * Im Saal-WLAN teilen sich hunderte Geräte eine Adresse, und das Limit je Anschluss reißt.
 * Dann darf niemand still ohne Team weiter: Hinweis, selbst noch einmal fragen, Team behalten.
 */
describe('EinladungComponent im vollen Saal (Neuversuch)', () => {
  let fixture: ComponentFixture<EinladungComponent>;
  let http: HttpTestingController;

  function starten(fragment: string | null = 'Code123') {
    TestBed.configureTestingModule({
      imports: [EinladungComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { fragment } } },
      ],
    });
    fixture = TestBed.createComponent(EinladungComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  }

  beforeEach(() => {
    localStorage.clear();
    // Ohne Streuung: Jeder Neuversuch wartet genau die Stufe (2 s, 4 s, 8 s …).
    spyOn(Math, 'random').and.returnValue(1);
  });

  afterEach(() => {
    http.verify();
    localStorage.clear();
  });

  function el(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function hinweis(): HTMLElement | null {
    return el().querySelector('[data-testid="viel-los"]');
  }

  function pruefenAnfrage() {
    const anfrage = http.expectOne(`${URL}/pruefen`);
    expect(anfrage.request.body).toEqual({ code: 'Code123' });
    return anfrage;
  }

  function mitTeamAntworten() {
    pruefenAnfrage().flush({ einloesbar: true, team: TEAM });
    http.match(FUNKTIONEN).forEach((r) => r.flush({ funktionen: { teams: false } }));
    fixture.detectChanges();
  }

  describe('Prüfen', () => {
    it('bei 429 kein Formular ohne Team, sondern ein Hinweis; nach dem Neuversuch das Team', fakeAsync(() => {
      starten();
      pruefenAnfrage().flush('zu viele', ZU_VIELE);
      http.expectOne(SITZUNG).flush({ isAuthenticated: false });
      fixture.detectChanges();

      expect(hinweis()?.textContent).toContain(VIEL_LOS);
      expect(el().querySelector('[role="status"]')?.textContent).toContain(VIEL_LOS);
      expect(el().querySelector('input[type="email"]')).toBeNull();
      expect(el().querySelector('[data-testid="team-kasten"]')).toBeNull();

      tick(NEUVERSUCH_START_MS);
      mitTeamAntworten();

      expect(hinweis()).toBeNull();
      expect(el().querySelector('[data-testid="team-kasten"]')?.textContent).toContain('BDK 26 Berlin');
      expect(el().querySelector('input[type="email"]')).not.toBeNull();
    }));

    it('versucht es nach Netz- und Serverfehlern immer wieder, mit wachsendem Abstand', fakeAsync(() => {
      starten();
      http.expectOne(SITZUNG).flush({ isAuthenticated: false });
      pruefenAnfrage().error(new ProgressEvent('error'), { status: 0, statusText: '' });
      fixture.detectChanges();
      expect(hinweis()?.textContent).toContain(VERBINDUNG_HAKT);

      tick(NEUVERSUCH_START_MS);
      pruefenAnfrage().flush('weg', { status: 502, statusText: 'Bad Gateway' });
      fixture.detectChanges();
      expect(hinweis()?.textContent).toContain(VIEL_LOS);
      // Zweiter Neuversuch erst nach der doppelten Zeit
      tick(NEUVERSUCH_START_MS * 2 - 1);
      http.expectNone(`${URL}/pruefen`);
      tick(1);
      pruefenAnfrage().flush('weg', { status: 503, statusText: 'Service Unavailable' });
      fixture.detectChanges();
      expect(hinweis()).not.toBeNull();

      tick(NEUVERSUCH_START_MS * 4);
      mitTeamAntworten();
      expect(el().querySelector('[data-testid="team-kasten"]')).not.toBeNull();
    }));

    it(`sagt nach ${PRUEFEN_LANGE_AB} Neuversuchen dazu, dass die Seite dranbleibt`, fakeAsync(() => {
      starten();
      http.expectOne(SITZUNG).flush({ isAuthenticated: false });
      pruefenAnfrage().flush('weg', { status: 500, statusText: 'Server Error' });
      for (let i = 1; i < PRUEFEN_LANGE_AB; i++) {
        tick(60_000);
        pruefenAnfrage().flush('weg', { status: 500, statusText: 'Server Error' });
      }
      fixture.detectChanges();
      expect(hinweis()?.textContent).toContain('wir bleiben dran');

      tick(60_000);
      mitTeamAntworten();
      expect(hinweis()).toBeNull();
    }));

    it('wartet so lange, wie Retry-After verlangt', fakeAsync(() => {
      starten();
      http.expectOne(SITZUNG).flush({ isAuthenticated: false });
      pruefenAnfrage().flush('zu viele', { ...ZU_VIELE, headers: new HttpHeaders({ 'Retry-After': '30' }) });

      tick(30_000);
      http.expectNone(`${URL}/pruefen`);
      tick(6_000);
      mitTeamAntworten();
      expect(el().querySelector('[data-testid="team-kasten"]')).not.toBeNull();
    }));

    it('erst eine echt ungültige Einladung meldet „gilt nicht“', fakeAsync(() => {
      starten();
      http.expectOne(SITZUNG).flush({ isAuthenticated: false });
      pruefenAnfrage().flush('zu viele', ZU_VIELE);
      tick(NEUVERSUCH_START_MS);
      pruefenAnfrage().flush({ einloesbar: false });
      fixture.detectChanges();

      expect(el().textContent).toContain('gilt nicht');
      expect(hinweis()).toBeNull();
    }));

    it('bei 422 (kein Engpass) kein Neuversuch, das Formular wie bisher', fakeAsync(() => {
      starten();
      http.expectOne(SITZUNG).flush({ isAuthenticated: false });
      pruefenAnfrage().flush({ detail: [] }, { status: 422, statusText: 'Unprocessable Entity' });
      fixture.detectChanges();

      expect(el().querySelector('input[type="email"]')).not.toBeNull();
      tick(60_000);
      http.expectNone(`${URL}/pruefen`);
    }));

    it('hört auf, wenn die Seite verlassen wird', fakeAsync(() => {
      starten();
      http.expectOne(SITZUNG).flush({ isAuthenticated: false });
      pruefenAnfrage().flush('zu viele', ZU_VIELE);
      fixture.destroy();

      tick(60_000);
      http.expectNone(`${URL}/pruefen`);
    }));

    it('angemeldet: der Merker bleibt, bis die Antwort da ist', fakeAsync(() => {
      localStorage.setItem(
        'gutgesagt-einladung-team',
        JSON.stringify({ code: 'Code123', kennung: null, oeffentlich: false, bis: Date.now() + 60 * 60_000 }),
      );
      starten(null);
      http.expectOne(SITZUNG).flush({ isAuthenticated: true });
      pruefenAnfrage().flush('zu viele', ZU_VIELE);

      expect(teamMerkerLesen()?.code).toBe('Code123');
      tick(NEUVERSUCH_START_MS);
      mitTeamAntworten();
      expect(el().querySelector('[data-testid="team-ja"]')).not.toBeNull();
      expect(teamMerkerLesen()).toBeNull();
    }));
  });

  describe('Einlösen', () => {
    function mitTeamImFormular() {
      starten();
      http.expectOne(SITZUNG).flush({ isAuthenticated: false });
      mitTeamAntworten();
      el().querySelector<HTMLButtonElement>('[data-testid="team-ja"]')!.click();
      const c = fixture.componentInstance;
      c.email = 'neu@example.org';
      c.vorname = 'Anna';
      c.nachname = 'Beispiel';
      c.einloesen();
      fixture.detectChanges();
    }

    it('bei 429 Hinweis, Team und Angaben bleiben, derselbe Antrag geht noch einmal', fakeAsync(() => {
      mitTeamImFormular();
      const erste = http.expectOne(`${URL}/einloesen`);
      const body = erste.request.body;
      expect(body.team_einwilligung).toBeTrue();
      erste.flush('zu viele', ZU_VIELE);
      fixture.detectChanges();

      expect(hinweis()?.textContent).toContain(VIEL_LOS);
      expect(hinweis()?.textContent).toContain('Wahl zum Team');
      expect(el().textContent).not.toContain('Viertelstunde');
      expect(el().querySelector('[data-testid="team-kasten"]')).not.toBeNull();
      expect(el().querySelector<HTMLButtonElement>('[data-testid="team-ja"]')!.disabled).toBeTrue();
      // Wer jetzt noch tippt, ändert nichts mehr am Antrag: Die Felder sind gesperrt.
      tick();
      fixture.detectChanges();
      for (const feld of ['vorname', 'nachname', 'email']) {
        expect(el().querySelector<HTMLInputElement>(`input[name="${feld}"]`)!.disabled).withContext(feld).toBeTrue();
      }

      // 429 ohne Grenze: auch nach vielen Runden noch ein Neuversuch
      for (let i = 1; i <= 8; i++) {
        tick(Math.min(NEUVERSUCH_START_MS * 2 ** (i - 1), 60_000));
        const nochmal = http.expectOne(`${URL}/einloesen`);
        expect(nochmal.request.body).toEqual(body);
        if (i < 8) {
          nochmal.flush('zu viele', ZU_VIELE);
        } else {
          nochmal.flush({ success: true }, { status: 202, statusText: 'Accepted' });
        }
      }
      fixture.detectChanges();

      expect(el().textContent).toContain('Postfach');
      expect(hinweis()).toBeNull();
      expect(teamMerkerLesen()).toEqual({ code: 'Code123', kennung: TEAM.einwilligung_kennung, oeffentlich: false });
    }));

    it(`nach Serverfehlern höchstens ${EINLOESEN_NEUVERSUCHE} Neuversuche, dann die Meldung`, fakeAsync(() => {
      mitTeamImFormular();
      http.expectOne(`${URL}/einloesen`).flush('weg', { status: 504, statusText: 'Gateway Timeout' });
      for (let i = 1; i <= EINLOESEN_NEUVERSUCHE; i++) {
        tick(NEUVERSUCH_START_MS * 2 ** (i - 1));
        http.expectOne(`${URL}/einloesen`).flush('weg', { status: 504, statusText: 'Gateway Timeout' });
      }
      fixture.detectChanges();

      expect(el().textContent).toContain('hat nicht geklappt');
      expect(hinweis()).toBeNull();
      tick(60_000);
      http.expectNone(`${URL}/einloesen`);
    }));

    it('viele 429 nehmen einem späteren Serverfehler nicht die Neuversuche', fakeAsync(() => {
      mitTeamImFormular();
      http.expectOne(`${URL}/einloesen`).flush('zu viele', ZU_VIELE);
      for (let i = 0; i < 6; i++) {
        tick(60_000);
        http.expectOne(`${URL}/einloesen`).flush('zu viele', ZU_VIELE);
      }
      tick(60_000);
      http.expectOne(`${URL}/einloesen`).flush('weg', { status: 502, statusText: 'Bad Gateway' });
      tick(60_000);
      http.expectOne(`${URL}/einloesen`).flush({ success: true }, { status: 202, statusText: 'Accepted' });
      fixture.detectChanges();

      expect(el().textContent).toContain('Postfach');
    }));

    it('410 nach einem unklaren Fehler: vielleicht hat es geklappt, nicht „gilt nicht“', fakeAsync(() => {
      mitTeamImFormular();
      http.expectOne(`${URL}/einloesen`).flush('weg', { status: 504, statusText: 'Gateway Timeout' });
      tick(NEUVERSUCH_START_MS);
      http.expectOne(`${URL}/einloesen`).flush('weg', { status: 410, statusText: 'Gone' });
      fixture.detectChanges();

      expect(el().querySelector('[data-testid="vielleicht-gesendet"]')?.textContent).toContain('Postfach');
      expect(el().textContent).not.toContain('gilt nicht');
    }));

    it('ein 503 vom Gateway heißt nach den Neuversuchen nicht „nicht eingerichtet“', fakeAsync(() => {
      mitTeamImFormular();
      http.expectOne(`${URL}/einloesen`).flush('weg', { status: 503, statusText: 'Service Unavailable' });
      for (let i = 1; i <= EINLOESEN_NEUVERSUCHE; i++) {
        tick(60_000);
        http.expectOne(`${URL}/einloesen`).flush('weg', { status: 503, statusText: 'Service Unavailable' });
      }
      fixture.detectChanges();

      expect(el().textContent).toContain('hat nicht geklappt');
      expect(el().textContent).not.toContain('noch nicht anlegen');
    }));
  });
});
