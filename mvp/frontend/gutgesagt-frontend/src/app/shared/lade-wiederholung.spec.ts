import { fakeAsync, tick } from '@angular/core/testing';
import { Subject } from 'rxjs';

import { LadeWiederholung, WIEDERHOLUNG_MS, lohntWiederholung } from './lade-wiederholung';

describe('LadeWiederholung', () => {
  it('plant nach einem lohnenden Fehler einen Versuch, den Erfolg wieder abraeumt', fakeAsync(() => {
    const ende$ = new Subject<void>();
    const wiederholung = new LadeWiederholung(ende$);
    const laden = jasmine.createSpy('laden');

    expect(wiederholung.fehlgeschlagen({ status: 503 }, laden)).toBeTrue();
    wiederholung.erfolg();
    tick(WIEDERHOLUNG_MS[WIEDERHOLUNG_MS.length - 1]);
    window.dispatchEvent(new Event('online'));

    expect(laden).not.toHaveBeenCalled();
    ende$.next();
  }));

  it('wiederholt nur ohne Status, bei 0, 408, 429 und 5xx', () => {
    expect([undefined, 0, 408, 429, 500, 503].map((status) => lohntWiederholung(status === undefined ? new Error('x') : { status }))).toEqual([
      true, true, true, true, true, true,
    ]);
    expect([400, 401, 403, 404].map((status) => lohntWiederholung({ status }))).toEqual([false, false, false, false]);
  });

  it('streut die Abstaende auf Wunsch, ohne Streuung wie bisher fest', fakeAsync(() => {
    const ende$ = new Subject<void>();
    const laden = jasmine.createSpy('laden');
    // zufall 0: 30 % frueher
    const frueh = new LadeWiederholung(ende$, { streuung: 0.3, zufall: () => 0 });
    frueh.fehlgeschlagen({ status: 503 }, laden);
    tick(WIEDERHOLUNG_MS[0] * 0.7 - 1);
    expect(laden).not.toHaveBeenCalled();
    tick(1);
    expect(laden).toHaveBeenCalledTimes(1);

    // zufall 1: 30 % spaeter
    const spaet = new LadeWiederholung(ende$, { streuung: 0.3, zufall: () => 1 });
    spaet.fehlgeschlagen({ status: 503 }, laden);
    tick(WIEDERHOLUNG_MS[0] * 1.3 - 1);
    expect(laden).toHaveBeenCalledTimes(1);
    tick(1);
    expect(laden).toHaveBeenCalledTimes(2);

    const fest = new LadeWiederholung(ende$);
    fest.fehlgeschlagen({ status: 503 }, laden);
    tick(WIEDERHOLUNG_MS[0]);
    expect(laden).toHaveBeenCalledTimes(3);
    ende$.next();
  }));
});
