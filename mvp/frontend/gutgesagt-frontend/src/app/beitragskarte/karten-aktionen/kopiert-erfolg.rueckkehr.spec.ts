import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';

import { GepostetStand, KopiertErfolgComponent, RUECKKEHR_AB_MS, RUECKKEHR_LEUCHTEN_MS } from './kopiert-erfolg.component';
import { GEPOSTET_FRAGE, GEPOSTET_RUECKKEHR, GEPOSTET_RUECKKEHR_OHNE_KONTO } from './gepostet-texte';

/** Rückkehr-Moment (Entscheidung 25.11.): Hinweis beim Zurückkommen nach dem Kopieren. */
describe('Erfolgskasten - Rückkehr-Moment', () => {
  let fixture: ComponentFixture<KopiertErfolgComponent>;
  let reduziert: boolean;

  beforeEach(async () => {
    reduziert = false;
    // Nur die Frage nach „Bewegung reduzieren“ beantworten, alle anderen (CDK) wie gewohnt.
    const echt = window.matchMedia.bind(window);
    spyOn(window, 'matchMedia').and.callFake((frage: string) => {
      const mql = echt(frage);
      if (!frage.includes('reduced-motion')) {
        return mql;
      }
      return { matches: reduziert, media: frage } as MediaQueryList;
    });
    await TestBed.configureTestingModule({
      imports: [KopiertErfolgComponent, NoopAnimationsModule],
      providers: [provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(KopiertErfolgComponent);
  });

  function setzen(werte: { sichtbar?: boolean; gepostet?: GepostetStand; kopierLauf?: number; ohneKonto?: boolean }): void {
    for (const [name, wert] of Object.entries(werte)) {
      fixture.componentRef.setInput(name, wert);
    }
    fixture.detectChanges();
  }

  /** Kasten offen mit Frage, frisch kopiert. */
  function kopieren(lauf = 1, ohneKonto = false): void {
    setzen({ sichtbar: true, gepostet: 'frage', kopierLauf: lauf, ohneKonto });
  }

  function zurueck(): void {
    document.dispatchEvent(new Event('visibilitychange'));
    fixture.detectChanges();
  }

  function frage(): string {
    return (fixture.nativeElement.querySelector('.erfolg-gepostet-frage')?.textContent ?? '').trim();
  }

  function leuchtet(): boolean {
    return !!fixture.nativeElement.querySelector('.ja-gepostet--rueckkehr');
  }

  it('nach mindestens 3 s: Knopf leuchtet kurz auf, die Frage wird zum Hinweis', fakeAsync(() => {
    kopieren();
    expect(frage()).toBe(GEPOSTET_FRAGE);
    tick(RUECKKEHR_AB_MS);
    zurueck();
    expect(frage()).toBe(GEPOSTET_RUECKKEHR);
    expect(leuchtet()).toBeTrue();
    tick(RUECKKEHR_LEUCHTEN_MS);
    fixture.detectChanges();
    expect(leuchtet()).toBeFalse();
    // Der Hinweis bleibt stehen, bis neu kopiert wird.
    expect(frage()).toBe(GEPOSTET_RUECKKEHR);
  }));

  it('auch über den Fokus des Fensters', fakeAsync(() => {
    kopieren();
    tick(RUECKKEHR_AB_MS);
    window.dispatchEvent(new Event('focus'));
    fixture.detectChanges();
    expect(frage()).toBe(GEPOSTET_RUECKKEHR);
    tick(RUECKKEHR_LEUCHTEN_MS);
  }));

  it('unter 3 s nichts, eine spätere Rückkehr zählt dann noch', fakeAsync(() => {
    kopieren();
    tick(RUECKKEHR_AB_MS - 1000);
    zurueck();
    expect(frage()).toBe(GEPOSTET_FRAGE);
    expect(leuchtet()).toBeFalse();
    tick(1000);
    zurueck();
    expect(frage()).toBe(GEPOSTET_RUECKKEHR);
    tick(RUECKKEHR_LEUCHTEN_MS);
  }));

  it('nach dem Melden nichts', fakeAsync(() => {
    kopieren();
    setzen({ gepostet: 'sendet' });
    tick(RUECKKEHR_AB_MS);
    zurueck();
    expect(frage()).toBe(GEPOSTET_FRAGE);
    expect(leuchtet()).toBeFalse();
    setzen({ gepostet: 'gemeldet' });
    zurueck();
    expect(leuchtet()).toBeFalse();
    expect(fixture.componentInstance.frageText).toBe(GEPOSTET_FRAGE);
  }));

  it('nach dem Schließen nichts', fakeAsync(() => {
    kopieren();
    setzen({ sichtbar: false });
    tick(RUECKKEHR_AB_MS);
    zurueck();
    expect(fixture.componentInstance.leuchtet).toBeFalse();
    expect(fixture.componentInstance.frageText).toBe(GEPOSTET_FRAGE);
  }));

  it('ohne Frage (nicht angeboten) nichts', fakeAsync(() => {
    kopieren();
    setzen({ gepostet: 'aus' });
    tick(RUECKKEHR_AB_MS);
    zurueck();
    expect(fixture.componentInstance.leuchtet).toBeFalse();
    expect(fixture.componentInstance.frageText).toBe(GEPOSTET_FRAGE);
  }));

  it('die zweite Rückkehr nichts mehr, das nächste Kopieren startet neu', fakeAsync(() => {
    kopieren(1);
    tick(RUECKKEHR_AB_MS);
    zurueck();
    tick(RUECKKEHR_LEUCHTEN_MS);
    fixture.detectChanges();
    tick(RUECKKEHR_AB_MS);
    zurueck();
    expect(leuchtet()).toBeFalse();

    kopieren(2);
    expect(frage()).toBe(GEPOSTET_FRAGE);
    tick(RUECKKEHR_AB_MS);
    zurueck();
    expect(leuchtet()).toBeTrue();
    expect(frage()).toBe(GEPOSTET_RUECKKEHR);
    tick(RUECKKEHR_LEUCHTEN_MS);
  }));

  it('ein verdeckter Tab ist noch keine Rückkehr', fakeAsync(() => {
    kopieren();
    tick(RUECKKEHR_AB_MS);
    spyOnProperty(document, 'visibilityState', 'get').and.returnValue('hidden');
    zurueck();
    expect(frage()).toBe(GEPOSTET_FRAGE);
  }));

  it('mit „Bewegung reduzieren“ nur der Text, keine Animationsklasse', fakeAsync(() => {
    reduziert = true;
    kopieren();
    tick(RUECKKEHR_AB_MS);
    zurueck();
    expect(frage()).toBe(GEPOSTET_RUECKKEHR);
    expect(leuchtet()).toBeFalse();
  }));

  it('ohne Konto der Hinweis ohne „zählt mit“', fakeAsync(() => {
    kopieren(1, true);
    tick(RUECKKEHR_AB_MS);
    zurueck();
    expect(frage()).toBe(GEPOSTET_RUECKKEHR_OHNE_KONTO);
    expect(frage()).not.toContain('zählt');
    tick(RUECKKEHR_LEUCHTEN_MS);
  }));

  it('die Statusregion sagt nur den geänderten Satz an, nicht den ganzen Kasten', () => {
    kopieren();
    expect(fixture.nativeElement.querySelector('.kopiert-erfolg-region').getAttribute('aria-atomic')).toBe('false');
  });
});
