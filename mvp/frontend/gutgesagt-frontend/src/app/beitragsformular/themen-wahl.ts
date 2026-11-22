import { DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AbstractControl } from '@angular/forms';
import { Subscription } from 'rxjs';
import { Thema } from '../services/dtos/themenDtos';
import { ThemenVorschlaege } from '../shared/themen/themen-vorschlaege';
import { AussageMitThemenFeld, ThemenService } from '../services/themen.service';
import { AntwortAuf } from './antwort-auf/antwort-auf.component';
import { themenWaehlbar } from './aussage-fuer-anfrage';

/**
 * Die Themenwahl fuer die Aussage eines Beitragsformulars (#455), fuer das
 * Kommentar- und das Hintergrundinfo-Formular gleich. Haelt das Control der Themen
 * passend zur Aussage im Antwort-auf-Block.
 *
 * Ist eine vorhandene Aussage gewaehlt, haelt sie deren Themen (`vorhandene`): Das
 * Formular zeigt sie mit „Themen ändern“ wie die Ergebnisseite (app-aussage-themen), denn
 * ein Beitrag hat keine eigenen Themen, er steht unter denen seiner Aussage.
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
  /** Themenvorschlaege (#401) zum Text der neuen Aussage, fuer [vorschlaege]. */
  readonly themenVorschlaege = new ThemenVorschlaege();
  /**
   * Die gewaehlte, vorhandene Aussage mit ihren Themen; null ohne, solange sie laden oder
   * wenn das Nachsehen scheiterte (dann kein Zuordnen, das vorhandene ersetzte).
   */
  vorhandene: AussageMitThemenFeld | null = null;
  /** Die ID, deren Themen gerade geladen werden oder geladen sind. */
  private vorhandeneId: string | null = null;
  private vorhandeneAbo?: Subscription;
  private readonly themenService = inject(ThemenService);
  private readonly destroyRef = inject(DestroyRef);

  constructor(private readonly themen: AbstractControl<string[] | null>) {
    // Ist die Liste nicht ladbar, fehlt die Themenwahl; speichern geht trotzdem.
    this.themenService
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
    this.themenVorschlaege.text(waehlbar ? aussage.text : '');
    this.vorhandeneLaden(aussage.id || null);
  }

  /** Die Themen der gewaehlten, vorhandenen Aussage nachsehen, einmal je Aussage. */
  private vorhandeneLaden(id: string | null): void {
    if (id === this.vorhandeneId) {
      return;
    }
    this.vorhandeneAbo?.unsubscribe();
    this.vorhandeneId = id;
    this.vorhandene = null;
    if (!id) {
      return;
    }
    this.vorhandeneAbo = this.themenService
      .vonAussage(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (themen) => (this.vorhandene = { statement_id: id, themen }),
        error: () => (this.vorhandene = null),
      });
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
    this.themenVorschlaege.text('');
    this.vorhandeneLaden(null);
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
