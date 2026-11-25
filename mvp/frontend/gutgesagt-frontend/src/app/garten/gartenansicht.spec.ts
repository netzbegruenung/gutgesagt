import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { BehaviorSubject } from 'rxjs';

import { environment } from '../../environments/environment';
import { AuthService, UserInfo } from '../auth/auth.service';
import { FunktionenService } from '../services/funktionen.service';
import { SUCHTEXT_PARAM } from '../shared/formular-adresse';
import { GartenansichtComponent } from './gartenansicht.component';
import { GartenHinweisComponent } from './garten-hinweis.component';
import { Beet, antwortenText, ohneAntwortText } from './garten.service';

const URL = `${environment.baseUrl}/api/v1/search/garten`;

const BEETE: Beet[] = [
  { schluessel: 'klima', name: 'Klima', motiv: 'themen/klima.svg', antworten: 12, ohne_antwort: 3 },
  { schluessel: 'verkehr', name: 'Verkehr', motiv: 'themen/verkehr.svg', antworten: 1, ohne_antwort: 0 },
  { schluessel: 'europa', name: 'Europa', motiv: null, antworten: 0, ohne_antwort: 1 },
];

describe('Gartenansicht (#783)', () => {
  it('nennt Zahlen ehrlich in Einzahl und Mehrzahl', () => {
    expect([antwortenText(0), antwortenText(1), antwortenText(12)]).toEqual(['noch keine Antwort', '1 Antwort', '12 Antworten']);
    expect([ohneAntwortText(0), ohneAntwortText(1), ohneAntwortText(3)]).toEqual(['', '1 Spruch ohne Antwort', '3 Sprüche ohne Antwort']);
    // Ueber der Grenze der Liste „Hier fehlt eine Antwort“ wie dort „50+“
    expect([ohneAntwortText(50), ohneAntwortText(51)]).toEqual(['50 Sprüche ohne Antwort', '50+ Sprüche ohne Antwort']);
  });

  describe('Seite', () => {
    let http: HttpTestingController;

    function starten(angemeldet: boolean) {
      const nutzer = new BehaviorSubject<UserInfo | null>({ isAuthenticated: angemeldet, userId: null, userName: null, claims: null });
      TestBed.configureTestingModule({
        imports: [GartenansichtComponent],
        providers: [
          provideHttpClient(),
          provideHttpClientTesting(),
          provideRouter([]),
          { provide: AuthService, useValue: { userInfo$: nutzer } },
        ],
      });
      http = TestBed.inject(HttpTestingController);
      const fixture = TestBed.createComponent(GartenansichtComponent);
      fixture.detectChanges();
      return fixture;
    }

    afterEach(() => {
      http.verify();
      TestBed.resetTestingModule();
    });

    function beete(fixture: { nativeElement: HTMLElement }): HTMLElement[] {
      return Array.from(fixture.nativeElement.querySelectorAll('.beet'));
    }

    it('zeigt je Thema Motiv mit Namen und die Zahlen, Besuchern ohne Link auf die Liste', () => {
      const fixture = starten(false);
      expect(fixture.nativeElement.querySelector('mat-spinner')).not.toBeNull();
      http.expectOne(URL).flush({ beete: BEETE });
      fixture.detectChanges();

      const [klima, verkehr, europa] = beete(fixture);
      expect(klima.querySelector('.beet-name')!.textContent).toBe('Klima');
      const motiv = klima.querySelector('img.beet-motiv') as HTMLImageElement;
      expect(motiv.getAttribute('src')).toBe('themen/klima.svg');
      expect(motiv.getAttribute('alt')).toBe('');
      expect(klima.textContent).toContain('12 Antworten');
      expect(klima.textContent).toContain('3 Sprüche ohne Antwort');
      expect(verkehr.textContent).toContain('1 Antwort');
      expect(verkehr.querySelector('.beet-ohne')).toBeNull();
      expect(europa.querySelector('img')).toBeNull();
      expect(europa.textContent).toContain('Europa');
      expect(fixture.nativeElement.querySelector('.beet-antworten')).toBeNull();
      expect(fixture.nativeElement.querySelector('.garten-konto')).not.toBeNull();
    });

    it('führt mit dem Namen des Themas zur Suche, also zu „Alles zum Thema“', () => {
      const fixture = starten(false);
      http.expectOne(URL).flush({ beete: BEETE });
      fixture.detectChanges();
      const link = beete(fixture)[0].querySelector('a.beet-link') as HTMLAnchorElement;
      const adresse = new window.URL(link.href);
      expect(adresse.pathname).toBe('/result');
      expect(adresse.searchParams.get(SUCHTEXT_PARAM)).toBe('Klima');
    });

    it('gibt Angemeldeten bei Sprüchen ohne Antwort den Weg zur gefilterten Liste', () => {
      const fixture = starten(true);
      http.expectOne(URL).flush({ beete: BEETE });
      fixture.detectChanges();

      const links = Array.from(fixture.nativeElement.querySelectorAll('a.beet-antworten')) as HTMLAnchorElement[];
      expect(links.length).toBe(2);
      const adresse = new window.URL(links[0].href);
      expect(adresse.pathname).toBe('/hier-fehlt-eine-antwort');
      expect(adresse.searchParams.get('thema')).toBe('klima');
      // Der Name beginnt mit dem sichtbaren Text (WCAG 2.5.3)
      expect(links[0].textContent!.replace(/\s+/g, ' ').trim()).toBe('Jetzt antworten im Thema Klima');
      expect(fixture.nativeElement.querySelector('.garten-konto')).toBeNull();
    });

    it('sagt bei 404, dass die Übersicht aus ist, und fragt nicht weiter', () => {
      const fixture = starten(false);
      http.expectOne(URL).flush('weg', { status: 404, statusText: 'Not Found' });
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Diese Übersicht ist gerade nicht eingeschaltet.');
      expect(beete(fixture).length).toBe(0);
    });

    it('verspricht nach 403 keinen neuen Versuch und zeigt keinen Spinner', () => {
      const fixture = starten(false);
      http.expectOne(URL).flush('nein', { status: 403, statusText: 'Forbidden' });
      fixture.detectChanges();
      expect(fixture.nativeElement.textContent).toContain('Diese Übersicht ist gerade nicht erreichbar.');
      expect(fixture.nativeElement.textContent).not.toContain('Wir versuchen es gleich noch einmal.');
      expect(fixture.nativeElement.querySelector('mat-spinner')).toBeNull();
    });

    it('meldet einen Ladefehler ohne „neu laden“', () => {
      const fixture = starten(false);
      http.expectOne(URL).flush('weg', { status: 500, statusText: 'Fehler' });
      fixture.detectChanges();
      const status = fixture.nativeElement.querySelector('.garten-fehler') as HTMLElement;
      expect(status.getAttribute('role')).toBe('status');
      expect(status.textContent).toContain('Wir versuchen es gleich noch einmal.');
      expect(status.textContent).not.toMatch(/neu laden/i);
    });
  });

  describe('Hinweis auf der Startseite', () => {
    function hinweis(schalter: boolean) {
      TestBed.configureTestingModule({
        imports: [GartenHinweisComponent],
        providers: [provideRouter([]), { provide: FunktionenService, useValue: { an: () => signal(schalter) } }],
      });
      const fixture = TestBed.createComponent(GartenHinweisComponent);
      fixture.detectChanges();
      return fixture.nativeElement as HTMLElement;
    }

    afterEach(() => TestBed.resetTestingModule());

    it('fehlt ohne Schalter', () => {
      expect(hinweis(false).querySelector('a')).toBeNull();
    });

    it('führt mit Schalter zur Gartenansicht', () => {
      const link = hinweis(true).querySelector('a') as HTMLAnchorElement;
      expect(new window.URL(link.href).pathname).toBe('/garten');
      expect(link.textContent).toContain('Themen im Überblick');
    });
  });
});
