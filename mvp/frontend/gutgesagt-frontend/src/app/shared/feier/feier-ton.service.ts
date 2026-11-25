import { Injectable, InjectionToken, inject, signal } from '@angular/core';

/**
 * Hier merkt sich der Browser „Ton bei Erfolgen“ (#787): nur der Wert '1', solange der Ton
 * an ist. Ausschalten löscht den Eintrag. Absatz in der Datenschutzerklärung unter
 * „Speicherung auf deinem Gerät“.
 */
export const FEIER_TON_SCHLUESSEL = 'gutgesagt-ton-bei-erfolgen';

/** Der Ton spielt nur, wenn der Browser ihn binnen dieser Zeit freigibt; später wäre er fehl am Platz. */
export const FEIER_TON_SPAETESTENS_MS = 1000;

/**
 * Baut den AudioContext; eigenes Token, damit Tests ohne Lautsprecher prüfen, ob und was
 * gespielt wird. Ohne Web Audio null: Dann bleibt es still.
 */
export const FEIER_AUDIO = new InjectionToken<() => AudioContext | null>('FEIER_AUDIO', {
  providedIn: 'root',
  factory: () => () => {
    const Kontext =
      typeof window === 'undefined'
        ? undefined
        : (window.AudioContext ??
          (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext);
    return Kontext ? new Kontext() : null;
  },
});

/**
 * Drei Töne, aufsteigend wie ein kleines Glockenspiel (C-Dur: E5, G5, C6), je 0,32 s mit
 * kurzem Anschlag und weichem Ausklingen; der letzte endet nach 0,46 s.
 */
const TOENE: ReadonlyArray<{ hz: number; ab: number }> = [
  { hz: 659.25, ab: 0 },
  { hz: 783.99, ab: 0.07 },
  { hz: 1046.5, ab: 0.14 },
];
const TON_DAUER_S = 0.32;
const ANSCHLAG_S = 0.012;
/** Leise: drei überlagerte Sinustöne bleiben deutlich unter voller Lautstärke. */
const LAUTSTAERKE = 0.08;

/**
 * „Ton bei Erfolgen“: ein kurzer, leiser Ton für einen Feier-Moment, selbst erzeugt mit der
 * Web Audio API (keine Audiodatei). Standard aus. Spielt nur, wenn die Person den Ton
 * selbst eingeschaltet hat, und nur, wenn der Browser Audio freigibt (Autoplay-Regeln:
 * nach einer Bedienung auf der Seite); sonst bleibt es still. Ohne Speicher (privates
 * Fenster) gilt die Wahl bis zum Neuladen.
 */
@Injectable({ providedIn: 'root' })
export class FeierTonService {
  private readonly audio = inject(FEIER_AUDIO);
  private kontext: AudioContext | null = null;
  private readonly _an = signal(gelesen());

  /** Ob die Person den Ton eingeschaltet hat. */
  readonly an = this._an.asReadonly();

  /**
   * Ein- oder ausschalten. Beim Einschalten spielt der Ton gleich einmal zur Probe: Das ist
   * die Bedienung, die der Browser für Audio verlangt.
   */
  setzen(an: boolean): void {
    this._an.set(an);
    try {
      if (an) {
        localStorage.setItem(FEIER_TON_SCHLUESSEL, '1');
      } else {
        localStorage.removeItem(FEIER_TON_SCHLUESSEL);
      }
    } catch {
      // Ohne Speicher gilt die Wahl nur bis zum Neuladen.
    }
    if (an) {
      this.spielen();
    }
  }

  /** Spielt den Ton, wenn er an ist; sonst passiert nichts, auch kein AudioContext. */
  spielen(): void {
    if (!this._an()) {
      return;
    }
    try {
      this.kontext ??= this.audio();
    } catch {
      this.kontext = null;
    }
    const kontext = this.kontext;
    if (!kontext) {
      return;
    }
    if (kontext.state === 'running') {
      this.akkord(kontext);
      return;
    }
    // Gibt der Browser Audio erst später frei, wäre der Ton fehl am Platz: dann still.
    const gefragt = Date.now();
    kontext
      .resume()
      .then(() => {
        if (kontext.state === 'running' && Date.now() - gefragt <= FEIER_TON_SPAETESTENS_MS) {
          this.akkord(kontext);
        }
      })
      .catch(() => undefined);
  }

  private akkord(kontext: AudioContext): void {
    const beginn = kontext.currentTime + 0.01;
    const summe = kontext.createGain();
    summe.gain.value = LAUTSTAERKE;
    summe.connect(kontext.destination);
    for (const { hz, ab } of TOENE) {
      const start = beginn + ab;
      const ton = kontext.createOscillator();
      ton.type = 'sine';
      ton.frequency.value = hz;
      const huelle = kontext.createGain();
      huelle.gain.setValueAtTime(0.0001, start);
      huelle.gain.exponentialRampToValueAtTime(1, start + ANSCHLAG_S);
      huelle.gain.exponentialRampToValueAtTime(0.0001, start + TON_DAUER_S);
      ton.connect(huelle);
      huelle.connect(summe);
      ton.start(start);
      ton.stop(start + TON_DAUER_S + 0.01);
    }
  }
}

function gelesen(): boolean {
  try {
    return localStorage.getItem(FEIER_TON_SCHLUESSEL) === '1';
  } catch {
    return false;
  }
}
