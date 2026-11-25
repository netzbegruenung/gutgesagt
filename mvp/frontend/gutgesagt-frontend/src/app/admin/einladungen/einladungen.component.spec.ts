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

    function mitTeams(einladungen: Einladung[], aktiv = true) {
      http.expectOne(URL).flush({
        einloesen_eingerichtet: true,
        einladungen,
        teams_aktiv: aktiv,
        aktuelle_saison: '2026',
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
