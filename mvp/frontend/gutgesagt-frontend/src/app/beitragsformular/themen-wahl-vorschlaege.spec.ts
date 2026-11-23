import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { FormControl } from '@angular/forms';
import { of } from 'rxjs';
import { ThemenService } from '../services/themen.service';
import { ThemenWahl } from './themen-wahl';

/** Themenvorschlaege (#401) in der Themenwahl der Beitragsformulare. */
@Component({ standalone: true, template: '' })
class WirtComponent {
  readonly themen = new FormControl<string[] | null>([]);
  readonly wahl = new ThemenWahl(this.themen);
}

describe('ThemenWahl: Themenvorschlaege (#401)', () => {
  let wahl: ThemenWahl;
  let texte: string[];

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        {
          provide: ThemenService,
          useValue: { liste: () => of([{ schluessel: 'verkehr', name: 'Verkehr' }]), vonAussage: () => of([]) },
        },
      ],
    });
    wahl = TestBed.createComponent(WirtComponent).componentInstance.wahl;
    texte = [];
    spyOn(wahl.themenVorschlaege, 'text').and.callFake((t) => texte.push(t ?? ''));
  });

  it('gibt den Text nur fuer eine neue Aussage weiter', () => {
    wahl.anAussageAnpassen({ id: '', text: 'Das Tempolimit bringt nichts', neuGewaehlt: true });

    expect(texte).toEqual(['Das Tempolimit bringt nichts']);
  });

  it('leert die Vorschlaege fuer eine vorhandene Aussage und beim Zuruecksetzen', () => {
    wahl.anAussageAnpassen({ id: 'a-1', text: 'Vorhandene Aussage mit Themen' });
    wahl.zuruecksetzen();

    expect(texte).toEqual(['', '']);
  });
});
