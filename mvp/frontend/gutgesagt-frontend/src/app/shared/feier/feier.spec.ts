import { TestBed } from '@angular/core/testing';

import { FEIER_BEWEGUNG, FeierKeimComponent } from './feier-keim.component';
import { FEIER_AUDIO, FEIER_TON_SCHLUESSEL, FeierTonService } from './feier-ton.service';
import { FeierTonSchalterComponent, TON_BEI_ERFOLGEN } from './feier-ton-schalter.component';

/** Ein AudioContext zum Mitzählen: wie viele Töne starten, ohne Lautsprecher. */
class AudioAttrappe {
  state: AudioContextState = 'running';
  currentTime = 0;
  destination = {} as AudioDestinationNode;
  gestartet: number[] = [];
  resume = jasmine.createSpy('resume').and.callFake(() => Promise.resolve());

  createGain(): GainNode {
    const param = {
      value: 0,
      setValueAtTime: () => param,
      exponentialRampToValueAtTime: () => param,
    };
    return { gain: param, connect: () => undefined } as unknown as GainNode;
  }

  createOscillator(): OscillatorNode {
    return {
      type: 'sine',
      frequency: { value: 0 },
      connect: () => undefined,
      start: (t: number) => this.gestartet.push(t),
      stop: () => undefined,
    } as unknown as OscillatorNode;
  }
}

describe('Feier-Moment (#787)', () => {
  let attrappe: AudioAttrappe;
  let gebaut: jasmine.Spy;

  beforeEach(() => {
    localStorage.removeItem(FEIER_TON_SCHLUESSEL);
    attrappe = new AudioAttrappe();
    gebaut = jasmine.createSpy('audio').and.callFake(() => attrappe);
  });

  afterEach(() => localStorage.removeItem(FEIER_TON_SCHLUESSEL));

  function ton(): FeierTonService {
    TestBed.configureTestingModule({ providers: [{ provide: FEIER_AUDIO, useValue: gebaut }] });
    return TestBed.inject(FeierTonService);
  }

  describe('Ton bei Erfolgen', () => {
    it('ist standardmäßig aus: kein Ton, nicht einmal ein AudioContext', () => {
      const dienst = ton();
      expect(dienst.an()).toBeFalse();
      dienst.spielen();
      expect(gebaut).not.toHaveBeenCalled();
      expect(localStorage.getItem(FEIER_TON_SCHLUESSEL)).toBeNull();
    });

    it('spielt nach dem Einschalten einmal zur Probe drei kurze Töne und merkt sich die Wahl', () => {
      const dienst = ton();
      dienst.setzen(true);
      expect(localStorage.getItem(FEIER_TON_SCHLUESSEL)).toBe('1');
      expect(attrappe.gestartet.length).toBe(3);
      // Alles binnen 0,5 s: letzter Anschlag nach 0,15 s, jeder Ton 0,32 s
      expect(Math.max(...attrappe.gestartet) + 0.33).toBeLessThanOrEqual(0.5);

      dienst.spielen();
      expect(attrappe.gestartet.length).toBe(6);
      expect(gebaut).toHaveBeenCalledTimes(1);
    });

    it('liest die Wahl beim Start und löscht den Eintrag beim Ausschalten', () => {
      localStorage.setItem(FEIER_TON_SCHLUESSEL, '1');
      const dienst = ton();
      expect(dienst.an()).toBeTrue();

      dienst.setzen(false);
      expect(localStorage.getItem(FEIER_TON_SCHLUESSEL)).toBeNull();
      dienst.spielen();
      expect(attrappe.gestartet.length).toBe(0);
    });

    it('bleibt still, wenn der Browser Audio nicht freigibt', async () => {
      localStorage.setItem(FEIER_TON_SCHLUESSEL, '1');
      attrappe.state = 'suspended';
      attrappe.resume.and.callFake(() => Promise.reject(new Error('nicht erlaubt')));
      ton().spielen();
      await Promise.resolve();
      await Promise.resolve();
      expect(attrappe.resume).toHaveBeenCalled();
      expect(attrappe.gestartet.length).toBe(0);
    });

    it('spielt nach der Freigabe, wenn sie gleich kommt', async () => {
      localStorage.setItem(FEIER_TON_SCHLUESSEL, '1');
      attrappe.state = 'suspended';
      attrappe.resume.and.callFake(() => {
        attrappe.state = 'running';
        return Promise.resolve();
      });
      ton().spielen();
      await Promise.resolve();
      await Promise.resolve();
      expect(attrappe.gestartet.length).toBe(3);
    });

    it('bleibt still, wenn die Freigabe erst nach mehr als einer Sekunde kommt', async () => {
      localStorage.setItem(FEIER_TON_SCHLUESSEL, '1');
      attrappe.state = 'suspended';
      let freigeben: () => void = () => undefined;
      attrappe.resume.and.callFake(
        () =>
          new Promise<void>((fertig) => {
            freigeben = () => {
              attrappe.state = 'running';
              fertig();
            };
          }),
      );
      jasmine.clock().install();
      try {
        jasmine.clock().mockDate(new Date(2026, 10, 25, 12, 0, 0));
        ton().spielen();
        jasmine.clock().tick(1500);
        freigeben();
        await Promise.resolve();
        await Promise.resolve();
        expect(attrappe.gestartet.length).toBe(0);
      } finally {
        jasmine.clock().uninstall();
      }
    });

    it('bleibt still ohne Web Audio', () => {
      localStorage.setItem(FEIER_TON_SCHLUESSEL, '1');
      gebaut.and.returnValue(null);
      expect(() => ton().spielen()).not.toThrow();
    });

    it('der Umschalter ist beschriftet, steht auf aus und schaltet den Ton ein', async () => {
      ton();
      const fixture = TestBed.createComponent(FeierTonSchalterComponent);
      fixture.detectChanges();
      await fixture.whenStable();
      const knopf = (fixture.nativeElement as HTMLElement).querySelector('button[role="switch"]') as HTMLButtonElement;
      expect((fixture.nativeElement as HTMLElement).textContent!.trim()).toBe(TON_BEI_ERFOLGEN);
      expect(knopf.getAttribute('aria-checked')).toBe('false');
      expect(attrappe.gestartet.length).toBe(0);

      knopf.click();
      fixture.detectChanges();
      expect(knopf.getAttribute('aria-checked')).toBe('true');
      expect(localStorage.getItem(FEIER_TON_SCHLUESSEL)).toBe('1');
      expect(attrappe.gestartet.length).toBe(3);
    });
  });

  describe('Keim', () => {
    function keim(bewegung: boolean): HTMLElement {
      TestBed.configureTestingModule({ providers: [{ provide: FEIER_BEWEGUNG, useValue: bewegung }] });
      const fixture = TestBed.createComponent(FeierKeimComponent);
      fixture.detectChanges();
      return fixture.nativeElement as HTMLElement;
    }

    it('ist reine Zierde: für Screenreader verborgen', () => {
      expect(keim(true).getAttribute('aria-hidden')).toBe('true');
    });

    it('„Bewegung reduzieren“: keine Animation, nur das Endbild ohne fliegende Blätter', () => {
      const el = keim(false);
      expect(el.classList).not.toContain('bewegt');
      el.querySelectorAll('svg *').forEach((teil) => {
        expect(getComputedStyle(teil).animationName).withContext(teil.getAttribute('class') ?? '').toBe('none');
      });
      expect(getComputedStyle(el.querySelector('.blatt-links')!).transform).toBe('none');
      expect(getComputedStyle(el.querySelector('.stiel')!).strokeDashoffset).toBe('0px');
      el.querySelectorAll('.flugblatt').forEach((blatt) => expect(getComputedStyle(blatt).display).toBe('none'));
    });

    it('mit Bewegung: jede Animation läuft einmal und endet nach höchstens 1,5 s', () => {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        pending('Der Testbrowser verlangt reduzierte Bewegung');
        return;
      }
      const el = keim(true);
      expect(el.classList).toContain('bewegt');
      const animiert = Array.from(el.querySelectorAll('svg *')).filter(
        (teil) => getComputedStyle(teil).animationName !== 'none',
      );
      expect(animiert.length).toBeGreaterThan(0);
      for (const teil of animiert) {
        const stil = getComputedStyle(teil);
        expect(stil.animationIterationCount).toBe('1');
        const ende = parseFloat(stil.animationDelay) + parseFloat(stil.animationDuration);
        expect(ende).withContext(teil.getAttribute('class') ?? '').toBeLessThanOrEqual(1.5);
      }
    });
  });
});
