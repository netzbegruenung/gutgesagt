import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MAT_BOTTOM_SHEET_DATA, MatBottomSheetRef } from '@angular/material/bottom-sheet';
import { of, throwError } from 'rxjs';

import { EinwurfThemenSheetComponent, EinwurfThemenSheetDaten } from './einwurf-themen-sheet.component';
import { EinwurfService } from '../services/einwurf.service';
import { ThemenService } from '../services/themen.service';

const KLIMA = { schluessel: 'klima', name: 'Klima', motiv: 'themen/klima.svg' };
const VERKEHR = { schluessel: 'verkehr', name: 'Verkehr', motiv: 'themen/verkehr.svg' };
const EUROPA = { schluessel: 'europa', name: 'Europa', motiv: 'themen/europa.svg' };

describe('EinwurfThemenSheetComponent', () => {
  let fixture: ComponentFixture<EinwurfThemenSheetComponent>;
  let einwurfService: jasmine.SpyObj<EinwurfService>;
  let sheet: jasmine.SpyObj<MatBottomSheetRef<EinwurfThemenSheetComponent, boolean>>;

  function zeigen(daten: EinwurfThemenSheetDaten = { einwurfId: 'e-1', themen: [KLIMA], titel: 'Guter Thread' }): HTMLElement {
    einwurfService = jasmine.createSpyObj('EinwurfService', ['themenSetzen']);
    sheet = jasmine.createSpyObj('MatBottomSheetRef', ['dismiss']);
    TestBed.configureTestingModule({
      imports: [EinwurfThemenSheetComponent],
      providers: [
        { provide: MAT_BOTTOM_SHEET_DATA, useValue: daten },
        { provide: MatBottomSheetRef, useValue: sheet },
        { provide: EinwurfService, useValue: einwurfService },
        { provide: ThemenService, useValue: { liste: () => of([KLIMA, VERKEHR, EUROPA]) } },
      ],
    });
    fixture = TestBed.createComponent(EinwurfThemenSheetComponent);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  const chip = (e: HTMLElement, name: string) =>
    (Array.from(e.querySelectorAll('.thema-chip')) as HTMLButtonElement[]).find((k) => k.textContent?.trim() === name)!;

  it('zeigt die Auswahl gleich offen, mit dem Einwurf und hoechstens zwei', () => {
    const e = zeigen();

    expect(e.querySelector('.sheet-titel')!.textContent).toContain('Themen ändern');
    expect(e.querySelector('.sheet-einwurf')!.textContent).toContain('Guter Thread');
    expect(e.querySelector('.themen-umschalter')).toBeNull();
    expect(chip(e, 'Klima').getAttribute('aria-pressed')).toBe('true');
    expect(e.querySelector('.themen-hinweis')!.textContent).toContain('Bis zu zwei Themen');
  });

  it('speichert jeden Klick gleich und meldet beim Schliessen die Aenderung', () => {
    const e = zeigen();
    einwurfService.themenSetzen.and.returnValue(of({ id: 'e-1', themen: [KLIMA, VERKEHR] } as any));

    chip(e, 'Verkehr').click();
    fixture.detectChanges();

    expect(einwurfService.themenSetzen).toHaveBeenCalledOnceWith('e-1', ['klima', 'verkehr']);
    expect(chip(e, 'Verkehr').getAttribute('aria-pressed')).toBe('true');
    // Zwei gewaehlt: ein drittes geht erst nach dem Abwaehlen
    expect(chip(e, 'Europa').disabled).toBeTrue();
    expect(e.textContent).toContain('Themen gespeichert.');

    (e.querySelector('.fertig') as HTMLButtonElement).click();
    expect(sheet.dismiss).toHaveBeenCalledOnceWith(true);
  });

  it('schliesst ohne Aenderung mit false', () => {
    const e = zeigen();

    (e.querySelector('.fertig') as HTMLButtonElement).click();

    expect(sheet.dismiss).toHaveBeenCalledOnceWith(false);
  });

  it('nennt die fehlende Zustimmung zu den Nutzungsbedingungen', () => {
    const e = zeigen();
    einwurfService.themenSetzen.and.returnValue(
      throwError(() => ({ status: 403, error: { detail: 'nutzungsbedingungen_fehlen' } })),
    );

    chip(e, 'Verkehr').click();
    fixture.detectChanges();

    expect(e.querySelector('.themen-fehler')!.textContent).toContain('Nutzungsbedingungen');
    expect(chip(e, 'Verkehr').getAttribute('aria-pressed')).toBe('false');
  });
});
