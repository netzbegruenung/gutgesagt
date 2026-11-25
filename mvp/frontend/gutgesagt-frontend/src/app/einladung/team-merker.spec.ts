import {
  TEAM_MERKER_DAUER_MS,
  TEAM_MERKER_SCHLUESSEL,
  teamMerkerAblegen,
  teamMerkerLesen,
  teamMerkerLoeschen,
  teamMerkerNehmen,
} from './team-merker';

describe('team-merker', () => {
  afterEach(() => localStorage.clear());

  it('legt Code, Kennung und zweite Antwort ab und liest sie wieder', () => {
    teamMerkerAblegen({ code: 'Abc', kennung: 'team-2026-11-25', oeffentlich: true }, 1000);

    expect(teamMerkerLesen(1000)).toEqual({ code: 'Abc', kennung: 'team-2026-11-25', oeffentlich: true });
  });

  it('legt ohne Kennung die zweite Antwort nie als ja ab', () => {
    teamMerkerAblegen({ code: 'Abc', kennung: null, oeffentlich: true });

    expect(teamMerkerLesen()?.oeffentlich).toBeFalse();
  });

  it('verwirft einen abgelaufenen Eintrag', () => {
    teamMerkerAblegen({ code: 'Abc', kennung: null, oeffentlich: false }, 0);

    expect(teamMerkerLesen(TEAM_MERKER_DAUER_MS + 1)).toBeNull();
    expect(localStorage.getItem(TEAM_MERKER_SCHLUESSEL)).toBeNull();
  });

  it('verwirft einen kaputten Eintrag', () => {
    localStorage.setItem(TEAM_MERKER_SCHLUESSEL, '{kein json');

    expect(teamMerkerLesen()).toBeNull();
    expect(localStorage.getItem(TEAM_MERKER_SCHLUESSEL)).toBeNull();
  });

  it('gibt beim Nehmen einmal zurück und entfernt den Eintrag', () => {
    teamMerkerAblegen({ code: 'Abc', kennung: null, oeffentlich: false });

    expect(teamMerkerNehmen()?.code).toBe('Abc');
    expect(teamMerkerNehmen()).toBeNull();
  });

  it('wirft nicht, wenn der Speicher gesperrt ist', () => {
    spyOn(localStorage, 'setItem').and.throwError('gesperrt');
    spyOn(localStorage, 'getItem').and.throwError('gesperrt');
    spyOn(localStorage, 'removeItem').and.throwError('gesperrt');

    expect(() => teamMerkerAblegen({ code: 'Abc', kennung: null, oeffentlich: false })).not.toThrow();
    expect(teamMerkerLesen()).toBeNull();
    expect(() => teamMerkerLoeschen()).not.toThrow();
  });
});
