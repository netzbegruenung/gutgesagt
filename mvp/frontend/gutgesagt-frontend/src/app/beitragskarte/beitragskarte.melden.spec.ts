import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { Clipboard } from '@angular/cdk/clipboard';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { provideRouter } from '@angular/router';
import { BehaviorSubject } from 'rxjs';

import { BeitragskarteComponent } from './beitragskarte.component';
import { ausSuchergebnis } from './karten-daten';
import { AuthService, UserInfo } from '../auth/auth.service';
import { ContentService } from '../services/content.service';
import { FunktionenService } from '../services/funktionen.service';
import { LoggingService } from '../services/logging.service';
import { UsageTrackingService } from '../services/usage-tracking.service';
import { VotingService } from '../services/voting.service';
import { MeilensteinHinweisService } from '../meine-beitraege/meilenstein-hinweis.service';

/**
 * „Melden“ klein am Ende der Meta-Zeile der Karte (Meldeweg, Basisfunktion seit dem Schalter-Umbau 27.11.):
 * in der Zeile, die es schon gibt, damit die Karte nicht höher wird (Entscheidung 26.11.).
 */
describe('Beitragskarte: Melden in der Meta-Zeile', () => {
  const ID = '123e4567-e89b-12d3-a456-426614174843';
  let fixture: ComponentFixture<BeitragskarteComponent>;
  let dialog: jasmine.SpyObj<MatDialog>;
  let auth: jasmine.SpyObj<AuthService>;

  function daten(felder: Record<string, unknown> = {}) {
    return ausSuchergebnis({
      score: 0.9,
      statement_text: null,
      statement_similarity_score: null,
      reply_relevance: null,
      user_vote: null,
      commentary_result: {
        id: ID,
        text: 'Wärmepumpen laufen mit Strom.',
        content_type: 'commentary',
        created: new Date(Date.now() - 5 * 24 * 3600 * 1000).toISOString(),
        title: 'Wärmepumpen sparen Geld',
        references: [],
        usage_count: 12,
        ...felder,
      },
    } as any);
  }

  function zeigen(inputs: Record<string, unknown> = {}, felder: Record<string, unknown> = {}): void {
    fixture = TestBed.createComponent(BeitragskarteComponent);
    fixture.componentRef.setInput('daten', daten(felder));
    for (const [name, wert] of Object.entries(inputs)) {
      fixture.componentRef.setInput(name, wert);
    }
    fixture.detectChanges();
  }

  function meta(): HTMLElement | null {
    return fixture.nativeElement.querySelector('.karte-meta');
  }

  function knopf(): HTMLButtonElement | null {
    return fixture.nativeElement.querySelector('.karte-meta .melden-knopf');
  }

  async function menueMelden(): Promise<string[]> {
    (fixture.nativeElement.querySelector('.menue-knopf') as HTMLButtonElement).click();
    fixture.detectChanges();
    await fixture.whenStable();
    return Array.from(document.querySelectorAll('.mat-mdc-menu-panel .melden-eintrag')).map((e) =>
      e.textContent!.replace(/\s+/g, ' ').trim(),
    );
  }

  beforeEach(async () => {
    dialog = jasmine.createSpyObj('MatDialog', ['open']);
    auth = jasmine.createSpyObj('AuthService', ['getUserInfo', 'login']);
    auth.getUserInfo.and.returnValue({ isAuthenticated: false } as UserInfo);
    (auth as any).userInfo$ = new BehaviorSubject<UserInfo | null>({ isAuthenticated: false } as UserInfo);

    await TestBed.configureTestingModule({
      imports: [BeitragskarteComponent, NoopAnimationsModule],
      providers: [
        { provide: MeilensteinHinweisService, useValue: jasmine.createSpyObj('MeilensteinHinweisService', ['bestaetigen']) },
        { provide: VotingService, useValue: jasmine.createSpyObj('VotingService', ['setLike']) },
        { provide: ContentService, useValue: jasmine.createSpyObj('ContentService', ['beitragLaden']) },
        { provide: MatSnackBar, useValue: jasmine.createSpyObj('MatSnackBar', ['open']) },
        { provide: AuthService, useValue: auth },
        { provide: Clipboard, useValue: jasmine.createSpyObj('Clipboard', ['copy']) },
        {
          provide: UsageTrackingService,
          useValue: jasmine.createSpyObj('UsageTrackingService', { trackContentUsage: undefined, gepostetBekannt: false }),
        },
        {
          provide: LoggingService,
          useValue: jasmine.createSpyObj('LoggingService', ['error', 'debug', 'info', 'warn', 'logInteraction', 'logError']),
        },
        { provide: MatDialog, useValue: dialog },
        {
          provide: FunktionenService,
          // Alle Schalter aus: der Meldeweg braucht keinen
          useValue: { an: () => signal(false) },
        },
        provideRouter([]),
      ],
    }).compileComponents();
  });

  afterEach(() => document.querySelectorAll('.cdk-overlay-container').forEach((c) => (c.innerHTML = '')));

  it('ohne Schalter: „Melden“ am Ende der Meta-Zeile, Name „Beitrag melden“, der Menüeintrag bleibt', async () => {
    zeigen();

    const k = knopf()!;
    expect(k).not.toBeNull();
    expect(meta()!.lastElementChild).toBe(k);
    expect(k.getAttribute('aria-label')).toBe('Beitrag melden');
    expect(k.querySelector('mat-icon')!.getAttribute('aria-hidden')).toBe('true');
    expect(k.querySelector('.melden-wort')!.textContent!.trim()).toBe('Melden');
    expect(fixture.nativeElement.querySelector('.melden-zeile')).toBeNull();
    expect(await menueMelden()).toEqual(['flagInhalt melden']);
  });

  it('macht die Karte nicht höher: die Meta-Zeile ist nicht höher als ihr Text', () => {
    zeigen();

    expect(knopf()).not.toBeNull();
    const stil = getComputedStyle(meta()!);
    const text = meta()!.querySelector('.karte-meta-text')!.getBoundingClientRect().height;
    expect(meta()!.getBoundingClientRect().height).toBeLessThanOrEqual(
      text + parseFloat(stil.paddingTop) + parseFloat(stil.paddingBottom) + 1,
    );
  });

  it('angemeldet mit Autorzeile und Teams, schmal: „Melden“ bleibt in der ersten Zeile', () => {
    auth.getUserInfo.and.returnValue({ isAuthenticated: true, userId: 'test-user' } as UserInfo);
    const teams = ['Nordwind', 'Sonnenblume', 'Lastenrad'].map((name) => ({ name, motiv: null, motiv_name: null }));
    fixture = TestBed.createComponent(BeitragskarteComponent);
    fixture.nativeElement.style.display = 'block';
    fixture.nativeElement.style.width = '256px';
    fixture.componentRef.setInput('daten', daten({ autor_name: 'Kim Beispiel', autor_teams: teams }));
    fixture.detectChanges();
    expect(meta()!.textContent).toContain('Von: Kim Beispiel');

    const text = meta()!.querySelector('.karte-meta-text')!.getBoundingClientRect();
    const k = knopf()!.getBoundingClientRect();
    // Rechts neben dem Text, nicht darunter: oben auf Höhe der ersten Textzeile
    expect(k.left).toBeGreaterThanOrEqual(text.right);
    expect(k.top).toBeLessThan(text.top + 4);
    // Keine eigene Zeile nur für „Melden“: unter dem Text folgt nur der Innenabstand der Zeile.
    // (Wird der Text schmaler, kann er selbst eine Zeile mehr brauchen; das misst dieser Test nicht.)
    expect(meta()!.getBoundingClientRect().bottom - text.bottom).toBeLessThanOrEqual(
      parseFloat(getComputedStyle(meta()!).paddingBottom) + 1,
    );
    expect(k.bottom).toBeLessThanOrEqual(text.bottom + 7);
  });

  it('Tippziel mindestens 24 × 24 px (WCAG 2.5.8)', () => {
    zeigen();

    const r = knopf()!.getBoundingClientRect();
    expect(r.width).toBeGreaterThanOrEqual(24);
    expect(r.height).toBeGreaterThanOrEqual(24);
  });

  it('öffnet den Melde-Dialog mit Beitrag und Typ', () => {
    zeigen();

    knopf()!.click();

    expect(dialog.open).toHaveBeenCalledTimes(1);
    expect(dialog.open.calls.mostRecent().args[1]!.data).toEqual(
      jasmine.objectContaining({ contentId: ID, contentType: 'commentary' }),
    );
  });

  it('auch an der schlanken Karte ohne Alter und Nutzung', () => {
    zeigen({ schlank: true }, { usage_count: 0 });

    expect(meta()!.querySelector('.karte-meta-text')).toBeNull();
    expect(knopf()).not.toBeNull();
  });

  it('nicht in der Formular-Vorschau', () => {
    zeigen({ vorschau: true });

    expect(knopf()).toBeNull();
  });

  it('nicht im eigenen Album', () => {
    zeigen({ eigenesAlbum: true });

    expect(knopf()).toBeNull();
  });
});
