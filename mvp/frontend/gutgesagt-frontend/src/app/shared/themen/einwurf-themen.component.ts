import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  DestroyRef,
  EventEmitter,
  Input,
  OnChanges,
  OnInit,
  Output,
  SimpleChanges,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, of } from 'rxjs';
import { catchError, concatMap, map, tap } from 'rxjs/operators';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { Thema } from '../../services/dtos/themenDtos';
import { EinwurfService, HOECHSTENS_THEMEN_JE_EINWURF } from '../../services/einwurf.service';
import { ThemenService, schluesselVon } from '../../services/themen.service';
import { einwilligungFehlt } from '../../services/art9-einwilligung.service';
import { ThemenAuswahlComponent } from './themen-auswahl.component';
import { THEMEN_NICHT_GESPEICHERT } from './themen-meldung';

let naechsteId = 0;

/** Ein Auftrag: welcher Einwurf welche Themen bekommen soll. */
interface Auftrag {
  einwurfId: string;
  schluessel: string[];
}

/**
 * Die Themen eines Einwurfs nachtraeglich aendern: in der Destillier-Ansicht unter dem
 * Kopf (aufklappbar) und im Sheet „Themen ändern“ aus dem ⋮-Menue der Einwurf-Karte
 * (`immerOffen`). Bedienung wie bei der Aussage (app-aussage-themen): Jeder Klick
 * speichert gleich, der Reihe nach, damit am Ende der letzte gilt; ein Spinner zeigt
 * das Speichern. Hoechstens zwei wie beim Einwerfen. Darf jede angemeldete Person, wie
 * das Destillieren (PUT /rawinput/{id}/themen).
 *
 * Die Marken zeigt der Kopf des Einwurfs selbst; hier stehen nur Umschalter und Auswahl.
 * Gemeldet wird jeder neue Stand (`themenChange`): gleich nach dem Klick und noch einmal,
 * wenn gespeichert ist (nach einem Fehler der Stand davor).
 */
@Component({
  selector: 'app-einwurf-themen',
  standalone: true,
  imports: [CommonModule, MatProgressSpinnerModule, ThemenAuswahlComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ng-container *ngIf="liste.length">
      <div class="einwurf-themen-kopf" *ngIf="!immerOffen || speichert">
        <button *ngIf="!immerOffen" type="button" class="themen-umschalter"
                [attr.aria-expanded]="offen" [attr.aria-controls]="offen ? id : null"
                (click)="umschalten()">{{ themen.length ? 'Themen des Einwurfs ändern' : 'Themen wählen' }}</button>
        <mat-spinner *ngIf="speichert" class="themen-speichert" diameter="16"
                     aria-label="Themen werden gespeichert"></mat-spinner>
      </div>
      <div *ngIf="offen || immerOffen" class="themen-bearbeiten" [id]="id">
        <app-themen-auswahl [themen]="liste" [gewaehlt]="gewaehlt" [hoechstens]="hoechstens"
                            beschriftung="Themen des Einwurfs"
                            (gewaehltChange)="setzen($event)"></app-themen-auswahl>
        <p *ngIf="fehler" class="themen-fehler" role="alert">{{ fehler }}</p>
      </div>
    </ng-container>
    <span class="visually-hidden" aria-live="polite">{{ ansage }}</span>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .einwurf-themen-kopf {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      /* Nebenaktion: leise, aber als Link erkennbar; Tippziel 44 px hoch (WCAG 2.5.5) */
      .themen-umschalter {
        min-height: 44px;
        border: none;
        background: none;
        padding: 0;
        font: inherit;
        font-size: 14px;
        color: var(--text-leise);
        text-decoration: underline;
        text-underline-offset: 3px;
        cursor: pointer;
      }

      .themen-umschalter:hover {
        color: var(--text);
      }

      .themen-umschalter:focus-visible {
        outline: 2px solid var(--akzent-tanne);
        outline-offset: 2px;
      }

      .themen-bearbeiten {
        margin-top: 4px;
      }

      .themen-fehler {
        margin: 4px 0 0;
        font-size: 13px;
        color: var(--fehler);
      }
    `,
  ],
})
export class EinwurfThemenComponent implements OnInit, OnChanges {
  @Input({ required: true }) einwurfId!: string;
  /** Die Themen des Einwurfs, wie er geladen ist. */
  @Input() themen: Thema[] = [];
  /** Im Sheet: die Auswahl steht gleich da, ohne Umschalter. */
  @Input() immerOffen = false;
  @Output() themenChange = new EventEmitter<Thema[]>();

  readonly hoechstens = HOECHSTENS_THEMEN_JE_EINWURF;
  readonly id = `einwurf-themen-${naechsteId++}`;
  liste: Thema[] = [];
  offen = false;
  speichert = false;
  fehler: string | null = null;
  ansage = '';
  /** Ob seit dem Oeffnen etwas gespeichert ist; das Sheet laedt danach die Liste neu. */
  geaendert = false;

  private readonly auftraege = new Subject<Auftrag>();
  private offeneAuftraege = 0;
  private gespeichert: Thema[] = [];
  private zuletztThemen: Thema[] | null = null;
  private zuletztSchluessel: string[] = [];

  constructor(
    private einwurfService: EinwurfService,
    private themenService: ThemenService,
    private cdr: ChangeDetectorRef,
    private destroyRef: DestroyRef,
  ) {}

  /** Ein anderer Einwurf (Naechster Einwurf) beginnt zugeklappt, ohne Fehler der vorigen. */
  ngOnChanges(changes: SimpleChanges): void {
    if (changes['einwurfId'] && !changes['einwurfId'].firstChange) {
      this.offen = false;
      this.fehler = null;
      this.ansage = '';
    }
    if (changes['themen'] && this.offeneAuftraege === 0) {
      this.gespeichert = this.themen;
    }
  }

  ngOnInit(): void {
    // Ist die Liste nicht ladbar, fehlt die Auswahl; der Kopf zeigt die Themen trotzdem.
    this.themenService
      .liste()
      .pipe(
        catchError(() => of([] as Thema[])),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((liste) => {
        this.liste = liste;
        this.cdr.markForCheck();
      });
    this.auftraege
      .pipe(
        // Beim Einreihen zaehlen, nicht beim Senden: sonst gaelte der Einwurf zwischen zwei
        // Auftraegen als fertig und zeigte kurz den vorletzten Stand.
        tap(() => this.offeneAuftraege++),
        concatMap((auftrag) =>
          this.einwurfService.themenSetzen(auftrag.einwurfId, auftrag.schluessel).pipe(
            map((einwurf) => ({ auftrag, themen: einwurf.themen ?? [], fehler: null as unknown })),
            catchError((fehler) => of({ auftrag, themen: null, fehler })),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(({ auftrag, themen, fehler }) => {
        this.offeneAuftraege--;
        // Eine Antwort zu einem vorigen Einwurf setzt hier nichts mehr.
        if (auftrag.einwurfId !== this.einwurfId) {
          return;
        }
        if (themen === null) {
          this.fehler = einwilligungFehlt(fehler)
            ? 'Dafür brauchst du die Zustimmung zu den Nutzungsbedingungen.'
            : THEMEN_NICHT_GESPEICHERT;
        } else {
          this.gespeichert = themen;
          this.geaendert = true;
        }
        if (this.offeneAuftraege === 0) {
          this.speichert = false;
          if (!this.fehler) {
            this.ansage = 'Themen gespeichert.';
          }
          this.themenChange.emit(this.gespeichert);
        }
        this.cdr.markForCheck();
      });
  }

  /** Die gewaehlten Schluessel, als dasselbe Array, solange sich die Themen nicht aendern. */
  get gewaehlt(): string[] {
    if (this.themen !== this.zuletztThemen) {
      this.zuletztThemen = this.themen;
      this.zuletztSchluessel = schluesselVon(this.themen);
    }
    return this.zuletztSchluessel;
  }

  umschalten(): void {
    this.fehler = null;
    this.offen = !this.offen;
  }

  setzen(schluessel: string[]): void {
    this.fehler = null;
    this.ansage = '';
    this.speichert = true;
    // Die Anzeige folgt sofort, damit ein zweiter schneller Klick auf dem ersten aufbaut.
    const jetzt = schluessel
      .map((s) => this.liste.find((t) => t.schluessel === s))
      .filter((t): t is Thema => t !== undefined);
    this.themenChange.emit(jetzt);
    this.auftraege.next({ einwurfId: this.einwurfId, schluessel });
  }
}
