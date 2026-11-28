import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import { environment } from '../../../environments/environment';
import { SaalSpruchListe } from '../../services/saal-spruch.service';
import { SaalSpruecheComponent, saalTag } from './saal-sprueche.component';

const URL = `${environment.baseUrl}/api/v1/moderation/saal-sprueche`;

function liste(teil: Partial<SaalSpruchListe> = {}): SaalSpruchListe {
  return {
    sprueche: [{ datum: '2026-12-04', text: 'Das bringt doch alles nichts.' }],
    schalter_wirksam: false,
    heute: '2026-12-04',
    text_max: 200,
    ...teil,
  };
}

describe('SaalSpruecheComponent', () => {
  let fixture: ComponentFixture<SaalSpruecheComponent>;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [SaalSpruecheComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideNoopAnimations(), provideRouter([])],
    });
    fixture = TestBed.createComponent(SaalSpruecheComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  it('zeigt die Sprüche ab heute mit Tag und Schalterstand', () => {
    http.expectOne(URL).flush(liste());
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;

    expect(el.querySelector('[data-testid="saal-sprueche-zustand"]')!.textContent).toContain('aus');
    const eintrag = el.querySelector('[data-testid="saal-spruch-eintrag"]')!;
    expect(eintrag.textContent).toContain('Fr 04.12.2026');
    expect(eintrag.textContent).toContain('heute');
    expect(eintrag.textContent).toContain('Das bringt doch alles nichts.');
  });

  it('legt einen Spruch je Tag fest, auch bei Schalter aus', () => {
    http.expectOne(URL).flush(liste({ sprueche: [] }));
    fixture.detectChanges();
    const komponente = fixture.componentInstance;
    komponente.datum = '2026-12-05';
    komponente.text = '  Klimaschutz kostet nur.  ';
    komponente.speichern();

    const anfrage = http.expectOne(`${URL}/2026-12-05`);
    expect(anfrage.request.method).toBe('PUT');
    expect(anfrage.request.body).toEqual({ text: 'Klimaschutz kostet nur.' });
    anfrage.flush(liste({ sprueche: [{ datum: '2026-12-05', text: 'Klimaschutz kostet nur.' }] }));
    fixture.detectChanges();

    expect(komponente.datum).toBe('');
    expect(fixture.nativeElement.textContent).toContain('Sa 05.12.2026');
  });

  for (const [treffer, warnt] of [[0, true], [3, false], [null, false]] as const) {
    it(`warnt nach dem Speichern bei ${treffer} Treffern: ${warnt} (Rundgang 2)`, () => {
      http.expectOne(URL).flush(liste({ sprueche: [] }));
      fixture.detectChanges();
      const komponente = fixture.componentInstance;
      komponente.datum = '2026-12-05';
      komponente.text = 'Klimaschutz kostet nur.';
      komponente.speichern();
      http.expectOne(`${URL}/2026-12-05`).flush(liste({ treffer_gespeichert: treffer }));
      fixture.detectChanges();

      const warnung = fixture.nativeElement.querySelector('[data-testid="saal-spruch-warnung"]') as HTMLElement;
      expect(warnung.getAttribute('role')).toBe('status');
      if (warnt) {
        expect(warnung.textContent).toContain('findet die Suche noch keine Antwort');
        expect(warnung.textContent).toContain('„Klimaschutz kostet nur.“');
      } else {
        expect(warnung.textContent!.trim()).toBe('');
      }
    });
  }

  it('entfernt einen Spruch und lädt die Liste neu', () => {
    http.expectOne(URL).flush(liste());
    fixture.detectChanges();
    fixture.componentInstance.entfernen({ datum: '2026-12-04', text: 'x' });

    const anfrage = http.expectOne(`${URL}/2026-12-04`);
    expect(anfrage.request.method).toBe('DELETE');
    anfrage.flush(null, { status: 204, statusText: 'No Content' });
    http.expectOne(URL).flush(liste({ sprueche: [] }));
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Ab heute kein Spruch festgelegt.');
  });

  it('Entfernen: Eintrag sofort weg, auch wenn das Nachladen scheitert', () => {
    http.expectOne(URL).flush(liste());
    fixture.detectChanges();
    fixture.componentInstance.entfernen({ datum: '2026-12-04', text: 'x' });
    http.expectOne(`${URL}/2026-12-04`).flush(null, { status: 204, statusText: 'No Content' });
    http.expectOne(URL).flush(null, { status: 502, statusText: 'Bad Gateway' });
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('[data-testid="saal-spruch-eintrag"]')).toBeNull();
  });

  it('„Ändern“ füllt das Formular und setzt den Fokus ins Textfeld', () => {
    http.expectOne(URL).flush(liste());
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;
    (el.querySelector('[data-testid="saal-spruch-eintrag"] button') as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(fixture.componentInstance.text).toBe('Das bringt doch alles nichts.');
    expect(document.activeElement).toBe(el.querySelector('[data-testid="saal-spruch-textfeld"]'));
  });

  it('„Suche ansehen“ zeigt, was „Antworten ansehen“ finden würde', () => {
    http.expectOne(URL).flush(liste());
    fixture.detectChanges();
    const link = fixture.nativeElement.querySelector('[data-testid="saal-spruch-suche"]') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe(`/result?searchQuery=${encodeURIComponent('Das bringt doch alles nichts.')}`);
  });

  it('ohne Tag oder Text kein Speichern', () => {
    http.expectOne(URL).flush(liste());
    const komponente = fixture.componentInstance;
    komponente.datum = '2026-12-05';
    komponente.text = '   ';
    expect(komponente.vollstaendig()).toBeFalse();
    komponente.speichern();
    http.expectNone(`${URL}/2026-12-05`);
  });

  it('saalTag', () => {
    http.expectOne(URL).flush(liste());
    expect(saalTag('2026-12-06')).toBe('So 06.12.2026');
  });
});
