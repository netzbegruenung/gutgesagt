import { ComponentFixture, TestBed } from '@angular/core/testing';
import { WritableSignal, signal } from '@angular/core';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { Clipboard } from '@angular/cdk/clipboard';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';

import { KartenAktionenComponent } from './karten-aktionen.component';
import { AuthService } from '../../auth/auth.service';
import { LoggingService } from '../../services/logging.service';
import { UsageTrackingService } from '../../services/usage-tracking.service';
import { VotingService } from '../../services/voting.service';
import { FunktionenService } from '../../services/funktionen.service';
import { TEILEN_NAVIGATOR } from '../../shared/teilen.service';
import { MeilensteinHinweisService } from '../../meine-beitraege/meilenstein-hinweis.service';

/** „Melden“ direkt sichtbar an der Karte (Schalter meldeweg_sichtbar, Standard aus). */
describe('KartenAktionenComponent - Melden sichtbar', () => {
  const INHALT_ID = '123e4567-e89b-12d3-a456-426614174000';
  let fixture: ComponentFixture<KartenAktionenComponent>;
  let dialog: jasmine.SpyObj<MatDialog>;
  let meldeweg: WritableSignal<boolean>;

  beforeEach(async () => {
    meldeweg = signal(false);
    dialog = jasmine.createSpyObj('MatDialog', ['open']);
    const auth = jasmine.createSpyObj('AuthService', ['getUserInfo']);
    auth.getUserInfo.and.returnValue({ isAuthenticated: false });
    await TestBed.configureTestingModule({
      imports: [KartenAktionenComponent, NoopAnimationsModule],
      providers: [
        { provide: VotingService, useValue: jasmine.createSpyObj('VotingService', ['setLike']) },
        { provide: LoggingService, useValue: jasmine.createSpyObj('LoggingService', ['logInteraction', 'logError']) },
        { provide: MatSnackBar, useValue: jasmine.createSpyObj('MatSnackBar', ['open']) },
        { provide: Clipboard, useValue: jasmine.createSpyObj('Clipboard', ['copy']) },
        {
          provide: UsageTrackingService,
          useValue: jasmine.createSpyObj('UsageTrackingService', ['trackContentUsage', 'gepostetAngeboten', 'gepostetBekannt']),
        },
        { provide: AuthService, useValue: auth },
        { provide: MatDialog, useValue: dialog },
        { provide: Router, useValue: jasmine.createSpyObj('Router', ['navigate']) },
        { provide: TEILEN_NAVIGATOR, useValue: {} },
        { provide: MeilensteinHinweisService, useValue: jasmine.createSpyObj('MeilensteinHinweisService', ['bestaetigen']) },
        {
          provide: FunktionenService,
          useValue: { an: (name: string) => (name === 'meldeweg_sichtbar' ? meldeweg.asReadonly() : signal(false)) },
        },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(KartenAktionenComponent);
    fixture.componentRef.setInput('inhaltId', INHALT_ID);
    fixture.componentRef.setInput('typ', 'commentary');
    fixture.componentRef.setInput('kopierText', 'Text');
    fixture.detectChanges();
  });

  afterEach(() => document.querySelectorAll('.cdk-overlay-container').forEach((c) => (c.innerHTML = '')));

  function knopf(): HTMLButtonElement | null {
    return fixture.nativeElement.querySelector('.melden-zeile .melden-knopf');
  }

  async function menueMelden(): Promise<string[]> {
    (fixture.nativeElement.querySelector('.menue-knopf') as HTMLButtonElement).click();
    fixture.detectChanges();
    await fixture.whenStable();
    return Array.from(document.querySelectorAll('.mat-mdc-menu-panel .melden-eintrag')).map((e) =>
      e.textContent!.replace(/\s+/g, ' ').trim(),
    );
  }

  it('Schalter aus: kein Knopf, „Inhalt melden“ bleibt im Menü', async () => {
    expect(knopf()).toBeNull();
    expect(await menueMelden()).toEqual(['flagInhalt melden']);
  });

  it('Schalter an: Knopf mit Symbol und Text „Melden“, der Menüeintrag bleibt', async () => {
    meldeweg.set(true);
    fixture.detectChanges();

    const k = knopf()!;
    expect(k).not.toBeNull();
    expect(k.querySelector('mat-icon')!.getAttribute('aria-hidden')).toBe('true');
    expect(k.querySelector('mat-icon')!.textContent!.trim()).toBe('outlined_flag');
    expect(k.querySelector('.melden-wort')!.textContent!.trim()).toBe('Melden');
    // Kein abweichendes aria-label: der sichtbare Text „Melden“ ist der Name (WCAG 2.5.3)
    expect(k.hasAttribute('aria-label')).toBeFalse();
    expect(await menueMelden()).toEqual(['flagInhalt melden']);
  });

  it('kommt und geht ohne Neuladen, sobald der Schalter umschaltet', () => {
    expect(knopf()).toBeNull();
    meldeweg.set(true);
    fixture.detectChanges();
    expect(knopf()).not.toBeNull();
    meldeweg.set(false);
    fixture.detectChanges();
    expect(knopf()).toBeNull();
  });

  it('ist leiser als Kopieren: Textknopf mit kleinerer Schrift, nicht der Hauptknopf', () => {
    meldeweg.set(true);
    fixture.detectChanges();

    const k = knopf()!;
    const kopieren = fixture.nativeElement.querySelector('.kopieren-knopf') as HTMLElement;
    expect(k.classList).not.toContain('gutgesagt-primary-dark');
    expect(k.classList).not.toContain('mat-mdc-raised-button');
    expect(parseFloat(getComputedStyle(k).fontSize)).toBeLessThan(parseFloat(getComputedStyle(kopieren).fontSize));
  });

  it('überlappt das ⋮ darüber nicht (Tippziele, WCAG 2.5.8)', () => {
    meldeweg.set(true);
    fixture.detectChanges();

    const menue = (fixture.nativeElement.querySelector('.menue-knopf') as HTMLElement).getBoundingClientRect();
    const melden = knopf()!.getBoundingClientRect();
    expect(melden.top).toBeGreaterThanOrEqual(menue.bottom);
  });

  it('öffnet den Melde-Dialog mit Beitrag und Typ', () => {
    meldeweg.set(true);
    fixture.detectChanges();

    knopf()!.click();

    expect(dialog.open).toHaveBeenCalledTimes(1);
    expect(dialog.open.calls.mostRecent().args[1]!.data).toEqual(
      jasmine.objectContaining({ contentId: INHALT_ID, contentType: 'commentary' }),
    );
  });

  it('nicht in der Formular-Vorschau', () => {
    meldeweg.set(true);
    fixture.componentRef.setInput('vorschau', true);
    fixture.detectChanges();

    expect(knopf()).toBeNull();
  });

  it('nicht im eigenen Album', () => {
    meldeweg.set(true);
    fixture.componentRef.setInput('album', true);
    fixture.detectChanges();

    expect(knopf()).toBeNull();
  });
});
