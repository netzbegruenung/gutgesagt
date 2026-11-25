import {
  MEINE_TEAMS_TITEL,
  TEAM_DATENSCHUTZ_HINWEIS,
  TEAM_VERLASSEN,
  teamBegruessungSaetze,
  teamBegruessungTitel,
  teamDabeiSatz,
  teamGruppeSatz,
} from './team-texte';

describe('Texte der Teams', () => {
  it('Begrüßung: Team und voraussichtliche Nummer im Kopf', () => {
    expect(teamBegruessungTitel('BDK 26 Berlin', 37)).toBe(
      'Herzlich willkommen im Team BDK 26 Berlin! Du wärst Nr. 37.'
    );
  });

  it('Wie viele dabei sind: bis 3 nach Anfang, Einzahl und Mehrzahl sauber, ab 4 die Zahl', () => {
    expect(teamDabeiSatz(0)).toBe('Mit dir fängt das Team an.');
    expect(teamDabeiSatz(1)).toBe('Die erste Person ist schon dabei.');
    expect(teamDabeiSatz(2)).toBe('Die ersten 2 sind schon dabei.');
    expect(teamDabeiSatz(3)).toBe('Die ersten 3 sind schon dabei.');
    expect(teamDabeiSatz(4)).toBe('Schon 4 dabei.');
    expect(teamDabeiSatz(36)).toBe('Schon 36 dabei.');
    expect(teamDabeiSatz(-1)).toBe('Mit dir fängt das Team an.');
    expect(teamDabeiSatz(Number.NaN)).toBe('Mit dir fängt das Team an.');
  });

  it('Begrüßung: was gespeichert wird, wer es sieht, Rückschluss und Widerruf', () => {
    const text = teamBegruessungSaetze('Bayreuth').join(' ');

    expect(text).toContain('dass du im Team Bayreuth bist, mit deiner Nummer und dem Tag');
    expect(text).toContain('Das siehst nur du, unter „Meine Teams“.');
    expect(text).toContain('auf deine politische Haltung und deinen Ort schließen lassen');
    expect(text).toContain('mit „Team verlassen“ widerrufen, dann löschen wir es sofort');
  });

  it('Team nach Gruppe: der Satz über der Frage, wortgleich, mit dem Teamnamen an beiden Stellen', () => {
    expect(teamGruppeSatz('Die grüne Welle')).toBe(
      'Dieses Team ist mit Zustimmung von Die grüne Welle nach ihr benannt. Verantwortlich für Gut gesagt ist allein die Netzbegrünung; Die grüne Welle bekommt keine Daten über dich.'
    );
  });

  it('nennt dieselben Namen wie die Datenschutzerklärung', () => {
    expect(MEINE_TEAMS_TITEL).toBe('Meine Teams');
    expect(TEAM_VERLASSEN).toBe('Team verlassen');
    expect(TEAM_DATENSCHUTZ_HINWEIS).toContain('„Teams“');
  });
});
