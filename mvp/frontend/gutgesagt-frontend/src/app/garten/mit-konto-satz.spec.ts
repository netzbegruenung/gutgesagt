import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { BehaviorSubject } from 'rxjs';

import { FunktionenService } from '../services/funktionen.service';
import { GARTEN_SATZ, MitKontoComponent } from '../mit-konto/mit-konto.component';

/** „Das erwartet dich mit Konto“ nennt die Gartenansicht (#783, Basisfunktion seit dem Schalter-Umbau 27.11.). */
describe('Vorschau mit Konto und Gartenansicht (#783)', () => {
  function seite(an: boolean): HTMLElement {
    const query = new BehaviorSubject(convertToParamMap({}));
    TestBed.configureTestingModule({
      imports: [MitKontoComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { queryParamMap: query, snapshot: { queryParamMap: query.value } } },
        { provide: FunktionenService, useValue: { an: () => signal(an) } },
      ],
    });
    const fixture = TestBed.createComponent(MitKontoComponent);
    fixture.detectChanges();
    return fixture.nativeElement;
  }

  afterEach(() => TestBed.resetTestingModule());

  it('ergänzt den Satz ohne Schalter', () => {
    expect(GARTEN_SATZ).toBe('Mit Konto kannst du Brachflächen begrünen.');
    expect(seite(false).textContent).toContain(GARTEN_SATZ);
  });
});
