import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';

import { abschnitt } from '../testing/rechtstext';
import { DatenschutzComponent } from '../datenschutz/datenschutz.component';
import { FunktionenService } from '../services/funktionen.service';
import { WEGGEKLICKT_SCHLUESSEL, WEGGEKLICKT_TAGE } from './naechster-schritt';

/**
 * Die Sätze der Datenschutzerklärung zur Karte „Dein nächster Schritt“ (#789): unter
 * „Rückmeldung zur Nutzung“ der Halbsatz aus dem Issue, unter „Speicherung auf deinem
 * Gerät“ Schlüssel, Inhalt und Dauer. Der erste Satz steht nur mit Schalter, der zweite
 * immer: Ein Eintrag kann nach dem Ausschalten noch bis zu sieben Tage liegen.
 */
describe('Datenschutzerklärung zu „Dein nächster Schritt“ (#789)', () => {
  function seite(an: boolean): HTMLElement {
    TestBed.configureTestingModule({
      imports: [DatenschutzComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting(), { provide: FunktionenService, useValue: { an: () => signal(an) } }],
    });
    const fixture = TestBed.createComponent(DatenschutzComponent);
    fixture.detectChanges();
    return fixture.nativeElement;
  }

  afterEach(() => TestBed.resetTestingModule());

  it('nennt unter „Rückmeldung zur Nutzung“, dass nichts zusätzlich gespeichert wird', () => {
    const text = abschnitt(seite(true), 'Rückmeldung zur Nutzung deiner Beiträge');
    expect(text).toContain(
      'und schlagen dir aus deinen eigenen Beiträgen einen nächsten Schritt vor; wir speichern dafür nichts zusätzlich',
    );
  });

  it('nennt unter „Speicherung auf deinem Gerät“ Schlüssel, Inhalt und Dauer', () => {
    const text = abschnitt(seite(true), 'Weitere Einträge');
    expect(text).toContain(`„${WEGGEKLICKT_SCHLUESSEL}“`);
    expect(text).toContain('welche Art von Vorschlag du weggeklickt hast und an welchem Tag');
    expect(text).toContain('keine Kennung und keinen Prüfwert');
    expect(WEGGEKLICKT_TAGE).toBe(7);
    expect(text).toContain('sieben Tage');
  });

  it('nennt den Satz zur Rückmeldung nur mit Schalter, den Eintrag auf dem Gerät immer', () => {
    const s = seite(false);
    expect(abschnitt(s, 'Rückmeldung zur Nutzung deiner Beiträge')).not.toContain('nächsten Schritt');
    // Ein Eintrag aus der Zeit, als der Schalter an war, kann noch bis zu sieben Tage liegen
    expect(abschnitt(s, 'Weitere Einträge')).toContain(WEGGEKLICKT_SCHLUESSEL);
    expect(abschnitt(s, 'Weitere Einträge')).toContain('beim Abmelden');
  });
});
