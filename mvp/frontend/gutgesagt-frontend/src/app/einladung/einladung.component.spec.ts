import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { EINLOESEN_NEUVERSUCHE, EinladungComponent, codeAusEingabe } from './einladung.component';
import { NEUVERSUCH_HOECHSTENS_MS } from '../shared/neuversuch';
import { environment } from '../../environments/environment';

const URL = `${environment.baseUrl}/api/v1/einladungen`;
const SITZUNG = `${environment.baseUrl}/api/check-session`;

describe('EinladungComponent', () => {
  let fixture: ComponentFixture<EinladungComponent>;
  let http: HttpTestingController;

  function starten(fragment: string | null) {
    TestBed.configureTestingModule({
      imports: [EinladungComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideNoopAnimations(),
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { fragment } } },
      ],
    });
    fixture = TestBed.createComponent(EinladungComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  }

  afterEach(() => {
    http.verify();
    localStorage.clear();
  });

  function el(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  /** /pruefen und die Sitzung kommen zusammen; ohne Team und abgemeldet wie vor den Teams. */
  function pruefen(einloesbar: boolean) {
    const anfrage = http.expectOne(`${URL}/pruefen`);
    expect(anfrage.request.body).toEqual({ code: 'Code123' });
    anfrage.flush({ einloesbar });
    http.expectOne(SITZUNG).flush({ isAuthenticated: false });
    fixture.detectChanges();
  }

  function absenden(email: string, vorname = 'Anna', nachname = 'Beispiel') {
    fixture.componentInstance.email = email;
    fixture.componentInstance.vorname = vorname;
    fixture.componentInstance.nachname = nachname;
    fixture.componentInstance.einloesen();
    return http.expectOne(`${URL}/einloesen`);
  }

  it('ohne Code im Link fragt die Seite nach dem Link, statt "gilt nicht" zu melden', () => {
    starten(null);

    expect(el().textContent).not.toContain('gilt nicht');
    expect(el().querySelector('input[name="link"]')).not.toBeNull();
    expect(el().querySelector('input[type="email"]')).toBeNull();
  });

  it('nimmt den eingefuegten Link, prueft den Code und zeigt dann das Formular', () => {
    starten(null);
    fixture.componentInstance.link = `  ${window.location.origin}/einladung#Code123\n`;
    fixture.componentInstance.linkUebernehmen();
    fixture.detectChanges();

    pruefen(true);
    expect(el().querySelector('input[type="email"]')).not.toBeNull();
  });

  it('meldet einen Link, der keiner einer Einladung sein kann, ohne Anfrage', () => {
    starten(null);
    fixture.componentInstance.link = 'https://example.org/einladung#Code mit / Zeichen?';
    fixture.componentInstance.linkUebernehmen();
    fixture.detectChanges();

    http.expectNone(`${URL}/pruefen`);
    expect(el().querySelector('[role="alert"]')?.textContent).toContain('kein Link einer Einladung');
  });

  it('nach einer Einladung, die nicht gilt, laesst sich ein anderer Link einfuegen', async () => {
    starten('Code123');
    pruefen(false);
    const knopf = Array.from(el().querySelectorAll('button')).find((b) => b.textContent?.includes('Anderen Link'));
    knopf!.click();
    fixture.detectChanges();
    await fixture.whenStable();

    expect(el().querySelector('input[name="link"]')).not.toBeNull();
    // Der Fokus steht im Feld, nicht auf dem verschwundenen Knopf (Tastatur, Screenreader)
    expect(document.activeElement).toBe(el().querySelector('input[name="link"]'));
  });

  it('setzt beim ersten Aufruf ohne Code den Fokus nicht von selbst ins Feld', async () => {
    starten(null);
    await fixture.whenStable();

    expect(document.activeElement).not.toBe(el().querySelector('input[name="link"]'));
  });

  it('eine ungueltige Einladung zeigt kein Formular', () => {
    starten('Code123');
    pruefen(false);

    expect(el().textContent).toContain('gilt nicht');
    expect(el().querySelector('input[type="email"]')).toBeNull();
  });

  it('legt mit Name und Mail-Adresse ein Konto an und verweist auf die Mail', () => {
    starten('Code123');
    pruefen(true);
    expect(el().querySelector('input[type="email"]')).not.toBeNull();

    const anfrage = absenden('neu@example.org', ' Anna Maria ', 'Beispiel ');
    expect(anfrage.request.body).toEqual({
      code: 'Code123',
      email: 'neu@example.org',
      vorname: 'Anna Maria',
      nachname: 'Beispiel',
    });
    anfrage.flush({ success: true }, { status: 202, statusText: 'Accepted' });
    fixture.detectChanges();

    expect(el().textContent).toContain('Postfach');
    expect(el().textContent).toContain('Passwort vergessen');
  });

  it('meldet, wenn die Einladung inzwischen nicht mehr gilt', () => {
    starten('Code123');
    pruefen(true);

    absenden('neu@example.org').flush('weg', { status: 410, statusText: 'Gone' });
    fixture.detectChanges();

    expect(el().textContent).toContain('gilt nicht');
  });

  it('meldet einen Fehler beim Anlegen nach den Neuversuchen und laesst es erneut versuchen', fakeAsync(() => {
    starten('Code123');
    pruefen(true);

    absenden('neu@example.org').flush('kaputt', { status: 502, statusText: 'Bad Gateway' });
    for (let i = 0; i < EINLOESEN_NEUVERSUCHE; i++) {
      tick(NEUVERSUCH_HOECHSTENS_MS);
      http.expectOne(`${URL}/einloesen`).flush('kaputt', { status: 502, statusText: 'Bad Gateway' });
    }
    fixture.detectChanges();

    expect(el().textContent).toContain('hat nicht geklappt');
    expect(el().querySelector('input[type="email"]')).not.toBeNull();
    tick(NEUVERSUCH_HOECHSTENS_MS);
    http.expectNone(`${URL}/einloesen`);
  }));

  it('fragt Vor- und Nachname mit sichtbarer Beschriftung und Autofill ab', () => {
    starten('Code123');
    pruefen(true);

    const vorname = el().querySelector<HTMLInputElement>('input[name="vorname"]')!;
    const nachname = el().querySelector<HTMLInputElement>('input[name="nachname"]')!;
    expect(vorname.getAttribute('autocomplete')).toBe('given-name');
    expect(nachname.getAttribute('autocomplete')).toBe('family-name');
    expect(vorname.getAttribute('aria-describedby')).toContain('name-hinweis');
    expect(nachname.getAttribute('aria-describedby')).toContain('name-hinweis');
    expect(el().querySelector('#name-hinweis')?.textContent).toContain(
      'Du kannst auch einen anderen Namen angeben; wir zeigen ihn als ‚Vorname N.‘ an.',
    );
    const labels = Array.from(el().querySelectorAll('mat-label')).map((l) => l.textContent?.trim());
    expect(labels).toEqual(jasmine.arrayContaining(['Vorname', 'Nachname', 'Mail-Adresse']));
  });

  it('laesst ohne Namen nicht absenden', () => {
    starten('Code123');
    pruefen(true);
    fixture.componentInstance.email = 'neu@example.org';
    fixture.detectChanges();

    const knopf = Array.from(el().querySelectorAll('button')).find((b) => b.textContent?.includes('Konto anlegen'));
    // Aktiv, sagt aber beim Klick, was fehlt (Rundgang 2, V8a)
    expect(knopf!.disabled).toBeFalse();
    knopf!.click();
    fixture.detectChanges();
    http.expectNone(`${URL}/einloesen`);
    const meldung = el().querySelector('[data-testid="felder-fehlen"]')!;
    expect(meldung.getAttribute('role')).toBe('alert');
    expect(meldung.textContent).toContain('Es fehlt noch: Vorname, Nachname.');
    expect(document.activeElement).toBe(el().querySelector('input[name="vorname"]'));
    expect(el().querySelector('input[name="vorname"]')!.getAttribute('aria-invalid')).toBe('true');
    expect(el().querySelector('input[name="email"]')!.getAttribute('aria-invalid')).toBeNull();

    // Nachgetragen: Die Liste schrumpft mit
    fixture.componentInstance.vorname = 'Anna';
    fixture.componentInstance.feldGeaendert();
    fixture.detectChanges();
    expect(meldung.textContent).toContain('Es fehlt noch: Nachname.');
  });

  it('meldet Zeichen im Namen, die Keycloak ablehnt, ohne Anfrage', () => {
    starten('Code123');
    pruefen(true);
    fixture.componentInstance.email = 'neu@example.org';
    fixture.componentInstance.vorname = 'Anna!';
    fixture.componentInstance.nachname = 'Beispiel';
    fixture.componentInstance.einloesen();
    fixture.detectChanges();

    http.expectNone(`${URL}/einloesen`);
    expect(el().querySelector('[role="alert"]')?.textContent).toContain('prüf deinen Namen');
    expect(el().querySelector('input[name="vorname"]')?.getAttribute('aria-invalid')).toBe('true');
  });

  it('sagt bei 422 zum Namen, dass der Name nicht passt, nicht die Adresse', () => {
    starten('Code123');
    pruefen(true);

    absenden('neu@example.org').flush(
      { detail: [{ loc: ['body', 'nachname'], msg: 'Value error' }] },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    fixture.detectChanges();

    expect(el().textContent).toContain('prüf deinen Namen');
    expect(el().textContent).not.toContain('nicht wie eine Mail-Adresse');
  });

  // 429 und andere vorübergehende Fehler versucht die Seite selbst noch einmal (einladung-neuversuch.component.spec.ts).
  for (const [status, antwort, text] of [
    [422, 'nein', 'nicht wie eine Mail-Adresse'],
    [503, { detail: 'Registration not configured' }, 'noch nicht anlegen'],
  ] as const) {
    it(`sagt bei ${status}, woran es liegt`, () => {
      starten('Code123');
      pruefen(true);

      absenden('neu@example.org').flush(antwort, { status, statusText: 'Fehler' });
      fixture.detectChanges();
      http.expectNone(`${URL}/einloesen`);

      expect(el().textContent).toContain(text);
      expect(el().textContent).not.toContain('hat nicht geklappt');
    });
  }

  it('sagt den Stand in einer Live-Region an, die immer da ist', () => {
    starten('Code123');
    const region = el().querySelector('[role="status"]');
    expect(region?.textContent).toContain('wird geprüft');

    pruefen(false);

    expect(el().querySelector('[role="status"]')).toBe(region);
    expect(region?.textContent).toContain('gilt nicht');
  });
});

describe('codeAusEingabe', () => {
  it('nimmt das Stueck hinter # aus dem ganzen Link', () => {
    expect(codeAusEingabe('https://gutgesagt.example/einladung#Ab-c_123')).toBe('Ab-c_123');
  });

  it('nimmt einen Code ohne Link, ohne Leerraum und Umbrueche', () => {
    expect(codeAusEingabe(' Ab-c\n_123 ')).toBe('Ab-c_123');
  });

  it('gibt null fuer Leeres, fremde Zeichen und zu Langes', () => {
    expect(codeAusEingabe('')).toBeNull();
    expect(codeAusEingabe('https://gutgesagt.example/einladung#')).toBeNull();
    expect(codeAusEingabe('https://gutgesagt.example/einladung')).toBeNull();
    expect(codeAusEingabe('a'.repeat(65))).toBeNull();
  });
});
