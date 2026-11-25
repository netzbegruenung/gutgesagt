import { HttpErrorResponse } from '@angular/common/http';
import { TAGESDECKEL_MELDUNG, tagesdeckelErreicht, validierungsMeldung } from './speicherfehler';

describe('speicherfehler', () => {
  const tagesdeckel = new HttpErrorResponse({
    status: 429,
    error: { detail: 'Für heute ist Schluss', error: 'TAGESDECKEL' },
  });

  it('erkennt den Tagesdeckel an Status und Kennung', () => {
    expect(tagesdeckelErreicht(tagesdeckel)).toBeTrue();
  });

  it('haelt ein anderes 429 (Rate-Limit) nicht fuer den Tagesdeckel', () => {
    const rateLimit = new HttpErrorResponse({ status: 429, error: { error: 'TOO_MANY_REQUESTS' } });

    expect(tagesdeckelErreicht(rateLimit)).toBeFalse();
    expect(validierungsMeldung(rateLimit)).toBeNull();
  });

  it('gibt am Tagesdeckel die freundliche Meldung statt der allgemeinen', () => {
    expect(validierungsMeldung(tagesdeckel)).toBe(TAGESDECKEL_MELDUNG);
    expect(TAGESDECKEL_MELDUNG).toContain('morgen');
  });

  it('nimmt bei 422 weiter die Meldung des Backends', () => {
    const fehler = new HttpErrorResponse({ status: 422, error: { detail: [{ msg: 'Value error, Zu kurz' }] } });

    expect(validierungsMeldung(fehler)).toBe('Zu kurz');
  });
});
