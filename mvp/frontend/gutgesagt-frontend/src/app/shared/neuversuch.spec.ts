import { HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { fakeAsync, tick } from '@angular/core/testing';
import { defer, of, throwError } from 'rxjs';
import {
  NEUVERSUCH_HOECHSTENS_MS,
  NEUVERSUCH_START_MS,
  RETRY_AFTER_HOECHSTENS_MS,
  mitNeuversuch,
  retryAfterMs,
  voruebergehend,
  wartezeitMs,
} from './neuversuch';

function fehler(status: number, retryAfter?: string): HttpErrorResponse {
  return new HttpErrorResponse({
    status,
    headers: retryAfter === undefined ? undefined : new HttpHeaders({ 'Retry-After': retryAfter }),
  });
}

describe('neuversuch', () => {
  it('nennt Netz, 429 und 5xx vorübergehend, 4xx sonst nicht', () => {
    for (const s of [0, 429, 500, 502, 503, 504]) {
      expect(voruebergehend(fehler(s))).withContext(String(s)).toBeTrue();
    }
    for (const s of [400, 401, 403, 404, 409, 410, 422]) {
      expect(voruebergehend(fehler(s))).withContext(String(s)).toBeFalse();
    }
    expect(voruebergehend(null)).toBeFalse();
    expect(voruebergehend(new Error('x'))).toBeFalse();
  });

  it('liest Retry-After als Sekunden oder als HTTP-Datum und kappt Unsinn', () => {
    const jetzt = Date.parse('2026-12-04T10:00:00Z');
    expect(retryAfterMs(fehler(429, '30'))).toBe(30_000);
    expect(retryAfterMs(fehler(429, 'Fri, 04 Dec 2026 10:00:45 GMT'), jetzt)).toBe(45_000);
    expect(retryAfterMs(fehler(429, 'Fri, 04 Dec 2026 09:00:00 GMT'), jetzt)).toBe(0);
    expect(retryAfterMs(fehler(429, '999999'))).toBe(RETRY_AFTER_HOECHSTENS_MS);
    expect(retryAfterMs(fehler(429, 'bald'))).toBeNull();
    expect(retryAfterMs(fehler(429))).toBeNull();
    expect(retryAfterMs({ status: 0 })).toBeNull();
  });

  it('wartet ohne Vorgabe 2 s, 4 s, 8 s … bis 60 s, gestreut auf die halbe bis ganze Stufe', () => {
    const e = fehler(429);
    expect(wartezeitMs(e, 1, () => 1)).toBe(NEUVERSUCH_START_MS);
    expect(wartezeitMs(e, 2, () => 1)).toBe(NEUVERSUCH_START_MS * 2);
    expect(wartezeitMs(e, 3, () => 0)).toBe(NEUVERSUCH_START_MS * 2);
    expect(wartezeitMs(e, 20, () => 1)).toBe(NEUVERSUCH_HOECHSTENS_MS);
  });

  it('wartet mit Retry-After nie kürzer als verlangt', () => {
    expect(wartezeitMs(fehler(429, '30'), 1, () => 0)).toBeGreaterThanOrEqual(30_000);
    expect(wartezeitMs(fehler(429, '30'), 1, () => 1)).toBeLessThanOrEqual(36_000);
    // Auch über der Obergrenze ohne Vorgabe: Der Server weiß, wann das Fenster frei wird.
    expect(wartezeitMs(fehler(429, '120'), 1, () => 0)).toBeGreaterThanOrEqual(120_000);
  });

  it('wiederholt nach vorübergehenden Fehlern und liefert dann das Ergebnis', fakeAsync(() => {
    let aufrufe = 0;
    const gewartet: number[] = [];
    let ergebnis: string | null = null;
    defer(() => (++aufrufe < 3 ? throwError(() => fehler(503)) : of('da')))
      .pipe(mitNeuversuch({ zufall: () => 1, beimWarten: (_e, _v, ms) => gewartet.push(ms) }))
      .subscribe((wert) => (ergebnis = wert));

    tick(NEUVERSUCH_START_MS * 3);
    expect(aufrufe).toBe(3);
    expect(gewartet).toEqual([NEUVERSUCH_START_MS, NEUVERSUCH_START_MS * 2]);
    expect(ergebnis as string | null).toBe('da');
  }));

  it('gibt andere Fehler sofort weiter, ebenso wenn nochmal nein sagt', fakeAsync(() => {
    let aufrufe = 0;
    let gemeldet: unknown = null;
    defer(() => {
      aufrufe++;
      return throwError(() => fehler(410));
    })
      .pipe(mitNeuversuch())
      .subscribe({ error: (e) => (gemeldet = e) });
    expect(aufrufe).toBe(1);
    expect((gemeldet as HttpErrorResponse).status).toBe(410);

    aufrufe = 0;
    defer(() => {
      aufrufe++;
      return throwError(() => fehler(502));
    })
      .pipe(mitNeuversuch({ zufall: () => 1, nochmal: (_e, versuch) => versuch <= 2 }))
      .subscribe({ error: (e) => (gemeldet = e) });
    tick(60_000);
    expect(aufrufe).toBe(3);
    expect((gemeldet as HttpErrorResponse).status).toBe(502);
  }));
});
