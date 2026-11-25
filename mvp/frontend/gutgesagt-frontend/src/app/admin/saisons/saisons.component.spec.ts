import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

import { SaisonsComponent } from './saisons.component';
import { SaisonListe } from '../../services/saison.service';
import { environment } from '../../../environments/environment';

const URL = `${environment.baseUrl}/api/v1/moderation/saisons`;

function liste(teil: Partial<SaisonListe> = {}): SaisonListe {
  return {
    saisons: [
      {
        id: 's-2', name: 'Frühjahr 27', beginn: '2027-03-01', ende: '2027-05-31', ziel: 2000,
        zustand: 'geplant', erreicht: 0, laufende_woche: null,
      },
      {
        id: 's-1', name: 'Winter 26', beginn: '2026-11-30', ende: '2027-02-28', ziel: 1000,
        zustand: 'laufend', erreicht: 312, laufende_woche: 23,
      },
    ],
    schalter_wirksam: false,
    schwelle_erreicht: false,
    schwelle_menschen: 25,
    schwelle_wochen: 3,
    name_max: 20,
    ...teil,
  };
}

describe('SaisonsComponent', () => {
  let fixture: ComponentFixture<SaisonsComponent>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SaisonsComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideNoopAnimations()],
    }).compileComponents();
    fixture = TestBed.createComponent(SaisonsComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => {
    fixture.destroy();
    http.verify();
  });

  function text(): string {
    return (fixture.nativeElement as HTMLElement).textContent?.replace(/\s+/g, ' ').trim() ?? '';
  }

  function knopf(name: string): HTMLButtonElement {
    const alle: HTMLButtonElement[] = Array.from(fixture.nativeElement.querySelectorAll('button'));
    const gefunden = alle.find((b) => (b.getAttribute('aria-label') ?? b.textContent ?? '').includes(name));
    if (!gefunden) throw new Error(`Kein Knopf ${name}`);
    return gefunden;
  }

  function laden(daten = liste()): void {
    http.expectOne(URL).flush(daten);
    fixture.detectChanges();
  }

  it('zeigt Stand, Schwelle und je Saison Widerspruchs-Wochen', () => {
    laden();
    expect(text()).toContain('Schalter: aus · Balken für alle: noch nicht');
    expect(text()).toContain('ab 3 Wochen in Folge mit je mindestens 25 Menschen');
    expect(text()).toContain('312 von 1.000 Widerspruchs-Wochen');
    expect(text()).toContain('laufende Woche bisher 23');
    expect(text()).toContain('30.11.2026 bis 28.02.2027');
  });

  it('Löschen nur vor dem Beginn', () => {
    laden();
    expect(() => knopf('Saison Frühjahr 27 löschen')).not.toThrow();
    expect(() => knopf('Saison Winter 26 löschen')).toThrow();
  });

  it('legt eine Saison an und übernimmt die Antwort', async () => {
    laden(liste({ saisons: [] }));
    const komp = fixture.componentInstance;
    komp.eingabe = { name: '  Frühjahr 27 ', beginn: '2027-03-01', ende: '2027-05-31', ziel: 2000 };
    komp.speichern();
    const anfrage = http.expectOne((r) => r.url === URL && r.method === 'POST');
    expect(anfrage.request.body).toEqual({ name: 'Frühjahr 27', beginn: '2027-03-01', ende: '2027-05-31', ziel: 2000 });
    anfrage.flush(liste());
    fixture.detectChanges();
    expect(text()).toContain('Frühjahr 27');
    expect(komp.eingabe.name).toBe('');
  });

  it('laufende Saison: Name und Beginn nur lesbar', () => {
    laden();
    knopf('Saison Winter 26 ändern').click();
    fixture.detectChanges();
    const name: HTMLInputElement = fixture.nativeElement.querySelector('input[name="name"]');
    const beginn: HTMLInputElement = fixture.nativeElement.querySelector('input[name="beginn"]');
    const ende: HTMLInputElement = fixture.nativeElement.querySelector('input[name="ende"]');
    expect(name.readOnly).toBeTrue();
    expect(beginn.readOnly).toBeTrue();
    expect(ende.readOnly).toBeFalse();
    expect(text()).toContain('nur Ziel und Ende');
  });

  it('ändert per PUT und zeigt den Satz des Servers bei 409', () => {
    laden();
    knopf('Saison Winter 26 ändern').click();
    fixture.componentInstance.speichern();
    http
      .expectOne((r) => r.url === `${URL}/s-1` && r.method === 'PUT')
      .flush({ detail: 'Überschneidet sich mit der Saison „Frühjahr 27“.' }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();
    expect(document.body.textContent).toContain('Überschneidet sich mit der Saison „Frühjahr 27“.');
  });

  it('löscht und lädt die Liste neu', () => {
    laden();
    knopf('Saison Frühjahr 27 löschen').click();
    http.expectOne((r) => r.url === `${URL}/s-2` && r.method === 'DELETE').flush(null, { status: 204, statusText: 'No Content' });
    http.expectOne((r) => r.url === URL && r.method === 'GET').flush(liste({ saisons: [liste().saisons[1]] }));
    fixture.detectChanges();
    expect(text()).not.toContain('Frühjahr 27 ·');
  });
});
