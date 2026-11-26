import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';

import { FunktionenService } from '../../services/funktionen.service';
import { FeedbackDialogComponent } from './feedback-dialog.component';
import { GestoertEinstiegComponent } from './gestoert-einstieg.component';

describe('GestoertEinstiegComponent (Schalter feedback_gestoert)', () => {
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
    fixture.detectChanges();
  });

  function knopf(): HTMLButtonElement | null {
    return (fixture.nativeElement as HTMLElement).querySelector('[data-testid="gestoert-einstieg"]');
  }

  it('fragt den Schalter feedback_gestoert', () => {
    expect(gefragt).toEqual(['feedback_gestoert']);
  });

  it('ist bei ausgeschaltetem Schalter unsichtbar', () => {
    expect(knopf()).toBeNull();
    expect((fixture.nativeElement as HTMLElement).textContent?.trim()).toBe('');
  });

  it('erscheint beim Umschalten ohne Neuladen und verschwindet wieder', () => {
    an.set(true);
    fixture.detectChanges();
    expect(knopf()?.textContent).toContain('Was hat dich gestört?');

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
});
