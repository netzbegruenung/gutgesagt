import { Signal, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';

import { FunktionenService } from '../services/funktionen.service';
import { LEGAL_ENTITY } from '../shared/legal-entity';
import { DatenschutzComponent } from './datenschutz.component';
import {
  KURZFASSUNG,
  KURZFASSUNG_ANKER,
  KURZFASSUNG_PLATZHALTER,
  KURZFASSUNG_SAETZE,
  KURZFASSUNG_SCHLUSS,
  KurzfassungSatz,
  kurzfassungFertig,
} from './dse-kurzfassung';

/** Testsätze ohne Platzhalter; kein Wortlaut, nur damit der Kasten erscheinen kann. */
const TESTSAETZE: readonly KurzfassungSatz[] = [
  { text: 'Testsatz eins.', anker: KURZFASSUNG_ANKER.verantwortlich, linkText: 'Mehr dazu' },
  { text: 'Testsatz zwei.', anker: KURZFASSUNG_ANKER.gespeichert, linkText: 'Mehr dazu' },
  { text: 'Testsatz drei.', anker: KURZFASSUNG_ANKER.loeschen, linkText: 'Mehr dazu' },
];

/**
 * Kasten „Kurz gesagt“ (Jura b, Basisfunktion seit dem Schalter-Umbau 27.11.): oben in der
 * Erklärung, ohne Schalter, aber nie mit Platzhaltertext (Schutzgrenze kurzfassungFertig);
 * jeder Satz springt auf einen Absatz im Volltext.
 */
describe('Kurzfassung der Datenschutzerklärung (dse_kurzfassung)', () => {
  function seite(saetze?: readonly KurzfassungSatz[]) {
    // Alle Schalter aus: der Kasten hängt an keinem
    const funktionen = { an: (): Signal<boolean> => signal(false) };
    TestBed.configureTestingModule({
      imports: [DatenschutzComponent],
      providers: [
        provideRouter([]), provideHttpClient(), provideHttpClientTesting(),
        { provide: FunktionenService, useValue: funktionen },
        ...(saetze ? [{ provide: KURZFASSUNG, useValue: saetze }] : []),
      ],
    });
    const fixture = TestBed.createComponent(DatenschutzComponent);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  function kasten(element: HTMLElement): HTMLElement | null {
    return element.querySelector('[data-testid="dse-kurzfassung"]');
  }

  it('ohne Schalter, aber ein Satz trägt noch den Platzhalter: kein Kasten, kein Platzhaltertext', () => {
    const mitPlatzhalter = [
      TESTSAETZE[0],
      { ...TESTSAETZE[1], text: `${KURZFASSUNG_PLATZHALTER} Was gespeichert wird` },
      TESTSAETZE[2],
    ];
    const element = seite(mitPlatzhalter);

    expect(kasten(element)).toBeNull();
    expect(element.textContent).not.toContain(KURZFASSUNG_PLATZHALTER);
  });

  it('mit den Sätzen im Code: nie Platzhaltertext auf der Seite', () => {
    const element = seite();

    expect(element.textContent).not.toContain(KURZFASSUNG_PLATZHALTER);
    expect(kasten(element) !== null).toBe(kurzfassungFertig(KURZFASSUNG_SAETZE));
  });

  it('Wortlaut Jura (vorläufig 26.11.2026): fünf Sätze, der Name wie im Abschnitt „Verantwortlicher“', () => {
    expect(kurzfassungFertig(KURZFASSUNG_SAETZE)).toBeTrue();
    const ganz = [...KURZFASSUNG_SAETZE.map((satz) => satz.text), KURZFASSUNG_SCHLUSS].join(' ');
    expect(ganz).toBe(
      // Der Name endet auf „e. V.“: ein Punkt, nicht zwei
      `Verantwortlich für Gut gesagt ist ${LEGAL_ENTITY.NAME.replace(/\.$/, '')}. Suchen und Lesen geht ohne Konto. ` +
        'Wer mitmacht, gibt uns Beiträge und Bewertungen; was sich daraus über deine politische ' +
        'Haltung schließen lässt, verarbeiten wir nur mit deiner ausdrücklichen Einwilligung. ' +
        'Jede Einwilligung kannst du unter „Meine Beiträge“ widerrufen und dein Konto jederzeit ' +
        'löschen. Alle Einzelheiten stehen unten.',
    );

    const element = seite();
    const verantwortlich = element.querySelector('#verantwortlicher .contact-info strong')!;
    expect(verantwortlich.textContent!.trim()).toBe(LEGAL_ENTITY.NAME);
    const box = kasten(element)!;
    expect(box.querySelectorAll('li')[0].textContent).toContain(verantwortlich.textContent!.trim());
    expect(box.textContent).toContain(KURZFASSUNG_SCHLUSS);
    expect(box.textContent).not.toContain('..');
  });

  it('ohne Schalter mit fertigen Sätzen: Kasten oben mit drei Sätzen und je einem Sprunglink', () => {
    const element = seite(TESTSAETZE);
    const box = kasten(element);

    expect(box).not.toBeNull();
    expect(box!.querySelector('h2')!.textContent).toContain('Kurz gesagt');
    // Vor dem ersten Abschnitt des Volltexts
    expect(element.querySelector('.legal-section, [data-testid="dse-kurzfassung"]')).toBe(box);

    const punkte = box!.querySelectorAll('li');
    expect(punkte.length).toBe(3);
    TESTSAETZE.forEach((satz, i) => {
      expect(punkte[i].textContent).toContain(satz.text);
      const link = punkte[i].querySelector('a')!;
      expect(link.getAttribute('href')).toBe(`/datenschutz#${satz.anker}`);
    });
  });

  it('Sprunglink scrollt zum Absatz (unter dem klebenden Kopf) und setzt den Anker in die Adresse', () => {
    const element = seite(TESTSAETZE);
    document.body.appendChild(element);
    const vorher = location.href;
    try {
      const ziel = element.querySelector<HTMLElement>(`#${KURZFASSUNG_ANKER.loeschen}`)!;
      const scrollen = spyOn(ziel, 'scrollIntoView');
      const link = kasten(element)!.querySelectorAll('a')[2];
      const klick = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 });

      link.dispatchEvent(klick);

      expect(scrollen).toHaveBeenCalledWith({ block: 'start' });
      expect(klick.defaultPrevented).toBeTrue();
      expect(location.hash).toBe(`#${KURZFASSUNG_ANKER.loeschen}`);
      // Fokus auf dem Absatz, damit Tab dort weitergeht (WCAG 2.4.3)
      expect(document.activeElement).toBe(ziel);
    } finally {
      history.replaceState(history.state, '', vorher);
      element.remove();
    }
  });

  it('jeder Anker zeigt auf einen Absatz, den es im Volltext gibt', () => {
    const element = seite();

    for (const satz of KURZFASSUNG_SAETZE) {
      const absatz = element.querySelector(`section#${satz.anker}`);
      expect(absatz).withContext(satz.anker).not.toBeNull();
      expect(absatz?.getAttribute('tabindex')).withContext(satz.anker).toBe('-1');
    }
  });

  describe('kurzfassungFertig', () => {
    it('lässt einen Satz mit Platzhalter, leerem Text, anderem Platzhalter in Klammern oder ohne Anker nicht gelten', () => {
      const mit = (aenderung: Partial<KurzfassungSatz>) => [
        { ...TESTSAETZE[0], ...aenderung },
        TESTSAETZE[1],
        TESTSAETZE[2],
      ];

      expect(kurzfassungFertig(TESTSAETZE)).toBeTrue();
      expect(kurzfassungFertig(mit({ text: `${KURZFASSUNG_PLATZHALTER} Satz` }))).toBeFalse();
      expect(kurzfassungFertig(mit({ text: '  ' }))).toBeFalse();
      expect(kurzfassungFertig(mit({ text: 'Verantwortlich ist [Name].' }))).toBeFalse();
      expect(kurzfassungFertig(mit({ anker: '' }))).toBeFalse();
    });

    it('verlangt genau drei Sätze', () => {
      expect(kurzfassungFertig(TESTSAETZE.slice(0, 2))).toBeFalse();
      expect(kurzfassungFertig([...TESTSAETZE, TESTSAETZE[0]])).toBeFalse();
    });
  });
});
