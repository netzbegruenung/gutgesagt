import { TestBed } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { of } from 'rxjs';
import { AnkuenfteComponent, AnkuenfteService, AnkuenfteStand } from './ankuenfte.component';

describe('AnkuenfteComponent', () => {
  function zeigen(stand: AnkuenfteStand): HTMLElement {
    TestBed.configureTestingModule({
      imports: [AnkuenfteComponent, NoopAnimationsModule],
      providers: [{ provide: AnkuenfteService, useValue: { stand: () => of(stand) } }],
    });
    const fixture = TestBed.createComponent(AnkuenfteComponent);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('zeigt mit Schalter aus nichts, auch keine leere Karte', () => {
    const el = zeigen({ aktiv: false, tage: [] });

    expect(el.querySelector('[data-testid="ankuenfte"]')).toBeNull();
  });

  it('zeigt je Tag und Wort eine Zeile', () => {
    const el = zeigen({
      aktiv: true,
      tage: [
        { tag: '2026-12-04', k: 'bdk', anzahl: 12 },
        { tag: '2026-12-03', k: 'sticker', anzahl: 3 },
      ],
    });

    const zeilen = Array.from(el.querySelectorAll('[data-testid="ankunft-zeile"]'));
    expect(zeilen.length).toBe(2);
    const zellen = Array.from(zeilen[0].querySelectorAll('td')).map((z) => z.textContent!.trim());
    expect(zellen[1]).toBe('bdk');
    expect(zellen[2]).toBe('12');
    expect(zellen[0]).toContain('4.12.');
  });

  it('sagt ohne Ankünfte, dass noch keine da sind', () => {
    const el = zeigen({ aktiv: true, tage: [] });

    expect(el.querySelector('[data-testid="ankuenfte-leer"]')!.textContent).toContain('Noch keine Ankünfte');
    expect(el.querySelector('table')).toBeNull();
  });
});
