import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { SchalterComponent } from './schalter.component';
import { SaisonsComponent } from '../saisons/saisons.component';
import { SaalSpruecheComponent } from '../saal-sprueche/saal-sprueche.component';
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
    gruppe: 'Einzelschalter',
    wartet_auf_recht: false,
    ...teil,
  };
}

/** Die Saisons haben eine eigene Spec; hier ohne eigene Abrufe. */
@Component({ selector: 'app-saisons', standalone: true, template: '' })
class SaisonsStubComponent {}

/** Die Saal-Sprüche ebenso. */
@Component({ selector: 'app-saal-sprueche', standalone: true, template: '' })
class SaalSpruecheStubComponent {}

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
        remove: { imports: [SaisonsComponent, SaalSpruecheComponent] },
        add: { imports: [SaisonsStubComponent, SaalSpruecheStubComponent] },
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
      schalter({ name: 'spielgefuehl_buehne', gruppe: 'Pakete', dsfa_hinweis: DSFA }),
      schalter({ name: 'merkliste', gruppe: 'Einzelschalter', obergrenze: false }),
    ]);

    const [spiel, merkliste] = karten();
    expect(spiel.textContent).toContain('Paket Spielgefühl');
    expect(spiel.textContent).toContain('Was er tut.');
    expect(spiel.textContent).toContain('Server erlaubt: ja');
    expect(spiel.querySelector('[data-testid="dsfa-hinweis"]')!.textContent).toContain('DSFA beschlossen');
    expect(knopf(spiel).disabled).toBeFalse();

    expect(merkliste.textContent).toContain('Server erlaubt: nein');
    expect(merkliste.querySelector('[data-testid="gesperrt"]')).not.toBeNull();
    expect(merkliste.querySelector('[data-testid="dsfa-hinweis"]')).toBeNull();
    expect(knopf(merkliste).disabled).toBeTrue();
  });

  it('zeigt einen eigenen Einschalt-Hinweis des Servers statt des allgemeinen DSFA-Hinweises', () => {
    const teams = 'Rechtlich freigegeben (Go des Vorstands 27.11.); Team-Summe erst ab 5 Mitgliedern mit Einwilligung.';
    laden([
      schalter({ name: 'teams', gruppe: 'Pakete', dsfa_hinweis: teams }),
      schalter({ name: 'teams_oeffentlich', gruppe: 'Einzelschalter', dsfa_hinweis: DSFA }),
    ]);

    const [t, oeffentlich] = karten();
    expect(t.querySelector('[data-testid="dsfa-hinweis"]')!.textContent).toContain(teams);
    expect(t.querySelector('[data-testid="dsfa-hinweis"]')!.textContent).not.toContain('DSFA beschlossen');
    expect(oeffentlich.querySelector('[data-testid="dsfa-hinweis"]')!.textContent).toContain('DSFA beschlossen');
  });

  // Schalter-Umbau 27.11.: vier Pakete, sieben Einzelschalter, Gruppen vom Server
  it('zeigt die vier Pakete und die sieben Einzelschalter mit Namen', () => {
    laden([
      schalter({ name: 'teams', gruppe: 'Pakete' }),
      schalter({ name: 'spielgefuehl_buehne', gruppe: 'Pakete' }),
      schalter({ name: 'wirkungs_echo', gruppe: 'Pakete' }),
      schalter({ name: 'k_begruessung', gruppe: 'Pakete' }),
      schalter({ name: 'team_quests', gruppe: 'Einzelschalter' }),
      schalter({ name: 'muster_stimmen', gruppe: 'Einzelschalter' }),
      schalter({ name: 'teams_oeffentlich', gruppe: 'Einzelschalter' }),
      schalter({ name: 'merkliste', gruppe: 'Einzelschalter' }),
      schalter({ name: 'aufrufe_zaehlen', gruppe: 'Einzelschalter' }),
      schalter({ name: 'danke_ohne_konto', gruppe: 'Einzelschalter' }),
      schalter({ name: 'k_ankuenfte', gruppe: 'Einzelschalter' }),
    ]);

    expect(karten().map((k) => k.querySelector('h4')!.textContent)).toEqual([
      'Paket Teams',
      'Paket Spielgefühl',
      'Paket Wirkungs-Echo',
      'Paket BDK-Begrüßung',
      'Team-Quests',
      'Muster-Hinweise aus Zustimmungen',
      'Teams am Anzeigenamen',
      'Merkliste',
      'Aufrufe und Besucher pro Tag',
      'Danke-Knopf ohne Konto',
      'Ankünfte je Kampagnenwort und Tag',
    ]);
    const gruppen = Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('[data-testid="gruppe"] h3 span:first-child'));
    expect(gruppen.map((g) => g.textContent!.trim())).toEqual(['Pakete', 'Einzelschalter']);
  });

  it('zeigt einen früheren Schalter, den ein älterer Server noch meldet, mit seinem technischen Namen', () => {
    laden([schalter({ name: 'sharepic' })]);
    expect(karten()[0].querySelector('h4')!.textContent).toBe('sharepic');
  });

  describe('Gruppen, Status und Filter (25.11.)', () => {
    const LISTE = (): Schalter[] => [
      schalter({ name: 'wirkungs_echo', gruppe: 'Pakete', admin_wert: true, wirksam: true }),
      schalter({ name: 'k_begruessung', gruppe: 'Pakete' }),
      schalter({ name: 'team_quests', gruppe: 'Einzelschalter', obergrenze: false, dsfa_hinweis: 'Rechtlich freigegeben (Go des Vorstands 27.11.)' }),
      schalter({ name: 'teams_oeffentlich', gruppe: 'Einzelschalter', obergrenze: false, dsfa_hinweis: DSFA, wartet_auf_recht: true }),
      schalter({ name: 'merkliste', gruppe: 'Einzelschalter', dsfa_hinweis: 'Aus lassen (Jura 26.11.)', wartet_auf_recht: true }),
    ];

    function gruppen(): HTMLElement[] {
      return Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('[data-testid="gruppe"]'));
    }

    function chip(text: string): HTMLButtonElement {
      const chips = Array.from(
        (fixture.nativeElement as HTMLElement).querySelectorAll('[data-testid="filter-chip"]'),
      ) as HTMLButtonElement[];
      return chips.find((c) => c.textContent!.trim().startsWith(text))!;
    }

    it('zeigt je Gruppe des Servers einen Abschnitt mit Überschrift und Zähler, in dessen Reihenfolge', () => {
      laden(LISTE());

      const g = gruppen();
      expect(g.map((x) => x.querySelector('h3 span')!.textContent!.trim())).toEqual(['Pakete', 'Einzelschalter']);
      expect(g[0].querySelector('[data-testid="gruppe-zaehler"]')!.textContent!.trim()).toBe('1 von 2 an');
      expect(g[1].querySelector('[data-testid="gruppe-zaehler"]')!.textContent!.trim()).toBe('0 von 3 an');
      // Überschriften-Hierarchie: Seite h2, Gruppe h3, Schalter h4; Abschnitt nach seiner Überschrift benannt
      expect(g[0].getAttribute('aria-labelledby')).toBe(g[0].querySelector('h3')!.id);
      expect(g[0].querySelectorAll('h4').length).toBe(2);
    });

    it('berechnet die Status-Pille: an, frei einschaltbar, wartet auf Recht, gesperrt (Server)', () => {
      laden(LISTE());

      const pillen = karten().map((k) => k.querySelector('[data-testid="status"]')!.textContent!.trim());
      // team_quests: Hinweis steht, aber rechtlich freigegeben, und der Server sperrt ihn
      expect(pillen).toEqual(['an', 'frei einschaltbar', 'gesperrt (Server)', 'wartet auf Recht', 'wartet auf Recht']);
    });

    // Wartet auf Recht nur bei den fünf heiklen Einzelschaltern (schalter_service.EINZEL_SCHALTER)
    it('„wartet auf Recht“ folgt dem Server: die fünf heiklen ja, Pakete und freigegebene Einzelschalter nein', () => {
      const heikel = ['teams_oeffentlich', 'merkliste', 'aufrufe_zaehlen', 'danke_ohne_konto', 'k_ankuenfte'];
      const frei = ['teams', 'spielgefuehl_buehne', 'wirkungs_echo', 'k_begruessung', 'team_quests', 'muster_stimmen'];
      laden([
        ...frei.map((name) => schalter({ name, dsfa_hinweis: 'Rechtlich freigegeben (Go des Vorstands 27.11.)' })),
        ...heikel.map((name) => schalter({ name, dsfa_hinweis: 'Aus lassen (Jura 26.11.)', wartet_auf_recht: true })),
      ]);

      const pillen = karten().map((k) => k.querySelector('[data-testid="status"]')!.textContent!.trim());
      expect(pillen.slice(0, frei.length)).toEqual(frei.map(() => 'frei einschaltbar'));
      expect(pillen.slice(frei.length)).toEqual(heikel.map(() => 'wartet auf Recht'));
    });

    it('sagt bei einem wirksamen Schalter mit offenem Recht „an, Recht offen“', () => {
      laden([schalter({ name: 'merkliste', admin_wert: true, wirksam: true, dsfa_hinweis: DSFA, wartet_auf_recht: true })]);

      const pille = karten()[0].querySelector('[data-testid="status"]') as HTMLElement;
      expect(pille.textContent!.trim()).toBe('an, Recht offen');
      expect(pille.classList).toContain('pille-recht');
      expect(fixture.componentInstance.anzahl('an')).toBe(1);
    });

    it('fasst Schalter ohne Gruppe vom Server unter „Weitere“', () => {
      laden([schalter({ name: 'merkliste', gruppe: '' })]);
      expect(gruppen()[0].querySelector('h3 span')!.textContent!.trim()).toBe('Weitere');
    });

    it('filtert nach Status, zählt je Chip und blendet leere Gruppen aus', () => {
      laden(LISTE());
      expect(chip('Alle').getAttribute('aria-pressed')).toBe('true');
      expect(chip('Wartet auf Recht').textContent).toContain('2');

      chip('Wartet auf Recht').click();
      fixture.detectChanges();

      expect(chip('Wartet auf Recht').getAttribute('aria-pressed')).toBe('true');
      expect(chip('Alle').getAttribute('aria-pressed')).toBe('false');
      expect(karten().map((k) => k.querySelector('h4')!.textContent)).toEqual(['Teams am Anzeigenamen', 'Merkliste']);
      expect(gruppen().length).toBe(1);
      // Der Zähler gilt für die ganze Gruppe, nicht nur für die gefilterten
      expect(gruppen()[0].querySelector('[data-testid="gruppe-zaehler"]')!.textContent!.trim()).toBe('0 von 3 an');
    });

    it('sagt, wenn kein Schalter zum Filter passt', () => {
      laden([schalter({ name: 'merkliste' })]);
      chip('Gesperrt').click();
      fixture.detectChanges();

      expect(karten().length).toBe(0);
      expect((fixture.nativeElement as HTMLElement).querySelector('[data-testid="filter-leer"]')!.textContent).toContain(
        'Kein Schalter passt',
      );
    });

    it('klappt die Details auf und zu, mit aria-expanded, und behält das beim Nachladen', () => {
      laden(LISTE());
      const karte = karten()[1];
      const knopfAuf = karte.querySelector('[data-testid="aufklappen"]') as HTMLButtonElement;
      const details = karte.querySelector('[data-testid="details"]') as HTMLElement;
      expect(knopfAuf.getAttribute('aria-expanded')).toBe('false');
      expect(knopfAuf.getAttribute('aria-controls')).toBe(details.id);
      expect(knopfAuf.getAttribute('aria-label')).toBe('Details zu Paket BDK-Begrüßung');
      expect(details.hidden).toBeTrue();

      knopfAuf.focus();
      knopfAuf.click();
      fixture.detectChanges();
      // Dieselbe Zeile bleibt stehen, der Fokus auf dem Knopf (WCAG 2.4.3)
      expect(knopfAuf.isConnected).toBeTrue();
      expect(document.activeElement).toBe(knopfAuf);
      expect(knopfAuf.getAttribute('aria-expanded')).toBe('true');
      expect(details.hidden).toBeFalse();
      expect((karte.querySelector('[data-testid="zustand"]') as HTMLElement).hidden).toBeFalse();

      (fixture.componentInstance as unknown as { uebernehmen(d: unknown): void }).uebernehmen({ schalter: LISTE() });
      fixture.detectChanges();
      expect((karten()[1].querySelector('[data-testid="details"]') as HTMLElement).hidden).toBeFalse();

      (karten()[1].querySelector('[data-testid="aufklappen"]') as HTMLButtonElement).click();
      fixture.detectChanges();
      expect((karten()[1].querySelector('[data-testid="details"]') as HTMLElement).hidden).toBeTrue();
    });

    it('zeigt den Zustand auch zugeklappt, wenn der Admin-Wert an ist, aber nicht wirkt', () => {
      laden([
        schalter({ name: 'teams', admin_wert: true, wirksam: true }),
        schalter({ name: 'merkliste', obergrenze: false, admin_wert: true, wirksam: false }),
      ]);

      const [teams, merkliste] = karten().map((k) => k.querySelector('[data-testid="zustand"]') as HTMLElement);
      expect(teams.hidden).toBeTrue();
      expect(merkliste.hidden).toBeFalse();
    });
  });

  describe('Pakete an und aus', () => {
    it('schaltet ein Paket ein und zeigt den neuen Stand ohne Neuladen', () => {
      laden([schalter({ name: 'teams', gruppe: 'Pakete' })]);
      expect(karten()[0].querySelector('[data-testid="status"]')!.textContent!.trim()).toBe('frei einschaltbar');

      knopf(karten()[0]).click();
      fixture.detectChanges();

      const anfrage = http.expectOne(`${URL}/teams`);
      expect(anfrage.request.method).toBe('PUT');
      expect(anfrage.request.body).toEqual({ an: true });
      anfrage.flush({ schalter: [schalter({ name: 'teams', gruppe: 'Pakete', admin_wert: true, wirksam: true })] });
      fixture.detectChanges();

      expect(karten()[0].textContent).toContain('Admin: an · wirksam: an');
      expect(karten()[0].querySelector('[data-testid="status"]')!.textContent!.trim()).toBe('an');
      expect(knopf(karten()[0]).getAttribute('aria-checked')).toBe('true');
    });

    it('schaltet ein Paket aus', () => {
      laden([schalter({ name: 'spielgefuehl_buehne', gruppe: 'Pakete', admin_wert: true, wirksam: true })]);

      knopf(karten()[0]).click();
      fixture.detectChanges();

      const anfrage = http.expectOne(`${URL}/spielgefuehl_buehne`);
      expect(anfrage.request.body).toEqual({ an: false });
      anfrage.flush({ schalter: [schalter({ name: 'spielgefuehl_buehne', gruppe: 'Pakete' })] });
      fixture.detectChanges();

      expect(karten()[0].textContent).toContain('Admin: aus · wirksam: aus');
      expect(knopf(karten()[0]).getAttribute('aria-checked')).toBe('false');
    });
  });

  it('nennt dem Screenreader den Schalter und beschreibt den Zustand', () => {
    laden([schalter({ name: 'spielgefuehl_buehne', admin_wert: true, wirksam: true })]);

    const karte = karten()[0];
    const button = knopf(karte);
    expect(button.getAttribute('aria-label')).toBe('Paket Spielgefühl, Admin');
    // Sichtbarer Text des Umschalters steckt im Namen (WCAG 2.5.3)
    expect(karte.querySelector('mat-slide-toggle')!.textContent!.trim()).toBe('Admin');
    const beschreibung = button.getAttribute('aria-describedby')!.split(' ');
    const zustand = karte.querySelector('[data-testid="zustand"]') as HTMLElement;
    expect(beschreibung).toContain(zustand.id);
    expect(zustand.textContent).toContain('wirksam: an');
  });

  it('erklärt, warum ein eingeschalteter Admin-Wert nicht wirkt', () => {
    laden([
      schalter({ name: 'wirkungs_echo', admin_wert: false, wirksam: false }),
      schalter({ name: 'danke_ohne_konto', admin_wert: true, wirksam: false }),
      schalter({ name: 'merkliste', obergrenze: false, admin_wert: true, wirksam: false }),
    ]);

    const [echo, ohneKonto, merkliste] = karten().map(
      (k) => (k.querySelector('[data-testid="zustand"]') as HTMLElement).textContent!.trim(),
    );
    expect(echo).toBe('Admin: aus · wirksam: aus');
    expect(ohneKonto).toBe('Admin: an · wirksam: aus, weil Paket Wirkungs-Echo aus');
    expect(merkliste).toBe('Admin: an · wirksam: aus (Server erlaubt nicht)');
    expect(knopf(karten()[2]).getAttribute('aria-checked')).toBe('true');
  });

  it('nimmt den Umschalter bei 409 zurück und zeigt die Erklärung', () => {
    laden([schalter({ name: 'merkliste' })]);

    knopf(karten()[0]).click();
    fixture.detectChanges();
    http
      .expectOne(`${URL}/merkliste`)
      .flush({ detail: 'Der Server erlaubt diesen Schalter nicht.' }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();

    expect(knopf(karten()[0]).getAttribute('aria-checked')).toBe('false');
    expect(document.body.textContent).toContain('Der Server erlaubt diesen Schalter nicht.');
  });

  describe('Kopplungen (Schalter-Umbau 27.11.: Einzelschalter an Paketen)', () => {
    const zustand = (k: HTMLElement) => (k.querySelector('[data-testid="zustand"]') as HTMLElement).textContent!.trim();
    const kopplung = (k: HTMLElement) => k.querySelector('[data-testid="kopplung"]')?.textContent!.trim() ?? null;

    for (const [einzel, paket, anzeige] of [
      ['team_quests', 'teams', 'Paket Teams'],
      ['teams_oeffentlich', 'teams', 'Paket Teams'],
      ['muster_stimmen', 'spielgefuehl_buehne', 'Paket Spielgefühl'],
      ['danke_ohne_konto', 'wirkungs_echo', 'Paket Wirkungs-Echo'],
    ] as const) {
      it(`${einzel}: wirkt nur mit ${anzeige} und sagt warum`, () => {
        laden([
          schalter({ name: paket, gruppe: 'Pakete', admin_wert: false, wirksam: false }),
          schalter({ name: einzel, gruppe: 'Einzelschalter', admin_wert: true, wirksam: false }),
        ]);

        const karte = karten()[1];
        expect(zustand(karte)).toBe(`Admin: an · wirksam: aus, weil ${anzeige} aus`);
        expect((karte.querySelector('[data-testid="zustand"]') as HTMLElement).hidden).toBeFalse();
        expect(kopplung(karte)).toBe(`Wirkt nur zusammen mit: ${anzeige}.`);
      });
    }

    it('wirkt das Paket, nennt die Zeile keinen Grund aus der Kopplung', () => {
      laden([
        schalter({ name: 'teams', gruppe: 'Pakete', admin_wert: true, wirksam: true }),
        schalter({ name: 'team_quests', gruppe: 'Einzelschalter', admin_wert: true, wirksam: true }),
      ]);

      expect(zustand(karten()[1])).toBe('Admin: an · wirksam: an');
    });

    it('Pakete und Einzelschalter ohne Paket haben keine Kopplung, auch keinen Ausschluss mehr', () => {
      laden([
        schalter({ name: 'teams' }),
        schalter({ name: 'spielgefuehl_buehne' }),
        schalter({ name: 'wirkungs_echo' }),
        schalter({ name: 'k_begruessung' }),
        schalter({ name: 'merkliste' }),
        schalter({ name: 'aufrufe_zaehlen' }),
        schalter({ name: 'k_ankuenfte' }),
      ]);

      expect(karten().map((k) => kopplung(k))).toEqual([null, null, null, null, null, null, null]);
    });
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

    it('zeigt team_live mit Namen, Kopplung an das Paket und das Enddatum als Einstellung (Jura 28.11.)', () => {
      const ende: Einstellung = {
        name: 'team_live_bis',
        erklaerung: 'BDK-Ende: Bis zu diesem Tag (deutsche Zeit, einschließlich) wirkt …',
        wert: '2026-12-06',
        standard: '2026-12-06',
        max_laenge: 10,
      };
      const abgelaufen = 'Abgelaufen: wirkt seit dem Ende am 06.12.2026 (Einstellung team_live_bis) nicht mehr';
      mitEinstellungen(
        [
          schalter({ name: 'teams', admin_wert: true, wirksam: true }),
          schalter({ name: 'team_live', admin_wert: true, wirksam: false, erklaerung: `Team-Fortschritt quasi-live. ${abgelaufen}` }),
        ],
        [ende],
      );

      const live = karten()[1];
      expect(live.querySelector('h4')!.textContent).toBe('Team-Fortschritt quasi-live');
      expect(live.textContent).toContain(abgelaufen);
      expect(einstellung().querySelector('h3')!.textContent).toBe('Team-Fortschritt quasi-live bis (BDK-Ende)');
      expect(einstellung().textContent).toContain('Gespeichert: 2026-12-06');
    });

    it('zeigt das Paket teams und den Einzelschalter teams_oeffentlich mit Namen', () => {
      mitEinstellungen([schalter({ name: 'teams' }), schalter({ name: 'teams_oeffentlich' })]);

      const [teams, oeffentlich] = karten();
      expect(teams.querySelector('h4')!.textContent).toBe('Paket Teams');
      expect(oeffentlich.querySelector('h4')!.textContent).toBe('Teams am Anzeigenamen');
    });

    it('erklärt, warum teams_oeffentlich ohne das Paket Teams nicht wirkt', () => {
      mitEinstellungen([
        schalter({ name: 'teams', admin_wert: false, wirksam: false }),
        schalter({ name: 'teams_oeffentlich', admin_wert: true, wirksam: false }),
      ]);

      expect((karten()[1].querySelector('[data-testid="zustand"]') as HTMLElement).textContent!.trim()).toBe(
        'Admin: an · wirksam: aus, weil Paket Teams aus',
      );
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
