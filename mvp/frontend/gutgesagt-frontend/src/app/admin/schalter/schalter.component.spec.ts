import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { SchalterComponent } from './schalter.component';
import { SaisonsComponent } from '../saisons/saisons.component';
import { Einstellung, Schalter } from '../../services/moderation.service';
import { environment } from '../../../environments/environment';

const URL = `${environment.baseUrl}/api/v1/moderation/schalter`;

function schalter(teil: Partial<Schalter> & { name: string }): Schalter {
  return {
    erklaerung: 'Was er tut.',
    umgebungsvariable: 'SEMANTIC_SEARCH_X_AKTIV',
    obergrenze: true,
    admin_wert: false,
    wirksam: false,
    dsfa_hinweis: null,
    ...teil,
  };
}

/** Die Saisons haben eine eigene Spec; hier ohne eigene Abrufe. */
@Component({ selector: 'app-saisons', standalone: true, template: '' })
class SaisonsStubComponent {}

const DSFA = 'Vor dem Einschalten auf Prod: DSFA beschlossen (docs/DSFA.md Abschnitt 7)';

describe('SchalterComponent', () => {
  let fixture: ComponentFixture<SchalterComponent>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SchalterComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideNoopAnimations()],
    })
      .overrideComponent(SchalterComponent, {
        remove: { imports: [SaisonsComponent] },
        add: { imports: [SaisonsStubComponent] },
      })
      .compileComponents();

    fixture = TestBed.createComponent(SchalterComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => {
    fixture.destroy();
    http.verify();
  });

  function karten(): HTMLElement[] {
    return Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('[data-testid="schalter"]'));
  }

  function knopf(karte: HTMLElement): HTMLButtonElement {
    return karte.querySelector('mat-slide-toggle button') as HTMLButtonElement;
  }

  function laden(liste: Schalter[]): void {
    http.expectOne(URL).flush({ schalter: liste });
    fixture.detectChanges();
  }

  it('zeigt je Schalter Name, Erklärung, Obergrenze und den DSFA-Hinweis', () => {
    laden([
      schalter({ name: 'punkte', dsfa_hinweis: DSFA }),
      schalter({ name: 'gepostet', obergrenze: false }),
    ]);

    const [punkte, gepostet] = karten();
    expect(punkte.textContent).toContain('Punkte und Meilensteine');
    expect(punkte.textContent).toContain('Was er tut.');
    expect(punkte.textContent).toContain('Server erlaubt: ja');
    expect(punkte.querySelector('[data-testid="dsfa-hinweis"]')!.textContent).toContain('DSFA beschlossen');
    expect(knopf(punkte).disabled).toBeFalse();

    expect(gepostet.textContent).toContain('Server erlaubt: nein');
    expect(gepostet.querySelector('[data-testid="gesperrt"]')).not.toBeNull();
    expect(gepostet.querySelector('[data-testid="dsfa-hinweis"]')).toBeNull();
    expect(knopf(gepostet).disabled).toBeTrue();
  });

  it('setzt beim Umschalten den Admin-Wert und zeigt den neuen Stand ohne Neuladen', () => {
    laden([schalter({ name: 'punkte' })]);

    knopf(karten()[0]).click();
    fixture.detectChanges();

    const anfrage = http.expectOne(`${URL}/punkte`);
    expect(anfrage.request.method).toBe('PUT');
    expect(anfrage.request.body).toEqual({ an: true });
    anfrage.flush({ schalter: [schalter({ name: 'punkte', admin_wert: true, wirksam: true })] });
    fixture.detectChanges();

    expect(karten()[0].textContent).toContain('Admin: an · wirksam: an');
    expect(knopf(karten()[0]).getAttribute('aria-checked')).toBe('true');
  });

  it('nennt dem Screenreader den Schalter und beschreibt den Zustand', () => {
    laden([schalter({ name: 'punkte', admin_wert: true, wirksam: true })]);

    const karte = karten()[0];
    const button = knopf(karte);
    expect(button.getAttribute('aria-label')).toBe('Punkte und Meilensteine, Admin');
    // Sichtbarer Text des Umschalters steckt im Namen (WCAG 2.5.3)
    expect(karte.querySelector('mat-slide-toggle')!.textContent!.trim()).toBe('Admin');
    const beschreibung = button.getAttribute('aria-describedby')!.split(' ');
    const zustand = karte.querySelector('[data-testid="zustand"]') as HTMLElement;
    expect(beschreibung).toContain(zustand.id);
    expect(zustand.textContent).toContain('wirksam: an');
  });

  it('erklärt, warum ein eingeschalteter Admin-Wert nicht wirkt', () => {
    laden([
      schalter({ name: 'punkte', admin_wert: false, wirksam: false }),
      schalter({ name: 'abzeichen_sichtbar', admin_wert: true, wirksam: false }),
      schalter({ name: 'gepostet', obergrenze: false, admin_wert: true, wirksam: false }),
    ]);

    const [punkte, abzeichen, gepostet] = karten().map(
      (k) => (k.querySelector('[data-testid="zustand"]') as HTMLElement).textContent!.trim(),
    );
    expect(punkte).toBe('Admin: aus · wirksam: aus');
    expect(abzeichen).toBe('Admin: an · wirksam: aus, weil Punkte aus');
    expect(gepostet).toBe('Admin: an · wirksam: aus (Server erlaubt nicht)');
    expect(knopf(karten()[2]).getAttribute('aria-checked')).toBe('true');
  });

  it('nimmt den Umschalter bei 409 zurück und zeigt die Erklärung', () => {
    laden([schalter({ name: 'gepostet' })]);

    knopf(karten()[0]).click();
    fixture.detectChanges();
    http
      .expectOne(`${URL}/gepostet`)
      .flush({ detail: 'Der Server erlaubt diesen Schalter nicht.' }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();

    expect(knopf(karten()[0]).getAttribute('aria-checked')).toBe('false');
    expect(document.body.textContent).toContain('Der Server erlaubt diesen Schalter nicht.');
  });

  it('zeigt die Schalter des Spielgefühls mit Namen und erklärt die Unterschalter', () => {
    laden([
      schalter({ name: 'kopiert_erfolg' }),
      schalter({ name: 'danke_knopf', admin_wert: false, wirksam: false }),
      schalter({ name: 'danke_ohne_konto', admin_wert: true, wirksam: false }),
      schalter({ name: 'punkte', admin_wert: false, wirksam: false }),
      schalter({ name: 'rangliste', admin_wert: true, wirksam: false }),
    ]);

    const [kopiert, , ohneKonto, , rangliste] = karten();
    expect(kopiert.querySelector('h3')!.textContent).toBe('Erfolgstext nach dem Kopieren');
    expect(ohneKonto.querySelector('h3')!.textContent).toBe('Danke-Knopf ohne Konto');
    const zustand = (k: HTMLElement) => (k.querySelector('[data-testid="zustand"]') as HTMLElement).textContent!.trim();
    expect(zustand(ohneKonto)).toBe('Admin: an · wirksam: aus, weil Danke-Knopf aus');
    expect(zustand(rangliste)).toBe('Admin: an · wirksam: aus, weil Punkte aus');
  });

  describe('Teams und aktuelle Saison', () => {
    const SAISON: Einstellung = {
      name: 'aktuelle_saison',
      erklaerung: 'Saison der Teams, die am Namen erscheinen.',
      wert: '2026',
      standard: '2026',
      max_laenge: 20,
    };

    function mitEinstellungen(liste: Schalter[], einstellungen: Einstellung[] = [SAISON]): void {
      http.expectOne(URL).flush({ schalter: liste, einstellungen });
      fixture.detectChanges();
    }

    function einstellung(): HTMLElement {
      return (fixture.nativeElement as HTMLElement).querySelector('[data-testid="einstellung"]') as HTMLElement;
    }

    it('zeigt die Schalter teams und teams_oeffentlich mit Namen', () => {
      mitEinstellungen([schalter({ name: 'teams' }), schalter({ name: 'teams_oeffentlich' })]);

      const [teams, oeffentlich] = karten();
      expect(teams.querySelector('h3')!.textContent).toBe('Teams über Einladungen');
      expect(oeffentlich.querySelector('h3')!.textContent).toBe('Teams am Anzeigenamen');
    });

    it('erklärt, warum teams_oeffentlich ohne Teams nicht wirkt', () => {
      mitEinstellungen([
        schalter({ name: 'teams', admin_wert: false, wirksam: false }),
        schalter({ name: 'teams_oeffentlich', admin_wert: true, wirksam: false }),
      ]);

      expect((karten()[1].querySelector('[data-testid="zustand"]') as HTMLElement).textContent!.trim()).toBe(
        'Admin: an · wirksam: aus, weil Teams aus',
      );
    });

    it('erklärt die Kette Teams → Team-Fortschritt → Team-Quests', () => {
      mitEinstellungen([
        schalter({ name: 'teams', admin_wert: false, wirksam: false }),
        schalter({ name: 'team_fortschritt', admin_wert: true, wirksam: false }),
        schalter({ name: 'team_quests', admin_wert: true, wirksam: false }),
      ]);

      const [, fortschritt, quests] = karten().map((k) =>
        (k.querySelector('[data-testid="zustand"]') as HTMLElement).textContent!.trim(),
      );
      expect(fortschritt).toBe('Admin: an · wirksam: aus, weil Teams aus');
      expect(quests).toBe('Admin: an · wirksam: aus, weil Team-Fortschritt aus');
    });

    it('sagt, wenn eine laufende Saison die Einstellung ersetzt (#782)', () => {
      const hinweis = 'Gilt gerade nicht: Die Saison „Winter 26“ ist die aktuelle Saison der Teams, bis die nächste beginnt (Abschnitt Saisons).';
      mitEinstellungen([schalter({ name: 'teams' })], [{ ...SAISON, hinweis }]);
      expect(einstellung().querySelector('[data-testid="einstellung-hinweis"]')!.textContent).toContain(hinweis);
    });

    it('ohne laufende Saison kein Hinweis an der Einstellung', () => {
      mitEinstellungen([schalter({ name: 'teams' })]);
      expect(einstellung().querySelector('[data-testid="einstellung-hinweis"]')).toBeNull();
    });

    it('zeigt die aktuelle Saison als Textfeld mit Standard und Grenze', async () => {
      mitEinstellungen([schalter({ name: 'teams' })]);
      // ngModel schreibt den Wert erst nach einem Mikrotask ins Feld (whenStable wartete auf den Nachlade-Takt)
      await Promise.resolve();
      fixture.detectChanges();

      const karte = einstellung();
      expect(karte.querySelector('h3')!.textContent).toBe('Aktuelle Saison');
      expect(karte.textContent).toContain('Saison der Teams, die am Namen erscheinen.');
      expect(karte.textContent).toContain('Standard: 2026');
      const feld = karte.querySelector('input') as HTMLInputElement;
      expect(feld.value).toBe('2026');
      expect(feld.maxLength).toBe(20);
      expect((karte.querySelector('[data-testid="einstellung-speichern"]') as HTMLButtonElement).disabled).toBeTrue();
    });

    it('speichert eine neue Saison und zeigt den Stand des Servers ohne Neuladen', () => {
      mitEinstellungen([schalter({ name: 'teams' })]);
      const k = fixture.componentInstance;
      k.entwuerfe['aktuelle_saison'] = ' 2027 ';
      k.einstellungSpeichern(k.einstellungen[0]);

      const anfrage = http.expectOne(`${URL}/einstellungen/aktuelle_saison`);
      expect(anfrage.request.method).toBe('PUT');
      expect(anfrage.request.body).toEqual({ wert: '2027' });
      anfrage.flush({ schalter: [schalter({ name: 'teams' })], einstellungen: [{ ...SAISON, wert: '2027' }] });
      fixture.detectChanges();

      expect(einstellung().querySelector('[data-testid="einstellung-stand"]')!.textContent).toContain('Gespeichert: 2027');
      expect(k.entwuerfe['aktuelle_saison']).toBe('2027');
    });

    it('meldet einen ungültigen Wert (422)', () => {
      mitEinstellungen([schalter({ name: 'teams' })]);
      const k = fixture.componentInstance;
      k.entwuerfe['aktuelle_saison'] = 'x';
      k.einstellungSpeichern(k.einstellungen[0]);

      http
        .expectOne(`${URL}/einstellungen/aktuelle_saison`)
        .flush({ detail: 'Ungueltiger Wert' }, { status: 422, statusText: 'Unprocessable Entity' });
      fixture.detectChanges();

      expect(document.body.textContent).toContain('Ungültiger Wert');
      expect(k.entwuerfe['aktuelle_saison']).toBe('x');
    });

    it('überschreibt beim Nachladen keine angefangene Eingabe', () => {
      mitEinstellungen([schalter({ name: 'teams' })]);
      const k = fixture.componentInstance;
      k.entwuerfe['aktuelle_saison'] = 'Winter';
      (k as unknown as { uebernehmen(d: unknown): void }).uebernehmen({
        schalter: [schalter({ name: 'teams' })],
        einstellungen: [{ ...SAISON, wert: '2028' }],
      });

      expect(k.entwuerfe['aktuelle_saison']).toBe('Winter');
    });
  });
});
