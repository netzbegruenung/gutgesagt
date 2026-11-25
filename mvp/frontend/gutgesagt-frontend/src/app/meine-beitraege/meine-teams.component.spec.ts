import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { MatDialog } from '@angular/material/dialog';
import { of } from 'rxjs';

import { MeineTeamsComponent, verlassenFrage } from './meine-teams.component';
import { MeinTeam, MeineTeams } from '../services/teams.service';
import { environment } from '../../environments/environment';

const URL = `${environment.baseUrl}/api/v1/teams`;

function team(teil: Partial<MeinTeam> & { id: string }): MeinTeam {
  return {
    team_name: 'BDK 26 Berlin',
    motiv: 'vogel',
    motiv_name: 'Vogel',
    saison: '2026',
    nummer: 37,
    eingetreten_am: '2026-11-25',
    aktuelle_saison: true,
    ...teil,
  };
}

const WORTLAUT = 'Ich willige ausdrücklich ein, dass andere Angemeldete an meinem Namen sehen …';

function stand(teil: Partial<MeineTeams> = {}): MeineTeams {
  return {
    aktuelle_saison: '2026',
    oeffentlich_verfuegbar: false,
    oeffentlich_zeigen: null,
    oeffentlich_kennung: null,
    oeffentlich_text: null,
    teams: [team({ id: 'm1' }), team({ id: 'm2', team_name: 'Bayreuth', motiv: 'waage', saison: '2025', nummer: 4, aktuelle_saison: false })],
    ...teil,
  };
}

describe('MeineTeamsComponent', () => {
  let fixture: ComponentFixture<MeineTeamsComponent>;
  let http: HttpTestingController;
  let dialog: jasmine.SpyObj<MatDialog>;

  beforeEach(async () => {
    dialog = jasmine.createSpyObj<MatDialog>('MatDialog', ['open']);
    await TestBed.configureTestingModule({
      imports: [MeineTeamsComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideNoopAnimations(), provideRouter([])],
    })
      .overrideProvider(MatDialog, { useValue: dialog })
      .compileComponents();
    fixture = TestBed.createComponent(MeineTeamsComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => {
    fixture.destroy();
    http.verify();
  });

  function el(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function laden(daten: MeineTeams): void {
    http.expectOne(`${URL}/meine`).flush(daten);
    fixture.detectChanges();
  }

  it('zeigt die Teams der aktuellen Saison als Liste und vergangene als Abzeichen', () => {
    laden(stand());

    const listen = el().querySelectorAll('ul[role="list"]');
    expect(listen.length).toBe(2);
    const aktuell = el().querySelector('[data-testid="team"]')!;
    expect(aktuell.textContent).toContain('BDK 26 Berlin');
    expect(aktuell.textContent).toContain('Nr. 37');
    expect(aktuell.textContent).toContain('2026');
    expect(aktuell.querySelector('img')!.getAttribute('src')).toBe('/meilensteine/vogel.svg');
    const vergangen = el().querySelector('[data-testid="team-vergangen"]')!;
    expect(vergangen.textContent).toContain('Bayreuth');
    expect(vergangen.textContent).toContain('Nr. 4');
    expect(vergangen.querySelector('.team-pille.vergangen')).not.toBeNull();
    expect(el().textContent).toContain('Vergangene Saisons');
    expect(el().querySelector('[data-testid="sichtbarkeit"]')!.textContent).toContain('Nur du siehst deine Teams.');
  });

  it('zeigt ohne Schalter teams (404) keine Karte', () => {
    http.expectOne(`${URL}/meine`).flush({ detail: 'Not found' }, { status: 404, statusText: 'Not Found' });
    fixture.detectChanges();

    expect(el().querySelector('[data-testid="meine-teams"]')).toBeNull();
  });

  it('zeigt bei Schalter teams aus die eigenen Teams weiter, mit „Team verlassen“ und ohne Umschalter', () => {
    laden(stand({ teams_aktiv: false }));

    expect(el().querySelector('[data-testid="meine-teams"]')).not.toBeNull();
    expect(el().querySelector('[data-testid="teams-aus"]')!.textContent).toContain('weiter ansehen und verlassen');
    expect(el().querySelectorAll('[data-testid="verlassen"]').length).toBe(2);
    expect(el().querySelector('mat-slide-toggle')).toBeNull();
  });

  it('blendet die Karte bei Schalter teams aus aus, sobald keine eigenen Teams mehr da sind', () => {
    laden(stand({ teams_aktiv: false, teams: [] }));

    expect(el().querySelector('[data-testid="meine-teams"]')).toBeNull();
  });

  it('sagt ohne Teams in einem Satz, woher Teams kommen', () => {
    laden(stand({ teams: [] }));

    expect(el().querySelector('[data-testid="leer"]')!.textContent).toContain('Noch in keinem Team');
    expect(el().querySelector('ul')).toBeNull();
  });

  it('fehlt der Umschalter, solange teams_oeffentlich aus ist', () => {
    laden(stand());

    expect(el().querySelector('[data-testid="oeffentlich"]')).toBeNull();
    expect(el().querySelector('mat-slide-toggle')).toBeNull();
  });

  it('gibt die Einwilligung mit dem Wortlaut vor Augen und sagt den neuen Stand', () => {
    laden(stand({ oeffentlich_verfuegbar: true, oeffentlich_kennung: 'team-oeffentlich-2026-11-25', oeffentlich_text: WORTLAUT }));

    const block = el().querySelector('[data-testid="oeffentlich"]')!;
    expect(block.textContent).toContain(WORTLAUT);
    const knopf = block.querySelector('mat-slide-toggle button') as HTMLButtonElement;
    expect(knopf.getAttribute('aria-checked')).toBe('false');
    expect(knopf.getAttribute('aria-describedby')).toContain('oeffentlich-wortlaut');
    knopf.click();
    fixture.detectChanges();

    const anfrage = http.expectOne(`${URL}/oeffentlich`);
    expect(anfrage.request.method).toBe('PUT');
    expect(anfrage.request.body).toEqual({ zeigen: true, wortlaut: 'team-oeffentlich-2026-11-25' });
    anfrage.flush(null, { status: 204, statusText: 'No Content' });
    fixture.detectChanges();

    expect(el().querySelector('[data-testid="sichtbarkeit"]')!.textContent).toContain('Andere Angemeldete sehen an deinem Namen');
    expect(el().querySelector('[role="status"]')!.textContent).toContain('stehen jetzt an deinem Namen');
    // Die Karte laedt nach der Handlung selbst nach
    http.expectOne(`${URL}/meine`).flush(
      stand({ oeffentlich_verfuegbar: true, oeffentlich_zeigen: true, oeffentlich_kennung: 'team-oeffentlich-2026-11-25', oeffentlich_text: WORTLAUT }),
    );
  });

  it('verlässt ein Team erst nach der Rückfrage und nimmt es sofort aus der Liste', () => {
    laden(stand());
    dialog.open.and.returnValue({ afterClosed: () => of(true) } as never);

    (el().querySelector('[data-testid="verlassen"]') as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(dialog.open.calls.mostRecent().args[1]!.data).toEqual(verlassenFrage(stand().teams[0]));
    const anfrage = http.expectOne(`${URL}/meine/m1`);
    expect(anfrage.request.method).toBe('DELETE');
    anfrage.flush(null, { status: 204, statusText: 'No Content' });
    fixture.detectChanges();

    expect(el().querySelector('[data-testid="team"]')).toBeNull();
    expect(el().querySelectorAll('[data-testid="team-vergangen"]').length).toBe(1);
    expect(el().querySelector('[role="status"]')!.textContent).toContain('Team BDK 26 Berlin verlassen');
    http.expectOne(`${URL}/meine`).flush(stand({ teams: [stand().teams[1]] }));
  });

  it('verlässt kein Team, wenn die Rückfrage abgebrochen wird', () => {
    laden(stand());
    dialog.open.and.returnValue({ afterClosed: () => of(false) } as never);

    (el().querySelector('[data-testid="verlassen"]') as HTMLButtonElement).click();

    http.expectNone(`${URL}/meine/m1`);
    expect(el().textContent).toContain('BDK 26 Berlin');
  });

  it('nennt das Team im Namen des Knopfs „Team verlassen“', () => {
    laden(stand());

    const knopf = el().querySelector('[data-testid="verlassen"]')!;
    expect(knopf.textContent!.trim()).toBe('Team verlassen');
    expect(knopf.getAttribute('aria-label')).toBe('Team verlassen: BDK 26 Berlin, Saison 2026');
  });
});
