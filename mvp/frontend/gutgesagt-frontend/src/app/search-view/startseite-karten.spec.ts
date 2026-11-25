import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { BehaviorSubject } from 'rxjs';

import { AuthService, UserInfo } from '../auth/auth.service';
import { FunktionenService } from '../services/funktionen.service';
import { BesuchResponse, UsageTrackingService } from '../services/usage-tracking.service';
import { SeitLetztemBesuchComponent } from '../seit-letztem-besuch/seit-letztem-besuch.component';
import { NAECHSTER_SCHRITT_URL, NaechsterSchrittComponent } from '../naechster-schritt/naechster-schritt.component';
import { WEGGEKLICKT_SCHLUESSEL } from '../naechster-schritt/naechster-schritt';

/** Beide Karten in der Reihenfolge der Startseite (search-view.component.html). */
@Component({
  standalone: true,
  imports: [SeitLetztemBesuchComponent, NaechsterSchrittComponent],
  template: `
    @if (start()) {
      <app-seit-letztem-besuch></app-seit-letztem-besuch>
      <app-naechster-schritt></app-naechster-schritt>
    }
  `,
})
class StartseiteHost {
  readonly start = signal(true);
}

/**
 * Block und Karte zusammen mit dem echten SeitLetztemBesuchService (Review Spielgefühl
 * 25.11.): nie beide zugleich, Rückkehr ohne Springen. TestBed prüft dabei nach jeder
 * Change Detection nach, dass sich nichts nachträglich geändert hat (NG0100).
 */
describe('Startseite: „Seit deinem letzten Besuch“ und „Dein nächster Schritt“', () => {
  let http: HttpTestingController;
  let besuch: BehaviorSubject<BesuchResponse | null>;

  beforeEach(() => {
    localStorage.removeItem(WEGGEKLICKT_SCHLUESSEL);
    besuch = new BehaviorSubject<BesuchResponse | null>(null);
    TestBed.configureTestingModule({
      imports: [StartseiteHost],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: AuthService,
          useValue: { userInfo$: new BehaviorSubject<UserInfo | null>({ isAuthenticated: true, userId: 'kim', userName: null, claims: null }) },
        },
        { provide: FunktionenService, useValue: { an: () => signal(true) } },
        { provide: UsageTrackingService, useValue: { besuchStand$: besuch } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    localStorage.removeItem(WEGGEKLICKT_SCHLUESSEL);
  });

  const block = (el: HTMLElement) => el.querySelector('nav.seit-besuch');
  const karte = (el: HTMLElement) => el.querySelector('.naechster-schritt');

  it('zeigt nie beide zugleich und vor beiden Antworten keinen', () => {
    const fixture = TestBed.createComponent(StartseiteHost);
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;
    expect(block(el)).toBeNull();
    expect(karte(el)).toBeNull();

    besuch.next({ nutzung_seit_letztem_besuch: 0, neue_einwuerfe: 3, unbeantwortete_aussagen: 2 });
    fixture.detectChanges();
    // Die Vorschläge fehlen noch: Der Block wartet, statt gleich wieder zu verschwinden
    expect(block(el)).toBeNull();

    http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [{ art: 'einwerfen' }] });
    fixture.detectChanges();
    expect(karte(el)).not.toBeNull();
    expect(block(el)).toBeNull();
  });

  it('nach dem Ausblenden des Vorschlags steht der Block da, ohne Neuladen', () => {
    const fixture = TestBed.createComponent(StartseiteHost);
    besuch.next({ nutzung_seit_letztem_besuch: 0, neue_einwuerfe: 3 });
    fixture.detectChanges();
    http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [{ art: 'einwerfen' }] });
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;

    (el.querySelector('.naechster-schritt-weg') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(karte(el)).toBeNull();
    expect(block(el)).not.toBeNull();
  });

  it('eigenes Neues geht vor; nach dessen Klick kommt der Vorschlag', () => {
    const fixture = TestBed.createComponent(StartseiteHost);
    besuch.next({ nutzung_seit_letztem_besuch: 2 });
    fixture.detectChanges();
    http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [{ art: 'einwerfen' }] });
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;
    expect(block(el)).not.toBeNull();
    expect(karte(el)).toBeNull();

    // Allein ist es eine breite Zeile mit Knopf
    (el.querySelector('nav.seit-besuch a') as HTMLAnchorElement).click();
    fixture.detectChanges();
    expect(block(el)).toBeNull();
    expect(karte(el)).not.toBeNull();
  });

  it('bei der Rückkehr steht sofort dieselbe Karte da, ohne dass der Block dazwischen aufblitzt', () => {
    const fixture = TestBed.createComponent(StartseiteHost);
    besuch.next({ nutzung_seit_letztem_besuch: 0, neue_einwuerfe: 3 });
    fixture.detectChanges();
    http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [{ art: 'einwerfen' }] });
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;

    fixture.componentInstance.start.set(false);
    fixture.detectChanges();
    fixture.componentInstance.start.set(true);
    fixture.detectChanges();
    expect(karte(el)).not.toBeNull();
    expect(block(el)).toBeNull();

    http.expectOne(NAECHSTER_SCHRITT_URL).flush({ vorschlaege: [{ art: 'einwerfen' }] });
    fixture.detectChanges();
    expect(karte(el)).not.toBeNull();
    expect(block(el)).toBeNull();
  });
});
