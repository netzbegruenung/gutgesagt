import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Thema } from '../../services/dtos/themenDtos';
import { HOECHSTENS_THEMEN_JE_AUSSAGE } from '../../services/themen.service';

/** Die Grenze in Worten fuer den Hinweis; nur die, die vorkommen. */
const ZAHLWORT: Record<number, string> = { 2: 'zwei', 3: 'drei' };

/**
 * Themen waehlen, optional: fuer eine Aussage bis zu drei, beim Einwerfen bis zu zwei
 * (`hoechstens`). Jedes Thema ist ein Umschalter; ist die Grenze erreicht, lassen sich
 * weitere erst nach dem Abwaehlen eines davon waehlen.
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
              [attr.aria-pressed]="istGewaehlt(thema)"
              [disabled]="!istGewaehlt(thema) && voll"
              (click)="umschalten(thema)">{{ thema.name }}</button>
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
  @Output() gewaehltChange = new EventEmitter<string[]>();

  get voll(): boolean {
    return this.gewaehlt.length >= this.hoechstens;
  }

  get hinweis(): string {
    const zahl = ZAHLWORT[this.hoechstens] ?? String(this.hoechstens);
    return this.hoechstens === 1 ? 'Ein Thema, optional.' : `Bis zu ${zahl} Themen, optional.`;
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
