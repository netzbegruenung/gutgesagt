import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';

import { FunktionenService } from '../../services/funktionen.service';
import { FeedbackDialogComponent } from './feedback-dialog.component';
import { GestoertEinstiegComponent } from './gestoert-einstieg.component';
import { FEEDBACK_GESTOERT_ENDE_MS, gestoertOffen } from './feedback.service';

describe('GestoertEinstiegComponent (Not-Aus feedback_gestoert)', () => {
  let fixture: ComponentFixture<GestoertEinstiegComponent>;
  const an = signal(false);
  let dialog: jasmine.SpyObj<MatDialog>;
  let gefragt: string[];

  beforeEach(async () => {
    an.set(false);
    gefragt = [];
    dialog = jasmine.createSpyObj('MatDialog', ['open']);
    await TestBed.configureTestingModule({
      imports: [GestoertEinstiegComponent],
      providers: [
        {
          provide: FunktionenService,
          useValue: {
            an: (name: string) => {
              gefragt.push(name);
              return an;
            },
          },
        },
        { provide: MatDialog, useValue: dialog },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(GestoertEinstiegComponent);
    // Vor dem Stichtag, unabhängig vom Tag des Testlaufs
    fixture.componentInstance.jetzt = () => Date.UTC(2026, 10, 27, 12);
    fixture.detectChanges();
  });

  function knopf(): HTMLButtonElement | null {
    return (fixture.nativeElement as HTMLElement).querySelector('[data-testid="gestoert-einstieg"]');
  }

  it('fragt den Schalter feedback_gestoert', () => {
    expect(gefragt).toEqual(['feedback_gestoert']);
  });

  it('ist bei greifendem Not-Aus unsichtbar', () => {
    expect(knopf()).toBeNull();
    expect((fixture.nativeElement as HTMLElement).textContent?.trim()).toBe('');
  });

  it('erscheint beim Umschalten ohne Neuladen und verschwindet wieder', () => {
    an.set(true);
    fixture.detectChanges();
    expect(knopf()?.textContent).toContain('Was hat dich gestört?');
    // Startseite 28.11.: eine Textzeile mit Knopf in Link-Optik statt eigener Karte
    expect(knopf()?.textContent?.replace(/\s+/g, ' ').trim()).toBe('Was hat dich gestört? Sag es uns in einem Satz arrow_forward');

    an.set(false);
    fixture.detectChanges();
    expect(knopf()).toBeNull();
  });

  it('öffnet das Feedback-Formular mit der Kategorie „gestoert“', () => {
    an.set(true);
    fixture.detectChanges();

    knopf()!.click();

    expect(dialog.open).toHaveBeenCalledOnceWith(
      FeedbackDialogComponent,
      jasmine.objectContaining({ data: { kategorie: 'gestoert' } })
    );
  });

  describe('Stichtag 31.12.2026 (UTC, wie GESTOERT_GELOESCHT_AB im Backend)', () => {
    it('liegt am 31.12.2026 um 00:00 UTC', () => {
      expect(new Date(FEEDBACK_GESTOERT_ENDE_MS).toISOString()).toBe('2026-12-31T00:00:00.000Z');
      expect(gestoertOffen(FEEDBACK_GESTOERT_ENDE_MS - 1)).toBeTrue();
      expect(gestoertOffen(FEEDBACK_GESTOERT_ENDE_MS)).toBeFalse();
    });

    it('zeigt den Knopf ab dem Stichtag nicht mehr, auch wenn ein alter Stand ihn als an meldet', () => {
      const spaeter = TestBed.createComponent(GestoertEinstiegComponent);
      spaeter.componentInstance.jetzt = () => FEEDBACK_GESTOERT_ENDE_MS;
      an.set(true);
      spaeter.detectChanges();
      expect((spaeter.nativeElement as HTMLElement).querySelector('[data-testid="gestoert-einstieg"]')).toBeNull();
    });

    it('zeigt ihn am Tag davor noch', () => {
      const vorher = TestBed.createComponent(GestoertEinstiegComponent);
      vorher.componentInstance.jetzt = () => FEEDBACK_GESTOERT_ENDE_MS - 1;
      an.set(true);
      vorher.detectChanges();
      expect((vorher.nativeElement as HTMLElement).querySelector('[data-testid="gestoert-einstieg"]')).not.toBeNull();
    });
  });
});
