import { ComponentFixture, TestBed } from '@angular/core/testing';
import { WritableSignal, signal } from '@angular/core';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { Clipboard } from '@angular/cdk/clipboard';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { KartenAktionenComponent } from './karten-aktionen.component';
import { KOPIERT_ERFOLG, nutzungSatz, tonlagenHinweis } from './kopiert-erfolg';
import { AuthService } from '../../auth/auth.service';
import { LoggingService } from '../../services/logging.service';
import { UsageTrackingService } from '../../services/usage-tracking.service';
import { VotingService } from '../../services/voting.service';
import { FunktionenService } from '../../services/funktionen.service';
import { KOPIERT } from '../../shared/vorlagen-luecke';
import { TEILEN_NAVIGATOR } from '../../shared/teilen.service';
import { MeilensteinHinweisService } from '../../meine-beitraege/meilenstein-hinweis.service';
import { KOPIERT_GEPOSTET_FRAGE } from './gepostet-texte';

describe('Erfolgstext nach dem Kopieren - Texte (#785)', () => {
  it('nennt die Nutzung als Kopiervorgaenge, nie als Menschen', () => {
    expect(nutzungSatz(14)).toBe('Schon 14-mal genutzt.');
    expect(nutzungSatz(1)).toBe('Schon 1-mal genutzt.');
    expect(nutzungSatz(1234)).toBe('Schon 1.234-mal genutzt.');
    expect(nutzungSatz(14)).not.toContain('Menschen');
  });

  it('ohne Zahl bei 0 oder unbekannter Nutzung', () => {
    expect(nutzungSatz(0)).toBeNull();
    expect(nutzungSatz(null)).toBeNull();
    expect(nutzungSatz(undefined)).toBeNull();
  });

  it('den Tonlagen-Hinweis je Stil mit dem Wort der Oberflaeche', () => {
    expect(tonlagenHinweis({ id: 'a', stil: 'humorvoll' })).toEqual({
      frage: 'Lieber mit einem Augenzwinkern?',
      link: 'Es gibt noch eine humorvolle.',
    });
    expect(tonlagenHinweis({ id: 'a', stil: 'brueckenbauend' })?.link).toBe('Es gibt noch eine freundliche.');
    expect(tonlagenHinweis({ id: 'a', stil: 'persoenlich' })?.link).toBe('Es gibt noch eine persönliche.');
    expect(tonlagenHinweis({ id: 'a', stil: 'sachlich' })?.link).toBe('Es gibt noch eine sachliche.');
    expect(tonlagenHinweis({ id: 'a', stil: 'bissig' })?.link).toBe('Es gibt noch eine deutliche.');
  });

  it('ohne andere Tonlage keinen Hinweis', () => {
    expect(tonlagenHinweis(null)).toBeNull();
    expect(tonlagenHinweis(undefined)).toBeNull();
  });
});

describe('Erfolgstext nach dem Kopieren - Karte (#785)', () => {
  const INHALT_ID = '123e4567-e89b-12d3-a456-426614174000';
  const ANDERE_ID = '223e4567-e89b-12d3-a456-426614174000';
  let fixture: ComponentFixture<KartenAktionenComponent>;
  let component: KartenAktionenComponent;
  let schalter: WritableSignal<boolean>;
  let snackBar: jasmine.SpyObj<MatSnackBar>;
  let usage: jasmine.SpyObj<UsageTrackingService>;
  let auth: jasmine.SpyObj<AuthService>;

  beforeEach(async () => {
    schalter = signal(true);
    snackBar = jasmine.createSpyObj('MatSnackBar', ['open']);
    usage = jasmine.createSpyObj('UsageTrackingService', [
      'trackContentUsage',
      'gepostetAngeboten',
      'gepostetBekannt',
      'gepostetMelden',
    ]);
    usage.gepostetAngeboten.and.returnValue(of(false));
    usage.gepostetBekannt.and.returnValue(null);
    auth = jasmine.createSpyObj('AuthService', ['getUserInfo', 'login']);
    auth.getUserInfo.and.returnValue({ isAuthenticated: false } as any);
    await TestBed.configureTestingModule({
      imports: [KartenAktionenComponent, NoopAnimationsModule],
      providers: [
        provideRouter([]),
        { provide: VotingService, useValue: jasmine.createSpyObj('VotingService', ['setLike']) },
        { provide: LoggingService, useValue: jasmine.createSpyObj('LoggingService', ['logInteraction', 'logError', 'error']) },
        { provide: MatSnackBar, useValue: snackBar },
        { provide: Clipboard, useValue: jasmine.createSpyObj('Clipboard', ['copy']) },
        { provide: UsageTrackingService, useValue: usage },
        { provide: AuthService, useValue: auth },
        { provide: MatDialog, useValue: jasmine.createSpyObj('MatDialog', ['open']) },
        { provide: TEILEN_NAVIGATOR, useValue: {} },
        { provide: MeilensteinHinweisService, useValue: jasmine.createSpyObj('MeilensteinHinweisService', ['bestaetigen']) },
        {
          provide: FunktionenService,
          useValue: { an: (name: string) => (name === 'kopiert_erfolg' ? schalter : signal(false)) },
        },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(KartenAktionenComponent);
    component = fixture.componentInstance;
    component.inhaltId = INHALT_ID;
    component.kopierText = 'Windkraft schafft Arbeitsplätze.';
    component.nutzung = 14;
    fixture.detectChanges();
  });

  function kopieren(): void {
    (fixture.nativeElement.querySelector('.kopieren-knopf') as HTMLButtonElement).click();
    fixture.detectChanges();
  }

  function erfolg(): HTMLElement | null {
    return fixture.nativeElement.querySelector('.kopiert-erfolg');
  }

  it('zeigt nach dem Kopieren ohne Konto Erfolgssatz und Nutzung statt der Snackbar', () => {
    kopieren();

    const text = erfolg()!.textContent!.replace(/\s+/g, ' ');
    expect(text).toContain(KOPIERT_ERFOLG);
    expect(text).toContain('Schon 14-mal genutzt.');
    expect(snackBar.open).not.toHaveBeenCalled();
    expect(usage.trackContentUsage).toHaveBeenCalledTimes(1);
  });

  it('steht in einer Status-Region, das Pflaenzchen wird nicht vorgelesen', () => {
    kopieren();

    expect(fixture.nativeElement.querySelector('[role="status"] .kopiert-erfolg')).not.toBeNull();
    const zeichen = erfolg()!.querySelector('.erfolg-satz [aria-hidden="true"]')!;
    expect(zeichen.textContent).toBe('🌱');
  });

  it('bei 0 Nutzungen nur der Erfolgssatz', () => {
    component.nutzung = 0;
    kopieren();

    expect(erfolg()!.textContent).toContain(KOPIERT_ERFOLG);
    expect(erfolg()!.textContent).not.toContain('genutzt');
  });

  it('ohne andere Tonlage kein Hinweis und kein Link', () => {
    kopieren();

    expect(erfolg()!.querySelector('.erfolg-tonlage')).toBeNull();
    expect(erfolg()!.querySelector('a')).toBeNull();
  });

  it('mit anderer Tonlage ein Link auf diese Antwort', () => {
    component.andereTonlage = { id: ANDERE_ID, stil: 'humorvoll' };
    kopieren();

    const hinweis = erfolg()!.querySelector('.erfolg-tonlage')!;
    expect(hinweis.textContent!.replace(/\s+/g, ' ').trim()).toBe(
      'Lieber mit einem Augenzwinkern? Es gibt noch eine humorvolle.',
    );
    expect(hinweis.querySelector('a')!.getAttribute('href')).toBe(`/beitrag/${ANDERE_ID}`);
  });

  it('laesst sich schliessen', () => {
    kopieren();
    (erfolg()!.querySelector('.erfolg-schliessen') as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(erfolg()).toBeNull();
  });

  it('angemeldet mit Frage „Gepostet?“ kommt die Frage weiter als Snackbar dazu', () => {
    auth.getUserInfo.and.returnValue({ isAuthenticated: true, userId: 'person' } as any);
    usage.gepostetBekannt.and.returnValue(true);
    snackBar.open.and.returnValue({ onAction: () => of() } as any);
    kopieren();

    expect(erfolg()).not.toBeNull();
    expect(snackBar.open).toHaveBeenCalledOnceWith(KOPIERT_GEPOSTET_FRAGE, jasmine.any(String), jasmine.any(Object));
  });

  it('bei ausgeschaltetem Schalter wie bisher die Snackbar und kein Erfolgstext', () => {
    schalter.set(false);
    fixture.detectChanges();
    kopieren();

    expect(erfolg()).toBeNull();
    expect(snackBar.open).toHaveBeenCalledWith(KOPIERT, 'Schließen', jasmine.any(Object));
  });

  it('nicht in der Formular-Vorschau', () => {
    component.vorschau = true;
    component.kopieren();
    fixture.detectChanges();

    expect(erfolg()).toBeNull();
  });
});
