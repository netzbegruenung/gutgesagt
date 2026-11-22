import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  SimpleChanges,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AussageDesThemas, PassendesThema } from '../services/dtos/searchDtos';
import { SearchService } from '../services/search.service';
import { ROUTES } from '../shared/constants/app.constants';
import { SUCHTEXT_PARAM } from '../shared/formular-adresse';

/** So viele Aussagen liefert "Alle Aussagen zum Thema" hoechstens (ALLE_HOECHSTENS im Backend). */
export const ALLE_HOECHSTENS = 50;

/**
 * "Alles zum Thema" (#754): Passt eine kurze Sucheingabe ("Heizung") zu einem Thema,
 * steht ueber den Treffern ein Kasten mit Motiv und Namen des Themas und seinen
 * meistgenutzten Aussagen, auch wenn die Suche selbst nichts findet. Ein Klick auf eine
 * Aussage sucht nach ihr. "Alle N Aussagen zum Thema" laedt die uebrigen in den Kasten;
 * steht das Thema im Themenfilter der Treffer, schaltet "Nur Treffer zum Thema" ihn.
 *
 * Fuer Angemeldete und Besucher gleich; die Abfrage ist wie die Suche offen.
 */
@Component({
  selector: 'app-alles-zum-thema',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, RouterLink],
  templateUrl: './alles-zum-thema.component.html',
  styleUrls: ['./alles-zum-thema.component.css'],
})
export class AllesZumThemaComponent implements OnChanges {
  @Input() themen: PassendesThema[] = [];
  /** Das aktive Thema im Themenfilter der Treffer; null = alle. */
  @Input() aktiv: string | null = null;
  /** Die Themen, die der Themenfilter der Treffer anbietet; nur sie lassen sich hier schalten. */
  @Input() filterbar: readonly string[] = [];
  @Output() filtern = new EventEmitter<string | null>();

  readonly ergebnisse = ROUTES.RESULT;

  /** Je Thema alle Aussagen, sobald "Alle … zeigen" sie geladen hat. */
  private alle = new Map<string, AussageDesThemas[]>();
  laedt = new Set<string>();
  fehler = new Set<string>();
  /** Fuer Screenreader, nach dem Nachladen. */
  meldung = '';

  constructor(
    private searchService: SearchService,
    private cdr: ChangeDetectorRef,
    private element: ElementRef<HTMLElement>,
  ) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['themen']) {
      this.alle.clear();
      this.laedt.clear();
      this.fehler.clear();
      this.meldung = '';
    }
  }

  aussagenVon(thema: PassendesThema): AussageDesThemas[] {
    return this.alle.get(thema.schluessel) ?? thema.aussagen;
  }

  /** Gibt es mehr Aussagen, als der Kasten zeigt? */
  mehr(thema: PassendesThema): boolean {
    return !this.alle.has(thema.schluessel) && thema.anzahl_aussagen > thema.aussagen.length;
  }

  /** Der Knopf verspricht nicht mehr, als die Abfrage liefert. */
  alleText(thema: PassendesThema): string {
    return thema.anzahl_aussagen > ALLE_HOECHSTENS
      ? `Die ${ALLE_HOECHSTENS} meistgenutzten von ${thema.anzahl_aussagen} Aussagen zeigen`
      : `Alle ${thema.anzahl_aussagen} Aussagen zum Thema`;
  }

  antwortenText(anzahl: number): string {
    return anzahl === 1 ? '1 Antwort' : `${anzahl} Antworten`;
  }

  sucheNach(aussage: AussageDesThemas): Record<string, string> {
    return { [SUCHTEXT_PARAM]: aussage.text };
  }

  istFilterbar(thema: PassendesThema): boolean {
    return this.filterbar.includes(thema.schluessel);
  }

  filterUmschalten(thema: PassendesThema): void {
    this.filtern.emit(this.aktiv === thema.schluessel ? null : thema.schluessel);
  }

  alleLaden(thema: PassendesThema): void {
    const schluessel = thema.schluessel;
    if (this.laedt.has(schluessel)) {
      return;
    }
    this.laedt.add(schluessel);
    this.fehler.delete(schluessel);
    this.searchService.aussagenDesThemas(schluessel).subscribe({
      next: (antwort) => {
        this.laedt.delete(schluessel);
        // Ein neuer Suchtext kann den Kasten inzwischen ersetzt haben.
        if (!this.themen.some((t) => t.schluessel === schluessel)) {
          return;
        }
        const bisher = this.aussagenVon(thema).length;
        const aussagen = antwort.thema.aussagen;
        this.alle.set(schluessel, aussagen);
        this.meldung = `${aussagen.length} Aussagen zum Thema ${thema.name}`;
        // Der Knopf verschwindet: Der Fokus geht auf die erste neue Aussage, sonst auf die
        // letzte (wie "Alle N … zeigen" bei den Treffern), nicht verloren an die Seite.
        this.cdr.detectChanges();
        const links = this.element.nativeElement.querySelectorAll<HTMLElement>(
          `#alles-zum-thema-${CSS.escape(schluessel)} ~ .kasten-liste .kasten-aussage`,
        );
        (links[bisher] ?? links[links.length - 1])?.focus();
      },
      error: () => {
        this.laedt.delete(schluessel);
        this.fehler.add(schluessel);
        this.cdr.markForCheck();
      },
    });
    this.cdr.markForCheck();
  }

  nachSchluessel(_index: number, thema: PassendesThema): string {
    return thema.schluessel;
  }

  nachAussage(_index: number, aussage: AussageDesThemas): string {
    return aussage.statement_id;
  }
}
