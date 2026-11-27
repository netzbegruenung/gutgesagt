import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { WritableSignal, signal } from '@angular/core';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { Clipboard } from '@angular/cdk/clipboard';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';
import { of } from 'rxjs';

import { KartenAktionenComponent } from './karten-aktionen.component';
import { AuthService } from '../../auth/auth.service';
import { LoggingService } from '../../services/logging.service';
import { MeldungOhneKontoErgebnis, UsageTrackingService } from '../../services/usage-tracking.service';
import { VotingService } from '../../services/voting.service';
import { FunktionenService } from '../../services/funktionen.service';
import { TEILEN_NAVIGATOR } from '../../shared/teilen.service';
import { MeilensteinHinweisService } from '../../meine-beitraege/meilenstein-hinweis.service';
import { KOPIERT } from '../../shared/vorlagen-luecke';
import {
  GEPOSTET_FRAGE,
  GEPOSTET_FRAGE_OHNE_KONTO,
  GEPOSTET_NICHT_GEZAEHLT,
  GEPOSTET_OHNE_KONTO_DANK,
  GEPOSTET_RUECKKEHR,
  GEPOSTET_RUECKKEHR_OHNE_KONTO,
} from './gepostet-texte';
import { RUECKKEHR_AB_MS, RUECKKEHR_LEUCHTEN_MS } from './kopiert-erfolg.component';

/**
 * „Ja, gepostet“ ohne Konto (#799): nur mit Schalter, dieselbe Frage wie mit Konto im
 * Erfolgskasten, je Karte einmal (danach steht der Knopf als „Gepostet“ gesperrt da),
 * nichts im Browser-Speicher.
 */
describe('KartenAktionenComponent - Ja, gepostet ohne Konto', () => {
  const INHALT_ID = '123e4567-e89b-12d3-a456-426614174000';
  let fixture: ComponentFixture<KartenAktionenComponent>;
  let component: KartenAktionenComponent;
  let usage: jasmine.SpyObj<UsageTrackingService>;
  let auth: jasmine.SpyObj<AuthService>;
  let snackBar: jasmine.SpyObj<MatSnackBar>;
  let schalter: Record<string, WritableSignal<boolean>>;

  beforeEach(async () => {
    schalter = { gepostet_ohne_konto: signal(false) };
    usage = jasmine.createSpyObj('UsageTrackingService', [
      'trackContentUsage',
      'gepostetAngeboten',
      'gepostetBekannt',
      'gepostetMelden',
      'gepostetOhneKontoMelden',
      'dankeSagen',
    ]);
    usage.gepostetBekannt.and.returnValue(false);
    usage.gepostetOhneKontoMelden.and.returnValue(of<MeldungOhneKontoErgebnis>('gezaehlt'));
    auth = jasmine.createSpyObj('AuthService', ['getUserInfo', 'login']);
    auth.getUserInfo.and.returnValue({ isAuthenticated: false } as any);
    snackBar = jasmine.createSpyObj('MatSnackBar', ['open']);
    await TestBed.configureTestingModule({
      imports: [KartenAktionenComponent, NoopAnimationsModule],
      providers: [
        { provide: VotingService, useValue: jasmine.createSpyObj('VotingService', ['setLike']) },
        { provide: LoggingService, useValue: jasmine.createSpyObj('LoggingService', ['logInteraction', 'error']) },
        { provide: MatSnackBar, useValue: snackBar },
        { provide: Clipboard, useValue: jasmine.createSpyObj('Clipboard', ['copy']) },
        { provide: UsageTrackingService, useValue: usage },
        { provide: AuthService, useValue: auth },
        { provide: MatDialog, useValue: jasmine.createSpyObj('MatDialog', ['open']) },
        { provide: Router, useValue: jasmine.createSpyObj('Router', ['navigate']) },
        { provide: TEILEN_NAVIGATOR, useValue: {} },
        { provide: MeilensteinHinweisService, useValue: jasmine.createSpyObj('MeilensteinHinweisService', ['bestaetigen']) },
        {
          provide: FunktionenService,
          useValue: { an: (name: string) => (schalter[name] ?? signal(false)).asReadonly() },
        },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(KartenAktionenComponent);
    component = fixture.componentInstance;
    component.inhaltId = INHALT_ID;
    component.kopierText = 'Windkraft schafft Arbeitsplätze.';
    fixture.detectChanges();
  });

  function kopieren(): void {
    component.kopieren();
    fixture.detectChanges();
  }

  function jaKnopf(): HTMLButtonElement | null {
    return fixture.nativeElement.querySelector('.ja-gepostet');
  }

  function jaTippen(): void {
    jaKnopf()!.click();
    fixture.detectChanges();
  }

  function dank(): string {
    return (fixture.nativeElement.querySelector('.erfolg-gepostet-dank')?.textContent ?? '').trim();
  }

  it('Schalter aus: keine Rückfrage ohne Konto, nur die gewohnte Bestätigung', () => {
    kopieren();

    expect(jaKnopf()).toBeNull();
    expect(snackBar.open).toHaveBeenCalledWith(KOPIERT, 'Schließen', jasmine.any(Object));
    expect(usage.gepostetOhneKontoMelden).not.toHaveBeenCalled();
    expect(usage.gepostetAngeboten).not.toHaveBeenCalled();
  });

  it('Schalter an: Frage ohne „zählt mit“ im Kasten, Dank ohne Zahl und ohne Druck', () => {
    schalter['gepostet_ohne_konto'].set(true);
    kopieren();

    // Ohne Konto ohne „zählt mit“: Meldungen ohne Konto zählen nicht zu „Öffentlich gekontert“
    expect(fixture.nativeElement.querySelector('.kopiert-erfolg').textContent).toContain(GEPOSTET_FRAGE_OHNE_KONTO);
    expect(fixture.nativeElement.querySelector('.kopiert-erfolg').textContent).not.toContain(GEPOSTET_FRAGE);
    expect(snackBar.open).not.toHaveBeenCalled();
    expect(usage.gepostetOhneKontoMelden).not.toHaveBeenCalled();

    jaTippen();

    expect(usage.gepostetOhneKontoMelden).toHaveBeenCalledOnceWith();
    expect(dank()).toBe(GEPOSTET_OHNE_KONTO_DANK);
    expect(snackBar.open).not.toHaveBeenCalled();
    expect(GEPOSTET_OHNE_KONTO_DANK).not.toMatch(/\d|anmeld|konto/i);
    // Der Weg mit Konto bleibt unberührt
    expect(usage.gepostetMelden).not.toHaveBeenCalled();
  });

  it('Knopf sperrt sich: ein Doppeltipp zählt einmal, die Karte fragt danach nicht mehr', () => {
    schalter['gepostet_ohne_konto'].set(true);
    kopieren();

    jaTippen();
    jaTippen();
    expect(usage.gepostetOhneKontoMelden).toHaveBeenCalledTimes(1);
    expect(jaKnopf()!.getAttribute('aria-disabled')).toBe('true');

    kopieren();

    expect(jaKnopf()).toBeNull();
    expect(snackBar.open).toHaveBeenCalledWith(KOPIERT, 'Schließen', jasmine.any(Object));
    expect(usage.gepostetOhneKontoMelden).toHaveBeenCalledTimes(1);
  });

  it('ohne Tippen fragt die Karte beim nächsten Kopieren wieder', () => {
    schalter['gepostet_ohne_konto'].set(true);
    kopieren();
    kopieren();

    expect(jaKnopf()).not.toBeNull();
    expect(usage.gepostetOhneKontoMelden).not.toHaveBeenCalled();
  });

  it('nicht angeboten: kein Dank, die Frage geht; Fehler: Dank mit Hinweis', () => {
    schalter['gepostet_ohne_konto'].set(true);
    usage.gepostetOhneKontoMelden.and.returnValue(of<MeldungOhneKontoErgebnis>('nicht_angeboten'));
    kopieren();
    jaTippen();
    expect(dank()).toBe('');
    expect(jaKnopf()).toBeNull();

    const zweite = TestBed.createComponent(KartenAktionenComponent);
    zweite.componentInstance.inhaltId = INHALT_ID;
    zweite.componentInstance.kopierText = 'Noch ein Text.';
    zweite.detectChanges();
    usage.gepostetOhneKontoMelden.and.returnValue(of<MeldungOhneKontoErgebnis>('fehler'));
    zweite.componentInstance.kopieren();
    zweite.detectChanges();
    (zweite.nativeElement.querySelector('.ja-gepostet') as HTMLButtonElement).click();
    zweite.detectChanges();
    expect(zweite.nativeElement.querySelector('.erfolg-gepostet-dank').textContent.trim()).toBe(GEPOSTET_NICHT_GEZAEHLT);
  });

  it('angemeldet: nie der Weg ohne Konto, auch mit Schalter', () => {
    schalter['gepostet_ohne_konto'].set(true);
    auth.getUserInfo.and.returnValue({ isAuthenticated: true, userId: 'kim' } as any);
    usage.gepostetBekannt.and.returnValue(true);
    usage.gepostetMelden.and.returnValue(of(3));
    kopieren();

    jaTippen();

    expect(usage.gepostetOhneKontoMelden).not.toHaveBeenCalled();
    expect(usage.gepostetMelden).toHaveBeenCalledWith('kim', INHALT_ID);
  });

  it('kein Zugriff auf localStorage, sessionStorage oder Cookies', () => {
    const storage = ['getItem', 'setItem', 'removeItem', 'clear', 'key'].map((m) =>
      spyOn(Storage.prototype, m as keyof Storage).and.callThrough(),
    );
    const cookieSetzen = spyOnProperty(Document.prototype, 'cookie', 'set').and.callThrough();
    const cookieLesen = spyOnProperty(Document.prototype, 'cookie', 'get').and.callThrough();
    schalter['gepostet_ohne_konto'].set(true);

    kopieren();
    jaTippen();
    kopieren();

    for (const spion of storage) {
      expect(spion).not.toHaveBeenCalled();
    }
    expect(cookieSetzen).not.toHaveBeenCalled();
    expect(cookieLesen).not.toHaveBeenCalled();
  });

  it('Rückkehr-Moment: ohne Konto der Hinweis ohne „zählt mit“, je Kopieren neu', fakeAsync(() => {
    schalter['gepostet_ohne_konto'].set(true);
    kopieren();
    tick(RUECKKEHR_AB_MS);
    document.dispatchEvent(new Event('visibilitychange'));
    fixture.detectChanges();
    const frage = () => fixture.nativeElement.querySelector('.erfolg-gepostet-frage').textContent.trim();
    expect(frage()).toBe(GEPOSTET_RUECKKEHR_OHNE_KONTO);
    expect(frage()).not.toBe(GEPOSTET_RUECKKEHR);

    // Neues Kopieren: wieder die Frage, der Moment kommt erneut erst nach 3 s
    kopieren();
    expect(frage()).toBe(GEPOSTET_FRAGE_OHNE_KONTO);
    tick(RUECKKEHR_LEUCHTEN_MS);
  }));
});
