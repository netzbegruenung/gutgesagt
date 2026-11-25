import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { ActivatedRoute, Router, provideRouter } from '@angular/router';
import { EinladungComponent } from './einladung.component';
import { environment } from '../../environments/environment';
import { TeamBeimPruefen } from '../shared/einladung/team-einladung';
import { TEAM_MERKER_SCHLUESSEL, teamMerkerAblegen, teamMerkerLesen } from './team-merker';

const URL = `${environment.baseUrl}/api/v1/einladungen`;
const SITZUNG = `${environment.baseUrl}/api/check-session`;
const FUNKTIONEN = `${environment.baseUrl}/api/v1/funktionen`;

function team(anders: Partial<TeamBeimPruefen> = {}): TeamBeimPruefen {
  return {
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
    ...anders,
  };
}

const OEFFENTLICH = {
  oeffentlich_kennung: 'team-oeffentlich-2026-11-25',
  oeffentlich_text: 'Ich willige ausdrücklich ein, dass andere Angemeldete an meinem Namen sehen …',
};

describe('EinladungComponent mit Team', () => {
  let fixture: ComponentFixture<EinladungComponent>;
  let http: HttpTestingController;
  let router: Router;

  function starten(fragment: string | null) {
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
    router = TestBed.inject(Router);
    spyOn(router, 'navigate').and.resolveTo(true);
    fixture.detectChanges();
  }

  beforeEach(() => localStorage.clear());

  afterEach(() => {
    http.verify();
    localStorage.clear();
  });

  function el(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function pruefen(antwort: { einloesbar: boolean; team: TeamBeimPruefen | null }, angemeldet = false) {
    const anfrage = http.expectOne(`${URL}/pruefen`);
    expect(anfrage.request.body).toEqual({ code: 'Code123' });
    anfrage.flush(antwort);
    http.expectOne(SITZUNG).flush({ isAuthenticated: angemeldet });
    fixture.detectChanges();
  }

  function knopf(testid: string): HTMLButtonElement {
    return el().querySelector<HTMLButtonElement>(`[data-testid="${testid}"]`)!;
  }

  function klick(testid: string) {
    knopf(testid).click();
    fixture.detectChanges();
  }

  function formularAusfuellen() {
    const c = fixture.componentInstance;
    c.email = 'neu@example.org';
    c.vorname = 'Anna';
    c.nachname = 'Beispiel';
  }

  describe('Team nach Gruppe', () => {
    const SATZ =
      'Dieses Team ist mit Zustimmung von Netzfeuerwehr nach ihr benannt. Verantwortlich für Gut gesagt ist allein die Netzbegrünung; Netzfeuerwehr bekommt keine Daten über dich.';
    const NACH_GRUPPE = {
      name: 'Netzfeuerwehr',
      art: 'gruppe' as const,
      knopf_ja: 'Ja, speichert, dass ich im Team Netzfeuerwehr bin',
      einwilligung_text: 'Ich willige ausdrücklich ein, dass Gut gesagt an meinem Konto speichert, dass ich im Team Netzfeuerwehr bin …',
    };

    function satzDirektUeberDerFrage() {
      const satz = el().querySelector('[data-testid="team-gruppe"]')!;
      expect(satz.textContent!.trim()).toBe(SATZ);
      // direkt über der Frage: das nächste Element sind die Sätze vor den Knöpfen
      expect(satz.nextElementSibling?.id).toBe('team-erklaerung');
      expect(satz.compareDocumentPosition(knopf('team-ja'))).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
      expect(el().querySelector('.team-knoepfe[role="group"]')!.getAttribute('aria-describedby')).toBe(
        'team-gruppe team-erklaerung',
      );
    }

    it('ohne Konto: zeigt den Satz wortgleich direkt über der Frage', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team(NACH_GRUPPE) });

      expect(el().querySelector('[data-testid="team-schon-konto"]')).not.toBeNull();
      satzDirektUeberDerFrage();
    });

    it('angemeldet beitreten: zeigt denselben Satz direkt über der Frage', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team(NACH_GRUPPE) }, true);

      // wirklich der angemeldete Weg: kein Hinweis „Hast du schon ein Konto?“, kein Formular
      expect(el().querySelector('[data-testid="team-schon-konto"]')).toBeNull();
      expect(el().querySelector('input[type="email"]')).toBeNull();
      satzDirektUeberDerFrage();
    });

    it('Team nach Anlass, Ort oder Saison: kein Satz', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team({ art: 'anlass' }) });

      expect(el().querySelector('[data-testid="team-gruppe"]')).toBeNull();
      expect(el().textContent).not.toContain('nach ihr benannt');
      expect(el().querySelector('.team-knoepfe[role="group"]')!.getAttribute('aria-describedby')).toBe(
        'team-erklaerung',
      );
    });

    it('ohne Art (älterer Server), neues Konto: kein Satz', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team() });
      expect(el().querySelector('[data-testid="team-gruppe"]')).toBeNull();
    });

    it('angemeldet ohne Art: kein Satz', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team() }, true);

      expect(el().querySelector('[data-testid="team-schon-konto"]')).toBeNull();
      expect(el().querySelector('[data-testid="team-gruppe"]')).toBeNull();
    });
  });

  describe('ohne Konto', () => {
    it('zeigt den Kasten über dem Formular mit Team, Motiv samt Name, Nummer und beiden Knöpfen', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team() });

      const kasten = el().querySelector('[data-testid="team-kasten"]')!;
      expect(kasten).not.toBeNull();
      expect(kasten.textContent).toContain('Herzlich willkommen im Team BDK 26 Berlin! Du wärst Nr. 37.');
      expect(kasten.textContent).toContain('Schon 36 dabei.');
      expect(kasten.textContent).toContain('Die Nummer steht erst fest, wenn dein Konto angelegt ist');
      // Die Sätze vor dem Ja: was, wer es sieht, Widerruf
      expect(kasten.textContent).toContain('Das siehst nur du, unter „Meine Teams“.');
      expect(kasten.textContent).toContain('mit „Team verlassen“ widerrufen');
      // Vor dem Ja kein Ticket und kein Medaillon; das Motiv klein, mit Namen daneben
      const bild = kasten.querySelector('img')!;
      expect(bild.getAttribute('src')).toBe('/meilensteine/vogel.svg');
      expect(bild.getAttribute('alt')).toBe('');
      expect(kasten.querySelector('[data-testid="team-motiv"]')?.textContent).toContain('Motiv: Vogel');
      expect(kasten.querySelector('.team-ticket, .team-medaillon')).toBeNull();
      expect(kasten.textContent).not.toContain('Deine Nummer');
      expect(kasten.textContent).toContain('Team BDK 26 Berlin');
      // Wer schon ein Konto hat, wird vor dem Formular zur Anmeldung geschickt
      expect(kasten.querySelector('[data-testid="team-schon-konto"]')?.textContent).toContain('melde dich zuerst an');
      expect(knopf('team-ja').textContent?.trim()).toBe('Ja, speichert, dass ich im Team BDK 26 Berlin bin');
      expect(knopf('team-nein').textContent?.trim()).toBe('Nein, ohne Team weiter');
      // gleichwertig: dieselbe Art Knopf, nichts vorausgewählt
      expect(knopf('team-ja').className).toEqual(knopf('team-nein').className);
      expect(knopf('team-ja').getAttribute('aria-pressed')).toBe('false');
      expect(knopf('team-nein').getAttribute('aria-pressed')).toBe('false');
      // Formular darunter, ohne zweite Frage, solange teams_oeffentlich aus ist
      expect(kasten.compareDocumentPosition(el().querySelector('input[type="email"]')!)).toBe(
        Node.DOCUMENT_POSITION_FOLLOWING,
      );
      expect(el().querySelector('[data-testid="team-oeffentlich"]')).toBeNull();
      expect(el().querySelector('[role="status"]')?.textContent).toContain('Einladung ins Team BDK 26 Berlin gefunden');
    });

    it('nennt die erste Person ehrlich, wenn noch niemand dabei ist', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team({ mitglieder: 0, naechste_nummer: 1 }) });

      expect(el().textContent).toContain('Noch ist niemand dabei.');
      expect(el().textContent).toContain('Du wärst Nr. 1.');
    });

    it('legt ohne Wahl kein Konto an und bittet, oben zu wählen', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team() });
      formularAusfuellen();
      fixture.componentInstance.einloesen();
      fixture.detectChanges();

      http.expectNone(`${URL}/einloesen`);
      expect(el().querySelector('[data-testid="team-wahl-fehlt"]')?.textContent).toContain('mit Team oder ohne Team');
    });

    it('schickt nach „Ja“ die Einwilligung mit und merkt sich nur Code und Kennung für den Rücksprung', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team() });
      klick('team-ja');
      expect(knopf('team-ja').getAttribute('aria-pressed')).toBe('true');
      expect(el().querySelector('[data-testid="team-gewaehlt"]')?.textContent).toContain('Wir speichern dein Team');
      // Vor dem Absenden ist nichts gespeichert, auch nicht im Browser
      expect(localStorage.getItem(TEAM_MERKER_SCHLUESSEL)).toBeNull();

      formularAusfuellen();
      fixture.componentInstance.einloesen();
      const anfrage = http.expectOne(`${URL}/einloesen`);
      expect(anfrage.request.body).toEqual({
        code: 'Code123',
        email: 'neu@example.org',
        vorname: 'Anna',
        nachname: 'Beispiel',
        team_einwilligung: true,
        team_oeffentlich: false,
        team_einwilligung_kennung: 'team-2026-11-26',
      });
      anfrage.flush({ success: true }, { status: 202, statusText: 'Accepted' });
      fixture.detectChanges();

      expect(el().textContent).toContain('Postfach');
      // Ehrlich: bei einem schon vorhandenen Konto entsteht kein Team
      const nachMail = el().querySelector('[data-testid="team-nach-mail"]')!;
      expect(nachMail.textContent).toContain('Gab es zu deiner Adresse schon ein Konto, speichern wir kein Team');
      // „melde dich an“ führt mit Merker zurück auf die Seite, wo noch einmal gefragt wird
      const link = Array.from(el().querySelectorAll('a')).find((a) => a.textContent?.includes('melde dich an'))!;
      link.click();
      expect(router.navigate).toHaveBeenCalledWith(['/login'], { queryParams: { returnUrl: '/einladung' } });
      expect(teamMerkerLesen()).toEqual({ code: 'Code123', kennung: 'team-2026-11-26', oeffentlich: false });
      expect(localStorage.getItem(TEAM_MERKER_SCHLUESSEL)).not.toContain('BDK');
    });

    it('fragt die zweite Frage nur bei wirksamem teams_oeffentlich, Standard nein, und schickt sie mit „Ja“', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team(OEFFENTLICH) });

      const haekchen = el().querySelector('[data-testid="team-oeffentlich"]')!;
      expect(haekchen.textContent).toContain('Team öffentlich am Namen zeigen');
      expect(fixture.componentInstance.teamOeffentlich).toBeFalse();
      expect(el().textContent).toContain(OEFFENTLICH.oeffentlich_text);

      fixture.componentInstance.teamOeffentlich = true;
      klick('team-ja');
      formularAusfuellen();
      fixture.componentInstance.einloesen();
      const anfrage = http.expectOne(`${URL}/einloesen`);
      expect(anfrage.request.body.team_einwilligung).toBeTrue();
      expect(anfrage.request.body.team_oeffentlich).toBeTrue();
      expect(anfrage.request.body.team_oeffentlich_kennung).toBe('team-oeffentlich-2026-11-25');
      anfrage.flush({ success: true }, { status: 202, statusText: 'Accepted' });

      expect(teamMerkerLesen()?.oeffentlich).toBeTrue();
    });

    it('schickt nach „Nein“ keine Einwilligung, auch nicht die zweite, und merkt sich nichts', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team(OEFFENTLICH) });
      fixture.componentInstance.teamOeffentlich = true;
      klick('team-nein');
      expect(el().querySelector('[data-testid="team-gewaehlt"]')?.textContent).toContain('ohne Team');

      formularAusfuellen();
      fixture.componentInstance.einloesen();
      const anfrage = http.expectOne(`${URL}/einloesen`);
      expect(anfrage.request.body.team_einwilligung).toBeFalse();
      expect(anfrage.request.body.team_oeffentlich).toBeFalse();
      anfrage.flush({ success: true }, { status: 202, statusText: 'Accepted' });
      fixture.detectChanges();

      expect(teamMerkerLesen()).toBeNull();
      expect(el().querySelector('[data-testid="team-nach-mail"]')).toBeNull();
    });

    it('Schalter aus (kein Team in /pruefen): kein Kasten, Einlösen ohne Teamfelder', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: null });

      expect(el().querySelector('[data-testid="team-kasten"]')).toBeNull();
      formularAusfuellen();
      fixture.componentInstance.einloesen();
      const anfrage = http.expectOne(`${URL}/einloesen`);
      expect(Object.keys(anfrage.request.body)).toEqual(['code', 'email', 'vorname', 'nachname']);
      anfrage.flush({ success: true }, { status: 202, statusText: 'Accepted' });
    });

    it('„melde dich an“ merkt nur den Code, ohne Einwilligung, und führt mit Rücksprungziel ohne Code zur Anmeldung', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team() });

      const link = Array.from(el().querySelectorAll('a')).find((a) => a.textContent?.includes('melde dich zuerst an'))!;
      link.click();

      expect(teamMerkerLesen()).toEqual({ code: 'Code123', kennung: null, oeffentlich: false });
      expect(router.navigate).toHaveBeenCalledWith(['/login'], { queryParams: { returnUrl: '/einladung' } });
    });

    it('holt bei inzwischen geändertem Wortlaut (422 an der Kennung) den neuen selbst und fragt noch einmal', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team() });
      klick('team-ja');
      formularAusfuellen();
      fixture.componentInstance.einloesen();
      http
        .expectOne(`${URL}/einloesen`)
        .flush(
          { detail: [{ loc: ['body', 'team_einwilligung_kennung'], msg: 'Unbekannter Wortlaut' }] },
          { status: 422, statusText: 'Unprocessable Entity' },
        );
      pruefen({ einloesbar: true, team: team({ einwilligung_text: 'Neuer Wortlaut für Team BDK 26 Berlin' }) });

      const hinweis = el().querySelector('[data-testid="team-wortlaut-neu"]');
      expect(hinweis?.getAttribute('role')).toBe('alert');
      expect(hinweis?.textContent).toContain('Text der Einwilligung hat sich inzwischen geändert');
      expect(el().textContent).toContain('Neuer Wortlaut für Team BDK 26 Berlin');
      expect(el().textContent).not.toContain('nicht wie eine Mail-Adresse');
      // Nichts vorausgewählt: Die Person entscheidet zum neuen Text neu.
      expect(fixture.componentInstance.teamWahl).toBeNull();
      expect(teamMerkerLesen()).toBeNull();
    });

    it('lässt den Merker liegen, solange niemand angemeldet ist', () => {
      teamMerkerAblegen({ code: 'Code123', kennung: 'team-2026-11-26', oeffentlich: false });
      starten('Code123');
      pruefen({ einloesbar: true, team: team() });

      expect(teamMerkerLesen()).not.toBeNull();
    });
  });

  describe('angemeldet', () => {
    it('zeigt statt des Formulars die Frage und tritt nach „Ja“ bei: neu in der Sammlung', async () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team() }, true);

      expect(el().querySelector('input[type="email"]')).toBeNull();
      expect(el().querySelector('[data-testid="team-kasten"]')).not.toBeNull();
      expect(el().textContent).toContain('Die Nummer steht erst fest, wenn du beitrittst');
      expect(el().textContent).not.toContain('melde dich an');

      klick('team-ja');
      const anfrage = http.expectOne(`${URL}/beitreten`);
      expect(anfrage.request.body).toEqual({
        code: 'Code123',
        einwilligung: true,
        einwilligung_kennung: 'team-2026-11-26',
        oeffentlich: false,
      });
      expect(knopf('team-ja').disabled).toBeTrue();
      anfrage.flush({ team: { name: 'BDK 26 Berlin', motiv: 'vogel', saison: '2026' }, nummer: 37, neu: true });
      fixture.detectChanges();
      await fixture.whenStable();

      const titel = el().querySelector('[data-testid="team-ergebnis"]')!;
      expect(titel.textContent?.trim()).toBe('Neu in deiner Sammlung: Team BDK 26 Berlin, Nr. 37');
      expect(document.activeElement).toBe(titel);
      expect(el().querySelector('img')?.getAttribute('alt')).toBe('Motiv Vogel');
      expect(el().textContent).toContain('Zu meinen Teams');
    });

    it('macht nach dem Beitreten „Ersten Spruch suchen“ zum Hauptknopf, „Zu meinen Teams“ zum zweiten (UX-Review 25.11.)', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team() }, true);
      klick('team-ja');
      http
        .expectOne(`${URL}/beitreten`)
        .flush({ team: { name: 'BDK 26 Berlin', motiv: 'vogel', saison: '2026' }, nummer: 37, neu: true });
      fixture.detectChanges();

      const knoepfe = Array.from(el().querySelectorAll<HTMLAnchorElement>('.team-knoepfe a'));
      expect(knoepfe.map((k) => k.textContent?.trim())).toEqual(['Ersten Spruch suchen', 'Zu meinen Teams']);
      expect(knoepfe[0].hasAttribute('mat-raised-button')).toBeTrue();
      expect(knoepfe[0].getAttribute('href')).toBe('/search#suchen');
      expect(knoepfe[1].hasAttribute('mat-stroked-button')).toBeTrue();
      expect(knoepfe[1].getAttribute('href')).toBe('/contributions');
      expect(el().querySelector('[data-testid="erster-spruch-satz"]')?.textContent).toContain(
        'Such den Spruch, der dich zuletzt geärgert hat',
      );
    });

    it('schickt die zweite Frage mit, wenn sie angehakt ist', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team(OEFFENTLICH) }, true);
      fixture.componentInstance.teamOeffentlich = true;
      klick('team-ja');

      const anfrage = http.expectOne(`${URL}/beitreten`);
      expect(anfrage.request.body.oeffentlich).toBeTrue();
      expect(anfrage.request.body.oeffentlich_kennung).toBe('team-oeffentlich-2026-11-25');
      anfrage.flush({ team: { name: 'BDK 26 Berlin', motiv: 'vogel', saison: '2026' }, nummer: 37, neu: true });
    });

    it('meldet „schon dabei“ mit der vorhandenen Nummer, wenn /beitreten neu=false sagt', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team() }, true);
      klick('team-ja');
      http
        .expectOne(`${URL}/beitreten`)
        .flush({ team: { name: 'BDK 26 Berlin', motiv: 'vogel', saison: '2026' }, nummer: 12, neu: false });
      fixture.detectChanges();

      expect(el().querySelector('[data-testid="team-ergebnis"]')?.textContent?.trim()).toBe('Du bist schon dabei (Nr. 12)');
      expect(el().textContent).toContain('zählt für dich nicht noch einmal');
      // Auch hier zuerst die Suche
      expect(el().querySelector('.team-knoepfe a')?.textContent?.trim()).toBe('Ersten Spruch suchen');
    });

    it('zeigt „schon dabei“ ohne Frage und ohne Anfrage, wenn /pruefen die eigene Nummer kennt', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team({ eigene_nummer: 5 }) }, true);

      http.expectNone(`${URL}/beitreten`);
      expect(el().querySelector('[data-testid="team-kasten"]')).toBeNull();
      expect(el().querySelector('[data-testid="team-ergebnis"]')?.textContent?.trim()).toBe('Du bist schon dabei (Nr. 5)');
    });

    it('speichert nach „Nein“ nichts und sagt das', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team() }, true);
      klick('team-nein');

      http.expectNone(`${URL}/beitreten`);
      expect(el().textContent).toContain('Ohne Team weiter');
      expect(el().textContent).toContain('wir speichern kein Team');
    });

    it('Einladung ohne Team bei wirksamem Schalter: Hinweis statt Formular', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: null }, true);
      http.expectOne(FUNKTIONEN).flush({ funktionen: { teams: true } });
      fixture.detectChanges();

      expect(el().querySelector('input[type="email"]')).toBeNull();
      expect(el().textContent).toContain('Du hast schon ein Konto');
    });

    it('Schalter teams aus: die Seite bleibt wie vorher, mit Formular', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: null }, true);
      http.expectOne(FUNKTIONEN).flush({ funktionen: { teams: false } });
      fixture.detectChanges();

      expect(el().querySelector('input[type="email"]')).not.toBeNull();
      expect(el().textContent).not.toContain('Du hast schon ein Konto');
    });

    for (const [status, text] of [
      [410, 'gilt nicht'],
      [409, 'Du hast schon ein Konto'],
      [404, 'Du hast schon ein Konto'],
      [429, 'Viertelstunde'],
      [401, 'nicht mehr angemeldet'],
      [500, 'hat nicht geklappt'],
    ] as const) {
      it(`sagt bei ${status} von /beitreten, woran es liegt`, () => {
        starten('Code123');
        pruefen({ einloesbar: true, team: team() }, true);
        klick('team-ja');
        http.expectOne(`${URL}/beitreten`).flush('nein', { status, statusText: 'Fehler' });
        fixture.detectChanges();

        expect(el().textContent).toContain(text);
      });
    }

    it('holt bei 422 an der Kennung von /beitreten den neuen Wortlaut selbst und fragt noch einmal', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team() }, true);
      klick('team-ja');
      http
        .expectOne(`${URL}/beitreten`)
        .flush(
          { detail: [{ loc: ['body', 'einwilligung_kennung'], msg: 'Unbekannter Wortlaut' }] },
          { status: 422, statusText: 'Unprocessable Entity' },
        );
      pruefen({ einloesbar: true, team: team({ einwilligung_text: 'Neuer Wortlaut für Team BDK 26 Berlin' }) }, true);

      expect(el().querySelector('[data-testid="team-wortlaut-neu"]')?.textContent).toContain('Gespeichert ist noch nichts');
      expect(el().textContent).toContain('Neuer Wortlaut für Team BDK 26 Berlin');
      expect(el().textContent).not.toContain('hat nicht geklappt');

      klick('team-ja');
      expect(http.expectOne(`${URL}/beitreten`).request.body.einwilligung_kennung).toBe('team-2026-11-26');
    });

    it('führt nach einem Fehler zurück zur Frage', () => {
      starten('Code123');
      pruefen({ einloesbar: true, team: team() }, true);
      klick('team-ja');
      http.expectOne(`${URL}/beitreten`).flush('kaputt', { status: 500, statusText: 'Fehler' });
      fixture.detectChanges();

      Array.from(el().querySelectorAll('button')).find((b) => b.textContent?.includes('Zurück zur Frage'))!.click();
      fixture.detectChanges();
      expect(el().querySelector('[data-testid="team-kasten"]')).not.toBeNull();
    });
  });

  describe('Rücksprung nach dem Anlegen', () => {
    it('nimmt den Code aus dem Merker und zeigt das beim Anlegen gespeicherte Team als neu', () => {
      teamMerkerAblegen({ code: 'Code123', kennung: 'team-2026-11-26', oeffentlich: false });
      starten(null);
      pruefen({ einloesbar: true, team: team({ eigene_nummer: 37 }) }, true);

      http.expectNone(`${URL}/beitreten`);
      expect(el().querySelector('[data-testid="team-ergebnis"]')?.textContent?.trim()).toBe(
        'Neu in deiner Sammlung: Team BDK 26 Berlin, Nr. 37',
      );
      expect(teamMerkerLesen()).toBeNull();
    });

    it('fragt nach dem „Ja“ beim Anlegen noch einmal, wenn es das Konto vorher schon gab, und sendet nichts von selbst', () => {
      // Geteiltes Gerät: Angemeldet kann jemand anderes sein als die Person, die „Ja“ gedrückt hat.
      teamMerkerAblegen({ code: 'Code123', kennung: 'team-2026-11-26', oeffentlich: true });
      starten(null);
      pruefen({ einloesbar: true, team: team(OEFFENTLICH) }, true);

      http.expectNone(`${URL}/beitreten`);
      expect(el().querySelector('[data-testid="team-kasten"]')).not.toBeNull();
      expect(el().querySelector('[data-testid="team-nochmal"]')?.textContent).toContain('gespeichert ist aber noch nichts');
      // nichts vorausgewählt, auch die zweite Frage nicht
      expect(fixture.componentInstance.teamOeffentlich).toBeFalse();
      expect(teamMerkerLesen()).toBeNull();

      klick('team-ja');
      const anfrage = http.expectOne(`${URL}/beitreten`);
      expect(anfrage.request.body).toEqual({
        code: 'Code123',
        einwilligung: true,
        einwilligung_kennung: 'team-2026-11-26',
        oeffentlich: false,
      });
      anfrage.flush({ team: { name: 'BDK 26 Berlin', motiv: 'vogel', saison: '2026' }, nummer: 38, neu: true });
      fixture.detectChanges();

      expect(el().textContent).toContain('Neu in deiner Sammlung: Team BDK 26 Berlin, Nr. 38');
    });

    it('fragt neu, wenn sich der Wortlaut seit dem „Ja“ geändert hat', () => {
      teamMerkerAblegen({ code: 'Code123', kennung: 'team-2026-01-01', oeffentlich: false });
      starten(null);
      pruefen({ einloesbar: true, team: team() }, true);

      http.expectNone(`${URL}/beitreten`);
      expect(el().querySelector('[data-testid="team-kasten"]')).not.toBeNull();
    });

    it('fragt nach der Anmeldung über „melde dich an“, ohne von selbst beizutreten', () => {
      teamMerkerAblegen({ code: 'Code123', kennung: null, oeffentlich: false });
      starten(null);
      pruefen({ einloesbar: true, team: team() }, true);

      http.expectNone(`${URL}/beitreten`);
      expect(el().querySelector('[data-testid="team-kasten"]')).not.toBeNull();
      expect(teamMerkerLesen()).toBeNull();
    });

    it('sagt bei einem inzwischen aufgebrauchten Link ehrlich, dass kein Team gespeichert ist', () => {
      teamMerkerAblegen({ code: 'Code123', kennung: 'team-2026-11-26', oeffentlich: false });
      starten(null);
      pruefen({ einloesbar: false, team: null }, true);

      expect(el().querySelector('[data-testid="kein-team"]')?.textContent).toContain('Kein Team gespeichert');
      expect(el().textContent).not.toContain('Meine Beiträge');
    });

    it('zeigt einem Mitglied auch bei aufgebrauchtem Link das Team als neu', () => {
      teamMerkerAblegen({ code: 'Code123', kennung: 'team-2026-11-26', oeffentlich: false });
      starten(null);
      pruefen({ einloesbar: false, team: team({ eigene_nummer: 37 }) }, true);

      expect(el().querySelector('[data-testid="team-ergebnis"]')?.textContent?.trim()).toBe(
        'Neu in deiner Sammlung: Team BDK 26 Berlin, Nr. 37',
      );
    });

    it('ohne Merker und ohne Code fragt die Seite wie bisher nach dem Link', () => {
      starten(null);

      http.expectNone(`${URL}/pruefen`);
      expect(el().querySelector('input[name="link"]')).not.toBeNull();
    });
  });
});
