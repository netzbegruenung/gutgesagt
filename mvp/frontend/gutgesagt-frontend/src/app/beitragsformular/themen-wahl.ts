import { inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AbstractControl } from '@angular/forms';
import { Thema } from '../services/dtos/themenDtos';
import { ThemenService } from '../services/themen.service';
import { AntwortAuf } from './antwort-auf/antwort-auf.component';
import { themenWaehlbar } from './aussage-fuer-anfrage';

/**
 * Die Themenwahl fuer die Aussage eines Beitragsformulars (#455), fuer das
 * Kommentar- und das Hintergrundinfo-Formular gleich. Haelt das Control der Themen
 * passend zur Aussage im Antwort-auf-Block.
 *
 * Im Konstruktor der Komponente anlegen: Die Liste laedt sie selbst und hoert mit
 * der Komponente auf.
 */
export class ThemenWahl {
  /** Die feste Themenliste; leer, solange sie nicht geladen (oder nicht ladbar) ist. */
  liste: Thema[] = [];
  /** Die Themen des Einwurfs, aus dem der Beitrag entsteht (vorschlagen); sonst leer. */
  private vorschlag: string[] = [];
  /** Ob die Themenwahl zuletzt zu sehen war; der Vorschlag kommt nur beim Erscheinen. */
  private warWaehlbar = false;

  constructor(private readonly themen: AbstractControl<string[] | null>) {
    // Ist die Liste nicht ladbar, fehlt die Themenwahl; speichern geht trotzdem.
    inject(ThemenService)
      .liste()
      .pipe(takeUntilDestroyed())
      .subscribe({
        next: (liste) => {
          this.liste = liste;
          // Kommt die Liste erst, waehrend die Wahl schon zu sehen ist: jetzt vorschlagen.
          if (this.warWaehlbar) {
            this.vorschlagEinsetzen();
          }
        },
        error: () => (this.liste = []),
      });
  }

  /** Zu sehen fuer eine neue Aussage per Text (themenWaehlbar), wenn die Liste da ist. */
  zeigtFuer(aussage: AntwortAuf): boolean {
    return this.liste.length > 0 && themenWaehlbar(aussage);
  }

  /**
   * Ist keine Themenwahl mehr moeglich (eine vorhandene Aussage gewaehlt, das Feld
   * leer), fallen die gewaehlten Themen weg: Unsichtbar mitgefuehrt kaemen sie
   * spaeter ungesehen mit einer anderen Aussage zurueck.
   */
  anAussageAnpassen(aussage: AntwortAuf): void {
    const waehlbar = themenWaehlbar(aussage);
    if (!waehlbar && this.themen.value?.length) {
      this.themen.setValue([]);
    }
    if (waehlbar && !this.warWaehlbar) {
      this.vorschlagEinsetzen();
    }
    this.warWaehlbar = waehlbar;
  }

  /**
   * Die beim Einwerfen gewaehlten Themen als Vorauswahl fuer eine neue Aussage. Sie stehen
   * erst da, wenn die Themenwahl erscheint (eine Aussage per Text ist gewaehlt), und nur,
   * wenn noch keins gewaehlt ist; danach aendert die Person sie wie sonst. Wer alle
   * abwaehlt, bekommt sie nicht zurueck, solange die Wahl zu sehen bleibt.
   */
  vorschlagen(themen: string[]): void {
    this.vorschlag = [...themen];
    if (this.warWaehlbar) {
      this.vorschlagEinsetzen();
    }
  }

  /**
   * Nach "Zuruecksetzen": Die Seite leert den Antwort-auf-Block ohne aussageSetzen. Wie
   * vor der ersten Wahl kommt der Vorschlag mit der naechsten neuen Aussage wieder.
   */
  zuruecksetzen(): void {
    this.warWaehlbar = false;
    this.themen.setValue([]);
  }

  /**
   * Nur mit geladener Liste und nur Schluessel daraus: Ohne Liste ist die Wahl unsichtbar
   * (zeigtFuer), und ungesehene Themen kaemen mit der Aussage in die Datenbank.
   */
  private vorschlagEinsetzen(): void {
    const bekannt = this.vorschlag.filter((s) => this.liste.some((t) => t.schluessel === s));
    if (bekannt.length && !this.themen.value?.length) {
      this.themen.setValue(bekannt);
    }
  }

  setzen(themen: string[]): void {
    this.themen.setValue(themen);
  }
}
