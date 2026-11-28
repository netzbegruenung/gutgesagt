import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { MatDialog } from '@angular/material/dialog';
import { of } from 'rxjs';

import { MeineTeamsComponent, verlassenFrage } from './meine-teams.component';
import { MeinTeam, MeineTeams, TeamLive } from '../services/teams.service';
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

  it('zeigt ein Emoji-Motiv als Zeichen und den Namen des Motivs sichtbar daneben', () => {
    laden({ ...stand(), teams: [team({ id: 'm3', motiv: '🌻', motiv_name: 'Sonnenblume' })] });

    const eintrag = el().querySelector('[data-testid="team"]')!;
    const emoji = eintrag.querySelector('[data-testid="motiv-emoji"]')!;
    expect(emoji.textContent!.trim()).toBe('🌻');
    // Der Name steht sichtbar daneben; das Zeichen selbst liest der Screenreader nicht doppelt
    expect(emoji.getAttribute('aria-hidden')).toBe('true');
    expect(emoji.getAttribute('title')).toBe('Sonnenblume');
    expect(eintrag.querySelector('[data-testid="team-motiv-name"]')!.textContent).toContain('Motiv: Sonnenblume');
    expect(eintrag.querySelector('.medaillon.emoji')).not.toBeNull();
  });

  it('zeigt frühere Motive weiter als Bild, mit Namen daneben', () => {
    laden(stand());

    const eintrag = el().querySelector('[data-testid="team"]')!;
    expect(eintrag.querySelector('img')!.getAttribute('src')).toBe('/meilensteine/vogel.svg');
    expect(eintrag.querySelector('[data-testid="team-motiv-name"]')!.textContent).toContain('Motiv: Vogel');
  });

  it('zeigt ohne Schalter teams und ohne eigene Teams keine Karte (200 statt 404, Saal)', () => {
    laden(stand({ teams_aktiv: false, teams: [], oeffentlich_verfuegbar: false }));

    expect(el().querySelector('[data-testid="meine-teams"]')).toBeNull();
  });

  it('zeigt ohne Schalter teams bei einem älteren Backend (404) keine Karte', () => {
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

    expect(el().querySelector('[data-testid="leer"]')!.textContent).toBe('Teams entstehen über Einladungslinks, zum Beispiel am Stand. Sobald du einem beitrittst, steht es hier.');
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

  it('setzt den Fokus nach „Team verlassen“ auf die Überschrift, nicht auf <body> (WCAG 2.4.3)', async () => {
    document.body.appendChild(fixture.nativeElement);
    laden(stand());
    dialog.open.and.returnValue({ afterClosed: () => of(true) } as never);
    const knopf = el().querySelector('[data-testid="verlassen"]') as HTMLButtonElement;
    knopf.focus();

    knopf.click();
    http.expectOne(`${URL}/meine/m1`).flush(null, { status: 204, statusText: 'No Content' });
    fixture.detectChanges();
    await fixture.whenStable();

    expect(document.activeElement).toBe(el().querySelector('#meine-teams-titel'));
    http.expectOne(`${URL}/meine`).flush(stand({ teams: [stand().teams[1]] }));
    fixture.nativeElement.remove();
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
  describe('Team-Fortschritt und Team-Quest', () => {
    const wirkung = {
      woche: '2026-11-16',
      waechst_noch: false,
      beitraege: 'rund 15',
      bewertungen: 'weniger als 10',
      gepostet: 'rund 40',
    };
    const quest = {
      woche: '2026-11-23',
      ziel: 4,
      thema: 'energie-heizen',
      thema_name: 'Energie und Heizen',
      thema_motiv: 'themen/energie-heizen.svg',
      vorige_geschafft: false,
      vorige_thema_name: null,
    };

    /** Vor der gezeigten Woche beigetreten, wenn nicht anders gesagt. */
    function mit(teil: Partial<MeinTeam>): MeineTeams {
      return stand({ teams: [team({ id: 'm1', eingetreten_am: '2026-11-10', ...teil })] });
    }

    it('zeigt statt einer Woche vor dem eigenen Beitritt „Eure erste gemeinsame Woche läuft“ (UX-Review 26.11.)', () => {
      // Beigetreten am Donnerstag der BDK; gezeigt würde die Vorwoche 16.11. bis 22.11.
      laden(mit({ wirkung, quest: { ...quest, vorige_geschafft: true, vorige_thema_name: 'Klima' }, eingetreten_am: '2026-11-26' }));

      expect(el().querySelector('[data-testid="team-erste-woche"]')!.textContent).toContain(
        'Eure erste gemeinsame Woche läuft. Am Montag seht ihr hier, was ihr zusammen geschafft habt.',
      );
      expect(el().querySelector('[data-testid="team-zahlen"]')).toBeNull();
      expect(el().textContent).not.toContain('Letzte Woche gemeinsam');
      expect(el().textContent).not.toContain('weniger als 10');
      // Die Quest: das Ziel der laufenden Woche ja, ein „geschafft“ aus der Zeit davor nicht
      expect(el().querySelector('[data-testid="quest-ziel"]')).not.toBeNull();
      expect(el().querySelector('[data-testid="quest-geschafft"]')).toBeNull();
    });

    it('zeigt die Woche, wenn der Beitritt in ihr lag (bis Sonntag)', () => {
      laden(mit({ wirkung, eingetreten_am: '2026-11-22' }));
      expect(el().querySelector('[data-testid="team-zahlen"]')).not.toBeNull();
      expect(el().querySelector('[data-testid="team-erste-woche"]')).toBeNull();
    });

    it('unter 5 Mitgliedern bleibt „wächst noch“, auch in der ersten Woche', () => {
      laden(mit({ wirkung: { ...wirkung, waechst_noch: true }, eingetreten_am: '2026-11-26' }));
      expect(el().querySelector('[data-testid="team-waechst"]')).not.toBeNull();
      expect(el().querySelector('[data-testid="team-erste-woche"]')).toBeNull();
    });

    it('zeigt die abgeschlossene Woche mit den gerundeten Texten des Servers', () => {
      laden(mit({ wirkung }));

      const block = el().querySelector('[data-testid="team-fortschritt"]')!;
      expect(block.textContent).toContain('Letzte Woche gemeinsam (16.11. bis 22.11.)');
      const zahlen = block.querySelector('[data-testid="team-zahlen"]')!;
      expect(zahlen.textContent).toContain('Beiträge');
      expect(zahlen.textContent).toContain('rund 15');
      expect(zahlen.textContent).toContain('weniger als 10');
      expect(zahlen.textContent).toContain('„Ja, gepostet“');
      expect(zahlen.textContent).toContain('rund 40');
      expect(zahlen.getAttribute('aria-labelledby')).toBe('wirkung-m1');
      expect(el().querySelector('#wirkung-m1')).not.toBeNull();
    });

    it('sagt unter 5 Mitgliedern nur, dass das Team noch wächst', () => {
      laden(mit({ wirkung: { ...wirkung, waechst_noch: true, beitraege: null, bewertungen: null, gepostet: null } }));

      expect(el().querySelector('[data-testid="team-waechst"]')!.textContent).toContain(
        'Euer Team wächst noch, ab 5 zeigen wir eure gemeinsame Wirkung.',
      );
      expect(el().querySelector('[data-testid="team-zahlen"]')).toBeNull();
    });

    it('zeigt das Wochenziel ohne Stand, mit Motiv und Namen des Themas', () => {
      laden(mit({ wirkung, quest }));

      const ziel = el().querySelector('[data-testid="quest-ziel"]')!;
      expect(ziel.textContent).toContain('Euer Wochenziel: gemeinsam 4-mal beitragen, bewerten oder „Ja, gepostet“ melden.');
      expect(ziel.textContent).toContain('Gern im Beet');
      expect(ziel.textContent).toContain('Energie und Heizen');
      const motiv = ziel.querySelector('img')!;
      expect(motiv.getAttribute('src')).toBe('themen/energie-heizen.svg');
      expect(motiv.getAttribute('alt')).toBe('');
      expect(ziel.querySelector('a')!.getAttribute('href')).toBe('/hier-fehlt-eine-antwort');
      expect(el().querySelector('[data-testid="quest-geschafft"]')).toBeNull();
    });

    it('sagt nach Wochenende nur „geschafft“, ein verfehltes Ziel nie', () => {
      laden(mit({ quest: { ...quest, vorige_geschafft: true, vorige_thema_name: 'Klima' } }));
      expect(el().querySelector('[data-testid="quest-geschafft"]')!.textContent).toContain(
        'Euer Wochenziel letzte Woche im Beet Klima ist geschafft. Danke, dass du dabei bist.',
      );
      expect(el().textContent).not.toContain('verfehlt');
      expect(el().textContent).not.toContain('nicht geschafft');
    });

    it('fehlt ohne Schalter (Felder null) und bei vergangenen Saisons', () => {
      laden(
        stand({
          teams: [
            team({ id: 'm1', wirkung: null, quest: null }),
            team({ id: 'm2', saison: '2025', aktuelle_saison: false, wirkung, quest }),
          ],
        }),
      );

      expect(el().querySelector('[data-testid="team-fortschritt"]')).toBeNull();
    });
  });

  describe('Team-Fortschritt quasi-live (team_live)', () => {
    const live: TeamLive = {
      laeuft_noch: false,
      mitglieder: 40,
      bis: 14,
      tagessumme: 'rund 80',
      quest_stufe: 2,
      hinweis_neu: false,
    };
    const HINWEIS =
      'Neu: Ab jetzt siehst du die Summe deines Teams auch für heute, zur vollen Stunde und nie mit einzelnen Namen. ' +
      'Mehr in der Datenschutzerklärung.';

    function mit(teil: Partial<TeamLive>, extra: Partial<MeinTeam> = {}): MeineTeams {
      return stand({ teams: [team({ id: 'm1', eingetreten_am: '2026-11-10', live: { ...live, ...teil }, ...extra })] });
    }

    function text(testid: string): string | null {
      return el().querySelector(`[data-testid="${testid}"]`)?.textContent?.replace(/\s+/g, ' ').trim() ?? null;
    }

    it('zeigt die Tagessumme bis zur vollen Stunde, die Mitglieder und die Quest-Stufe', () => {
      laden(mit({}));

      expect(text('team-live-tag')).toBe('Heute bis 14 Uhr: rund 80');
      expect(text('team-live-mitglieder')).toBe('Mindestens 40 sind dabei.');
      expect(text('team-live-quest')).toBe('Euer Wochenziel: zwei Drittel geschafft.');
      expect(el().querySelector('[data-testid="team-live-stunde"]')).toBeNull();
    });

    it('sagt „läuft noch“, solange heute nichts freigegeben ist', () => {
      laden(mit({ bis: null, tagessumme: null, laeuft_noch: true, quest_stufe: 0 }));

      expect(text('team-live-tag')).toBe('Heute: läuft noch');
      expect(el().querySelector('[data-testid="team-live-quest"]')).toBeNull();
    });

    it('nennt neben der Tagessumme, dass die letzte Stunde noch läuft', () => {
      laden(mit({ laeuft_noch: true, tagessumme: 'weniger als 10', bis: 11 }));

      expect(text('team-live-tag')).toBe('Heute bis 11 Uhr: weniger als 10 · Die letzte Stunde läuft noch.');
    });

    const STUFEN: [number | null, string | null][] = [
      [1, 'Euer Wochenziel: ein Drittel geschafft.'],
      [3, 'Euer Wochenziel ist geschafft. Danke, dass du dabei bist.'],
      [null, null],
    ];
    for (const [stufe, erwartet] of STUFEN) {
      it(`Quest-Stufe ${stufe}: ${erwartet ?? 'ohne Quest nichts'}`, () => {
        laden(mit({ quest_stufe: stufe }));
        expect(text('team-live-quest')).toBe(erwartet);
      });
    }

    it('fehlt ohne team_live (null) und bei vergangenen Saisons', () => {
      laden(stand({ teams: [team({ id: 'm1', live: null }), team({ id: 'm2', aktuelle_saison: false, live })] }));

      expect(el().querySelector('[data-testid="team-live"]')).toBeNull();
      expect(el().querySelector('[data-testid="team-live-hinweis"]')).toBeNull();
    });

    it('zeigt Bestandsmitgliedern den Hinweis wortgleich aus der Akte, mit Verweis auf die Erklärung', () => {
      laden(mit({ hinweis_neu: true }));

      expect(text('team-live-hinweis')).toBe(HINWEIS);
      const verweis = el().querySelector('[data-testid="team-live-hinweis"] a')!;
      expect(verweis.getAttribute('href')).toBe('/datenschutz#teams');
    });

    it('zeigt den Hinweis nur, wenn der Server ihn meldet', () => {
      laden(mit({ hinweis_neu: false }));

      expect(el().querySelector('[data-testid="team-live-hinweis"]')).toBeNull();
    });

    it('zeigt den Hinweis einmal je Sitzung: in der Karte bleibt er, eine neue Karte zeigt ihn nicht mehr', () => {
      laden(mit({ hinweis_neu: true }));
      expect(el().querySelector('[data-testid="team-live-hinweis"]')).not.toBeNull();

      const zweite = TestBed.createComponent(MeineTeamsComponent);
      zweite.detectChanges();
      http.expectOne(`${URL}/meine`).flush(mit({ hinweis_neu: true }));
      zweite.detectChanges();

      expect((zweite.nativeElement as HTMLElement).querySelector('[data-testid="team-live-hinweis"]')).toBeNull();
      expect(el().querySelector('[data-testid="team-live-hinweis"]')).not.toBeNull();
      zweite.destroy();
    });
  });
});
