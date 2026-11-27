import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { signal } from '@angular/core';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { Clipboard } from '@angular/cdk/clipboard';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { provideRouter } from '@angular/router';
import { BehaviorSubject, Subject, of } from 'rxjs';

import { KartenAktionenComponent } from './karten-aktionen.component';
import { KOPIERT_ERFOLG, nutzungSatz, tonlagenHinweis } from './kopiert-erfolg';
import { AuthService, UserInfo } from '../../auth/auth.service';
import { BeitragskarteComponent } from '../beitragskarte.component';
import { ausSuchergebnis } from '../karten-daten';
import { LoggingService } from '../../services/logging.service';
import { UsageTrackingService } from '../../services/usage-tracking.service';
import { VotingService } from '../../services/voting.service';
import { FunktionenService } from '../../services/funktionen.service';
import { TEILEN_NAVIGATOR } from '../../shared/teilen.service';
import { MeilensteinHinweisService } from '../../meine-beitraege/meilenstein-hinweis.service';
import { GEPOSTET_FRAGE, JA_GEPOSTET } from './gepostet-texte';

describe('Erfolgstext nach dem Kopieren - Texte (#785)', () => {
  it('nennt die Nutzung als Kopiervorgaenge, nie als Menschen', () => {
    expect(nutzungSatz(14)).toBe('Schon 14-mal genutzt.');
    expect(nutzungSatz(2)).toBe('Schon 2-mal genutzt.');
    expect(nutzungSatz(1234)).toBe('Schon 1.234-mal genutzt.');
    expect(nutzungSatz(14)).not.toContain('Menschen');
  });

  it('bei 0 und 1 vorher nach Anfang statt nach „schon 1-mal“ (Leerzustaende 26.11.)', () => {
    expect(nutzungSatz(0)).toBe('Deine Kopie ist die erste.');
    expect(nutzungSatz(1)).toBe('Deine Kopie ist die zweite.');
    expect(nutzungSatz(1.7)).toBe('Deine Kopie ist die zweite.');
  });

  it('am eigenen Beitrag ohne „die erste“: die eigene Kopie zaehlt nicht', () => {
    expect(nutzungSatz(0, true)).toBeNull();
    expect(nutzungSatz(1, true)).toBe('Einmal genutzt.');
    expect(nutzungSatz(3, true)).toBe('Schon 3-mal genutzt.');
  });

  it('ohne Satz bei unbekannter Nutzung', () => {
    expect(nutzungSatz(null)).toBeNull();
    expect(nutzungSatz(undefined)).toBeNull();
    expect(nutzungSatz(-1)).toBeNull();
    expect(nutzungSatz(Number.NaN)).toBeNull();
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
  let snackBar: jasmine.SpyObj<MatSnackBar>;
  let usage: jasmine.SpyObj<UsageTrackingService>;
  let auth: jasmine.SpyObj<AuthService>;

  beforeEach(async () => {
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
          // Alle Schalter aus: der Erfolgstext ist Basisfunktion (Schalter-Umbau 27.11.)
          useValue: { an: () => signal(false) },
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

  it('bei 0 Nutzungen der Anfang: diese Kopie ist die erste', () => {
    component.nutzung = 0;
    kopieren();

    const text = erfolg()!.textContent!.replace(/\s+/g, ' ');
    expect(text).toContain(KOPIERT_ERFOLG);
    expect(text).toContain('Deine Kopie ist die erste.');
    expect(text).not.toContain('genutzt');
  });

  it('am eigenen Beitrag bei 0 Nutzungen nur der Erfolgssatz', () => {
    component.nutzung = 0;
    component.eigeneStimmeImZaehler = false;
    kopieren();

    const text = erfolg()!.textContent!.replace(/\s+/g, ' ');
    expect(text).toContain(KOPIERT_ERFOLG);
    expect(text).not.toContain('die erste');
    expect(text).not.toContain('genutzt');
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
    (fixture.nativeElement.querySelector('.erfolg-schliessen') as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(erfolg()).toBeNull();
    expect(fixture.nativeElement.querySelector('.erfolg-schliessen')).toBeNull();
  });

  it('der Schliessen-Knopf steht ausserhalb der Status-Region', () => {
    kopieren();

    expect(fixture.nativeElement.querySelector('[role="status"] .erfolg-schliessen')).toBeNull();
    expect(fixture.nativeElement.querySelector('.erfolg-schliessen')).not.toBeNull();
  });

  it('angemeldet mit Frage „Gepostet?“ steht „Ja, gepostet“ im Kasten, keine Snackbar, „Kopiert“ nur einmal', () => {
    auth.getUserInfo.and.returnValue({ isAuthenticated: true, userId: 'person' } as any);
    usage.gepostetBekannt.and.returnValue(true);
    kopieren();

    expect(erfolg()!.textContent).toContain(GEPOSTET_FRAGE);
    expect(fixture.nativeElement.querySelector('.ja-gepostet').textContent.trim()).toBe(JA_GEPOSTET);
    expect(snackBar.open).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent.split('Kopiert').length - 1).toBe(1);
  });

  it('die Frage kommt nach, wenn der Server sie erst nach dem Kopieren anbietet', () => {
    const antwort = new Subject<boolean>();
    auth.getUserInfo.and.returnValue({ isAuthenticated: true, userId: 'person' } as any);
    usage.gepostetAngeboten.and.returnValue(antwort.asObservable());
    kopieren();
    expect(fixture.nativeElement.querySelector('.ja-gepostet')).toBeNull();

    antwort.next(true);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.ja-gepostet')).not.toBeNull();
    expect(snackBar.open).not.toHaveBeenCalled();
  });

  it('geschlossen, bevor der Server antwortet: der Kasten kommt nicht wieder', () => {
    const antwort = new Subject<boolean>();
    auth.getUserInfo.and.returnValue({ isAuthenticated: true, userId: 'person' } as any);
    usage.gepostetAngeboten.and.returnValue(antwort.asObservable());
    kopieren();
    (fixture.nativeElement.querySelector('.erfolg-schliessen') as HTMLButtonElement).click();
    fixture.detectChanges();

    antwort.next(true);
    fixture.detectChanges();

    expect(erfolg()).toBeNull();
  });

  it('ohne Angebot kein Knopf und keine Frage', () => {
    auth.getUserInfo.and.returnValue({ isAuthenticated: true, userId: 'person' } as any);
    usage.gepostetBekannt.and.returnValue(false);
    kopieren();

    expect(erfolg()!.textContent).not.toContain(GEPOSTET_FRAGE);
    expect(fixture.nativeElement.querySelector('.ja-gepostet')).toBeNull();
  });

  it('nicht in der Formular-Vorschau', () => {
    component.vorschau = true;
    component.kopieren();
    fixture.detectChanges();

    expect(erfolg()).toBeNull();
  });
});

describe('Erfolgstext nach dem Kopieren - in der Beitragskarte (#785)', () => {

  function inhalt(id: string, usageCount: number): any {
    return {
      id,
      text: 'Windkraft schafft Arbeitsplätze.',
      content_type: 'commentary',
      created: new Date().toISOString(),
      last_modified: new Date().toISOString(),
      original_author: '0f3c2a9e-1111-2222-3333-444455556666',
      last_modified_by: 'Test Author',
      title: 'Test Title',
      references: [],
      usage_count: usageCount,
    };
  }

  function karte(id: string, usageCount: number): ComponentFixture<BeitragskarteComponent> {
    const fixture = TestBed.createComponent(BeitragskarteComponent);
    fixture.componentRef.setInput(
      'daten',
      ausSuchergebnis({
        score: 0.95,
        statement_text: 'Windräder töten die Vögel!',
        statement_similarity_score: 0.9,
        reply_relevance: 0.85,
        commentary_result: inhalt(id, usageCount),
      } as any),
    );
    fixture.detectChanges();
    return fixture;
  }

  function kopieren(fixture: ComponentFixture<BeitragskarteComponent>): void {
    (fixture.nativeElement.querySelector('.kopieren-knopf') as HTMLButtonElement).click();
    fixture.detectChanges();
  }

  function erfolg(fixture: ComponentFixture<BeitragskarteComponent>): HTMLElement | null {
    return fixture.nativeElement.querySelector('.kopiert-erfolg');
  }

  function nutzungAnDerKarte(fixture: ComponentFixture<BeitragskarteComponent>): string {
    return fixture.nativeElement.querySelector('.karte-nutzung').textContent.trim();
  }

  beforeEach(async () => {
    const auth = jasmine.createSpyObj('AuthService', ['getUserInfo', 'login']);
    auth.getUserInfo.and.returnValue({ isAuthenticated: false });
    auth.userInfo$ = new BehaviorSubject<UserInfo | null>(null);
    const usage = jasmine.createSpyObj('UsageTrackingService', {
      trackContentUsage: undefined,
      gepostetBekannt: null,
      gepostetAngeboten: of(false),
    });
    await TestBed.configureTestingModule({
      imports: [BeitragskarteComponent, NoopAnimationsModule],
      providers: [
        provideRouter([]),
        { provide: MeilensteinHinweisService, useValue: jasmine.createSpyObj('MeilensteinHinweisService', ['bestaetigen']) },
        { provide: VotingService, useValue: jasmine.createSpyObj('VotingService', ['setLike']) },
        { provide: MatSnackBar, useValue: jasmine.createSpyObj('MatSnackBar', ['open']) },
        { provide: AuthService, useValue: auth },
        { provide: Clipboard, useValue: jasmine.createSpyObj('Clipboard', ['copy']) },
        { provide: UsageTrackingService, useValue: usage },
        {
          provide: LoggingService,
          useValue: jasmine.createSpyObj('LoggingService', ['logInteraction', 'logError', 'error', 'debug', 'info', 'warn']),
        },
        { provide: MatDialog, useValue: jasmine.createSpyObj('MatDialog', ['open']) },
        { provide: TEILEN_NAVIGATOR, useValue: {} },
        {
          provide: FunktionenService,
          // Alle Schalter aus: der Erfolgstext ist Basisfunktion (Schalter-Umbau 27.11.)
          useValue: { an: () => signal(false) },
        },
      ],
    }).compileComponents();
  });

  it('bei 0 Nutzungen „die erste“: die eigene Kopie zaehlt im Satz nicht mit', fakeAsync(() => {
    const fixture = karte('a', 0);
    kopieren(fixture);

    expect(nutzungAnDerKarte(fixture)).toBe('1× genutzt');
    const text = erfolg(fixture)!.textContent!.replace(/\s+/g, ' ');
    expect(text).toContain(KOPIERT_ERFOLG);
    expect(text).toContain('Deine Kopie ist die erste.');
    expect(text).not.toContain('genutzt');
    tick(600);
  }));

  it('am eigenen Beitrag bei 1 Nutzung „Einmal genutzt.“, die Karte zaehlt nicht hoch', fakeAsync(() => {
    (TestBed.inject(AuthService).getUserInfo as jasmine.Spy).and.returnValue({ isAuthenticated: true, userId: 'ich' });
    const fixture = TestBed.createComponent(BeitragskarteComponent);
    fixture.componentRef.setInput('daten', { ...ausSuchergebnis({
      score: 0.95,
      statement_text: 'Windräder töten die Vögel!',
      statement_similarity_score: 0.9,
      reply_relevance: 0.85,
      commentary_result: inhalt('a', 1),
    } as any), eigen: true });
    fixture.detectChanges();
    kopieren(fixture);

    expect(nutzungAnDerKarte(fixture)).toBe('1× genutzt');
    const text = erfolg(fixture)!.textContent!.replace(/\s+/g, ' ');
    expect(text).toContain('Einmal genutzt.');
    expect(text).not.toContain('zweite');
    tick(600);
  }));

  it('bei 1 Nutzung vorher „Deine Kopie ist die zweite.“', fakeAsync(() => {
    const fixture = karte('a', 1);
    kopieren(fixture);

    expect(nutzungAnDerKarte(fixture)).toBe('2× genutzt');
    expect(erfolg(fixture)!.textContent!.replace(/\s+/g, ' ')).toContain('Deine Kopie ist die zweite.');
    tick(600);
  }));

  it('bei 14 Nutzungen „Schon 14-mal“, auch wenn die Karte schon 15 zeigt', fakeAsync(() => {
    const fixture = karte('a', 14);
    kopieren(fixture);

    expect(nutzungAnDerKarte(fixture)).toBe('15× genutzt');
    expect(erfolg(fixture)!.textContent!.replace(/\s+/g, ' ')).toContain('Schon 14-mal genutzt.');
    tick(600);
  }));

  it('zeigt den Erfolgstext nur an der zuletzt kopierten Karte', fakeAsync(() => {
    const karteA = karte('a', 3);
    const karteB = karte('b', 5);

    kopieren(karteA);
    expect(erfolg(karteA)).not.toBeNull();

    kopieren(karteB);
    karteA.detectChanges();
    expect(erfolg(karteA)).toBeNull();
    expect(karteA.nativeElement.querySelector('.erfolg-schliessen')).toBeNull();
    expect(erfolg(karteB)!.textContent!.replace(/\s+/g, ' ')).toContain('Schon 5-mal genutzt.');
    expect(document.body.textContent!.split('🌱').length - 1).toBeLessThanOrEqual(1);

    kopieren(karteA);
    karteB.detectChanges();
    expect(erfolg(karteB)).toBeNull();
    expect(erfolg(karteA)!.textContent!.replace(/\s+/g, ' ')).toContain('Schon 4-mal genutzt.');
    tick(600);
  }));

  it('Schliessen an einer alten Karte nimmt der neuen nichts weg', fakeAsync(() => {
    const karteA = karte('a', 3);
    const karteB = karte('b', 5);

    kopieren(karteA);
    kopieren(karteB);
    karteA.debugElement.query(By.directive(KartenAktionenComponent)).componentInstance.kopiertErfolgSchliessen();
    karteA.detectChanges();
    karteB.detectChanges();

    expect(erfolg(karteB)).not.toBeNull();
    tick(600);
  }));
});
