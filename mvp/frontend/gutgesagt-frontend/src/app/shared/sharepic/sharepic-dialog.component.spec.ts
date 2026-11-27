import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';

import { TEILEN_NAVIGATOR, TeilenNavigator } from '../teilen.service';
import { SHAREPIC_ZEITGRENZE_MS, SharepicDaten, SharepicLader } from './sharepic';
import { SHAREPIC_LADER, SHAREPIC_TEXTE, SharepicDialogComponent } from './sharepic-dialog.component';

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

  /** Ohne Netz und Schriftladen (#819): das Logo fehlt, die Schriften gelten als geladen. */
  const SCHNELL: SharepicLader = { bild: () => Promise.resolve(null), schriften: () => Promise.resolve() };

  /**
   * Malen laeuft ueber toBlob; auf einem ausgelasteten CI-Runner
   * dauert das laenger als eine Sekunde. Deshalb nach Uhrzeit warten statt nach Durchlaeufen,
   * mit Luft unter der Zeitgrenze der Tests (ZEITGRENZE_MS).
   */
  const MALEN_WARTEN_MS = 8000;
  const ZEITGRENZE_MS = 15000;
  async function warten(bis: () => boolean): Promise<void> {
    const ende = Date.now() + MALEN_WARTEN_MS;
    while (!bis() && Date.now() < ende) {
      await new Promise((r) => setTimeout(r, 20));
    }
  }

  function einrichten(navigator: TeilenNavigator, lader: SharepicLader): void {
    nav = navigator;
    dialogRef = jasmine.createSpyObj('MatDialogRef', ['close']);
    TestBed.configureTestingModule({
      imports: [SharepicDialogComponent, NoopAnimationsModule],
      providers: [
        { provide: MAT_DIALOG_DATA, useValue: DATEN },
        { provide: MatDialogRef, useValue: dialogRef },
        { provide: TEILEN_NAVIGATOR, useFactory: () => nav },
        { provide: SHAREPIC_LADER, useValue: lader },
      ],
    });
  }

  async function erzeugen(navigator: TeilenNavigator): Promise<void> {
    einrichten(navigator, SCHNELL);
    await TestBed.compileComponents();
    fixture = TestBed.createComponent(SharepicDialogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    // Warten, bis die Datei steht.
    await warten(() => !!component.datei);
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
  }, ZEITGRENZE_MS);

  it('teilt die Datei ueber das Teilen-Menue und meldet geteilt', async () => {
    const share = jasmine.createSpy('share').and.resolveTo();
    await erzeugen({ share, canShare: () => true });

    expect(knopf('sharepic-teilen')?.textContent).toContain('Bild teilen');
    await component.teilen();

    const daten = share.calls.mostRecent().args[0] as ShareData;
    expect(daten.files?.[0].type).toBe('image/png');
    expect(daten.text).toBe(DATEN.link);
    expect(dialogRef.close).toHaveBeenCalledWith('geteilt');
  }, ZEITGRENZE_MS);

  it('schliesst nach einem Abbruch im Teilen-Menue nicht', async () => {
    const abbruch = Object.assign(new Error('abgebrochen'), { name: 'AbortError' });
    await erzeugen({ share: jasmine.createSpy('share').and.rejectWith(abbruch), canShare: () => true });

    await component.teilen();

    expect(dialogRef.close).not.toHaveBeenCalled();
  }, ZEITGRENZE_MS);

  it('malt beim Formatwechsel neu', async () => {
    await erzeugen({});
    const vorher = component.datei;

    component.formatWaehlen('story');
    await warten(() => !!component.datei && component.datei !== vorher);

    expect(component.datei?.name).toBe('gut-gesagt-story.png');
  }, ZEITGRENZE_MS);

  it('meldet nach der Zeitgrenze freundlich und malt mit Noch einmal versuchen neu (#819)', fakeAsync(() => {
    const bild = jasmine.createSpy('bild').and.callFake(() => new Promise(() => undefined));
    einrichten({}, { bild, schriften: () => Promise.resolve() });
    fixture = TestBed.createComponent(SharepicDialogComponent);
    component = fixture.componentInstance;
    const meldung = () => fixture.nativeElement.querySelector('[role="alert"]') as HTMLElement | null;
    fixture.detectChanges();

    tick(SHAREPIC_ZEITGRENZE_MS - 1);
    fixture.detectChanges();
    expect(component.laedt).toBeTrue();
    expect(meldung()).toBeNull();

    tick(1);
    fixture.detectChanges();
    expect(component.laedt).toBeFalse();
    expect(meldung()?.textContent).toContain(SHAREPIC_TEXTE.zuLangsam);
    expect(meldung()?.textContent).not.toContain('neu laden');
    expect(knopf('sharepic-herunterladen')?.disabled).toBeTrue();

    knopf('sharepic-nochmal')!.click();
    fixture.detectChanges();
    expect(knopf('sharepic-nochmal')).toBeNull();
    expect(fixture.nativeElement.querySelector('[role="status"]')?.textContent).toContain(SHAREPIC_TEXTE.laedt);
    expect(bild).toHaveBeenCalledTimes(2);

    tick(SHAREPIC_ZEITGRENZE_MS);
    fixture.detectChanges();
    expect(knopf('sharepic-nochmal')?.textContent).toContain('Noch einmal versuchen');
  }));
});
