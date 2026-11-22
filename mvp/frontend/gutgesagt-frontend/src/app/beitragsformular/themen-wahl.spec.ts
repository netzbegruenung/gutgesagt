import { TestBed } from '@angular/core/testing';
import { FormControl } from '@angular/forms';
import { Subject, of, throwError } from 'rxjs';

import { ThemenWahl } from './themen-wahl';
import { Thema } from '../services/dtos/themenDtos';
import { ThemenService } from '../services/themen.service';

const KLIMA: Thema = { schluessel: 'klima', name: 'Klima', motiv: 'themen/klima.svg' };

describe('ThemenWahl: Themen einer vorhandenen Aussage', () => {
  let themenService: jasmine.SpyObj<ThemenService>;
  let wahl: ThemenWahl;

  beforeEach(() => {
    themenService = jasmine.createSpyObj('ThemenService', ['liste', 'vonAussage']);
    themenService.liste.and.returnValue(of([KLIMA]));
    themenService.vonAussage.and.returnValue(of([KLIMA]));
    TestBed.configureTestingModule({ providers: [{ provide: ThemenService, useValue: themenService }] });
    wahl = TestBed.runInInjectionContext(() => new ThemenWahl(new FormControl<string[] | null>([])));
  });

  it('laedt die Themen einer gewaehlten, vorhandenen Aussage, einmal je Aussage', () => {
    wahl.anAussageAnpassen({ id: 'a-1', text: 'Wärmepumpen sind zu teuer' });
    wahl.anAussageAnpassen({ id: 'a-1', text: 'Wärmepumpen sind zu teuer' });

    expect(themenService.vonAussage).toHaveBeenCalledOnceWith('a-1');
    expect(wahl.vorhandene).toEqual({ statement_id: 'a-1', themen: [KLIMA] });
  });

  it('hat ohne vorhandene Aussage keine, auch nach dem Wechsel auf eine neue per Text', () => {
    wahl.anAussageAnpassen({ id: 'a-1', text: 'Wärmepumpen sind zu teuer' });
    wahl.anAussageAnpassen({ id: '', text: 'Wärmepumpen sind zu teuer', neuGewaehlt: true });

    expect(wahl.vorhandene).toBeNull();
  });

  it('zeigt die Themen einer vorigen Aussage nicht, wenn deren Antwort zu spaet kommt', () => {
    const langsam = new Subject<Thema[]>();
    themenService.vonAussage.and.returnValues(langsam, of([]));

    wahl.anAussageAnpassen({ id: 'a-1', text: 'Erste' });
    wahl.anAussageAnpassen({ id: 'a-2', text: 'Zweite' });
    langsam.next([KLIMA]);

    expect(wahl.vorhandene).toEqual({ statement_id: 'a-2', themen: [] });
  });

  it('bietet nach einem Fehler kein Zuordnen an, das vorhandene ersetzte', () => {
    themenService.vonAussage.and.returnValue(throwError(() => new Error('500')));

    wahl.anAussageAnpassen({ id: 'a-1', text: 'Wärmepumpen sind zu teuer' });

    expect(wahl.vorhandene).toBeNull();
  });

  it('vergisst sie beim Zuruecksetzen', () => {
    wahl.anAussageAnpassen({ id: 'a-1', text: 'Wärmepumpen sind zu teuer' });

    wahl.zuruecksetzen();

    expect(wahl.vorhandene).toBeNull();
  });
});
