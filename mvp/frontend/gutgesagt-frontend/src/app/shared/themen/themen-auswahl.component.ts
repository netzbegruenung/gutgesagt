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
 *
 * Themenvorschlaege (#401, `vorschlaege`): eine eigene Zeile „Vorschlag:“ ueber der Liste,
 * je noch nicht gewaehltem Vorschlag ein gestrichelter Chip „+ Thema“, dazu „Übernehmen“.
 * Ein Tipp auf einen Vorschlag waehlt ihn (dann ist er aus der Zeile weg), „Übernehmen“
 * waehlt alle, soweit die Grenze reicht. In der Liste selbst ist nichts hervorgehoben: Ein
 * hervorgehobener Chip sah aus wie schon gewaehlt (Sebastian 23.11.). Gewaehlt wird nie von
 * selbst. Ist die Grenze erreicht oder alles gewaehlt, fehlt die Zeile.
 */
@Component({
  selector: 'app-themen-auswahl',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ng-container *ngIf="offeneVorschlaege as offen">
    <div *ngIf="offen.length" class="themen-vorschlag" role="group" aria-label="Vorgeschlagene Themen">
      <span class="vorschlag-titel" aria-hidden="true">Vorschlag:</span>
      <button *ngFor="let thema of offen" type="button" class="chip vorschlag-chip"
              [attr.aria-label]="thema.name + ' übernehmen'"
              (click)="uebernehmen([thema])"><span class="vorschlag-plus" aria-hidden="true">+</span><img *ngIf="thema.motiv" class="thema-motiv" [src]="thema.motiv" alt="" aria-hidden="true" width="18" height="18">{{ thema.name }}</button>
      <button type="button" class="vorschlag-alle" (click)="uebernehmen(offen)">{{ alleUebernehmenText(offen.length) }}</button>
    </div>
    </ng-container>
    <div class="themen-auswahl" role="group" [attr.aria-label]="beschriftung">
      <button *ngFor="let thema of themen" type="button" class="chip thema-chip"
              [class.gewaehlt]="istGewaehlt(thema)"
              [attr.aria-pressed]="istGewaehlt(thema)"
              [disabled]="!istGewaehlt(thema) && voll"
              (click)="umschalten(thema)"><img *ngIf="thema.motiv" class="thema-motiv" [src]="thema.motiv" alt="" aria-hidden="true" width="18" height="18">{{ thema.name }}</button>
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
    return this.hoechstens === 1 ? 'Ein Thema, optional.' : `Bis zu ${zahl} Themen, optional.`;
  }

  /** Die Vorschlaege, die noch nicht gewaehlt sind und waehlbar waeren; leer: keine Zeile. */
  get offeneVorschlaege(): Thema[] {
    if (this.voll) {
      return [];
    }
    return this.vorschlaege
      .map((s) => this.themen.find((t) => t.schluessel === s))
      .filter((t): t is Thema => t !== undefined && !this.istGewaehlt(t));
  }

  /** „Übernehmen“, bei zweien „Beide übernehmen“, ab drei „Alle übernehmen“. */
  alleUebernehmenText(anzahl: number): string {
    return anzahl >= 3 ? 'Alle übernehmen' : anzahl === 2 ? 'Beide übernehmen' : 'Übernehmen';
  }

  /** Vorschlaege waehlen, der Reihe nach, soweit die Grenze reicht. */
  uebernehmen(vorschlaege: Thema[]): void {
    const frei = this.hoechstens - this.gewaehlt.length;
    const neu = vorschlaege
      .map((t) => t.schluessel)
      .filter((s) => !this.gewaehlt.includes(s))
      .slice(0, Math.max(0, frei));
    if (neu.length) {
      this.gewaehltChange.emit([...this.gewaehlt, ...neu]);
    }
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
