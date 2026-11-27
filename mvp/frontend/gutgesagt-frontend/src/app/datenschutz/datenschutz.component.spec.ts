import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { Subject } from 'rxjs';

import { abschnitt as abschnittIn, istTagesdatum, normalisiert, stand } from '../testing/rechtstext';
import { DatenschutzComponent } from './datenschutz.component';
import { SUCHANFRAGEN_ABSCHNITT } from '../search/search.component';
import { HOME_HINWEIS_MERKER, MEILENSTEIN_MERKER } from '../shared/geraetespeicher-schalter';
import { FEIER_TON_SCHLUESSEL } from '../shared/feier/feier-ton.service';
import { FunktionenService } from '../services/funktionen.service';

/** Der Satz zu Widerrufen vor dem Einspielen: mit Platzhalter oder mit Datum („1. Dezember 2026“). */
const WIDERRUF_VOR_DEM_EINSPIELEN = new RegExp(
  'Wer vor dem (\\[Datum des Einspielens\\]|([1-9]|[12]\\d|3[01])\\. ' +
    '(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember) \\d{4}) ' +
    'widerrufen hat, dessen Beiträge, Einwürfe und Sätze lösen wir innerhalb von sieben Tagen ' +
    'ab diesem Tag von ihm\\.'
);

/**
 * Die Datenschutzerklaerung beschreibt, was die App tut (#222). Geprueft wird der Text,
 * den Lesende sehen, je Abschnitt: Ein Abschnitt reicht von seiner Ueberschrift (h2 oder
 * h3) bis zur naechsten Ueberschrift derselben oder hoeheren Ebene.
 */
describe('DatenschutzComponent', () => {
  let seite: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DatenschutzComponent],
      providers: [provideRouter([])],
    }).compileComponents();

    const fixture = TestBed.createComponent(DatenschutzComponent);
    fixture.detectChanges();
    seite = fixture.nativeElement as HTMLElement;
  });

  function abschnitt(titel: string): string {
    return abschnittIn(seite, titel);
  }

  function ganzerText(): string {
    return normalisiert(seite.textContent);
  }

  describe('Anrede (Entscheidung 29.10.2026)', () => {
    it('duzt die Lesenden', () => {
      expect(ganzerText()).not.toMatch(/\b(Ihr|Ihre|Ihren|Ihrem|Ihrer|Ihres|Ihnen)\b/);
      expect(ganzerText()).not.toMatch(/\b(können|möchten|haben) Sie\b/);
      expect(abschnitt('Deine Rechte')).toContain('Wende dich dafür an');
    });
  });

  describe('Stand (#498)', () => {
    it('trägt das Tagesdatum der letzten Änderung, nicht nur den Monat', () => {
      const text = stand(seite);
      expect(istTagesdatum(text)).withContext(text).toBeTrue();
    });

    it('lässt Monat ohne Tag und einen Tag, den es nicht gibt, nicht gelten', () => {
      expect(istTagesdatum('November 2026')).toBeFalse();
      expect(istTagesdatum('31. September 2026')).toBeFalse();
      expect(istTagesdatum('29. Februar 2028')).toBeTrue();
    });
  });

  describe('Rückmeldung „Ja, gepostet“ (#643)', () => {
    it('nennt Prüfwert statt Kennung, kein Beitrag, Wochenfrist, lit. f und die Art.-9-Einwilligung', () => {
      const text = abschnitt('Rückmeldung „Ja, gepostet“');

      expect(text).toContain('nur einen Prüfwert');
      expect(text).toContain('welchen Beitrag du gepostet hast, speichern wir nicht');
      expect(text).toContain('bis kurz nach Ende der Kalenderwoche');
      expect(text).toContain('Widerrufst du sie, erscheint die Frage nicht mehr');
      expect(text).toContain('Artikel 6 Absatz 1 Buchstabe f DSGVO');
      expect(text).toContain('Artikel 9 Absatz 2 Buchstabe a DSGVO');
    });
  });

  describe('Rückmeldung zur Nutzung (#349)', () => {
    it('nennt die gespeicherte Zahl ohne Zeitpunkt, lit. f und die Frist bis zur Kontolöschung', () => {
      const text = abschnitt('Rückmeldung zur Nutzung deiner Beiträge');

      expect(text).toContain('Seit deinem letzten Besuch wurden deine Beiträge N-mal genutzt');
      expect(text).toContain('nur zwei Zahlen');
      expect(text).toContain('wie viele Einwürfe anderer es im Fangkorb gab');
      expect(text).toContain('Wann du da warst, speichern wir nicht');
      // Die zwei 7-Tage-Zahlen der Startseite (#741), Wortlaut freigegeben 20.11.
      expect(text).toContain(
        'Zwei weitere Zahlen auf der Startseite berechnen wir bei jedem Besuch neu und speichern sie nicht: ' +
          'wie viele deiner Einwürfe andere in den letzten sieben Tagen ausformuliert haben und wie viele neue ' +
          'Kommentare und Hintergrundinfos anderer es in dieser Zeit auf der Plattform gab.',
      );
      expect(text).toContain('Artikel 6 Absatz 1 Buchstabe f DSGVO');
      expect(text).toContain('bis zur Löschung deines Kontos');
    });
  });

  describe('Suchen ohne Treffer und „Hier fehlt eine Antwort“ (#350, #370)', () => {
    it('nennt alle angemeldeten Mitwirkenden mit der Zahl der Personen, die Zahl der Suchen nur für Admins', () => {
      const text = abschnitt('Suchen ohne Treffer');

      expect(text).toContain('alle angemeldeten Mitwirkenden');
      expect(text).toContain('„Hier fehlt eine Antwort“');
      expect(text).toContain('n Personen suchten das ohne Treffer');
      expect(text).toContain('die Zahl der Suchen sehen sie nicht');
      expect(text).toContain('das Moderationsteam, zusätzlich mit der Zahl der Suchen');
      expect(text).toContain('erst nach Prüfung durch das Moderationsteam');
    });

    it('bezieht die Zwei-Personen-Schwelle auf die Listen, nicht auf die Auffindbarkeit', () => {
      const text = abschnitt('Suchen ohne Treffer');

      expect(text).toContain('Auf die Listen der Suchen ohne Treffer kommt ein Eintrag erst');
      expect(text).not.toContain('Ein Eintrag wird erst sichtbar');
    });

    it('sagt, dass eine übernommene Suchanfrage die Kennung der anlegenden Person trägt', () => {
      const text = abschnitt('Suchen ohne Treffer');

      expect(text).toContain('Die Aussage gilt danach als von ihr angelegt und trägt ihre Kennung');
    });
  });

  describe('Wortlaut des CC0-Hinweises (#431)', () => {
    it('nennt die Kennung des Wortlauts an Beitrag, Satz und Einwurf mit Zweck und Rechtsgrundlage', () => {
      const text = abschnitt('Beiträge, die du einstellst');

      expect(text).toContain('An jedem Beitrag, jedem Satz und jedem Einwurf speichern wir außerdem');
      expect(text).toContain('welchen Wortlaut des Hinweises zur CC0-Freigabe');
      expect(text).toContain('die Freigabe nachweisen zu können');
    });
  });

  describe('Suchanfragen (#436)', () => {
    it('sagt, ab wann eine gespeicherte Suchanfrage für alle sichtbar ist', () => {
      const text = abschnitt('Deine Suchanfragen');

      expect(text).toContain('kann danach für alle auffindbar werden');
      expect(text).not.toContain('ist danach für alle auffindbar');
      expect(text).toContain('nur unserem Moderationsteam (unseren Administratorinnen und Administratoren)');
      expect(text).toContain('mindestens zwei verschiedene Personen innerhalb von vier Wochen');
      // Vormoderation (13.11.2026): erst nach Prüfung, auch nicht über eine gleichlautende Aussage.
      expect(text).toContain('Ein freigegebener Eintrag ist für alle sichtbar, solange in den letzten vier Wochen');
      expect(text).toContain('dauerhaft, sobald jemand einen Beitrag als Antwort darauf eingestellt hat');
      expect(text).toContain('Dafür entsteht eine eigene Aussage mit dem Wortlaut dieser Person');
      // Übernommen wird nur eine sichtbare Suchanfrage (freigegeben und über der Schwelle).
      expect(abschnitt('Suchen ohne Treffer')).toContain('einer für alle sichtbaren (freigegebenen), noch unbeantworteten Suchanfrage');
      // Keine Ausnahme für den Bestand (Entscheidung des Maintainers vom 13.11.2026).
      expect(text).toContain('nur wegen der Zahl der Suchen sichtbar waren, sind es erst nach dieser Prüfung wieder; hatte schon jemand darauf geantwortet, bleiben sie sichtbar');
      expect(text).toContain('Gib nichts in das Suchfeld ein, was nicht öffentlich werden soll');
    });
  });

  describe('Beitrag löschen durch den Autor (#250, #421)', () => {
    it('sagt, dass ein gelöschter Beitrag nach 30 Tagen samt Bewertungen endgültig entfernt wird', () => {
      const text = abschnitt('Beiträge, die du einstellst');

      expect(text).toContain('nicht sofort aus unseren Daten entfernt');
      expect(text).toContain('lässt sich nicht zurückholen');
      expect(text).toContain('Er bleibt noch 30 Tage mit deiner Kennung gespeichert');
      expect(text).toContain('Danach entfernen wir ihn endgültig, samt der Bewertungen daran');
      expect(text).toContain('spätestens 31 Tage nach dem Löschen');
      expect(text).not.toContain('Vollständig entfernt wird er nur');
      expect(abschnitt('Deine Rechte')).toContain('Das gilt auch für Beiträge, die du selbst gelöscht hast.');
    });
  });

  describe('Löschfristen (#421)', () => {
    it('Meldungen: 180 Tage nach der Bearbeitung, offene ohne Frist', () => {
      const text = abschnitt('Meldungen von Beiträgen');

      expect(text).toContain('180 Tage nach ihrer Bearbeitung automatisch');
      expect(text).toContain('Offene Meldungen haben keine Frist');
      expect(text).toContain('Artikel 20 DSA');
      expect(text).not.toContain('keine Löschfrist');
    });

    // PR #670 (freigegeben 13./14.11.2026): Kontoadresse mit Häkchen; geht mit dem Konto
    // (person_loeschen.sql loescht die Meldungen der Person samt Adresse)
    it('Meldungen Angemeldeter: Kontoadresse nur mit Häkchen, geht mit dem Konto', () => {
      const text = abschnitt('Meldungen von Beiträgen');

      expect(text).toContain('Bestätigung und Entscheidung per Mail an mein Konto');
      expect(text).toContain('ohne Häkchen speichern wir keine Adresse');
      expect(text).toContain('löschst du dein Konto, löschen wir deine Meldungen samt Adresse mit');
      expect(text).not.toContain('auch wenn du dein Konto vorher löschst');
      expect(abschnitt('Anmeldung und Zugang')).toContain('speichern wir die E-Mail-Adresse deines Kontos an dieser Meldung');
    });

    it('Art.-9-Einwilligung: „ohne Einwilligung weiter“ am Konto, Punkte gesondert (PR #670)', () => {
      const text = abschnitt('Rückschlüsse auf deine politische Haltung');

      expect(text).toContain('Gehst du ohne Einwilligung weiter, speichern wir das mit der Fassung des');
      expect(text).toContain('Punkte und Meilensteine gehören nicht zu dieser Einwilligung');
      expect(abschnitt('Punkte')).toContain('eine eigene, freiwillige Einwilligung');
    });

    it('Sperren: Kennung des Autors, Widerspruch, 180 Tage nach der Aufhebung (#448)', () => {
      const text = abschnitt('Sperren von Beiträgen und Widerspruch');

      expect(text).toContain('Kennung der Person, die den Beitrag eingestellt hat');
      expect(text).toContain('in „Meine Beiträge“');
      expect(text).toContain('Eine E-Mail schicken wir dazu nicht');
      expect(text).toContain('Artikel 17 und 20 DSA');
      expect(text).toContain('180 Tage danach automatisch');
      expect(text).toContain('entfernen wir deine Kennung und deinen Widerspruchstext');
    });

    it('Einwürfe: 365 Tage nach der letzten Arbeit, ausformulierte so lange wie ihr Beitrag', () => {
      const text = abschnitt('Einwürfe in den Fangkorb');

      expect(text).toContain('365 Tage nach der letzten Arbeit daran');
      expect(text).toContain('das gilt auch für verworfene Einwürfe');
      expect(text).toContain('bleibt er so lange wie dieser Beitrag');
      expect(text).not.toContain('keine Löschfrist');
    });

    it('Bewertungen: gehen mit dem endgültig entfernten Beitrag', () => {
      const text = abschnitt('Bewertungen');

      expect(text).toContain('der bewertete Beitrag endgültig entfernt wird');
      expect(text).not.toContain('keine Löschfrist');
    });
  });

  describe('Fassungen (#355)', () => {
    it('nennt die kopierte Fassung eines Kommentars und den Zähler je Fassung', () => {
      const text = abschnitt('Verwendung von Beiträgen');

      expect(text).toContain('bei einem Kommentar auch welche Fassung (kurz, mittel oder lang)');
      expect(text).toContain('Zähler pro Beitrag (alle Kopien und die ersten Kopien je Person und Tag), bei Kommentaren auch je Fassung');
    });
  });

  describe('Entdoppelte Nutzung, Punkte und Muster-Hinweise (#476, #499)', () => {
    it('Verwendung: Vermerk der ersten Kopie je Person und Tag, ablesbar „dieselbe Person“, nicht wer', () => {
      const text = abschnitt('Verwendung von Beiträgen');

      expect(text).toContain('ob es an diesem Tag die erste Kopie dieses Beitrags durch dieselbe Person war');
      expect(text).toContain('dass mehrere Vorgänge an einem Beitrag am selben Tag von derselben Person');
      expect(text).toContain('aber nicht, von wem');
      expect(text).not.toContain('noch ob mehrere Vorgänge vom selben Gerät kamen');
      expect(text).not.toContain('und ein Pseudonym werden dabei nicht gespeichert');
    });

    it('Verwendung: Prüfwert bis Tagesende mit einem täglichen Schlüssel nur im Arbeitsspeicher', () => {
      const text = abschnitt('Verwendung von Beiträgen');

      expect(text).toContain('bis zum Ende des Tages einen Prüfwert');
      expect(text).toContain('jeden Tag neu zufällig erzeugt, nur im Arbeitsspeicher hält und nirgends speichert');
      expect(text).toContain('Prüfwerte bleiben nur bis zum Ende ihres Tages');
    });

    it('Verwendung: ohne Anmeldung Prüfwert aus dem Anschluss für einen Tag, Deckel drei je Beitrag (Jura 27.11.)', () => {
      const text = abschnitt('Verwendung von Beiträgen');

      expect(text).toContain(
        'Ohne Anmeldung erkennen wir dich dabei nur für einen Tag an deinem Anschluss: Daraus bilden wir mit einem ' +
          'täglich wechselnden Schlüssel einen Prüfwert, den wir nach dem Tageswechsel verwerfen; deine Adresse ' +
          'speichern wir nicht. So zählt ohne Anmeldung höchstens eine erste Kopie je Anschluss, Beitrag und Tag, und ' +
          'insgesamt höchstens drei je Beitrag und Tag, egal von wem.',
      );
      expect(text).toContain('berechnet aus deiner Kennung, dem Beitrag und dem Datum.');
      expect(text).not.toContain('ohne Anmeldung aus deiner IP-Adresse');
    });

    it('Verwendung: Deckel-Plätze ohne Schlüssel, verworfen nach Mitternacht, über Neustart erhalten (Jura 27.11.)', () => {
      const text = abschnitt('Verwendung von Beiträgen');

      expect(text).toContain(
        'Auch wer die gespeicherten Daten hat, kann deshalb einen solchen Prüfwert weder auf dich noch auf den ' +
          'Beitrag zurückführen. Für den Deckel ohne Anmeldung merken wir uns zusätzlich bis zu drei Plätze je ' +
          'Beitrag und Tag; sie bestehen nur aus Beitrag, Tag und Platznummer und sagen nichts darüber, wer kopiert ' +
          'hat. Nach Mitternacht (UTC) verwirft der Server alle Prüfwerte und Plätze des Vortags. Startet er am ' +
          'selben Tag neu, passen die Prüfwerte nicht mehr und eine weitere Kopie zählt noch einmal; belegte Plätze ' +
          'bleiben belegt.',
      );
      expect(text).not.toContain('startet er neu, passt keiner mehr');
    });

    it('Verwendung: Kopien durch Startkonten zählen nicht', () => {
      expect(abschnitt('Verwendung von Beiträgen')).toContain('(Startkonten), zählen wir gar nicht');
    });

    it('Punkte: noch aus, nur für dich sichtbar, nicht gespeichert', () => {
      const text = abschnitt('Punkte');

      expect(text).toContain('Punkte sind noch nicht eingeschaltet');
      expect(text).toContain('siehst nur du');
      expect(text).toContain('Wir speichern ihn nicht, sondern berechnen ihn bei jedem Abruf');
    });

    it('Punkte: Paar-Prüfwert sieben Tage, Muster-Hinweis acht Wochen, nur für Admins, Einwilligung als Rechtsgrundlage', () => {
      const text = abschnitt('Punkte');

      expect(text).toContain('für sieben Tage einen Paar-Prüfwert');
      expect(text).toContain('ohne den Beitrag und ohne das Datum');
      expect(text).toContain('Muster-Hinweis');
      expect(text).toContain('nur unsere Administratorinnen und Administratoren');
      expect(text).toContain('Muster-Hinweise acht Wochen nach dem letzten auffälligen Tag');
      expect(text).toContain('Artikel 6 Absatz 1 Buchstabe a und Artikel 9 Absatz 2 Buchstabe a DSGVO');
    });

    it('Punkte: ohne Einwilligung keine Punkte, kein Paar-Prüfwert, kein Muster-Hinweis (#562)', () => {
      const text = abschnitt('Punkte');

      expect(text).toContain('Ohne sie (nie erteilt oder widerrufen) berechnen wir für dein Konto keine Punkte und keine Meilensteine');
      expect(text).toContain('weder ein Paar-Prüfwert noch ein Muster-Hinweis, der es nennt');
      expect(text).toContain('Kopien, die ein Konto ohne Einwilligung zu seiner Mitwirkung macht, bringen niemandem Punkte');
    });

    it('Punkte: eigene, freiwillige Einwilligung, getrennt von der zur Mitwirkung (#351)', () => {
      const text = abschnitt('Punkte');

      expect(text).toContain('deine eigene, freiwillige Einwilligung „Punkte und Meilensteine“');
      expect(text).toContain('nichts ist vorausgewählt');
      // Mit Schalter einwilligung_im_gewinn auch als Frage mit zwei Knöpfen (#788, Jura 25.11.)
      expect(text).toContain(
        'Du gibst sie selbst unter „Meine Beiträge“ (Häkchen oder Frage mit zwei gleichwertigen Knöpfen) ' +
          'oder mit einem eigenen Häkchen in den „Datenschutz-Einstellungen“',
      );
      expect(text).toContain('Ohne sie kannst du genauso beitragen und bewerten');
      expect(text).toContain('jederzeit in den „Datenschutz-Einstellungen“ widerrufen; danach wird nichts mehr berechnet');
      expect(text).not.toContain('Bevor wir Punkte einschalten');
    });

    it('Verwendung: Kopien ohne Einwilligung ohne Prüfwert, nur im Zähler aller Kopien (#562)', () => {
      const text = abschnitt('Verwendung von Beiträgen');

      expect(text).toContain('Kopien angemeldeter Konten ohne Einwilligung');
      expect(text).toContain('bekommen keinen Prüfwert');
      expect(text).toContain('nicht für „Diese Woche oft genutzt“ und nicht für Punkte');
    });

    it('Rückmeldung: Muster-Hinweise als einzige Ausnahme von „wer genutzt hat, zeigen wir nicht“', () => {
      const text = abschnitt('Rückmeldung zur Nutzung deiner Beiträge');

      expect(text).toContain('Wer deine Beiträge genutzt hat, wissen wir nicht und zeigen wir nicht');
      expect(text).toContain('Einzige Ausnahme, sobald Punkte eingeschaltet sind');
      expect(text).toContain('ohne die genutzten Beiträge (siehe „Punkte“)');
    });

    it('Profiling: nur mit eingeschalteten Punkten, keine allein automatisierte Entscheidung (Jura 26.11.)', () => {
      const text = abschnitt('Keine automatisierte Entscheidungsfindung');

      expect(text).toContain('solange Punkte ausgeschaltet sind');
      expect(text).toContain(
        'er wird automatisch berechnet. Deinen Punktestand zeigen wir nur dir. Eine Entscheidung, die allein ' +
          'automatisiert getroffen wird und dir gegenüber rechtliche oder ähnlich erhebliche Wirkung hat, gibt es nicht.',
      );
      expect(text).not.toContain('Saison-Rangliste');
    });
  });

  // Sprungziel des Hinweises unter dem Suchfeld (search.component.ts, SUCHANFRAGEN_ABSCHNITT)
  it('trägt am Abschnitt „Deine Suchanfragen“ die Sprungmarke des Suchfelds', () => {
    const ziel = seite.querySelector(`#${SUCHANFRAGEN_ABSCHNITT}`)!;
    expect(ziel.querySelector('h2')!.textContent!.trim()).toBe('Deine Suchanfragen');
  });

  describe('Gegenlesen (#358)', () => {
    it('nennt feste Regeln ohne KI, keine Speicherung und die flüchtige Zählung', () => {
      const text = abschnitt('Gegenlesen beim Schreiben');

      expect(text).toContain('gegen feste Schreibregeln');
      expect(text).toContain('ohne KI');
      expect(text).toContain('wir speichern weder deinen Entwurf noch die Anmerkungen');
      expect(text).toContain('höchstens etwa elf Minuten');
      expect(text).toContain('Artikel 6 Absatz 1 Buchstabe b DSGVO');
    });

    it('nennt den Kürzungsvorschlag: ohne KI, nicht gespeichert, erst beim Übernehmen in der Kurzfassung (#403, #550)', () => {
      const text = abschnitt('Gegenlesen beim Schreiben');

      expect(text).toContain('Kürzungsvorschlag');
      expect(text).toContain('der Vorschlag entsteht ohne KI, wird nicht gespeichert');
      expect(text).toContain('erst in der Kurzfassung, wenn du ihn übernimmst');
      expect(text).toContain('oder einen Kürzungsvorschlag anfragt');
    });

    it('nennt die Spracherkennung für Beiträge und neue Aussagen, auch beim Vorab-Anlegen (#405, #550)', () => {
      const text = abschnitt('Gegenlesen beim Schreiben');

      expect(text).toContain('lokale Spracherkennung');
      expect(text).toContain('zeigt dir dann einen Sprachhinweis');
      expect(text).toContain('neue Aussage');
      expect(text).toContain('„Aussage vorab anlegen“');
      expect(text).toContain('Titel und Text des Beitrags (beim Bild die Unterschrift)');
      expect(text).toContain('auch davon speichern wir nichts');
      expect(text).toContain('wie oft dein Konto gegenlesen lässt, die Spracherkennung fragt');
    });
  });

  describe('Ändern eigener Beiträge (#299, #550)', () => {
    it('beschreibt den Änderungsverlauf mit Kennung und Zeitpunkt, ohne den alten Wortlaut', () => {
      const text = abschnitt('Beiträge, die du einstellst');

      expect(text).toContain('Kommentar oder deine Hintergrundinfo kannst du unter „Meine Beiträge“ ändern');
      expect(text).toContain('Änderungsverlauf');
      expect(text).toContain('deine Kennung und den Zeitpunkt');
      expect(text).toContain('Den alten Wortlaut bewahren wir nicht auf');
      expect(text).not.toContain('Eine Bearbeitungsgeschichte führen wir nicht');
      expect(text).not.toContain('lassen sich derzeit gar nicht ändern');
      expect(text).not.toContain('Solange ein Beitrag nicht geändert werden kann');
    });

    it('nimmt die Kennung im Änderungsverlauf in die Anonymisierung bei Kontolöschung auf', () => {
      const text = abschnitt('Beiträge, die du einstellst');

      expect(text).toContain('an allen genannten Stellen, auch im Änderungsverlauf, durch einen Platzhalter');
    });

    it('stützt den Änderungsverlauf auch in der Zusammenfassung auf lit. f', () => {
      const text = abschnitt('Beiträge, die du einstellst');

      expect(text).toContain('für die Herkunftsangabe am Beitrag und den Änderungsverlauf');
    });

    it('sagt, dass eine entfernte Herkunft als Herkunft gespeichert bleibt', () => {
      const text = abschnitt('Beiträge, die du einstellst');

      expect(text).toContain('Eine Herkunft, die du dabei entfernst, verschwindet vom Beitrag, bleibt aber als Herkunft gespeichert');
    });

    it('nennt beim CC0-Wortlaut, dass Ändern die Kennung ersetzt', () => {
      const text = abschnitt('Beiträge, die du einstellst');

      expect(text).toContain('tritt die Kennung des Wortlauts, den dir das Formular zum Ändern gezeigt hat, an die Stelle der bisherigen');
      expect(text).toContain('Was du vor dem 29.10.2026 eingestellt und seither nicht geändert hast');
    });
  });

  describe('Kennung (#284, #333, #385)', () => {
    it('spricht von der Kennung, nicht von der Nutzerkennung', () => {
      expect(ganzerText()).not.toContain('Nutzerkennung');
      expect(abschnitt('Anmeldung über die Netzbegrünung')).toContain(
        'eine Kennung (eine feste Zeichenfolge, die dein Konto bezeichnet, kein Name)',
      );
    });

    it('behauptet nicht mehr, angemeldete Browser bekämen die Kennung', () => {
      expect(ganzerText()).not.toContain('Technisch übermitteln wir an angemeldete Browser auch die Kennung');
      expect(abschnitt('Beiträge, die du einstellst')).toContain(
        'Deine Kennung geben wir außer an deinen eigenen Browser nur an Administratorinnen und Administratoren heraus',
      );
    });
  });

  describe('Eigener Realm und Einladungen (#490)', () => {
    it('nennt den eigenen Realm als Anmeldedienst und keine Selbstregistrierung ohne Einladung', () => {
      const text = abschnitt('Anmeldung und Zugang');

      expect(text).toContain('Realm „gutgesagt“');
      expect(text).toContain('Ohne Einladung kann niemand selbst ein Konto anlegen');
      expect(text).not.toContain('eine Selbstregistrierung gibt es nicht');
      // Seit dem Realm-Umzug (20.11.) kein Übergangssatz mehr (#738)
      expect(text).not.toContain('Bis wir die Anmeldung umgestellt haben');
      expect(text).not.toContain('bis zur Umstellung vom');
    });

    it('Einladung: Mail-Adresse an den Anmeldedienst, Mail über dessen Mailserver, keine Adresse an der Einladung', () => {
      const text = abschnitt('Konto aus einer Einladung');

      expect(text).toContain('und eine E-Mail-Adresse ein');
      expect(text).toContain('über seinen Mailserver');
      expect(text).toContain('Die Plattform selbst speichert und protokolliert deine E-Mail-Adresse nicht');
      expect(text).toContain('An der Einladung speichern wir nur, wie oft sie eingelöst wurde');
      expect(text).toContain('Am Konto steht nicht, über welche Einladung es entstand');
      expect(text).toContain('Artikel 6 Absatz 1 Buchstabe b DSGVO');
    });

    it('Einladung: IP-Adresse nur flüchtig für die Begrenzung der Aufrufe', () => {
      const text = abschnitt('Konto aus einer Einladung');

      expect(text).toContain('deine IP-Adresse');
      expect(text).toContain('nur flüchtig im Arbeitsspeicher');
      expect(text).toContain('spätestens 16 Minuten');
      expect(text).toContain('Artikel 6 Absatz 1 Buchstabe f DSGVO');
    });

    it('Netzbegrünung: kein vorab angelegtes Konto, der Lauf auf Produktion war ohne (#738)', () => {
      const text = abschnitt('Anmeldung über die Netzbegrünung');

      expect(text).toContain('Bei deiner ersten Anmeldung legt der Anmeldedienst dafür ein Konto an');
      expect(text).not.toContain('vorab an');
    });

    it('kein Zugang, den wir selbst anlegen, seit dem Realm-Umzug (#738)', () => {
      expect(ganzerText()).not.toContain('Zugang, den wir selbst anlegen');
      expect(ganzerText()).not.toContain('einen Zugang von Hand anlegen');
    });

    it('Wo deine Daten liegen: Anmeldedienst samt Mailversand beim Auftragsverarbeiter (Entscheidung 03.11.2026)', () => {
      const text = abschnitt('Wo deine Daten liegen');

      expect(text).toContain('Dazu gehört auch der Anmeldedienst samt Mailversand. Weitere Empfänger gibt es nicht.');
    });

    it('Pflichtangaben: E-Mail-Adresse bei jeder Kontoart', () => {
      expect(abschnitt('Was du angeben musst und was freiwillig ist')).toContain(
        'Kennung und eine E-Mail-Adresse, bei jeder Kontoart',
      );
    });

    it('Einladung: Kennung, Mail-Adresse und Name beim Anmelden, Anzeigename aus dem Namen, nicht aus der Adresse (#730)', () => {
      const text = abschnitt('Konto aus einer Einladung');

      expect(text).toContain('erhält die Plattform vom Anmeldedienst deine Kennung und deine E-Mail-Adresse');
      expect(text).toContain('Außerdem erhält sie deinen Vor- und Nachnamen');
      expect(text).toContain('deinen Anzeigenamen, etwa „Anna B.“, und speichern nur diesen');
      expect(text).toContain('Aus deiner E-Mail-Adresse bilden wir keinen Anzeigenamen');
      expect(text).not.toContain('Einen Namen hat ein Konto aus einer Einladung nicht');
    });

    it('Einladung: Name und Mail-Adresse an den Anmeldedienst, Zweck mit Name (#730)', () => {
      const text = abschnitt('Konto aus einer Einladung');

      expect(text).toContain('gibst du deinen Vor- und Nachnamen und eine E-Mail-Adresse ein');
      expect(text).toContain('ohne es selbst zu speichern');
      expect(text).toContain('dein Vor- und Nachname und dein Passwort');
      expect(text).toContain('dich in E-Mails des Anmeldedienstes mit deinem Namen anzusprechen');
      expect(text).toContain('Deinen vollen Namen speichert nur der Anmeldedienst');
    });

    it('Einladung: Keycloak-Zeitpunkt der NB-Zustimmung nur bei alten Konten, archiviert, dann gelöscht (0.9.8)', () => {
      const text = abschnitt('Konto aus einer Einladung');

      expect(text).toContain('Bei Konten von vor dem 20. November 2026 außerdem der Zeitpunkt');
      expect(text).toContain('nachdem wir sie in der Plattform archiviert haben');
      expect(text).toContain('siehe „Deine Zustimmung und deine Einwilligung“');
      expect(text).not.toContain('[Datum der Umstellung]');
    });

    it('Einladung: Konto bleibt, bis wir es löschen; ohne Passwort 30 Tage nach Ablauf des Links (#538, #730)', () => {
      const text = abschnitt('Konto aus einer Einladung');

      expect(text).toContain('Das Konto im Anmeldedienst bleibt, bis wir es löschen');
      expect(text).toContain('Ein Konto, für das nie ein Passwort festgelegt wurde');
      expect(text).toContain('oder du nach dem Öffnen des Links abgebrochen hast');
      // NIE_BENUTZTES_KONTO_TAGE und MAIL_GUELTIG_SEKUNDEN im Semantic-Service
      expect(text).toContain('löschen wir automatisch 30 Tage nach Ablauf des Links, also etwa 33 Tage nach dem Einlösen');
      expect(text).not.toContain('bis du oder wir es löschen');
      expect(text).not.toContain('Es bleibt ohne Passwort stehen');
    });

    it('Netzbegrünung: Angaben vom Anmeldedienst', () => {
      const text = abschnitt('Anmeldung über die Netzbegrünung');

      expect(text).toContain('erhält diese Plattform vom Anmeldedienst eine Kennung');
      expect(text).toContain('Das gilt für alle Anmeldewege');
    });

    it('Anmelde-Cookie: beide Anmeldewege (#738)', () => {
      const text = abschnitt('Anmelde-Cookie');
      expect(text).toContain('Das gilt für beide Anmeldewege: über die Netzbegrünung und mit einem Konto aus einer Einladung.');
      expect(text).toContain('die der Anmeldedienst übermittelt, aber keine Zugangs-Tokens');
      expect(text).not.toContain('selbst anlegen');
    });
  });

  describe('Teams über Einladungen', () => {
    it('Einladung: das Team nur mit ausdrücklicher Zustimmung, nie die Einladung', () => {
      const text = abschnitt('Konto aus einer Einladung');

      expect(text).toContain('Am Konto steht nicht, über welche Einladung es entstand');
      expect(text).toContain(
        'Nur wenn eine Einladung zu einem Team gehört und du ausdrücklich zustimmst, speichern wir dein Team (siehe „Teams“), nicht aber die Einladung.'
      );
    });

    it('Teams: was gespeichert wird, ohne Einladung, nur für dich, Admins nur die Zahl', () => {
      const text = abschnitt('Teams');

      expect(text).toContain(
        'deine Kennung, den Namen des Teams, deine laufende Nummer im Team und den Tag, an dem du beigetreten bist'
      );
      expect(text).toContain('Welche Einladung du genutzt hast, speichern wir nicht.');
      expect(text).toContain('Sagst du nein, speichern wir nichts davon');
      expect(text).toContain('Deine Teams siehst nur du, unter „Meine Teams“.');
      expect(text).toContain('sehen je Team nur, wie viele dabei sind, keine Namen und keine Liste');
    });

    it('Teams: auch nach einer Gruppe, die zugestimmt hat; die Gruppe bekommt keine Daten', () => {
      const text = abschnitt('Teams').replace(/\s+/g, ' ');

      expect(text).toContain(
        'Manche Einladungen gehören zu einem Team, etwa einem Treffen, einem Ort oder einer Gruppe, die zugestimmt hat. Die Gruppe bekommt keine Daten über dich.'
      );
      expect(text).not.toContain('etwa einem Treffen oder einem Ort.');
    });

    it('Teams: eigene Einwilligung nach Art. 6 Abs. 1 lit. a und Art. 9 Abs. 2 lit. a, getrennt von den anderen', () => {
      const text = abschnitt('Teams');

      expect(text).toContain('Artikel 6 Absatz 1 Buchstabe a und Artikel 9 Absatz 2 Buchstabe a DSGVO');
      expect(text).toContain('Du gibst sie mit dem Knopf „Ja, speichert …“, nichts ist vorausgewählt.');
      expect(text).toContain('getrennt von der Einwilligung zu deiner Mitwirkung und von „Punkte und Meilensteine“');
      expect(text).toContain('mit der Kennung des Wortlauts und dem Zeitpunkt als Nachweis');
    });

    it('Teams: der Nachweis bleibt, solange du im Team bist, nicht bis zur Kontolöschung (25.11.2026)', () => {
      const text = abschnitt('Teams').replace(/\s+/g, ' ');

      expect(text).toContain(
        'Deine Antwort speichern wir mit der Kennung des Wortlauts und dem Zeitpunkt als Nachweis, solange du im Team bist.'
      );
      expect(text).not.toContain('als Nachweis, bis dein Konto gelöscht wird');
    });

    it('Teams: Zweck mit der Summe des Teams (25.11.2026)', () => {
      const text = abschnitt('Teams').replace(/\s+/g, ' ');

      expect(text).toContain(
        'Zweck: dir zu zeigen, in welchen Teams du dabei bist, und die Nummer in deinem Team zu vergeben und die Summe deines Teams zu bilden.'
      );
    });

    it('Teams: die Team-Summe mit derselben Einwilligung, mit Kommentaren und „Ja, gepostet“, noch nicht eingeschaltet (26.11.2026)', () => {
      const text = abschnitt('Teams').replace(/\s+/g, ' ');

      expect(text).toContain(
        'Diese Anzeige am Namen ist noch nicht eingeschaltet. ' +
          'Mit derselben Einwilligung darf die Zahl deiner Beiträge, Bewertungen und Kommentare und deiner Meldungen „Ja, gepostet“ in eine Summe deines Teams eingehen. ' +
          'Diese Summe sehen nur Mitglieder des Teams, nur für abgeschlossene Wochen, erst wenn mindestens fünf ' +
          'Mitglieder eingewilligt haben, gerundet und nie mit einzelnen Namen. Die Team-Summe ist noch nicht eingeschaltet.'
      );
    });

    it('Teams: „Team verlassen“ löscht sofort, Nummer nicht neu, Sicherungskopien bis zum Ablauf', () => {
      const text = abschnitt('Teams');

      expect(text).toContain('„Team verlassen“');
      expect(text).toContain('wir löschen den Eintrag sofort');
      expect(text).toContain('Deine Nummer vergeben wir nicht neu.');
      expect(text).toContain('siehe „Sicherungskopien“');
    });

    it('Teams: die Anzeige am Namen ist noch nicht eingeschaltet und braucht eine eigene Frage', () => {
      const text = abschnitt('Teams');

      expect(text).toContain('fragen wir dich vorher gesondert');
      expect(text).toContain('Diese Anzeige am Namen ist noch nicht eingeschaltet.');
    });
  });

  describe('Suchvorgänge (#239, #289, #495)', () => {
    it('nennt den Tag statt eines Zeitpunkts und das Ende des Tages als Frist mit Tageszähler', () => {
      const text = abschnitt('Suchvorgänge');

      expect(text).toContain('den Tag (keine Uhrzeit)');
      expect(text).toContain('dieses nur bis zum Ende des Tages');
      expect(text).toContain('automatisch nach Ablauf ihres Tages');
      expect(text).not.toContain('nach 90 Tagen');
      expect(text).toContain(
        'je Tag nur, wie oft gesucht wurde, wie oft davon ohne Treffer und von wie vielen verschiedenen Pseudonymen',
      );
      expect(text).not.toContain('keine Löschfrist');
    });
  });

  describe('Tagespseudonym statt Kennung im Browser (#446)', () => {
    it('Suchvorgänge: Besucher über die IP-Adresse allein und einen täglich neuen, nicht gespeicherten Schlüssel', () => {
      const text = abschnitt('Suchvorgänge');

      expect(text).toContain('nichts in deinem Browser ab');
      expect(text).toContain('nur aus dem heutigen Datum und deiner IP-Adresse');
      // #495: kein User-Agent mehr im Pseudonym.
      expect(text).toContain('Die Bezeichnung deines Browsers (User-Agent) und andere Merkmale deines Geräts gehen nicht ein.');
      expect(text).toContain('hat deshalb an einem Tag dasselbe Pseudonym');
      expect(text).toContain('im Mobilfunknetz teilen sich oft viele Menschen eine Adresse');
      expect(text).toContain('wenige Minuten später noch einmal');
      expect(text).toContain('jeden Tag neu zufällig erzeugt, nur im Arbeitsspeicher hält und nirgends speichert');
      expect(text).toContain('Die IP-Adresse wird dabei weder gespeichert noch protokolliert');
      expect(text).not.toContain('Sitzungskennung');
      // Der Schlüssel wechselt mit der ersten Suche des neuen Tages, nicht um Mitternacht.
      expect(text).toContain('Mit der ersten Suche eines neuen Tages ersetzt er ihn');
      expect(text).not.toContain('mit dem Tag ist auch der Schlüssel weg');
      // "Kennung" ist im Glossar die Kontokennung, nicht der User-Agent.
      expect(text).not.toContain('Kennung deines Browsers');
      expect(text).toContain('siehe „Protokolldateien“');
    });

    it('Suchen ohne Treffer: Netzwechsel zählt neu, je Anschluss höchstens eine Person, auch mit anderem Browser', () => {
      const text = abschnitt('Suchen ohne Treffer');

      expect(text).toContain('anderes Netz');
      // #495: das Pseudonym selbst steht für den Anschluss; ein anderer Browser zählt nicht neu.
      expect(text).toContain('nur aus deinem Anschluss entsteht');
      expect(text).toContain('je Anschluss höchstens eine Person');
      expect(text).not.toContain('Zusätzlich merken wir uns');
      expect(text).toContain('Summe der Personen der einzelnen Tage');
      expect(text).toContain('als eine, auch mit verschiedenen Browsern');
      expect(text).not.toContain('anderen Browser</strong>');
      expect(text).not.toContain('anderen Browser oder');
      expect(text).not.toContain('neue Sitzungskennung');
    });

    it('Verwendung von Beiträgen: kein Pseudonym und kein Kontobezug', () => {
      const text = abschnitt('Verwendung von Beiträgen');

      expect(text).toContain('nicht ablesen, welches Konto einen Beitrag verwendet hat');
      expect(text).not.toContain('höchstens 30 Tage');
      // #495: der Prüfwert ohne Anmeldung nur aus dem Anschluss.
      expect(text).toContain('(ohne Anmeldung: vom selben Anschluss)');
      expect(text).not.toContain('mit demselben Browser');
      expect(text).not.toContain('und der Bezeichnung deines');
    });

    it('Meldungen: ohne Konto das Tagespseudonym, nur bis zum Abschluss', () => {
      const text = abschnitt('Meldungen von Beiträgen');

      expect(text).toContain('tritt an ihre Stelle dein Tagespseudonym');
      expect(text).toContain('Es bleibt nur, solange die Meldung offen ist');
      expect(text).toContain('mit dem Abschluss der Bearbeitung löschen wir es');
      expect(text).not.toContain('stehen also beide nebeneinander');
    });

    it('Speicherung auf deinem Gerät: keine Kennung zum Wiedererkennen, alte wird entfernt', () => {
      const text = abschnitt('Keine Kennung zum Wiedererkennen');

      expect(text).toContain('keine Kennung in deinem Browser ab');
      expect(text).toContain('aus deinem Browser entfernt');
    });
  });

  describe('Feedback (#343)', () => {
    it('beschreibt Feedback ohne Kennung, nur für Admins, mit 180 Tagen Frist', () => {
      const text = abschnitt('Feedback');

      expect(text).toContain('auch ohne Konto');
      expect(text).toContain('Wir speichern dazu weder deine Kennung noch eine Sitzungskennung');
      expect(text).toContain('der Tag des Eingangs');
      expect(text).toContain('nur Administratorinnen und Administratoren');
      expect(text).toContain('nach 180 Tagen automatisch');
    });
  });

  describe('Einwürfe in den Fangkorb', () => {
    it('nennt keine Screenshots und statt „verarbeitende Person“ die Person, die den Einwurf verknüpft hat', () => {
      const text = abschnitt('Einwürfe in den Fangkorb');

      expect(ganzerText()).not.toContain('Screenshot');
      expect(ganzerText()).not.toContain('verarbeitenden Person');
      expect(text).toContain('die Kennung der Person, die den Einwurf mit einem Beitrag verknüpft hat');
    });

    it('nennt die Zeitpunkte an Sätzen und an der Verknüpfung', () => {
      const text = abschnitt('Einwürfe in den Fangkorb');

      expect(text).toContain('mit der Kennung der Person, die sie gespeichert hat, und dem Zeitpunkt');
      expect(text).toContain('der Zeitpunkt dieser Verknüpfung');
    });

    it('sagt, dass Sätze an fremden Einwürfen nach einer Kontolöschung bleiben und „ehemalige Person“ zeigen', () => {
      const text = abschnitt('Einwürfe in den Fangkorb');

      expect(text).toContain('Deine Sätze an Einwürfen anderer bleiben stehen');
      expect(text).toContain('„ehemalige Person“');
    });
  });

  describe('Kontolöschung (#278)', () => {
    it('nennt die Liste gelöschter Konten für Netzbegrünung-Login und Konto aus einer Einladung, von Hand gepflegt', () => {
      const text = abschnitt('Deine Rechte');

      expect(text).toContain('Hast du dich über die Netzbegrünung oder mit einem Konto aus einer Einladung angemeldet');
      expect(text).toContain('Liste gelöschter Konten');
      expect(text).toContain('von Hand wieder aus');
      expect(text).toContain('in der Regel 14 Tage nach der Kontolöschung');
      expect(ganzerText()).not.toContain('Sperrliste');
    });

    it('zählt die gespeicherte Zahl der Rückmeldung zu dem, was mit dem Konto geht', () => {
      expect(abschnitt('Deine Rechte')).toContain('die gespeicherte Zahl für die Rückmeldung zur Nutzung');
    });
  });

  describe('Protokolldateien (#275)', () => {
    it('nennt für die Anwendung den Pfad ohne Suchtext und keine verweisende Seite', () => {
      const text = abschnitt('Zugriffe innerhalb der Anwendung');

      expect(text).toContain('ohne Suchtext und sonstige Zusätze in der Adresse');
      expect(text).toContain('aber nicht die verweisende Seite');
      expect(text).toContain('Für Suchen und für Aufrufe der Ergebnisseite schreibt er gar keine Zeile');
    });

    it('nimmt ältere Zeilen von der Zusage aus, dass keine Suchtexte darin stehen', () => {
      expect(abschnitt('Protokolle der Anwendung')).toContain('Ausnahme');
    });
  });

  describe('Rückschlüsse auf die politische Haltung (Art. 9, Entscheidung 29.10.2026)', () => {
    it('nennt Art. 9 und keine Auswertung nach politischer Haltung', () => {
      const text = abschnitt('Rückschlüsse auf deine politische Haltung');

      expect(text).toContain('Artikel 9 DSGVO');
      expect(text).toContain('Wir werten deine Mitwirkung nicht danach aus, welche politische Haltung du hast');
    });

    it('Art.-9-Einwilligung: Rechtsgrundlage lit. a, Zeitpunkt und Kennung des Wortlauts (#557)', () => {
      const text = abschnitt('Rückschlüsse auf deine politische Haltung');

      expect(text).toContain('Artikel 9 Absatz 2 Buchstabe a DSGVO');
      expect(text).toContain('eigenes Häkchen, getrennt von den Nutzungsbedingungen und nicht vorbelegt');
      expect(text).toContain('den Zeitpunkt und die Kennung des Wortlauts');
      expect(text).toContain('sein Stand-Datum, bei einem zweiten Wortlaut vom selben Tag mit einem Buchstaben dahinter');
      expect(text).toContain('Ohne Einwilligung kannst du suchen und lesen, aber nichts beitragen und nichts bewerten');
    });

    it('Zustimmung zu den NB: eigenes Häkchen, Vertrag lit. b, Nachweis lit. f, bis zur Kontolöschung (0.9.8)', () => {
      const text = abschnitt('Rückschlüsse auf deine politische Haltung');

      expect(text).toContain('Deine Zustimmung und deine Einwilligung');
      expect(text).toContain('zwei Dinge, getrennt und mit je einem eigenen Häkchen, keins vorbelegt');
      expect(text).toContain('Die Zustimmung zu den Nutzungsbedingungen ist ein Vertrag (Rechtsgrundlage Art. 6 Abs. 1 lit. b DSGVO)');
      expect(text).toContain('den Zeitpunkt und den Stand der Nutzungsbedingungen, dem du zugestimmt hast');
      expect(text).toContain('(Art. 6 Abs. 1 lit. f DSGVO)');
      expect(text).toContain('Deine Zustimmungen zu den Nutzungsbedingungen bleiben ebenso bis zur Löschung deines Kontos');
      expect(normalisiert(seite.textContent)).not.toContain('(siehe „Deine Einwilligung“)');
    });

    it('Art.-9-Einwilligung: Widerruf im Profilmenü, Folgen und Dauer bis zur Kontolöschung (#557)', () => {
      const text = abschnitt('Rückschlüsse auf deine politische Haltung');

      expect(text).toContain('Widerrufen kannst du jederzeit im Profilmenü unter „Datenschutz-Einstellungen“');
      expect(text).toContain('nichts mehr beitragen und nichts bewerten, und deine Bewertungen löschen wir');
      expect(text).not.toContain('Was du sonst gespeichert hast, bleibt, bis du es löschst');
      expect(text).not.toContain('Was du schon gespeichert hast, bleibt');
      expect(text).toContain('was bis zum Widerruf geschehen ist, bleibt rechtmäßig');
      expect(text).toContain('Deine Einwilligungen, auch widerrufene, bleiben bis zur Löschung deines Kontos');
      expect(abschnitt('Deine Rechte')).toContain('deine Einwilligungen samt Widerrufen und die Muster-Hinweise, die dein Konto nennen');
    });

    it('Art.-9-Einwilligung: der Widerruf legt einen Löschauftrag an, binnen sieben Tagen (DSFA R9b)', () => {
      const text = abschnitt('Rückschlüsse auf deine politische Haltung');

      expect(text).toContain('Innerhalb von sieben Tagen lösen wir auch deine Beiträge, Einwürfe und Sätze von dir');
      // Widerrufe vor dem Einspielen: Frist ab dem Einspielen. Bis zum Release steht der Platzhalter,
      // danach ein Datum (docs/DEPLOYMENT.md, Releases); bei Tags prüft scripts/release_platzhalter.py,
      // dass der Platzhalter ersetzt ist.
      expect(text).toMatch(WIDERRUF_VOR_DEM_EINSPIELEN);
      expect(text).toContain('zeigen statt deines Namens „ehemalige Person“, deine Einwürfe löschen wir');
      expect(text).toContain('Dafür legen wir einen Löschauftrag an: deine Kennung, der Zeitpunkt deines Widerrufs und die Frist');
      expect(text).toContain('Einen erledigten Löschauftrag löschen wir ein Jahr nach der Erledigung, mit deinem Konto sofort');
      expect(text).toContain('Dein Konto bleibt');
      expect(text).toContain('fragen wir dich beim nächsten Besuch neu; deine frühere Einwilligung zählt dann nicht mehr');
      // Neue Einwilligung vor der Ausfuehrung (Entscheidung Maintainer, 13.11.2026)
      expect(text).toContain('was du danach beiträgst, erfasst ein noch offener Löschauftrag nicht');
      expect(abschnitt('Beiträge, die du einstellst')).toContain('Widerrufst du deine Art.-9-Einwilligung, ersetzen wir deine Kennung ebenso, innerhalb von sieben Tagen');
      expect(abschnitt('Einwürfe in den Fangkorb')).toContain('Widerrufst du deine Art.-9-Einwilligung, tun wir dasselbe innerhalb von sieben Tagen');
    });

    it('Satz zu Widerrufen vor dem Einspielen: Platzhalter oder echtes Datum, sonst nichts', () => {
      const satz = (tag: string) =>
        `Wer vor dem ${tag} widerrufen hat, dessen Beiträge, Einwürfe und Sätze lösen wir innerhalb von sieben Tagen ab diesem Tag von ihm.`;

      expect(satz('[Datum des Einspielens]')).toMatch(WIDERRUF_VOR_DEM_EINSPIELEN);
      expect(satz('1. Dezember 2026')).toMatch(WIDERRUF_VOR_DEM_EINSPIELEN);
      expect(satz('[Datum]')).not.toMatch(WIDERRUF_VOR_DEM_EINSPIELEN);
      expect(satz('Dezember 2026')).not.toMatch(WIDERRUF_VOR_DEM_EINSPIELEN);
    });
  });

  describe('Weitere Korrekturen am Ist-Stand', () => {
    it('Verwendung: nicht gespeichert wird der User-Agent', () => {
      expect(abschnitt('Verwendung von Beiträgen')).toContain('die genaue Bezeichnung deines Browsers (User-Agent)');
    });

    it('Gerätespeicher: kein Kennzahlen-Eintrag, dafür Fangkorb-Filter, Teilen-Menü und Service Worker', () => {
      const text = abschnitt('Weitere Einträge');

      expect(text).not.toContain('Kennzahlen');
      expect(text).toContain('deine Filter im Fangkorb');
      expect(text).toContain('Teilen-Menü');
      expect(text).toContain('Service Worker');
    });

    it('Gerätespeicher: der Merker für das Neuladen nach einer neuen Version (neue-version.ts)', () => {
      const text = abschnitt('Weitere Einträge').replace(/\s+/g, ' ');

      expect(text).toContain(
        'den Zeitpunkt, zu dem die Seite wegen einer neuen Version von Gut gesagt von selbst neu geladen hat ' +
          '(nur ein Merker, damit das nicht in einer Schleife geschieht; er gilt nur zehn Minuten)',
      );
    });

    it('Gerätespeicher: der angefangene Kommentar bis zum Tabschluss, höchstens eine Stunde (E1, 14.11.2026)', () => {
      const text = abschnitt('Weitere Einträge').replace(/\s+/g, ' ');

      expect(text).toContain(
        'Schreibst du einen Kommentar und wechselst kurz in eine andere App, merkt sich dein Browser den ' +
          'angefangenen Kommentar bis zum Schließen des Tabs, höchstens eine Stunde lang: Titel, Text, Kurz- und ' +
          'Langfassung, Zweck und Stil, die Aussage, auf die er antwortet, und einen Prüfwert, der ihn deinem Konto ' +
          'zuordnet, nicht deinen Namen. Wir löschen ihn, sobald du den Kommentar speicherst, das Formular leerst, ' +
          'dich abmeldest oder deine Einwilligung widerrufst. Er verlässt dein Gerät nicht von selbst.',
      );
    });

    it('Gerätespeicher: das Profilbild liegt nur nach eigener Wahl im Browser, bis zum Zurücksetzen (#437)', () => {
      const text = abschnitt('Weitere Einträge');

      expect(text).not.toContain('das Profilbild, das dir angezeigt wird');
      expect(text).toContain('wenn du es selbst wählst');
      expect(text).toContain('bis du die Wahl zurücksetzt');
      expect(text).toContain('Ohne eigene Wahl speichern wir nichts');
    });

    it('Gerätespeicher: der Merker einer Einladung mit Team, höchstens drei Tage, nach dem Lesen gelöscht (team-merker.ts)', () => {
      const text = abschnitt('Weitere Einträge').replace(/\s+/g, ' ');

      expect(text).toContain(
        'Sagst du ohne Konto bei einer Einladung zu einem Team „Ja, speichert …“, merkt sich dein Browser, auch über ' +
          'das Schließen des Tabs hinaus, den Code der Einladung, die Kennung des Wortlauts, dem du zugestimmt hast, ' +
          'ob du der zweiten Frage zugestimmt hast, ob deine Teams an deinem Namen erscheinen dürfen (ohne diese ' +
          'Frage: nein), und bis wann der Eintrag gilt.'
      );
      expect(text).toContain('Damit trägt er deine Antwort bis zur Anmeldung nach dem Anlegen deines Kontos.');
      expect(text).toContain(
        'Hast du schon ein Konto und willst dich zum Beitreten erst anmelden, merkt er sich nur den Code, bis du angemeldet zurückkommst.'
      );
      expect(text).toContain('Den Namen des Teams und deine Nummer enthält der Eintrag nie.');
      expect(text).toContain('Er gilt höchstens drei Tage, so lange wie der Link in der Mail.');
      expect(text).toContain(
        'Wir löschen ihn, sobald die Seite der Einladung ihn nach deiner Anmeldung gelesen hat, und einen abgelaufenen ' +
          'Eintrag beim nächsten Aufruf der Einladung.'
      );
    });

    it('Gerätespeicher: Willkommen und Rundgang „Mitmachen“ als zwei Vermerke ohne Übertragung (#516)', () => {
      const text = abschnitt('Weitere Einträge');

      expect(text).toContain('Willkommen beim ersten Besuch');
      expect(text).toContain('Rundgangs „Mitmachen“');
      expect(text).toContain('zwei Vermerke ohne Angaben über dich');
      expect(text).toContain('bis du die Websitedaten dieser Seite löschst');
      expect(text).toContain('Sie gehen nicht an uns und werden nicht gezählt.');
    });


    it('kein KI-Vorschlag für Bildunterschriften mehr, also auch kein Anbieter in den USA (#393)', () => {
      const text = abschnitt('Keine Übermittlung außerhalb der EU');

      expect(text).toContain('Wir setzen keinen Sprach- oder Bilderkennungsdienst eines Anbieters außerhalb der EU ein.');
      expect(text).not.toContain('Vorschlag für die Unterschrift');
      expect(text).not.toContain('KI-Anbieter');
    });
  });

  describe('Meldungen nach Art. 16 DSA (#438)', () => {
    it('nennt Name, E-Mail-Adresse und Erklärung guten Glaubens und wofür die Adresse dient', () => {
      const text = abschnitt('Meldungen von Beiträgen');

      expect(text).toContain('deine Erklärung, in gutem Glauben zu melden');
      expect(text).toContain('dein Name und deine E-Mail-Adresse, falls du sie angibst');
      expect(text).toContain('Name und E-Mail-Adresse sind freiwillig');
      expect(text).toContain('teilen wir dir unsere Entscheidung über die Meldung mit');
      expect(text).toContain('Artikel 16 Absatz 5 DSA');
      // #493: die Adresse dient auch der Eingangsbestätigung per Mail (Art. 16 Abs. 4 DSA).
      expect(text).toContain('Gleich nach der Meldung bestätigen wir dir den Eingang');
      expect(text).toContain('Artikel 16 Absatz 4 DSA');
      expect(text).not.toContain('nur, um dir unsere Entscheidung');
      // Der Satz zu Name und E-Mail-Adresse steht hinter dem zu den Kennungen, damit
      // sich „beide“ nicht auf sie beziehen lässt.
      expect(text).not.toContain('stehen also beide nebeneinander');
    });
  });

  describe('Bilder von fremden Servern (#447)', () => {
    it('sagt, dass der Browser ein fremdes Bild erst auf Klick lädt und ohne Klick nichts an den Server geht', () => {
      const text = abschnitt('Bilder von fremden Servern');

      expect(text).toContain('Platzhalter „Bild laden“');
      expect(text).toContain('Erst wenn du darauf klickst, lädt dein Browser dieses eine Bild');
      expect(text).toContain('Ohne deinen Klick erfährt der fremde Server nichts von dir');
      expect(text).toContain('Den Klick merken wir uns nicht');
      expect(text).toContain('ohne Konto');
      expect(text).toContain('Artikel 6 Absatz 1 Buchstabe f DSGVO');
      expect(text).not.toContain('Dein Browser lädt sie direkt von dem fremden Server');
    });

    it('nennt den Klick auch beim Abruf außerhalb der EU', () => {
      expect(abschnitt('Keine Übermittlung außerhalb der EU')).toContain('erst nach deinem Klick auf „Bild laden“');
    });

    it('nennt die Mitverantwortung für die Übermittlung an den fremden Server (EuGH C-40/17)', () => {
      const text = abschnitt('Keine Übermittlung außerhalb der EU');
      expect(text).toContain('Für das Einbinden und damit für die Übermittlung deiner IP-Adresse an den fremden Server sind wir mitverantwortlich');
      expect(text).toContain('was der fremde Server danach mit den Daten macht, verantwortet sein Betreiber');
      expect(ganzerText()).not.toContain('Diesen Abruf richtet dein Browser aus, nicht wir');
    });
  });

  describe('Merker der Meilensteine (#351, § 25 TDDDG geprüft 13.11.2026)', () => {
    function mitMerker(aktiv: boolean): string {
      TestBed.resetTestingModule();
      TestBed.configureTestingModule({
        imports: [DatenschutzComponent],
        providers: [provideRouter([]), { provide: MEILENSTEIN_MERKER, useValue: aktiv }],
      });
      const fixture = TestBed.createComponent(DatenschutzComponent);
      fixture.detectChanges();
      return normalisiert((fixture.nativeElement as HTMLElement).textContent);
    }

    it('beschreibt mit Merker Hinweis und Browser-Vermerk im freigegebenen Wortlaut', () => {
      const text = mitMerker(true);

      expect(text).toContain('nach dem Anmelden gilt, was du bis dahin erreicht hast, still als gesehen');
      expect(text).toContain(
        'Damit ein Hinweis zu deinen Meilensteinen nur einmal erscheint, merkt sich dein Browser, welche du schon gesehen hast. ' +
          'Der Vermerk enthält keine Angaben über dich, geht nicht an uns und wird beim Abmelden und beim nächsten Anmelden gelöscht.',
      );
      expect(text).not.toContain('Prüfwert deiner Kennung');
    });

    it('lässt beides weg, wenn der Merker ausgeschaltet ist', () => {
      const text = mitMerker(false);

      expect(text).not.toContain('merkt sich nur dein Browser');
      expect(text).not.toContain('Damit ein Hinweis zu deinen Meilensteinen nur einmal erscheint');
    });
  });

  describe('Merker des Hinweises zum Home-Bildschirm (14.11.2026)', () => {
    const ABSATZ =
      'Auf iPhone und iPad zeigen wir einen Hinweis, wie du Gut gesagt auf deinen Home-Bildschirm legst. ' +
      'Blendest du ihn aus, merkt sich dein Browser das, damit er nicht wiederkommt. Der Vermerk enthält ' +
      'keine Angaben über dich, bleibt auch über das Schließen hinaus, bis du die Websitedaten dieser Seite ' +
      'löschst, und geht nicht an uns.';

    function mitMerker(aktiv: boolean): string {
      TestBed.resetTestingModule();
      TestBed.configureTestingModule({
        imports: [DatenschutzComponent],
        providers: [provideRouter([]), { provide: HOME_HINWEIS_MERKER, useValue: aktiv }],
      });
      const fixture = TestBed.createComponent(DatenschutzComponent);
      fixture.detectChanges();
      return normalisiert((fixture.nativeElement as HTMLElement).textContent);
    }

    it('Schalter aus: kein Absatz, die zwei Vermerke wie bisher', () => {
      const text = mitMerker(false);
      expect(text).not.toContain('Auf iPhone und iPad zeigen wir einen Hinweis');
      expect(text).toContain('sie schon gesehen hast. Das sind zwei Vermerke ohne Angaben über dich.');
    });

    it('Schalter an: der Absatz im freigegebenen Wortlaut, der Satz zu den zwei Vermerken bleibt wie auf main', () => {
      const text = mitMerker(true);
      expect(text).toContain(ABSATZ);
      expect(text).toContain('sie schon gesehen hast. Das sind zwei Vermerke ohne Angaben über dich.');
    });
  });

  describe('Ton bei Erfolgen (#787)', () => {
    it('steht immer unter „Speicherung auf deinem Gerät“, unabhängig von Schalter und Browserzustand', () => {
      localStorage.removeItem(FEIER_TON_SCHLUESSEL);
      TestBed.resetTestingModule();
      TestBed.configureTestingModule({ imports: [DatenschutzComponent], providers: [provideRouter([])] });
      const fixture = TestBed.createComponent(DatenschutzComponent);
      fixture.detectChanges();
      const text = abschnittIn(fixture.nativeElement as HTMLElement, 'Weitere Einträge');
      expect(text).toContain(`unter dem Schlüssel „${FEIER_TON_SCHLUESSEL}“`);
      expect(text).toContain('Der Eintrag enthält nur, dass der Ton an ist, und keine Angaben über dich');
      expect(text).toContain('schaltest du ihn wieder aus, löschen wir den Eintrag');
      expect(text).toContain('bis du ihn änderst');
    });
  });
});

/** Spielgefühl als eine Frage (Schalter spielgefuehl_buehne): ersetzt die Einwilligungsteile. */
describe('DatenschutzComponent: Spielgefühl', () => {
  const ALLE = ['spielgefuehl_buehne', 'punkte', 'rangliste'];
  function seiteMit(an: boolean | string[]): HTMLElement {
    const namen = an === true ? ALLE : an === false ? [] : an;
    TestBed.configureTestingModule({
      imports: [DatenschutzComponent],
      providers: [
        provideRouter([]),
        { provide: FunktionenService, useValue: { an: (name: string) => signal(namen.includes(name)) } },
      ],
    });
    const fixture = TestBed.createComponent(DatenschutzComponent);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('Schalter aus: bisherige Einwilligungen, kein Absatz „Spielgefühl“', () => {
    const seite = seiteMit(false);

    expect(seite.querySelector('[data-testid="dse-spielgefuehl"]')).toBeNull();
    expect(abschnittIn(seite, 'Punkte')).toContain('Abzeichen an deinem Namen.');
    expect(abschnittIn(seite, 'Punkte')).toContain('ohne deine Einwilligung „Punkte und Meilensteine“ gibt es keine, auch keine Wegmarken');
    expect(seite.querySelector('[data-testid="dse-rangliste-platzhalter"]')).not.toBeNull();
    expect(abschnittIn(seite, 'Punkte')).toContain('deine eigene, freiwillige Einwilligung „Punkte und Meilensteine“');
  });

  it('Schalter an: Absatz „Spielgefühl“ statt Abzeichen am Namen, Rangliste und Einwilligung „Punkte“', () => {
    const seite = seiteMit(true);
    const punkte = abschnittIn(seite, 'Punkte');

    expect(seite.querySelector('#spielgefuehl')).not.toBeNull();
    expect(punkte).toContain('Spielgefühl. Du wählst selbst, ob und wie du mitspielst:');
    expect(punkte).not.toContain('in drei Stufen');
    expect(punkte).toContain('also deinem Anzeigenamen oder einem zufällig vergebenen Ranglistennamen');
    expect(punkte).toContain('Abzeichen zeigen wir nirgends sonst');
    expect(punkte).toContain('Rechtsgrundlage: siehe „Spielgefühl“ oben');
    expect(punkte).not.toContain('Abzeichen an deinem Namen.');
    expect(punkte).toContain('und mit deiner Stufe gilt auch der Schutz gegen Absprachen (unten)');
    expect(punkte).toContain('deine Abzeichen zeigen wir nur in der Rangliste, wenn du mitspielst');
    expect(punkte).toContain(
      'ohne die Stufe ‚Nur für mich‘ oder ‚In der Saison-Rangliste mitspielen‘ beim Spielgefühl gibt es keine, auch keine Wegmarken',
    );
    expect(punkte).not.toContain('ohne deine Einwilligung „Punkte und Meilensteine“ gibt es keine');
    expect(punkte).toContain('Muster-Hinweis');
    expect(seite.querySelector('[data-testid="dse-rangliste-platzhalter"]')).toBeNull();
    expect(punkte).not.toContain('deine eigene, freiwillige Einwilligung „Punkte und Meilensteine“');
    // Die Rechenregeln bleiben
    expect(punkte).toContain('Paar-Prüfwert');
  });

  it('Schalter an: die angebotenen Stufen als Liste, Rangliste nur mit Schalter rangliste', () => {
    const stufen = (an: string[]) =>
      Array.from(seiteMit(an).querySelectorAll('[data-testid="dse-spielgefuehl"] li')).map((li) => normalisiert(li.textContent));

    const mit = stufen(ALLE);
    expect(mit.length).toBe(3);
    expect(mit[0]).toBe('‚Aus‘: Wir berechnen nichts.');
    expect(mit[1]).toContain('‚Nur für mich‘: Wir berechnen Punkte und Meilensteine, die nur du siehst');
    expect(mit[2]).toContain('‚In der Saison-Rangliste mitspielen‘: Zusätzlich stehst du in der Rangliste');

    TestBed.resetTestingModule();
    const ohne = stufen(['spielgefuehl_buehne', 'punkte']);
    expect(ohne.length).toBe(2);
    expect(ohne.join(' ')).not.toContain('In der Saison-Rangliste mitspielen');
  });

  it('mit Rangliste: kein Satz, dass wir die Stufe gerade nicht anbieten', () => {
    const absatz = normalisiert(seiteMit(ALLE).querySelector('[data-testid="dse-spielgefuehl"]')!.textContent);
    expect(absatz).not.toContain('bieten wir gerade nicht an');
  });

  // Jura zum Gamification-Gegencheck (26.11.), Wortlaut nach der Sammelrunde 27.11.
  const SOCKEL =
    'Hast du beim Spielgefühl eine Stufe gewählt, speichern wir deine Wahl, deine Namenswahl, gegebenenfalls deinen ' +
    'Zufallsnamen, die Fassung des Einwilligungstexts und den Zeitpunkt. Ausschalten kannst du das jederzeit in deinen ' +
    'Datenschutz-Einstellungen, auch wenn wir die Funktion gerade nicht anbieten.';

  it('der Sockelsatz steht immer, auch ohne Schalter', () => {
    for (const namen of [[], ['spielgefuehl_buehne'], ALLE]) {
      TestBed.resetTestingModule();
      expect(normalisiert(seiteMit(namen).querySelector('[data-testid="dse-spielgefuehl-sockel"]')!.textContent)).toBe(SOCKEL);
    }
  });

  it('ohne Punkte kein Absatz „Spielgefühl“, auch wenn spielgefuehl_buehne an ist', () => {
    const seite = seiteMit(['spielgefuehl_buehne']);
    expect(seite.querySelector('[data-testid="dse-spielgefuehl"]')).toBeNull();
  });

  it('ohne Rangliste: statt der Stufe Rangliste der Satz, dass wir sie gerade nicht anbieten', () => {
    const absatz = normalisiert(
      seiteMit(['spielgefuehl_buehne', 'punkte']).querySelector('[data-testid="dse-spielgefuehl"]')!.textContent,
    );
    expect(absatz).toContain('Die Stufe ‚In der Saison-Rangliste mitspielen‘ bieten wir gerade nicht an.');
    expect(absatz).not.toContain('zufällig vergebenen Ranglistennamen');
    expect(absatz).toContain('Jede Antwort speichern wir mit Stufe');
  });

  it('Punkte: Bewertungen, Nutzung ohne Anmeldung und die Wegmarke „Erste 10 Bewertungen“', () => {
    const punkte = abschnittIn(seiteMit(false), 'Punkte');
    expect(punkte).toContain(
      'und einen kleinen Punkt je Bewertung eines fremden Beitrags, höchstens drei am Tag; die Richtung der Bewertung zählt nicht',
    );
    expect(punkte).toContain(
      'Kopiert oder nutzt jemand ohne Anmeldung deinen Beitrag, zählen wir das für deine Punkte höchstens dreimal je ' +
        'Beitrag und Tag; wer das war, wissen und speichern wir nicht.',
    );
    expect(punkte).toContain('und „Erste 10 Bewertungen“');
  });
});

/** „Danach wurde schon N-mal gesucht“ (#362, Jura vorläufig 26.11.): Absatz nur mit Schalter. */
describe('DatenschutzComponent: Suchen ohne Treffer, Anzahl auf der Ergebnisseite', () => {
  function seiteMit(an: boolean): HTMLElement {
    TestBed.configureTestingModule({
      imports: [DatenschutzComponent],
      providers: [
        provideRouter([]),
        { provide: FunktionenService, useValue: { an: (name: string) => signal(an && name === 'null_treffer_anzahl') } },
      ],
    });
    const fixture = TestBed.createComponent(DatenschutzComponent);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('nennt mit Schalter an „n-mal gesucht“ ab drei, je Pseudonym und Tag, nicht „Personen“', () => {
    const text = abschnittIn(seiteMit(true), 'Suchen ohne Treffer');

    expect(text).toContain('„Danach wurde in den letzten vier Wochen schon n-mal gesucht.“');
    expect(text).toContain('erst ab drei');
    expect(text).toContain('je Pseudonym und Tag');
    expect(text).toContain('nicht, wie viele verschiedene Menschen gesucht haben');
    expect(text).not.toContain('schon n Personen gesucht');
  });

  it('lässt den Absatz mit Schalter aus weg', () => {
    const text = abschnittIn(seiteMit(false), 'Suchen ohne Treffer');

    expect(text).not.toContain('n-mal gesucht');
    expect(text).toContain('Auf die Listen der Suchen ohne Treffer kommt ein Eintrag erst');
  });
});

/** Halbsatz zum Stimmenverfall bei ganz anderem Text (#636) hinter dem Schalter stimmen_text_verfall. */
describe('DatenschutzComponent - Stimmenverfall bei ganz anderem Text (#636)', () => {
  // Wortlaut Jura vorläufig 26.11.2026
  const HALBSATZ =
    'sagt der Text einer Aussage unter gleichem Titel später etwas ganz anderes, verfallen die Bewertungen dazu und werden gelöscht';
  const schalter = signal(false);

  function bewertungen(): string {
    const fixture = TestBed.createComponent(DatenschutzComponent);
    fixture.detectChanges();
    return abschnittIn(fixture.nativeElement as HTMLElement, 'Bewertungen');
  }

  beforeEach(async () => {
    schalter.set(false);
    await TestBed.configureTestingModule({
      imports: [DatenschutzComponent],
      providers: [
        provideRouter([]),
        {
          provide: FunktionenService,
          useValue: { an: (name: string) => (name === 'stimmen_text_verfall' ? schalter : signal(false)) },
        },
      ],
    }).compileComponents();
  });

  it('Schalter aus: nur der Titel, kein Halbsatz zum Text', () => {
    const text = bewertungen();

    expect(text).not.toContain(HALBSATZ);
    expect(text).toContain(
      'Ändert die Autorin oder der Autor den Titel so, dass er etwas anderes behauptet, löschen wir die Bewertungen dazu.'
    );
  });

  it('Schalter an: Halbsatz steht im Satz zum Titel', () => {
    schalter.set(true);
    const text = bewertungen();

    expect(text).toContain(`dass er etwas anderes behauptet, löschen wir die Bewertungen dazu; ${HALBSATZ}.`);
  });

  it('erscheint ohne Neuladen, sobald der Schalter umspringt', () => {
    const fixture = TestBed.createComponent(DatenschutzComponent);
    fixture.detectChanges();
    const seite = fixture.nativeElement as HTMLElement;
    expect(abschnittIn(seite, 'Bewertungen')).not.toContain(HALBSATZ);

    schalter.set(true);
    fixture.detectChanges();

    expect(abschnittIn(seite, 'Bewertungen')).toContain(HALBSATZ);
  });
});

/**
 * Absätze an Schaltern (vorläufige juristische Einschätzung 26.11.2026, interner Test):
 * Grundsatz „kein Schalter ohne seinen Absatz“. Jeder Absatz steht wortgleich, sobald sein
 * Schalter wirkt, und fehlt sonst; „noch nicht eingeschaltet“ entfällt mit dem Schalter.
 */
describe('DatenschutzComponent: Absätze an Schaltern (Jura vorläufig 26.11.2026)', () => {
  const RANGLISTE =
    'Rangliste. Wenn du Punkten zugestimmt hast, kannst du zusätzlich ausdrücklich einwilligen, in der ' +
    'Rangliste der laufenden Saison zu erscheinen, mit Ranglistenname, Platz und deinen Punkten der Saison. ' +
    'Den Ranglistennamen würfeln wir beim ersten Ja zufällig; deinen Anzeigenamen zeigen wir dort nur, wenn ' +
    'du ihn selbst wählst. Sehen kann die Rangliste nur, wer selbst darin steht, und erst ab zehn ' +
    'Teilnehmenden: die ersten zehn und dein eigener Platz. Jede Antwort auf diese Frage speichern wir mit ' +
    'Zeitpunkt, Kennung des Wortlauts, deiner Namenswahl und deinem Ranglistennamen als Nachweis; Plätze ' +
    'und Punkte speichern wir nicht, wir berechnen sie bei jedem Abruf. Widerrufst du unter „Meine ' +
    'Beiträge“, stehst du ab dem nächsten Abruf nicht mehr darin. Zweck: dir zeigen, wo du in der Saison ' +
    'stehst. Rechtsgrundlage: deine ausdrückliche Einwilligung (Art. 6 Abs. 1 lit. a, Art. 9 Abs. 2 lit. a ' +
    'DSGVO). Dauer: die Antworten bis zur Löschung deines Kontos.';
  const ECHO_DANKE =
    'An deinen Beiträgen zeigen wir dir, wie oft andere sie verwendet und sich dafür bedankt haben. Hast du ' +
    'einen fremden Beitrag kopiert, kannst du mit „Danke“ der Person danken, die ihn geschrieben hat; sie ' +
    'sieht nur die Summe, nie, wer gedankt hat. Dafür speichern wir je Beitrag nur zwei Summen, ohne ' +
    'Kennung und ohne Zeitpunkt. Damit dein Danke je Beitrag und Tag nur einmal zählt, nutzen wir einen ' +
    'eigenen Tages-Prüfwert, gebildet wie beim Kopieren und wie dieser mit dem Tageswechsel gelöscht. Was ' +
    'seit deinem letzten Besuch an Echo dazukam, merken wir uns als weiteren Zählerstand zu deiner Kennung.';
  const GEPOSTET_OHNE_KONTO =
    'Auch ohne Anmeldung kannst du nach dem Kopieren „Ja, gepostet“ tippen. Dann zählen wir für die laufende ' +
    'Kalenderwoche nur eins dazu, ohne Kennung, ohne Prüfwert und ohne etwas in deinem Browser zu ' +
    'speichern; der Knopf ist danach ausgegraut. Gegen Missbrauch begrenzen wir, wie viele solcher Meldungen ' +
    'insgesamt in wenigen Sekunden zählen; eine Adresse verwenden wir dafür nicht. Diese Meldungen weisen wir ' +
    'getrennt von denen Angemeldeter ' +
    'aus. Zweck: sehen, wie oft Gut gesagt beim Widersprechen hilft. Rechtsgrundlage: Art. 6 Abs. 1 lit. f ' +
    'DSGVO. Dauer: Die Wochensumme hat keinen Personenbezug.';
  const ANTWORTEN =
    'Hat jemand auf eine deiner Aussagen geantwortet, zeigen wir dir auf der Startseite, wie viele Antworten ' +
    'anderer in den letzten sieben Tagen dazugekommen sind, und im Reiter „Meine Aussagen“ deine Aussagen ' +
    'mit ihren Antworten. Dafür lesen wir beim Aufruf deine Aussagen, die Antworten daran und den Tag, an ' +
    'dem sie als Antwort verknüpft wurden. Ob eine Antwort von dir ist, zeigen wir dir; wer sie sonst ' +
    'geschrieben hat, nennen wir dort nicht. Auch das speichern wir nicht.';
  const MELDEN =
    'An jedem Beitrag kannst du über „Melden“ auf rechtswidrige oder regelwidrige Inhalte hinweisen; im Fuß ' +
    'jeder Seite findest du dazu „Melden & Kontakt“. Was wir mit einer Meldung speichern, steht in diesem ' +
    'Abschnitt.';
  const GESTOERT =
    'In der Startphase kannst du uns über „Was hat dich gestört?“ kurz schreiben, was dich gestört hat. Wir ' +
    'speichern nur deinen Text und den Tag, ohne deine Kennung und ohne Kontaktmöglichkeit; schreib ' +
    'bitte keine Namen oder Daten anderer hinein. Wir nutzen die Rückmeldungen, um Gut gesagt zu ' +
    'verbessern, und löschen alle spätestens am 31. Dezember 2026. Rechtsgrundlage: Art. 6 Abs. 1 lit. f DSGVO.';
  const NULL_TREFFER =
    'Findest du zu einer Aussage keine Antwort, zeigen wir, wie oft schon danach gesucht wurde, sobald es ' +
    'mindestens dreimal war. Die Zahl führen wir an der Aussage mit; wer gesucht hat, zeigen wir nicht ' +
    '(Einzelheiten im Absatz darunter).';
  const KAMPAGNENWORT =
    'Öffnest du Gut gesagt über einen Link oder QR-Code mit einem Kampagnenwort, etwa von einem Sticker, ' +
    'begrüßen wir dich passend dazu; das geschieht nur in deinem Browser.';
  const BESTANDSZAHL =
    'Wie viele Antworten es gibt und wie viele in den letzten sieben Tagen dazukamen, berechnen wir beim ' +
    'Aufruf aus den öffentlichen Beiträgen; dafür speichern wir nichts.';

  function seiteMit(...namen: string[]): HTMLElement {
    TestBed.configureTestingModule({
      imports: [DatenschutzComponent],
      providers: [
        provideRouter([]),
        { provide: FunktionenService, useValue: { an: (name: string) => signal(namen.includes(name)) } },
      ],
    });
    const fixture = TestBed.createComponent(DatenschutzComponent);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('alle Schalter aus: keiner der neuen Absätze, die Vorbehalte stehen', () => {
    const seite = seiteMit();
    const ganz = normalisiert(seite.textContent);

    for (const text of [
      RANGLISTE,
      ECHO_DANKE,
      GEPOSTET_OHNE_KONTO,
      ANTWORTEN,
      MELDEN,
      GESTOERT,
      NULL_TREFFER,
      KAMPAGNENWORT,
      BESTANDSZAHL,
    ]) {
      expect(ganz).not.toContain(text.slice(0, 60));
    }
    expect(ganz).toContain('Punkte sind noch nicht eingeschaltet.');
    expect(ganz).toContain('Die Team-Summe ist noch nicht eingeschaltet.');
    expect(ganz).toContain('Eine Rangliste je Saison ist noch nicht eingeschaltet');
    expect(ganz).toContain('Einzige Ausnahme, sobald Punkte eingeschaltet sind:');
    expect(ganz).toContain('Auch Abzeichen sind noch nicht eingeschaltet');
    expect(ganz).toContain('nur zwei Zahlen');
    expect(seite.querySelectorAll('#rangliste').length).toBe(1);
  });

  it('punkte: der Vorbehalt entfällt, die Muster-Hinweise gelten ohne „sobald“', () => {
    const ganz = normalisiert(seiteMit('punkte').textContent);

    expect(ganz).not.toContain('Punkte sind noch nicht eingeschaltet');
    expect(ganz).toContain('Einzige Ausnahme: Nutzen sich zwei Konten gegenseitig');
    expect(ganz).not.toContain('sobald Punkte eingeschaltet sind');
    // Abzeichen haben einen eigenen Schalter und bleiben aus
    expect(ganz).toContain('Abzeichen an deinem Namen. Abzeichen sind noch nicht eingeschaltet');
  });

  it('team_fortschritt: „Die Team-Summe ist noch nicht eingeschaltet“ entfällt, die Anzeige am Namen bleibt aus', () => {
    const text = abschnittIn(seiteMit('team_fortschritt'), 'Teams');

    expect(text).not.toContain('Die Team-Summe ist noch nicht eingeschaltet');
    expect(text).toContain('erst wenn mindestens fünf Mitglieder eingewilligt haben, gerundet und nie mit einzelnen Namen.');
    expect(text).toContain('Diese Anzeige am Namen ist noch nicht eingeschaltet.');
  });

  it('team_quests: der Absatz unter „Teams“', () => {
    expect(abschnittIn(seiteMit('team_fortschritt', 'team_quests'), 'Teams')).toContain(
      'In Teams gibt es gemeinsame Wochenaufgaben (Quests). Am Team speichern wir je Woche nur Thema und Ziel der ' +
        'Quest, ohne Namen. Ob das Team sie schafft, berechnen wir bei jedem Abruf aus der Mitwirkung der Mitglieder; ' +
        'die Mitglieder sehen nur die Summe des Teams, und erst ab fünf Mitgliedern. Hast du Punkte eingeschaltet, ' +
        'bringen dir erfüllte Quests auch Punkte.',
    );
  });

  it('ohne team_quests: kein Absatz zu Quests', () => {
    expect(abschnittIn(seiteMit('team_fortschritt'), 'Teams')).not.toContain('Quests');
  });

  it('rangliste: im Abschnitt „Punkte“ sehen Mitspielende den Punktestand', () => {
    expect(abschnittIn(seiteMit('punkte', 'rangliste'), 'Punkte')).toContain(
      'Deinen Punktestand siehst nur du, außer du spielst in der Rangliste mit; dann sehen ihn auch die anderen ' +
        'Mitspielenden (siehe unten). Wir speichern ihn nicht,',
    );
  });

  it('ohne rangliste: im Abschnitt „Punkte“ der alte Satz', () => {
    expect(abschnittIn(seiteMit('punkte'), 'Punkte')).toContain('Deinen Punktestand siehst nur du. Wir speichern ihn nicht,');
  });

  it('rangliste: der Absatz von Jura statt des Hinweises, unter „Punkte“', () => {
    const seite = seiteMit('punkte', 'rangliste');

    expect(abschnittIn(seite, 'Punkte')).toContain(RANGLISTE);
    expect(abschnittIn(seite, 'Punkte')).not.toContain('Eine Rangliste je Saison ist noch nicht eingeschaltet');
    expect(seite.querySelectorAll('#rangliste').length).toBe(1);
  });

  it('wirkungs_echo und danke_knopf: der ganze Absatz und „nur drei Zahlen“ mit der dritten', () => {
    const text = abschnittIn(seiteMit('wirkungs_echo', 'danke_knopf'), 'Rückmeldung zur Nutzung deiner Beiträge');

    expect(text).toContain(ECHO_DANKE);
    expect(text).toContain(
      'speichern wir zu deiner Kennung nur drei Zahlen: wie oft deine Beiträge insgesamt genutzt waren, wie viele ' +
        'Einwürfe anderer es im Fangkorb gab, als du zuletzt da warst, und wie viel Echo deine Beiträge beim letzten ' +
        'Besuch hatten. Mit der zweiten',
    );
    expect(text).not.toContain('nur zwei Zahlen');
  });

  it('nur danke_knopf: die Sätze zum Danke, kein Zählerstand des Echos, zwei Zahlen', () => {
    const text = abschnittIn(seiteMit('danke_knopf'), 'Rückmeldung zur Nutzung deiner Beiträge');

    expect(text).toContain('kannst du mit „Danke“ der Person danken');
    expect(text).toContain('einen eigenen Tages-Prüfwert, gebildet wie beim Kopieren');
    expect(text).not.toContain('an Echo dazukam');
    expect(text).toContain(
      'nur zwei Zahlen: wie oft deine Beiträge insgesamt genutzt waren und wie viele Einwürfe anderer es im ' +
        'Fangkorb gab, als du zuletzt da warst.',
    );
  });

  it('nur wirkungs_echo: Zählerstand des Echos, keine Sätze zum Danke-Knopf', () => {
    const text = abschnittIn(seiteMit('wirkungs_echo'), 'Rückmeldung zur Nutzung deiner Beiträge');

    expect(text).toContain('merken wir uns als weiteren Zählerstand zu deiner Kennung.');
    expect(text).not.toContain('kannst du mit „Danke“');
    expect(text).not.toContain('Tages-Prüfwert');
  });

  it('danke_ohne_konto allein bringt keinen Satz (Variante B nicht erfüllt, bleibt aus)', () => {
    const ganz = normalisiert(seiteMit('danke_ohne_konto').textContent);

    expect(ganz).not.toContain('Ohne Anmeldung zählt dein Danke');
    expect(ganz).not.toContain('kannst du mit „Danke“');
  });

  it('wirkungs_echo: „Ja, gepostet“ nennt die Summe je Beitrag statt „welchen Beitrag … speichern wir nicht“ allein', () => {
    const an = abschnittIn(seiteMit('wirkungs_echo'), 'Rückmeldung „Ja, gepostet“');

    expect(an).toContain(
      'Personen dieser Woche. Welchen Beitrag du gepostet hast, speichern wir nicht; an jedem Beitrag zählen wir ' +
        'nur mit, wie oft er insgesamt als gepostet gemeldet wurde, ohne Kennung (siehe ‚Rückmeldung zur Nutzung deiner Beiträge‘). ' +
        'Einen Link',
    );
    expect(an).not.toContain('Deine Kennung und welchen Beitrag');
  });

  it('ohne wirkungs_echo: „Ja, gepostet“ behält den alten Satz', () => {
    expect(abschnittIn(seiteMit(), 'Rückmeldung „Ja, gepostet“')).toContain(
      'Deine Kennung und welchen Beitrag du gepostet hast, speichern wir nicht. Einen Link',
    );
  });

  it('rangliste: der Punktestand ist für Mitspielende der Rangliste sichtbar (Keine automatisierte Entscheidungsfindung)', () => {
    const text = abschnittIn(seiteMit('punkte', 'rangliste'), 'Keine automatisierte Entscheidungsfindung');

    expect(text).toContain(
      'Deinen Punktestand zeigen wir nur dir, außer du spielst in der Saison-Rangliste mit; dann sehen ihn auch die ' +
        'anderen Mitspielenden. Eine Entscheidung, die allein automatisiert getroffen wird',
    );
  });

  it('gepostet_ohne_konto: der Absatz unter „Rückmeldung „Ja, gepostet““', () => {
    expect(abschnittIn(seiteMit('gepostet_ohne_konto'), 'Rückmeldung „Ja, gepostet“')).toContain(GEPOSTET_OHNE_KONTO);
  });

  it('antworten_hinweis: der Satz vom 25.11. unter „Rückmeldung zur Nutzung“', () => {
    expect(abschnittIn(seiteMit('antworten_hinweis'), 'Rückmeldung zur Nutzung deiner Beiträge')).toContain(ANTWORTEN);
  });

  it('meldeweg_sichtbar: der Satz im Abschnitt „Meldungen von Beiträgen“', () => {
    expect(abschnittIn(seiteMit('meldeweg_sichtbar'), 'Meldungen von Beiträgen')).toContain(MELDEN);
  });

  it('feedback_gestoert: der Absatz unter „Feedback“', () => {
    expect(abschnittIn(seiteMit('feedback_gestoert'), 'Feedback')).toContain(GESTOERT);
  });

  it('null_treffer_anzahl: der kurze Absatz unter „Suchen ohne Treffer“', () => {
    expect(abschnittIn(seiteMit('null_treffer_anzahl'), 'Suchen ohne Treffer')).toContain(NULL_TREFFER);
  });

  it('k_begruessung: nur der Begrüßungssatz unter „Messung der Nutzung“', () => {
    expect(abschnittIn(seiteMit('k_begruessung'), 'Messung der Nutzung')).toContain(KAMPAGNENWORT);
  });

  it('bestandszahl_zuwachs: eigener Unterabschnitt „Startseite“', () => {
    expect(abschnittIn(seiteMit('bestandszahl_zuwachs'), 'Startseite')).toBe(BESTANDSZAHL);
  });
});

/** Anker hinter einem Schalter (Gamification-Check 26.11., Befund 19): Sprung, sobald die Schalter da sind. */
describe('DatenschutzComponent: Anker hinter einem Schalter', () => {
  it('springt zu #spielgefuehl, wenn der Absatz erst nach GET /api/v1/funktionen erscheint', async () => {
    const spielgefuehl = signal(false);
    const antwort = new Subject<boolean | null>();
    TestBed.configureTestingModule({
      imports: [DatenschutzComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { fragment: 'spielgefuehl' } } },
        {
          provide: FunktionenService,
          useValue: {
            // Den Absatz gibt es nur mit Punkten (#855): Punkte an, Bühne kommt erst mit der Antwort.
            an: (name: string) =>
              name === 'spielgefuehl_buehne' ? spielgefuehl : signal(name === 'punkte'),
            stand$: () => antwort.asObservable(),
          },
        },
      ],
    });
    const springen = spyOn(Element.prototype, 'scrollIntoView');
    const fixture = TestBed.createComponent(DatenschutzComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    expect(springen).not.toHaveBeenCalled();

    spielgefuehl.set(true);
    antwort.next(true);
    fixture.detectChanges();
    await fixture.whenStable();

    expect(springen).toHaveBeenCalledTimes(1);
    expect(springen.calls.mostRecent().object).toBe(fixture.nativeElement.querySelector('#spielgefuehl'));
  });

  it('wirft nichts, wenn die Seite vor der Antwort verlassen wird (Review, NG0911)', async () => {
    const antwort = new Subject<boolean | null>();
    TestBed.configureTestingModule({
      imports: [DatenschutzComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { fragment: 'spielgefuehl' } } },
        { provide: FunktionenService, useValue: { an: () => signal(false), stand$: () => antwort.asObservable() } },
      ],
    });
    const fixture = TestBed.createComponent(DatenschutzComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.destroy();

    expect(() => antwort.next(true)).not.toThrow();
    expect(antwort.observed).toBeFalse();
  });

  it('fragt nichts nach, wenn der Anker schon beim ersten Zeichnen steht', async () => {
    const stand$ = jasmine.createSpy('stand$').and.returnValue(new Subject<boolean | null>());
    TestBed.configureTestingModule({
      imports: [DatenschutzComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { fragment: 'spielgefuehl' } } },
        { provide: FunktionenService, useValue: { an: (name: string) => signal(name === 'spielgefuehl_buehne' || name === 'punkte'), stand$ } },
      ],
    });
    const fixture = TestBed.createComponent(DatenschutzComponent);
    fixture.detectChanges();
    await fixture.whenStable();

    expect(stand$).not.toHaveBeenCalled();
  });
});
