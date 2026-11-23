import { HttpErrorResponse } from '@angular/common/http';

/**
 * Der Tagesdeckel (GLOSSARY.md): Wer heute schon so viele Beiträge, Aussagen und
 * Einwürfe angelegt hat, wie der Server erlaubt, bekommt 429 mit dieser Kennung
 * (middleware/tagesdeckel.py im Suchdienst). Erneut versuchen hilft dann nicht.
 */
export const TAGESDECKEL_MELDUNG = 'Für heute ist Schluss mit neuen Beiträgen, morgen geht’s weiter.';

export function tagesdeckelErreicht(fehler: unknown): boolean {
  const f = fehler as { status?: number; error?: { error?: unknown } | null } | null | undefined;
  return f?.status === 429 && f?.error?.error === 'TAGESDECKEL';
}

/**
 * Die Meldung zu einem gescheiterten Speichern: am Tagesdeckel dessen Meldung, bei 422
 * die erste Validierungsmeldung des Backends, knapp (ohne Pydantics "Value error, "),
 * sonst null - dann gilt die allgemeine Meldung.
 */
export function validierungsMeldung(fehler: unknown): string | null {
  if (tagesdeckelErreicht(fehler)) {
    return TAGESDECKEL_MELDUNG;
  }
  if (!(fehler instanceof HttpErrorResponse) || fehler.status !== 422) {
    return null;
  }
  const detail = (fehler.error as { detail?: unknown } | null)?.detail;
  const erste = Array.isArray(detail) ? detail[0] : detail;
  const text = typeof erste === 'string' ? erste : (erste as { msg?: unknown } | undefined)?.msg;
  return typeof text === 'string' && text.trim() ? text.replace(/^Value error,\s*/i, '').trim() : null;
}
