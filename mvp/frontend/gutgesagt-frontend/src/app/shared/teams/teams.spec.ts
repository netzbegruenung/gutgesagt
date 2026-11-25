import { TEAM_NAME_MAX, TEAM_SAISON_MAX, motivBild, motivName, teamTextGueltig } from './teams';

describe('teams', () => {
  it('kennt die sechs Motive mit Bild und Namen', () => {
    expect(motivBild('vogel')).toBe('/meilensteine/vogel.svg');
    expect(motivName('lautsprecher')).toBe('Lautsprecher');
  });

  it('baut für unbekannte Motive keine Bildadresse', () => {
    expect(motivBild('../geheim')).toBeNull();
    expect(motivBild(null)).toBeNull();
  });

  it('prüft Teamname und Saison wie das Backend', () => {
    expect(teamTextGueltig('BDK 26 Berlin', TEAM_NAME_MAX)).toBeTrue();
    expect(teamTextGueltig('   ', TEAM_NAME_MAX)).toBeFalse();
    expect(teamTextGueltig('a/b', TEAM_NAME_MAX)).toBeFalse();
    expect(teamTextGueltig('<b>', TEAM_NAME_MAX)).toBeFalse();
    expect(teamTextGueltig('x'.repeat(TEAM_SAISON_MAX + 1), TEAM_SAISON_MAX)).toBeFalse();
    // Leerraum zählt zusammengefasst
    expect(teamTextGueltig(`${'x'.repeat(20)}    `, TEAM_SAISON_MAX)).toBeTrue();
  });
});
