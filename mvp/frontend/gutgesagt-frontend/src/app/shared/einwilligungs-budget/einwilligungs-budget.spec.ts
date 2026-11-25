import {
  ABSTAND_NACH_LOB_MS,
  BudgetLage,
  EinwilligungsFrage,
  EinwilligungsMoment,
  frageErlaubt,
  imErstenMonat,
  punkteFrageFaellig,
} from './einwilligungs-budget';

const JETZT = Date.parse('2026-11-25T12:00:00Z');
const TAG = 24 * 60 * 60 * 1000;

function lage(teil: Partial<Omit<BudgetLage, 'moment'>> & { moment?: Partial<EinwilligungsMoment> } = {}): BudgetLage {
  return {
    gezeigt: teil.gezeigt ?? new Set<EinwilligungsFrage>(),
    moment: { abgestimmt: false, beantwortet: 1, konto_seit: '2026-11-20T12:00:00Z', ...teil.moment },
    gewinnUm: teil.gewinnUm ?? null,
    jetzt: teil.jetzt ?? JETZT,
  };
}

describe('Einwilligungs-Budget', () => {
  describe('höchstens eine Frage je Besuch', () => {
    it('erlaubt die erste Frage im Besuch', () => {
      expect(frageErlaubt('sichtbarkeit', lage())).toBeTrue();
    });

    it('verbietet eine zweite neue Frage im selben Besuch', () => {
      expect(frageErlaubt('sichtbarkeit', lage({ gezeigt: new Set(['punkte']) }))).toBeFalse();
    });

    it('lässt eine schon gestellte Frage stehen', () => {
      expect(frageErlaubt('punkte', lage({ gezeigt: new Set(['punkte']) }))).toBeTrue();
    });

    it('Art. 9 und Team kommen immer, verbrauchen aber den Besuch', () => {
      const gezeigt = new Set<EinwilligungsFrage>(['art9']);
      expect(frageErlaubt('team', lage({ gezeigt }))).toBeTrue();
      expect(frageErlaubt('art9', lage({ gezeigt: new Set(['punkte']) }))).toBeTrue();
      expect(frageErlaubt('punkte', lage({ gezeigt }))).toBeFalse();
    });
  });

  describe('höchstens vier im ersten Monat', () => {
    it('verbietet eine fünfte Frage im ersten Monat', () => {
      expect(frageErlaubt('sichtbarkeit', lage({ moment: { beantwortet: 4 } }))).toBeFalse();
      expect(frageErlaubt('sichtbarkeit', lage({ moment: { beantwortet: 3 } }))).toBeTrue();
    });

    it('erlaubt sie nach dem ersten Monat', () => {
      const alt = new Date(JETZT - 31 * TAG).toISOString();
      expect(frageErlaubt('sichtbarkeit', lage({ moment: { beantwortet: 4, konto_seit: alt } }))).toBeTrue();
    });

    it('ein Konto ohne bekannten Beginn gilt als neu', () => {
      expect(imErstenMonat(null, JETZT)).toBeTrue();
      expect(imErstenMonat('kein Datum', JETZT)).toBeTrue();
      expect(imErstenMonat(new Date(JETZT - 29 * TAG).toISOString(), JETZT)).toBeTrue();
      expect(imErstenMonat(new Date(JETZT - 30 * TAG).toISOString(), JETZT)).toBeFalse();
    });
  });

  describe('Reihenfolge der Frage nach Punkten und Meilensteinen', () => {
    it('kommt nicht vor dem ersten Gewinn', () => {
      expect(punkteFrageFaellig(lage())).toBeFalse();
    });

    it('kommt nach der ersten Stimme', () => {
      expect(punkteFrageFaellig(lage({ moment: { abgestimmt: true } }))).toBeTrue();
    });

    it('kommt nach „Ja, gepostet“ in diesem Besuch, aber nicht direkt nach dem Lob', () => {
      expect(punkteFrageFaellig(lage({ gewinnUm: JETZT - 2000 }))).toBeFalse();
      expect(punkteFrageFaellig(lage({ gewinnUm: JETZT - ABSTAND_NACH_LOB_MS }))).toBeTrue();
    });

    it('auch mit früherer Stimme nicht direkt nach einem frischen Lob', () => {
      expect(punkteFrageFaellig(lage({ moment: { abgestimmt: true }, gewinnUm: JETZT - 1000 }))).toBeFalse();
    });

    it('wartet, wenn im Besuch schon eine andere Frage kam', () => {
      expect(punkteFrageFaellig(lage({ moment: { abgestimmt: true }, gezeigt: new Set(['art9']) }))).toBeFalse();
    });

    it('bleibt stehen, wenn sie in diesem Besuch schon gestellt wurde', () => {
      expect(punkteFrageFaellig(lage({ gezeigt: new Set(['punkte']), gewinnUm: JETZT }))).toBeTrue();
    });
  });
});
