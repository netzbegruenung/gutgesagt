import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideAnimations } from '@angular/platform-browser/animations';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { FeedbackDialogComponent } from './feedback-dialog.component';
import { environment } from '../../../environments/environment';

const URL = `${environment.baseUrl}/api/v1/feedback/senden`;

describe('FeedbackDialogComponent', () => {
  let fixture: ComponentFixture<FeedbackDialogComponent>;
  let http: HttpTestingController;
  let dialogRef: jasmine.SpyObj<MatDialogRef<FeedbackDialogComponent>>;

  beforeEach(async () => {
    dialogRef = jasmine.createSpyObj('MatDialogRef', ['close']);
    await TestBed.configureTestingModule({
      imports: [FeedbackDialogComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideAnimations(),
        { provide: MatDialogRef, useValue: dialogRef },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FeedbackDialogComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function element(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  async function eingeben(selektor: string, wert: string) {
    const feld = element().querySelector(selektor) as HTMLInputElement | HTMLTextAreaElement;
    feld.value = wert;
    feld.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    await fixture.whenStable();
  }

  function sendenKnopf(): HTMLButtonElement {
    return element().querySelector('[data-testid="feedback-senden"]') as HTMLButtonElement;
  }

  it('sendet erst, wenn ein Text dasteht', async () => {
    expect(sendenKnopf().disabled).toBeTrue();

    await eingeben('textarea[name="text"]', '   ');
    expect(sendenKnopf().disabled).toBeTrue();

    await eingeben('textarea[name="text"]', 'Die Suche ist toll');
    expect(sendenKnopf().disabled).toBeFalse();
  });

  it('sendet Text und Kontakt und bedankt sich', async () => {
    await eingeben('textarea[name="text"]', 'Kopieren klappt mobil nicht');
    await eingeben('input[name="kontakt"]', 'anna@example.org');

    sendenKnopf().click();
    const anfrage = http.expectOne(URL);
    expect(anfrage.request.method).toBe('POST');
    expect(anfrage.request.body).toEqual({ text: 'Kopieren klappt mobil nicht', kontakt: 'anna@example.org' });
    anfrage.flush({ success: true }, { status: 201, statusText: 'Created' });
    fixture.detectChanges();

    expect(element().textContent).toContain('Danke');
    expect(element().querySelector('textarea')).toBeNull();
  });

  it('schickt ohne Kontakt keinen mit', async () => {
    await eingeben('textarea[name="text"]', 'Gefällt mir');

    sendenKnopf().click();
    const anfrage = http.expectOne(URL);
    expect(anfrage.request.body).toEqual({ text: 'Gefällt mir', kontakt: null });
    anfrage.flush({ success: true });
  });

  it('sagt vor dem Senden, was gespeichert wird und wann es geloescht wird', () => {
    const text = element().textContent ?? '';
    expect(text).toContain('optional');
    expect(text).toContain('180 Tagen');
    expect(text).toContain('dein Konto nicht mitgespeichert');
  });

  it('behaelt den Text, wenn das Senden scheitert', async () => {
    await eingeben('textarea[name="text"]', 'Mein langer Text');

    sendenKnopf().click();
    http.expectOne(URL).flush('kaputt', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    await fixture.whenStable();

    expect(element().textContent).toContain('nicht gesendet');
    expect((element().querySelector('textarea') as HTMLTextAreaElement).value).toBe('Mein langer Text');
    expect(dialogRef.close).not.toHaveBeenCalled();
  });

  it('nennt das Limit, wenn zu viel in kurzer Zeit kommt', async () => {
    await eingeben('textarea[name="text"]', 'Noch eins');

    sendenKnopf().click();
    http.expectOne(URL).flush('zu viel', { status: 429, statusText: 'Too Many Requests' });
    fixture.detectChanges();

    expect(element().textContent).toContain('ein paar Minuten');
  });

  it('Abbrechen schliesst ohne zu senden', () => {
    (element().querySelector('[data-testid="feedback-abbrechen"]') as HTMLButtonElement).click();

    expect(dialogRef.close).toHaveBeenCalled();
    http.expectNone(URL);
  });

  it('ist ohne Vorbelegung leer', () => {
    expect(fixture.componentInstance.text).toBe('');
  });
});

describe('FeedbackDialogComponent mit Vorbelegung (Warteliste, Designrunde 17.11.)', () => {
  it('belegt das Textfeld mit dem uebergebenen Text vor', async () => {
    await TestBed.configureTestingModule({
      imports: [FeedbackDialogComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideAnimations(),
        { provide: MatDialogRef, useValue: jasmine.createSpyObj('MatDialogRef', ['close']) },
        { provide: MAT_DIALOG_DATA, useValue: { text: 'Warteliste bitte' } },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(FeedbackDialogComponent);
    fixture.detectChanges();
    await fixture.whenStable();

    expect(fixture.componentInstance.text).toBe('Warteliste bitte');
    expect(fixture.componentInstance.kannSenden).toBeTrue();
  });
});

describe('FeedbackDialogComponent als „Was hat dich gestört?“ (Schalter feedback_gestoert)', () => {
  let fixture: ComponentFixture<FeedbackDialogComponent>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FeedbackDialogComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideAnimations(),
        { provide: MatDialogRef, useValue: jasmine.createSpyObj('MatDialogRef', ['close']) },
        { provide: MAT_DIALOG_DATA, useValue: { kategorie: 'gestoert' } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(FeedbackDialogComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    await fixture.whenStable();
  });

  afterEach(() => http.verify());

  function element(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  async function senden(text: string) {
    const feld = element().querySelector('textarea[name="text"]') as HTMLTextAreaElement;
    feld.value = text;
    feld.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    await fixture.whenStable();
    (element().querySelector('[data-testid="feedback-senden"]') as HTMLButtonElement).click();
  }

  it('fragt „Was hat dich gestört?“ mit dem Hinweis wörtlich und ohne Kontaktfeld', () => {
    expect(element().querySelector('h2')?.textContent).toContain('Was hat dich gestört?');
    expect(element().querySelector('[data-testid="feedback-keine-namen"]')?.textContent?.trim()).toBe(
      'Bitte keine Namen oder Daten anderer.'
    );
    expect(element().querySelector('input[name="kontakt"]')).toBeNull();
  });

  it('nennt den Löschtag statt der 180 Tage', () => {
    const text = (element().textContent ?? '').replace(/\s+/g, ' ');
    expect(text).toContain('Am 31.12.2026 wird alles gelöscht');
    expect(text).not.toContain('180 Tagen');
    expect(text).toContain('dein Konto nicht mitgespeichert');
  });

  it('sendet nur den Text mit der Kategorie, ohne Kontakt', async () => {
    await senden('Die Suche war langsam');

    const anfrage = http.expectOne(URL);
    expect(anfrage.request.body).toEqual({ text: 'Die Suche war langsam', kontakt: null, kategorie: 'gestoert' });
    anfrage.flush({ success: true }, { status: 201, statusText: 'Created' });
    fixture.detectChanges();
    expect(element().textContent).toContain('Danke');
  });

  it('sagt bei 409, dass der Knopf gerade aus ist, und nennt den anderen Weg', async () => {
    await senden('Noch was');

    http.expectOne(URL).flush('aus', { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();

    expect(element().textContent).toContain('Dieser Knopf ist gerade aus');
    expect(element().textContent).toContain('„Feedback“ im Menü „Mehr“');
  });
});
