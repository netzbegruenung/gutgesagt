import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';

import { TEILEN_NAVIGATOR, TeilenNavigator } from '../teilen.service';
import { SharepicDaten } from './sharepic';
import { SharepicDialogComponent } from './sharepic-dialog.component';

describe('SharepicDialogComponent (#756)', () => {
  const DATEN: SharepicDaten = {
    titel: 'Windkraft schafft Arbeitsplätze',
    text: 'Mehr Menschen arbeiten in der Windbranche als in der Kohle.',
    aussage: null,
    thema: null,
    link: 'https://gut-gesagt.example/beitrag/abc',
  };
  let fixture: ComponentFixture<SharepicDialogComponent>;
  let component: SharepicDialogComponent;
  let dialogRef: jasmine.SpyObj<MatDialogRef<SharepicDialogComponent>>;
  let nav: TeilenNavigator;

  async function erzeugen(navigator: TeilenNavigator): Promise<void> {
    nav = navigator;
    dialogRef = jasmine.createSpyObj('MatDialogRef', ['close']);
    await TestBed.configureTestingModule({
      imports: [SharepicDialogComponent, NoopAnimationsModule],
      providers: [
        { provide: MAT_DIALOG_DATA, useValue: DATEN },
        { provide: MatDialogRef, useValue: dialogRef },
        { provide: TEILEN_NAVIGATOR, useFactory: () => nav },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(SharepicDialogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    // Malen laeuft ueber Bild- und Schriftladen; warten, bis die Datei steht.
    for (let i = 0; i < 50 && !component.datei; i++) {
      await new Promise((r) => setTimeout(r, 20));
    }
    fixture.detectChanges();
  }

  const knopf = (klasse: string) => fixture.nativeElement.querySelector(`.${klasse}`) as HTMLButtonElement | null;

  it('zeigt Vorschau, Formatwahl mit Text und Herunterladen; ohne Datei-Teilen kein Teilen-Knopf', async () => {
    await erzeugen({});

    expect(component.datei).not.toBeNull();
    expect(fixture.nativeElement.querySelector('[data-testid="sharepic-vorschau"]')).not.toBeNull();
    const formate = Array.from(fixture.nativeElement.querySelectorAll('mat-button-toggle')).map((t: any) =>
      t.textContent.trim(),
    );
    expect(formate.join(' ')).toContain('Quadrat');
    expect(formate.join(' ')).toContain('Story');
    expect(knopf('sharepic-herunterladen')?.textContent).toContain('Bild herunterladen');
    expect(knopf('sharepic-teilen')).toBeNull();
  });

  it('teilt die Datei ueber das Teilen-Menue und meldet geteilt', async () => {
    const share = jasmine.createSpy('share').and.resolveTo();
    await erzeugen({ share, canShare: () => true });

    expect(knopf('sharepic-teilen')?.textContent).toContain('Bild teilen');
    await component.teilen();

    const daten = share.calls.mostRecent().args[0] as ShareData;
    expect(daten.files?.[0].type).toBe('image/png');
    expect(daten.text).toBe(DATEN.link);
    expect(dialogRef.close).toHaveBeenCalledWith('geteilt');
  });

  it('schliesst nach einem Abbruch im Teilen-Menue nicht', async () => {
    const abbruch = Object.assign(new Error('abgebrochen'), { name: 'AbortError' });
    await erzeugen({ share: jasmine.createSpy('share').and.rejectWith(abbruch), canShare: () => true });

    await component.teilen();

    expect(dialogRef.close).not.toHaveBeenCalled();
  });

  it('malt beim Formatwechsel neu', async () => {
    await erzeugen({});
    const vorher = component.datei;

    component.formatWaehlen('story');
    for (let i = 0; i < 50 && (!component.datei || component.datei === vorher); i++) {
      await new Promise((r) => setTimeout(r, 20));
    }

    expect(component.datei?.name).toBe('gut-gesagt-story.png');
  });
});
