import { ComponentFixture, TestBed } from '@angular/core/testing';
import { WritableSignal, signal } from '@angular/core';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { Clipboard } from '@angular/cdk/clipboard';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';
import { Subject, of } from 'rxjs';

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
  GEPOSTET_FRAGE_MS,
  GEPOSTET_NICHT_GEZAEHLT,
  GEPOSTET_OHNE_KONTO_DANK,
  JA_GEPOSTET,
  KOPIERT_GEPOSTET_FRAGE,
} from './gepostet-texte';

/**
 * „Ja, gepostet“ ohne Konto (#799): nur mit Schalter, dieselbe Frage wie mit Konto, je
 * Karte einmal (danach ist der Knopf weg), nichts im Browser-Speicher.
 */
describe('KartenAktionenComponent - Ja, gepostet ohne Konto', () => {
  const INHALT_ID = '123e4567-e89b-12d3-a456-426614174000';
  let fixture: ComponentFixture<KartenAktionenComponent>;
  let component: KartenAktionenComponent;
  let usage: jasmine.SpyObj<UsageTrackingService>;
  let auth: jasmine.SpyObj<AuthService>;
  let snackBar: jasmine.SpyObj<MatSnackBar>;
  let schalter: Record<string, WritableSignal<boolean>>;
  let aktion: Subject<void>;

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
    aktion = new Subject<void>();
    snackBar.open.and.returnValue({ onAction: () => aktion.asObservable() } as any);
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

  function frageGezeigt(): number {
    return snackBar.open.calls.allArgs().filter((a) => a[1] === JA_GEPOSTET).length;
  }

  it('Schalter aus: keine Rückfrage ohne Konto, nur die gewohnte Bestätigung', () => {
    kopieren();

    expect(frageGezeigt()).toBe(0);
    expect(snackBar.open).toHaveBeenCalledWith(KOPIERT, 'Schließen', jasmine.any(Object));
    expect(usage.gepostetOhneKontoMelden).not.toHaveBeenCalled();
    expect(usage.gepostetAngeboten).not.toHaveBeenCalled();
  });

  it('Schalter an: dieselbe Frage wie mit Konto, Dank ohne Zahl und ohne Druck', () => {
    schalter['gepostet_ohne_konto'].set(true);
    kopieren();

    expect(snackBar.open).toHaveBeenCalledOnceWith(KOPIERT_GEPOSTET_FRAGE, JA_GEPOSTET, { duration: GEPOSTET_FRAGE_MS });
    expect(usage.gepostetOhneKontoMelden).not.toHaveBeenCalled();

    aktion.next();

    expect(usage.gepostetOhneKontoMelden).toHaveBeenCalledOnceWith();
    expect(snackBar.open).toHaveBeenCalledWith(GEPOSTET_OHNE_KONTO_DANK, 'Schließen', { duration: 5000 });
    expect(GEPOSTET_OHNE_KONTO_DANK).not.toMatch(/\d|anmeld|konto/i);
    // Der Weg mit Konto bleibt unberührt
    expect(usage.gepostetMelden).not.toHaveBeenCalled();
  });

  it('Knopf deaktiviert sich: ein Doppeltipp zählt einmal, die Karte fragt danach nicht mehr', () => {
    schalter['gepostet_ohne_konto'].set(true);
    kopieren();

    aktion.next();
    aktion.next();
    expect(usage.gepostetOhneKontoMelden).toHaveBeenCalledTimes(1);

    snackBar.open.calls.reset();
    kopieren();

    expect(frageGezeigt()).toBe(0);
    expect(snackBar.open).toHaveBeenCalledWith(KOPIERT, 'Schließen', jasmine.any(Object));
    expect(usage.gepostetOhneKontoMelden).toHaveBeenCalledTimes(1);
  });

  it('ohne Tippen fragt die Karte beim nächsten Kopieren wieder', () => {
    schalter['gepostet_ohne_konto'].set(true);
    kopieren();
    kopieren();

    expect(frageGezeigt()).toBe(2);
    expect(usage.gepostetOhneKontoMelden).not.toHaveBeenCalled();
  });

  it('nicht angeboten: kein Dank; Fehler: Dank mit Hinweis', () => {
    schalter['gepostet_ohne_konto'].set(true);
    usage.gepostetOhneKontoMelden.and.returnValue(of<MeldungOhneKontoErgebnis>('nicht_angeboten'));
    kopieren();
    snackBar.open.calls.reset();
    aktion.next();
    expect(snackBar.open).not.toHaveBeenCalled();

    const zweite = TestBed.createComponent(KartenAktionenComponent).componentInstance;
    zweite.inhaltId = INHALT_ID;
    zweite.kopierText = 'Noch ein Text.';
    usage.gepostetOhneKontoMelden.and.returnValue(of<MeldungOhneKontoErgebnis>('fehler'));
    aktion = new Subject<void>();
    zweite.kopieren();
    aktion.next();
    expect(snackBar.open).toHaveBeenCalledWith(GEPOSTET_NICHT_GEZAEHLT, 'Schließen', { duration: 5000 });
  });

  it('angemeldet: nie der Weg ohne Konto, auch mit Schalter', () => {
    schalter['gepostet_ohne_konto'].set(true);
    auth.getUserInfo.and.returnValue({ isAuthenticated: true, userId: 'kim' } as any);
    usage.gepostetBekannt.and.returnValue(true);
    usage.gepostetMelden.and.returnValue(of(3));
    kopieren();

    aktion.next();

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
    aktion.next();
    kopieren();

    for (const spion of storage) {
      expect(spion).not.toHaveBeenCalled();
    }
    expect(cookieSetzen).not.toHaveBeenCalled();
    expect(cookieLesen).not.toHaveBeenCalled();
  });
});
