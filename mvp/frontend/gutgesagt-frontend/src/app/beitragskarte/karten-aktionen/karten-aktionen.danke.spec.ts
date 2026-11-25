import { ComponentFixture, TestBed } from '@angular/core/testing';
import { WritableSignal, signal } from '@angular/core';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { Clipboard } from '@angular/cdk/clipboard';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';
import { of, Subject } from 'rxjs';

import { KartenAktionenComponent } from './karten-aktionen.component';
import { AuthService } from '../../auth/auth.service';
import { LoggingService } from '../../services/logging.service';
import { DankeErgebnis, UsageTrackingService } from '../../services/usage-tracking.service';
import { VotingService } from '../../services/voting.service';
import { FunktionenService } from '../../services/funktionen.service';
import { TEILEN_NAVIGATOR } from '../../shared/teilen.service';
import { MeilensteinHinweisService } from '../../meine-beitraege/meilenstein-hinweis.service';
import { DANKE_ANGEKOMMEN, DANKE_FEHLER, DANKE_GESAGT, DANKE_NICHT_GEZAEHLT } from '../../shared/wirkung-texte';

/** „Danke an die Autorin“ nach dem Kopieren (#791): nur mit Schalter, nie am eigenen Beitrag. */
describe('KartenAktionenComponent - Danke an die Autorin', () => {
  const INHALT_ID = '123e4567-e89b-12d3-a456-426614174000';
  let fixture: ComponentFixture<KartenAktionenComponent>;
  let component: KartenAktionenComponent;
  let usage: jasmine.SpyObj<UsageTrackingService>;
  let auth: jasmine.SpyObj<AuthService>;
  let schalter: Record<string, WritableSignal<boolean>>;

  beforeEach(async () => {
    schalter = { danke_knopf: signal(false), danke_ohne_konto: signal(false) };
    usage = jasmine.createSpyObj('UsageTrackingService', [
      'trackContentUsage',
      'gepostetAngeboten',
      'gepostetBekannt',
      'gepostetMelden',
      'dankeSagen',
    ]);
    usage.gepostetBekannt.and.returnValue(false);
    auth = jasmine.createSpyObj('AuthService', ['getUserInfo', 'login']);
    auth.getUserInfo.and.returnValue({ isAuthenticated: true, userId: 'kim' } as any);
    await TestBed.configureTestingModule({
      imports: [KartenAktionenComponent, NoopAnimationsModule],
      providers: [
        { provide: VotingService, useValue: jasmine.createSpyObj('VotingService', ['setLike']) },
        { provide: LoggingService, useValue: jasmine.createSpyObj('LoggingService', ['logInteraction', 'error']) },
        { provide: MatSnackBar, useValue: jasmine.createSpyObj('MatSnackBar', ['open']) },
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

  function knopf(): HTMLButtonElement | null {
    return fixture.nativeElement.querySelector('app-danke-knopf .danke-knopf');
  }

  function kopieren(): void {
    component.kopieren();
    fixture.detectChanges();
  }

  it('ohne Schalter kein Knopf, auch nach dem Kopieren', () => {
    kopieren();
    expect(knopf()).toBeNull();
  });

  it('mit Schalter erst nach dem Kopieren, mit sichtbarem Namen', () => {
    schalter['danke_knopf'].set(true);
    fixture.detectChanges();
    expect(knopf()).toBeNull();

    kopieren();

    expect(knopf()!.textContent).toContain('Danke an die Autorin');
  });

  it('nicht am eigenen Beitrag, nicht im Album und nicht in der Vorschau', () => {
    schalter['danke_knopf'].set(true);
    kopieren();

    component.eigeneStimmeImZaehler = false;
    expect(component.dankeSichtbar).toBeFalse();
    component.eigeneStimmeImZaehler = true;
    component.album = true;
    expect(component.dankeSichtbar).toBeFalse();
    component.album = false;
    component.vorschau = true;
    expect(component.dankeSichtbar).toBeFalse();
  });

  it('ohne Konto nur mit dem Unterschalter', () => {
    auth.getUserInfo.and.returnValue({ isAuthenticated: false } as any);
    schalter['danke_knopf'].set(true);
    kopieren();
    expect(component.dankeSichtbar).toBeFalse();

    schalter['danke_ohne_konto'].set(true);
    expect(component.dankeSichtbar).toBeTrue();
  });

  it('sagt nach dem Klick, dass das Danke angekommen ist, und schickt nur die ID', () => {
    schalter['danke_knopf'].set(true);
    usage.dankeSagen.and.returnValue(of<DankeErgebnis>('gezaehlt'));
    kopieren();

    knopf()!.click();
    fixture.detectChanges();

    expect(usage.dankeSagen).toHaveBeenCalledOnceWith(INHALT_ID);
    // Der Knopf bleibt stehen (Fokus, WCAG 2.4.3), gesperrt und neu beschriftet
    expect(knopf()!.getAttribute('aria-disabled')).toBe('true');
    expect(knopf()!.textContent).toContain(DANKE_GESAGT);
    const status = fixture.nativeElement.querySelector('app-danke-knopf [role="status"]');
    expect(status.textContent).toContain(DANKE_ANGEKOMMEN);
  });

  it('nicht gezaehlt: nur die Regel nennen, nichts ueber die Person behaupten, kein zweites Senden', () => {
    schalter['danke_knopf'].set(true);
    usage.dankeSagen.and.returnValue(of<DankeErgebnis>('nicht_gezaehlt'));
    kopieren();

    knopf()!.click();
    fixture.detectChanges();
    knopf()!.click();

    expect(usage.dankeSagen).toHaveBeenCalledTimes(1);
    expect(knopf()!.getAttribute('aria-disabled')).toBe('true');
    expect(fixture.nativeElement.textContent).toContain(DANKE_NICHT_GEZAEHLT);
    expect(DANKE_NICHT_GEZAEHLT).not.toContain('Dein');
  });

  it('der Fokus bleibt nach dem Danke auf dem Knopf', () => {
    schalter['danke_knopf'].set(true);
    usage.dankeSagen.and.returnValue(of<DankeErgebnis>('gezaehlt'));
    kopieren();
    document.body.appendChild(fixture.nativeElement);

    knopf()!.focus();
    knopf()!.click();
    fixture.detectChanges();

    expect(document.activeElement).toBe(knopf());
    fixture.nativeElement.remove();
  });

  it('bei einem Fehler bleibt der Knopf zum erneuten Versuch', () => {
    schalter['danke_knopf'].set(true);
    usage.dankeSagen.and.returnValue(of<DankeErgebnis>('fehler'));
    kopieren();

    knopf()!.click();
    fixture.detectChanges();

    expect(knopf()).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain(DANKE_FEHLER);
  });

  it('während des Sendens gesperrt, ein Doppeltipp schickt nur einmal', () => {
    schalter['danke_knopf'].set(true);
    const antwort = new Subject<DankeErgebnis>();
    usage.dankeSagen.and.returnValue(antwort.asObservable());
    kopieren();

    knopf()!.click();
    fixture.detectChanges();
    knopf()!.click();

    expect(knopf()!.getAttribute('aria-disabled')).toBe('true');
    expect(knopf()!.disabled).toBeFalse();
    expect(usage.dankeSagen).toHaveBeenCalledTimes(1);
  });

  it('Ja, gepostet nimmt die ID mit; ob sie gesendet wird, entscheidet der Dienst', () => {
    const aktion = new Subject<void>();
    (TestBed.inject(MatSnackBar) as jasmine.SpyObj<MatSnackBar>).open.and.returnValue({
      onAction: () => aktion.asObservable(),
    } as any);
    usage.gepostetBekannt.and.returnValue(true);
    usage.gepostetMelden.and.returnValue(of(3));
    kopieren();

    aktion.next();

    expect(usage.gepostetMelden).toHaveBeenCalledOnceWith('kim', INHALT_ID);
  });
});
