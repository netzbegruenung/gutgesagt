import {
  TEAM_NAME_MAX,
  TEAM_SAISON_MAX,
  TeamMotivEintrag,
  motivBild,
  motivEmoji,
  motivName,
  motiveSuchen,
  teamSaisonGueltig,
  teamTextGueltig,
} from './teams';

describe('teams', () => {
  it('kennt die sechs früheren Motive weiter mit Bild und Namen', () => {
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

describe('teamSaisonGueltig', () => {
  it('erlaubt den Schraegstrich wie bei den Saisons (UX-Review 26.11.), sonst wie der Teamname', () => {
    expect(teamSaisonGueltig('Winter 26/27', TEAM_SAISON_MAX)).toBeTrue();
    expect(teamSaisonGueltig('<b>', TEAM_SAISON_MAX)).toBeFalse();
    expect(teamSaisonGueltig('a\\b', TEAM_SAISON_MAX)).toBeFalse();
    expect(teamSaisonGueltig('   ', TEAM_SAISON_MAX)).toBeFalse();
    expect(teamSaisonGueltig('x'.repeat(TEAM_SAISON_MAX + 1), TEAM_SAISON_MAX)).toBeFalse();
  });
});

describe('motivEmoji', () => {
  it('zeichnet Emoji der Liste als Text, frühere Schlüssel nicht', () => {
    expect(motivEmoji('🌻')).toBe('🌻');
    expect(motivEmoji('⚖️')).toBe('⚖️');
    expect(motivEmoji('vogel')).toBeNull();
    expect(motivBild('🌻')).toBeNull();
  });

  it('nimmt keine Sequenzen, keinen Text und nichts Leeres', () => {
    expect(motivEmoji('🐦\u200d⬛')).toBeNull();
    expect(motivEmoji('👍🏽')).toBeNull();
    expect(motivEmoji('🌻🌻')).toBeNull();
    expect(motivEmoji('<b>')).toBeNull();
    expect(motivEmoji('a')).toBeNull();
    expect(motivEmoji('')).toBeNull();
    expect(motivEmoji(null)).toBeNull();
  });
});

describe('motiveSuchen', () => {
  const MOTIVE: TeamMotivEintrag[] = [
    { schluessel: '🌳', name: 'Laubbaum', kategorie: 'tiere-natur', stichworte: 'baum natur' },
    { schluessel: '🚲', name: 'Fahrrad', kategorie: 'reisen-orte', stichworte: 'rad' },
    { schluessel: '🧀', name: 'Käsestück', kategorie: 'essen-trinken', stichworte: 'kaese' },
  ];
  const KATEGORIEN = [{ schluessel: 'reisen-orte', name: 'Reisen & Orte' }];

  it('findet über Name, Stichworte und Kategorie, ohne Groß/klein und Akzente', () => {
    expect(motiveSuchen(MOTIVE, 'BAUM').map((m) => m.schluessel)).toEqual(['🌳']);
    expect(motiveSuchen(MOTIVE, 'kase').map((m) => m.schluessel)).toEqual(['🧀']);
    expect(motiveSuchen(MOTIVE, 'reisen', KATEGORIEN).map((m) => m.schluessel)).toEqual(['🚲']);
    expect(motiveSuchen(MOTIVE, 'rad fahr').map((m) => m.schluessel)).toEqual(['🚲']);
  });

  it('zeigt bei leerer Suche alle und findet auch das Emoji selbst', () => {
    expect(motiveSuchen(MOTIVE, '  ').length).toBe(3);
    expect(motiveSuchen(MOTIVE, '🚲').map((m) => m.name)).toEqual(['Fahrrad']);
    expect(motiveSuchen(MOTIVE, 'xyz')).toEqual([]);
  });
});
