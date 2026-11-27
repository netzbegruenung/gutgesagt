import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { EinladungenComponent } from './einladungen.component';
import { Einladung } from '../../shared/einladung/einladung.service';
import { environment } from '../../../environments/environment';

const URL = `${environment.baseUrl}/api/v1/einladungen`;

const GRUPPE: Einladung = {
  id: 'e1',
  code: 'GruppenCode123',
  notiz: 'Kreisverband, Herbsttreffen',
  erlaubte_einloesungen: 50,
  einloesungen: 3,
  gueltig_bis: '2026-11-27',
  abgeschaltet: false,
  angelegt_am: '2026-10-30',
  zustand: 'aktiv',
};

describe('EinladungenComponent', () => {
  let fixture: ComponentFixture<EinladungenComponent>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [EinladungenComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideNoopAnimations()],
    }).compileComponents();

    fixture = TestBed.createComponent(EinladungenComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function el(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function laden(einladungen: Einladung[], eingerichtet = true) {
    http.expectOne(URL).flush({ einloesen_eingerichtet: eingerichtet, einladungen });
    fixture.detectChanges();
  }

  it('zeigt Notiz, Zaehler, letzten Tag, Zustand und Link', () => {
    laden([GRUPPE]);

    const zeile = el().querySelector('[data-testid="einladung"]')!;
    expect(zeile.textContent).toContain('Kreisverband, Herbsttreffen');
    expect(zeile.textContent).toContain('3 von 50');
    expect(zeile.textContent).toContain('27.11.2026');
    expect(zeile.textContent).toContain('Aktiv');
    expect(zeile.textContent).toContain(`${window.location.origin}/einladung#GruppenCode123`);
  });

  it('legt eine Einladung mit Notiz, Zahl und letztem Tag an', () => {
    laden([]);
    const komponente = fixture.componentInstance;
    komponente.notiz = 'Persönlicher Link';
    komponente.erlaubteEinloesungen = 1;
    komponente.gueltigBis = '2026-11-13';

    komponente.anlegen();

    const anfrage = http.expectOne((r) => r.method === 'POST' && r.url === URL);
    expect(anfrage.request.body).toEqual({
      notiz: 'Persönlicher Link',
      erlaubte_einloesungen: 1,
      gueltig_bis: '2026-11-13',
    });
    anfrage.flush({ ...GRUPPE, id: 'e2', notiz: 'Persönlicher Link', erlaubte_einloesungen: 1, einloesungen: 0 });
    fixture.detectChanges();

    expect(el().querySelectorAll('[data-testid="einladung"]').length).toBe(1);
    expect(el().textContent).toContain('0 von 1');
  });

  it('schaltet eine Einladung ab', () => {
    laden([GRUPPE]);

    (el().querySelector('[data-testid="schalten"]') as HTMLButtonElement).click();

    const anfrage = http.expectOne(`${URL}/e1`);
    expect(anfrage.request.method).toBe('PATCH');
    expect(anfrage.request.body).toEqual({ abgeschaltet: true });
    anfrage.flush({ ...GRUPPE, abgeschaltet: true, zustand: 'abgeschaltet' });
    fixture.detectChanges();

    expect(el().querySelector('[data-testid="einladung"]')!.textContent).toContain('Abgeschaltet');
    expect(el().querySelector('[data-testid="schalten"]')!.textContent).toContain('Einschalten');
  });

  it('meldet, wenn Umschalten scheitert, ohne die Liste zu verlieren', () => {
    laden([GRUPPE]);

    (el().querySelector('[data-testid="schalten"]') as HTMLButtonElement).click();
    http.expectOne(`${URL}/e1`).flush('kaputt', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();

    expect(el().textContent).toContain('nicht umgeschaltet');
    expect(el().textContent).not.toContain('nicht geladen');
    expect(el().querySelectorAll('[data-testid="einladung"]').length).toBe(1);
  });

  it('warnt, wenn Einloesen nicht eingerichtet ist', () => {
    laden([GRUPPE], false);

    expect(el().textContent).toContain('noch nicht eingerichtet');
  });

  it('meldet einen Ladefehler', () => {
    http.expectOne(URL).flush('kaputt', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();

    expect(el().textContent).toContain('gerade nicht erreichbar, neuer Versuch in Kürze');
  });
  describe('Teams', () => {
    const MOTIVE = [
      { schluessel: 'vogel', name: 'Vogel' },
      { schluessel: 'sprechblase', name: 'Sprechblase' },
      { schluessel: 'handschlag', name: 'Handschlag' },
      { schluessel: 'laufschuh', name: 'Laufschuh' },
      { schluessel: 'waage', name: 'Waage' },
      { schluessel: 'lautsprecher', name: 'Lautsprecher' },
    ];
    const TEAMLINK: Einladung = {
      ...GRUPPE,
      id: 't1',
      notiz: 'Stand BDK',
      team: { name: 'BDK 26 Berlin', motiv: 'vogel', saison: '2026', mitglieder: 36 },
    };

    function mitTeams(einladungen: Einladung[], aktiv = true, saisonVorschlag?: string) {
      http.expectOne(URL).flush({
        einloesen_eingerichtet: true,
        einladungen,
        teams_aktiv: aktiv,
        aktuelle_saison: '2026',
        ...(saisonVorschlag ? { saison_vorschlag: saisonVorschlag } : {}),
        motive: MOTIVE,
        teamname_hinweis: 'Nur nach Anlass, Ort oder Saison benennen.',
      });
      fixture.detectChanges();
    }

    it('zeigt ohne Schalter teams weder Teamblock noch Spalten', () => {
      mitTeams([GRUPPE], false);

      expect(el().querySelector('[data-testid="team-block"]')).toBeNull();
      expect(el().querySelector('[data-testid="team"]')).toBeNull();
      expect(el().textContent).not.toContain('Mitglieder');
    });

    it('zeigt den Block „Team (optional)“ mit Saison-Vorschlag, Hinweis und allen Motiven mit Namen', () => {
      mitTeams([]);

      const block = el().querySelector('[data-testid="team-block"]') as HTMLElement;
      expect(block.querySelector('legend')!.textContent).toContain('Team (optional)');
      expect(block.textContent).toContain('Nur nach Anlass, Ort oder Saison benennen.');
      const motive = Array.from(block.querySelectorAll('[data-testid="motiv"]'));
      expect(motive.length).toBe(6);
      expect(motive.map((m) => m.textContent!.trim())).toEqual(MOTIVE.map((m) => m.name));
      expect(motive.every((m) => m.querySelector('img[src^="/meilensteine/"]'))).toBeTrue();
      expect(block.querySelector('mat-radio-group')!.getAttribute('role')).toBe('radiogroup');
      expect(fixture.componentInstance.teamSaison).toBe('2026');
      expect((block.querySelector('input[name="teamName"]') as HTMLInputElement).maxLength).toBe(40);
    });

    it('schlägt die laufende oder nächste angelegte Saison vor, nicht die Einstellung', () => {
      mitTeams([], true, 'Winter 26/27');

      const feld = el().querySelector('input[name="teamSaison"]') as HTMLInputElement;
      expect(fixture.componentInstance.teamSaison).toBe('Winter 26/27');
      // Freitext bleibt möglich
      expect(feld.readOnly).toBeFalse();
    });

    it('legt einen Teamlink mit Name, Motiv und Saison an', () => {
      mitTeams([]);
      const k = fixture.componentInstance;
      k.notiz = 'Stand BDK';
      k.erlaubteEinloesungen = 50;
      k.gueltigBis = '2026-12-06';
      k.teamName = '  BDK 26 Berlin ';
      k.teamMotiv = 'waage';

      k.anlegen();

      const anfrage = http.expectOne((r) => r.method === 'POST' && r.url === URL);
      expect(anfrage.request.body).toEqual({
        notiz: 'Stand BDK',
        erlaubte_einloesungen: 50,
        gueltig_bis: '2026-12-06',
        team_name: 'BDK 26 Berlin',
        team_motiv: 'waage',
        team_saison: '2026',
        team_art: 'anlass',
      });
      anfrage.flush({ ...TEAMLINK, team: { ...TEAMLINK.team!, mitglieder: 0 } });
      fixture.detectChanges();
      expect(k.teamName).toBe('');
    });

    it('sperrt Anlegen mit Teamname ohne Saison oder mit verbotenen Zeichen', () => {
      mitTeams([]);
      const k = fixture.componentInstance;
      k.notiz = 'Stand';
      k.teamName = 'Team';
      k.teamSaison = ' ';
      expect(k.kannAnlegen).toBeFalse();
      k.teamSaison = '2026';
      expect(k.kannAnlegen).toBeTrue();
      k.teamName = 'a/b';
      expect(k.kannAnlegen).toBeFalse();
      k.anlegen();
      http.expectNone((r) => r.method === 'POST');
    });

    it('erlaubt eine Saison mit Schrägstrich wie „Winter 26/27“ (Befund 6)', () => {
      mitTeams([]);
      const k = fixture.componentInstance;
      k.notiz = 'Stand';
      k.teamName = 'BDK';
      k.teamSaison = 'Winter 26/27';
      expect(k.kannAnlegen).toBeTrue();
    });

    it('zeigt bei 422 den Text des Servers, etwa für eine Saison, die es nicht gibt', () => {
      mitTeams([]);
      const k = fixture.componentInstance;
      k.notiz = 'Stand';
      k.teamName = 'BDK';
      k.teamSaison = '2026';
      k.anlegen();
      http
        .expectOne((r) => r.method === 'POST' && r.url === URL)
        .flush({ detail: 'Diese Saison gibt es nicht.' }, { status: 422, statusText: 'Unprocessable' });
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain(
        'Die Einladung konnte nicht angelegt werden. Diese Saison gibt es nicht.',
      );
    });

    it('Teamart: Standard „Team nach Anlass, Ort oder Saison“, Datum nur bei „Team nach Gruppe“', () => {
      mitTeams([]);
      const block = el().querySelector('[data-testid="team-block"]') as HTMLElement;

      const arten = Array.from(block.querySelectorAll('[data-testid="team-art"]'));
      expect(arten.map((a) => a.textContent!.trim())).toEqual(['Team nach Anlass, Ort oder Saison', 'Team nach Gruppe']);
      expect(fixture.componentInstance.teamArt).toBe('anlass');
      expect(block.querySelector('[data-testid="team-zustimmung"]')).toBeNull();

      fixture.componentInstance.teamArt = 'gruppe';
      fixture.detectChanges();

      const feld = block.querySelector('[data-testid="team-zustimmung"]') as HTMLElement;
      expect(feld.textContent).toContain('Zustimmung der Gruppenleitung liegt schriftlich vor (Datum)');
      expect((feld.querySelector('input') as HTMLInputElement).type).toBe('date');
    });

    it('Team nach Gruppe: das Namensfeld heißt „Name der Gruppe …“ mit Hinweis, sonst „Teamname“', () => {
      mitTeams([]);
      const feld = () => el().querySelector('.team-name') as HTMLElement;
      expect(feld().querySelector('mat-label')!.textContent!.trim()).toBe('Teamname');
      expect(feld().textContent).not.toContain('Ohne Zusätze');

      fixture.componentInstance.teamArt = 'gruppe';
      fixture.detectChanges();

      expect(feld().querySelector('mat-label')!.textContent!.trim()).toBe(
        'Name der Gruppe (genau so, wie sie öffentlich heißt)'
      );
      const hinweis = feld().querySelector('[data-testid="teamname-hinweis"]')!.textContent!;
      expect(hinweis).toContain('Ohne Zusätze wie Ort oder Jahr: Die Begrüßung nennt die Gruppe mit genau diesem Namen.');
      // der allgemeine Hinweis zum Teamnamen bleibt dabei
      expect(hinweis).toContain('Nur nach Anlass, Ort oder Saison benennen.');
    });

    it('zeigt am Teamnamen den Hinweis wortgleich, auch ohne Hinweis vom Server', () => {
      http.expectOne(URL).flush({ einloesen_eingerichtet: true, einladungen: [], teams_aktiv: true, motive: MOTIVE });
      fixture.detectChanges();

      const name = el().querySelector('.team-name') as HTMLElement;
      expect(name.textContent).toContain(
        'Anlass, Ort, Saison oder öffentliche Gruppe mit schriftlicher Zustimmung; keine Namen zu Religion, Gesundheit, sexueller Orientierung, Herkunft oder Gewerkschaft.'
      );
      expect(name.textContent).not.toContain('Nie nach Personen');
    });

    it('Team nach Gruppe: Anlegen nur mit Datum der Zustimmung, höchstens heute; Datum geht mit', () => {
      mitTeams([]);
      const k = fixture.componentInstance;
      k.notiz = 'Gruppe';
      k.teamName = 'Netzfeuerwehr';
      k.teamArt = 'gruppe';
      fixture.detectChanges();
      expect(k.kannAnlegen).toBeFalse();
      expect(el().querySelector('[data-testid="team-zustimmung-fehlt"]')).not.toBeNull();
      k.teamZustimmungAm = '2999-01-01';
      expect(k.kannAnlegen).toBeFalse();
      k.anlegen();
      http.expectNone((r) => r.method === 'POST');

      k.teamZustimmungAm = '2026-11-20';
      expect(k.kannAnlegen).toBeTrue();
      k.anlegen();

      const anfrage = http.expectOne((r) => r.method === 'POST' && r.url === URL);
      expect(anfrage.request.body.team_art).toBe('gruppe');
      expect(anfrage.request.body.team_zustimmung_am).toBe('2026-11-20');
      anfrage.flush({ ...TEAMLINK, team: { ...TEAMLINK.team!, art: 'gruppe', zustimmung_am: '2026-11-20' } });
      fixture.detectChanges();
      expect(k.teamArt).toBe('anlass');
      expect(k.teamZustimmungAm).toBe('');
    });

    it('Team nach Anlass schickt kein Datum mit, auch wenn eines eingetragen war', () => {
      mitTeams([]);
      const k = fixture.componentInstance;
      k.notiz = 'Stand';
      k.teamName = 'Bayreuth';
      k.teamZustimmungAm = '2026-11-20';

      k.anlegen();

      const anfrage = http.expectOne((r) => r.method === 'POST' && r.url === URL);
      expect(anfrage.request.body.team_art).toBe('anlass');
      expect('team_zustimmung_am' in anfrage.request.body).toBeFalse();
      anfrage.flush(TEAMLINK);
    });

    it('zeigt in der Liste bei einem Team nach Gruppe Art und Tag der Zustimmung, sonst nicht', () => {
      const NACH_GRUPPE: Einladung = {
        ...TEAMLINK,
        id: 't2',
        team: { name: 'Netzfeuerwehr', motiv: 'vogel', saison: '2026', art: 'gruppe', zustimmung_am: '2026-11-20', mitglieder: 4 },
      };
      mitTeams([NACH_GRUPPE, TEAMLINK]);

      const [gruppe, anlass] = Array.from(el().querySelectorAll('[data-testid="einladung"]'));
      expect(gruppe.querySelector('[data-testid="team-art-zeile"]')!.textContent).toContain(
        'Nach Gruppe, Zustimmung vom 20.11.2026'
      );
      expect(anlass.querySelector('[data-testid="team-art-zeile"]')).toBeNull();
      expect(gruppe.querySelector('[data-testid="mitglieder"]')!.textContent!.trim()).toBe('4');
    });

    it('zeigt in der Liste Team mit Motiv und Saison und nur die Zahl der Mitglieder', () => {
      mitTeams([TEAMLINK, GRUPPE]);

      const [mit, ohne] = Array.from(el().querySelectorAll('[data-testid="einladung"]'));
      const team = mit.querySelector('[data-testid="team"]')!;
      expect(team.textContent).toContain('BDK 26 Berlin');
      expect(team.textContent).toContain('2026');
      expect(team.querySelector('img')!.getAttribute('src')).toBe('/meilensteine/vogel.svg');
      expect(mit.querySelector('[data-testid="mitglieder"]')!.textContent!.trim()).toBe('36');
      expect(ohne.querySelector('[data-testid="team"]')!.textContent).toContain('kein Team');
      expect(el().textContent).toContain('nur die Zahl der Mitglieder');
    });

    /** ngModel meldet seine Steuerelemente erst nach einem Microtask an; whenStable wartet wegen
        des Selbst-Nachladens ewig. */
    const ruhe = () => new Promise((fertig) => setTimeout(fertig));

    function tippen(name: string, wert: string) {
      const feld = el().querySelector(`input[name="${name}"]`) as HTMLInputElement;
      feld.value = wert;
      feld.dispatchEvent(new Event('input'));
      feld.dispatchEvent(new Event('blur'));
    }

    it('setzt das Formular nach dem Anlegen auf Standard zurück, ohne Fehleranzeige an der Notiz', async () => {
      // Der Standard der Saison ist der Vorschlag des Servers (laufende oder nächste Saison)
      mitTeams([], true, 'Winter 26/27');
      await ruhe();
      const k = fixture.componentInstance;
      tippen('notiz', 'Selbsttest');
      tippen('erlaubteEinloesungen', '30');
      tippen('gueltigBis', '2026-12-24');
      tippen('teamName', 'Selbsttest');
      tippen('teamSaison', 'Winter');
      k.teamMotiv = 'waage';
      fixture.detectChanges();

      const knopf = Array.from(el().querySelectorAll('button[type="submit"]'))[0] as HTMLButtonElement;
      expect(knopf.disabled).toBeFalse();
      knopf.click();
      http
        .expectOne((r) => r.method === 'POST' && r.url === URL)
        .flush({ ...TEAMLINK, id: 't2', notiz: 'Selbsttest', team: { ...TEAMLINK.team!, name: 'Selbsttest', mitglieder: 0 } });
      fixture.detectChanges();
      await ruhe();
      fixture.detectChanges();

      expect(k.notiz).toBe('');
      expect(k.erlaubteEinloesungen).toBe(1);
      expect(k.gueltigBis).not.toBe('2026-12-24');
      expect(k.teamName).toBe('');
      expect(k.teamSaison).toBe('Winter 26/27');
      expect(k.teamMotiv).toBe('vogel');
      expect(k.teamArt).toBe('anlass');
      const notiz = el().querySelector('input[name="notiz"]') as HTMLInputElement;
      expect(notiz.value).toBe('');
      expect(notiz.getAttribute('aria-invalid')).not.toBe('true');
      expect(el().querySelector('form .mat-form-field-invalid')).toBeNull();
      expect(el().querySelectorAll('[data-testid="einladung"]').length).toBe(1);
    });

    it('setzt ohne Schalter teams das Formular ebenso ohne Fehleranzeige zurück', async () => {
      mitTeams([], false);
      await ruhe();
      const k = fixture.componentInstance;
      tippen('notiz', 'Persönlicher Link');
      tippen('erlaubteEinloesungen', '5');
      tippen('gueltigBis', '2026-12-24');
      fixture.detectChanges();

      (el().querySelector('button[type="submit"]') as HTMLButtonElement).click();
      http.expectOne((r) => r.method === 'POST' && r.url === URL).flush({ ...GRUPPE, id: 'e2', notiz: 'Persönlicher Link' });
      fixture.detectChanges();
      await ruhe();
      fixture.detectChanges();

      expect(k.notiz).toBe('');
      expect(k.erlaubteEinloesungen).toBe(1);
      expect(k.gueltigBis).not.toBe('2026-12-24');
      expect((el().querySelector('input[name="erlaubteEinloesungen"]') as HTMLInputElement).value).toBe('1');
      expect(el().querySelector('form .mat-form-field-invalid')).toBeNull();
    });

    it('bricht die Team-Pille in einer engen Tabelle nicht mitten im Wort um', () => {
      // Knapp über der Kartenbreite, mit langer Notiz: die Tabelle ist zu eng und gibt jeder
      // Spalte nur ihre Mindestbreite. Vorher war die der Pille ein Buchstabe („Sel / bstt / est“).
      (fixture.nativeElement as HTMLElement).style.display = 'block';
      (fixture.nativeElement as HTMLElement).style.width = '960px';
      mitTeams([
        { ...TEAMLINK, team: { ...TEAMLINK.team!, name: 'Selbsttest' } },
        { ...TEAMLINK, id: 't2', notiz: 'Kreisverband Beispielstadt, Infostand am Wochenmarkt', team: { ...TEAMLINK.team!, name: 'Grüne Jugend Beispielstadt' } },
      ]);

      expect(el().querySelector('thead')!.getBoundingClientRect().height).toBeGreaterThan(0);
      for (const name of Array.from(el().querySelectorAll('[data-testid="team"] app-team-pille .name')) as HTMLElement[]) {
        // Jedes Wort passt in die Breite der Pille: kein Wort ist breiter als sein Kasten
        expect(name.scrollWidth).toBeLessThanOrEqual(name.clientWidth + 1);
      }
      const selbsttest = el().querySelector('[data-testid="team"] app-team-pille .name') as HTMLElement;
      const zeile = parseFloat(getComputedStyle(selbsttest).lineHeight);
      expect(selbsttest.getBoundingClientRect().height).toBeLessThan(zeile * 1.5);
    });

    it('zeigt den Kopier-Knopf neben dem gekürzten Link, mit Namen und mindestens 24 px', () => {
      mitTeams([TEAMLINK]);

      const zeile = el().querySelector('[data-testid="einladung"] .link-zeile') as HTMLElement;
      const text = zeile.querySelector('[data-testid="link-text"]') as HTMLElement;
      const knopf = zeile.querySelector('[data-testid="kopieren"]') as HTMLButtonElement;
      expect(getComputedStyle(zeile).display).toBe('flex');
      expect(text.contains(knopf)).toBeFalse();
      expect(text.getAttribute('title')).toBe(`${window.location.origin}/einladung#GruppenCode123`);
      expect(knopf.getAttribute('aria-label')).toBe('Link kopieren: Stand BDK');
      const t = text.getBoundingClientRect();
      const b = knopf.getBoundingClientRect();
      // Nebeneinander, nichts überdeckt
      expect(b.left).toBeGreaterThanOrEqual(t.right);
      expect(b.width).toBeGreaterThanOrEqual(24);
      expect(b.height).toBeGreaterThanOrEqual(24);
    });

    it('folgt beim Nachladen dem neuen Vorschlag, solange die Saison unverändert ist', () => {
      mitTeams([]);
      const k = fixture.componentInstance;
      (k as unknown as { uebernehmen(l: unknown): void }).uebernehmen({
        einloesen_eingerichtet: true,
        einladungen: [],
        teams_aktiv: true,
        aktuelle_saison: '2026',
        saison_vorschlag: 'Winter 26/27',
      });
      expect(k.teamSaison).toBe('Winter 26/27');
    });

    it('übernimmt beim Nachladen einen neuen Saison-Vorschlag nur, wenn niemand die Saison geändert hat', () => {
      mitTeams([]);
      const k = fixture.componentInstance;
      k.teamSaison = 'Winter';
      (k as unknown as { uebernehmen(l: unknown): void }).uebernehmen({
        einloesen_eingerichtet: true,
        einladungen: [],
        teams_aktiv: true,
        aktuelle_saison: '2027',
      });
      expect(k.teamSaison).toBe('Winter');
    });
  });
});
