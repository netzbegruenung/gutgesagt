import { Injectable, signal } from '@angular/core';

/**
 * Welche Karte gerade ihren Erfolgstext nach dem Kopieren zeigt (#785). Es steht immer nur
 * der Text der zuletzt kopierten Karte da: Kopiert jemand Karte B, verschwindet er an
 * Karte A, damit höchstens ein Pflänzchen auf dem Bildschirm steht und der alte Hinweis
 * nicht wie die aktuelle Rückmeldung aussieht. Nichts davon wird gespeichert.
 */
@Injectable({ providedIn: 'root' })
export class KopiertErfolgStelle {
  private readonly aktiveKarte = signal<object | null>(null);
  readonly aktiv = this.aktiveKarte.asReadonly();
  /** Die zuletzt kopierte Karte, auch wenn sie keinen Kasten zeigt (Snackbar-Weg). */
  private letzteKarte: object | null = null;

  zeigen(karte: object): void {
    this.letzteKarte = karte;
    this.aktiveKarte.set(karte);
  }

  /**
   * Diese Karte wurde kopiert und meldet es per Snackbar statt im Kasten: Ein offener
   * Kasten, auch an derselben Karte, geht zu, sonst stünde „Kopiert“ doppelt da.
   */
  ohneKasten(karte: object): void {
    this.letzteKarte = karte;
    this.aktiveKarte.set(null);
  }

  /** Ob seither keine andere Karte kopiert wurde; für späte Server-Antworten. */
  istZuletzt(karte: object): boolean {
    return this.letzteKarte === karte;
  }

  /** Nur die Karte, die gerade dran ist, kann ihren Text schließen. */
  schliessen(karte: object): void {
    if (this.aktiveKarte() === karte) {
      this.aktiveKarte.set(null);
    }
  }
}
