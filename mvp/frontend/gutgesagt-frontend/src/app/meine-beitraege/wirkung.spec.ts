import { wirkungssatz } from './wirkung';

describe('wirkungssatz', () => {
  it('nennt Nutzung und Woche', () => {
    expect(wirkungssatz(4, 3, 2)).toBe('Deine 4 Beiträge wurden 3-mal genutzt, 2 davon diese Woche.');
  });

  it('sagt "alle diese Woche", wenn alles aus dieser Woche ist', () => {
    expect(wirkungssatz(4, 3, 3)).toBe('Deine 4 Beiträge wurden 3-mal genutzt, alle diese Woche.');
    expect(wirkungssatz(1, 1, 1)).toBe('Dein Beitrag wurde einmal genutzt, diese Woche.');
  });

  it('laesst die Woche ohne Zahl oder bei 0 weg', () => {
    expect(wirkungssatz(2, 5, null)).toBe('Deine 2 Beiträge wurden 5-mal genutzt.');
    expect(wirkungssatz(2, 5, 0)).toBe('Deine 2 Beiträge wurden 5-mal genutzt.');
  });

  it('sagt ohne Nutzung, was als Naechstes kommt, statt "noch nicht genutzt"', () => {
    expect(wirkungssatz(1, 0, 0)).toBe('Sobald jemand deinen Beitrag nutzt, siehst du es hier.');
    expect(wirkungssatz(4, 0, null)).toBe('Sobald jemand einen deiner Beiträge nutzt, siehst du es hier.');
    expect(wirkungssatz(1, 0, 0)).not.toContain('noch nicht');
  });
});
