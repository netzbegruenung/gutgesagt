import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Thema } from '../../services/dtos/themenDtos';
import { HOECHSTENS_THEMEN_JE_AUSSAGE } from '../../services/themen.service';

/** Die Grenze in Worten fuer den Hinweis; nur die, die vorkommen. */
const ZAHLWORT: Record<number, string> = { 2: 'zwei', 3: 'drei' };

/** „A“, „A und B“, „A, B und C“. */
function undListe(namen: string[]): string {
  return namen.length < 2 ? namen.join('') : `${namen.slice(0, -1).join(', ')} und ${namen[namen.length - 1]}`;
}

/**
 * Themen waehlen, optional: fuer eine Aussage bis zu drei, beim Einwerfen bis zu zwei
 * (`hoechstens`). Jedes Thema ist ein Umschalter; ist die Grenze erreicht, lassen sich
 * weitere erst nach dem Abwaehlen eines davon waehlen.
 *
 * Themenvorschlaege (#401, `vorschlaege`): Noch nicht gewaehlte Vorschlaege tragen den
 * Hinweis „vorgeschlagen“ im Chip und stehen im Hinweis darunter; ein Tipp waehlt sie wie
 * jedes andere Thema. Gewaehlt wird nie von selbst.
 */
@Component({
  selector: 'app-themen-auswahl',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="themen-auswahl" role="group" [attr.aria-label]="beschriftung">
      <button *ngFor="let thema of themen" type="button" class="chip thema-chip"
              [class.gewaehlt]="istGewaehlt(thema)"
              [class.vorgeschlagen]="istVorgeschlagen(thema)"
              [attr.aria-pressed]="istGewaehlt(thema)"
              [disabled]="!istGewaehlt(thema) && voll"
              (click)="umschalten(thema)"><img *ngIf="thema.motiv" class="thema-motiv" [src]="thema.motiv" alt="" aria-hidden="true" width="18" height="18">{{ thema.name }}<span *ngIf="istVorgeschlagen(thema)" class="vorschlag-marke">vorgeschlagen</span></button>
    </div>
    <p class="themen-hinweis">{{ hinweis }}</p>
  `,
  styleUrls: ['./themen.css'],
})
export class ThemenAuswahlComponent {
  @Input() themen: Thema[] = [];
  /** Die gewaehlten Schluessel. */
  @Input() gewaehlt: string[] = [];
  @Input() beschriftung = 'Themen';
  /** Wie viele hoechstens; ohne Angabe die Grenze der Aussage. */
  @Input() hoechstens = HOECHSTENS_THEMEN_JE_AUSSAGE;
  /** Vorgeschlagene Schluessel (#401), das naechste zuerst; leer ohne Vorschlag. */
  @Input() vorschlaege: string[] = [];
  @Output() gewaehltChange = new EventEmitter<string[]>();

  get voll(): boolean {
    return this.gewaehlt.length >= this.hoechstens;
  }

  get hinweis(): string {
    const zahl = ZAHLWORT[this.hoechstens] ?? String(this.hoechstens);
    const grenze = this.hoechstens === 1 ? 'Ein Thema, optional.' : `Bis zu ${zahl} Themen, optional.`;
    const offen = this.offeneVorschlaege;
    return offen.length ? `${grenze} Vorgeschlagen: ${undListe(offen.map((t) => t.name))}.` : grenze;
  }

  /** Die Vorschlaege, die noch nicht gewaehlt sind und waehlbar waeren. */
  private get offeneVorschlaege(): Thema[] {
    if (this.voll) {
      return [];
    }
    return this.vorschlaege
      .map((s) => this.themen.find((t) => t.schluessel === s))
      .filter((t): t is Thema => t !== undefined && !this.istGewaehlt(t));
  }

  istVorgeschlagen(thema: Thema): boolean {
    return !this.voll && !this.istGewaehlt(thema) && this.vorschlaege.includes(thema.schluessel);
  }

  istGewaehlt(thema: Thema): boolean {
    return this.gewaehlt.includes(thema.schluessel);
  }

  umschalten(thema: Thema): void {
    if (this.istGewaehlt(thema)) {
      this.gewaehltChange.emit(this.gewaehlt.filter((s) => s !== thema.schluessel));
    } else if (!this.voll) {
      this.gewaehltChange.emit([...this.gewaehlt, thema.schluessel]);
    }
  }
}
