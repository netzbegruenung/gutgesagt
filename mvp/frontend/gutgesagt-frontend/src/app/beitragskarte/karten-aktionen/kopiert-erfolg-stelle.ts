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

  zeigen(karte: object): void {
    this.aktiveKarte.set(karte);
  }

  /** Nur die Karte, die gerade dran ist, kann ihren Text schließen. */
  schliessen(karte: object): void {
    if (this.aktiveKarte() === karte) {
      this.aktiveKarte.set(null);
    }
  }
}
