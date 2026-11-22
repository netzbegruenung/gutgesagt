import { inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, of } from 'rxjs';
import { debounceTime, distinctUntilChanged, map, switchMap } from 'rxjs/operators';
import { HOECHSTENS_THEMEN_JE_AUSSAGE, ThemenService } from '../../services/themen.service';

/** So lange Pause beim Tippen, bevor nach Vorschlaegen gefragt wird. */
export const VORSCHLAG_PAUSE_MS = 600;
/** Kuerzere Texte bekommen keinen Vorschlag: zu wenig Inhalt fuer ein Thema. */
export const VORSCHLAG_AB_ZEICHEN = 12;

/**
 * Themenvorschlaege (#401) zum Text eines Formulars, fuer <app-themen-auswahl [vorschlaege]>.
 * Fragt nach einer Pause beim Tippen; ein neuer Text verwirft die offene Antwort. Scheitert
 * die Abfrage, gibt es keinen Vorschlag (ThemenService.vorschlaege). Gewaehlt wird nichts.
 *
 * Im Konstruktor (Injektionskontext) anlegen: Sie hoert mit der Komponente auf.
 * `geaendert` ruft sie nach jedem neuen Vorschlag, etwa fuer markForCheck bei OnPush.
 */
export class ThemenVorschlaege {
  /** Die vorgeschlagenen Schluessel, das naechste zuerst. */
  vorschlaege: string[] = [];
  private readonly texte = new Subject<string>();

  constructor(hoechstens = HOECHSTENS_THEMEN_JE_AUSSAGE, geaendert?: () => void) {
    const service = inject(ThemenService);
    this.texte
      .pipe(
        map((text) => text.trim()),
        debounceTime(VORSCHLAG_PAUSE_MS),
        distinctUntilChanged(),
        switchMap((text) => (text.length < VORSCHLAG_AB_ZEICHEN ? of([]) : service.vorschlaege(text, hoechstens))),
        takeUntilDestroyed(),
      )
      .subscribe((vorschlaege) => {
        this.vorschlaege = vorschlaege;
        geaendert?.();
      });
  }

  /** Der aktuelle Text; leer nimmt die Vorschlaege (nach der Pause) weg. */
  text(text: string | null | undefined): void {
    this.texte.next(text ?? '');
  }
}
