import { MonoTypeOperatorFunction, throwError, timer } from 'rxjs';
import { retry } from 'rxjs/operators';

/** Erster Neuversuch nach etwa so vielen ms, danach jeweils doppelt so lange. */
export const NEUVERSUCH_START_MS = 2_000;
/** Ohne Vorgabe des Servers wartet kein Neuversuch länger. */
export const NEUVERSUCH_HOECHSTENS_MS = 60_000;
/**
 * Längste Vorgabe aus Retry-After, die befolgt wird: das Fenster der Rate-Limiter
 * (15 Minuten, utils/rate_limiter.py). Was darüber liegt, gilt als Unsinn und wird gekappt.
 */
export const RETRY_AFTER_HOECHSTENS_MS = 15 * 60_000;

function status(fehler: unknown): unknown {
  return (fehler as { status?: unknown } | null)?.status;
}

/**
 * Fehler, nach denen ein späterer Versuch klappen kann: kein Netz (0), zu viele Anfragen
 * von diesem Anschluss (429, im Saal-WLAN teilen sich hunderte Geräte eine Adresse) und
 * Server oder Gateway gerade nicht bereit (500, 502, 503, 504, etwa beim Deploy).
 */
export function voruebergehend(fehler: unknown): boolean {
  const s = status(fehler);
  return s === 0 || s === 429 || s === 500 || s === 502 || s === 503 || s === 504;
}

/** Retry-After der Antwort in ms (Sekunden oder HTTP-Datum); null, wenn er fehlt oder unlesbar ist. */
export function retryAfterMs(fehler: unknown, jetzt = Date.now()): number | null {
  const kopf = (fehler as { headers?: { get?: (name: string) => string | null } } | null)?.headers;
  const wert = typeof kopf?.get === 'function' ? kopf.get('Retry-After')?.trim() : null;
  if (!wert) {
    return null;
  }
  const ms = /^\d+$/.test(wert) ? Number(wert) * 1000 : Date.parse(wert) - jetzt;
  return Number.isFinite(ms) ? Math.min(Math.max(ms, 0), RETRY_AFTER_HOECHSTENS_MS) : null;
}

/**
 * Wartezeit vor dem ``versuch``-ten Neuversuch (ab 1). Mit Retry-After nie früher als
 * verlangt; sonst 2 s, 4 s, 8 s … bis höchstens 60 s. Gestreut, damit nicht alle Geräte
 * im Saal in derselben Sekunde wiederkommen.
 */
export function wartezeitMs(fehler: unknown, versuch: number, zufall: () => number = Math.random, jetzt = Date.now()): number {
  const vorgabe = retryAfterMs(fehler, jetzt);
  if (vorgabe !== null) {
    return Math.round(vorgabe + zufall() * Math.min(vorgabe * 0.2, 5_000) + 250);
  }
  const stufe = Math.min(NEUVERSUCH_HOECHSTENS_MS, NEUVERSUCH_START_MS * 2 ** Math.max(versuch - 1, 0));
  return Math.round(stufe * (0.5 + zufall() * 0.5));
}

export interface NeuversuchOptionen {
  /** Ob nach diesem Fehler noch einmal versucht wird; Standard: bei jedem vorübergehenden Fehler. */
  nochmal?: (fehler: unknown, versuch: number) => boolean;
  /** Vor jedem Warten, etwa um den Hinweis „Gerade ist viel los …“ zu zeigen. */
  beimWarten?: (fehler: unknown, versuch: number, ms: number) => void;
  zufall?: () => number;
}

/**
 * Wiederholt die Anfrage nach vorübergehenden Fehlern selbst, mit wachsendem Abstand und
 * Retry-After. Die Oberfläche lädt so selbst nach; niemand muss die Seite neu laden. Ein
 * Fehler, nach dem nicht mehr versucht wird, geht wie bisher an den Abonnenten.
 */
export function mitNeuversuch<T>(optionen: NeuversuchOptionen = {}): MonoTypeOperatorFunction<T> {
  const nochmal = optionen.nochmal ?? ((fehler: unknown) => voruebergehend(fehler));
  return retry<T>({
    delay: (fehler: unknown, versuch: number) => {
      if (!nochmal(fehler, versuch)) {
        return throwError(() => fehler);
      }
      const ms = wartezeitMs(fehler, versuch, optionen.zufall);
      optionen.beimWarten?.(fehler, versuch, ms);
      return timer(ms);
    },
  });
}
