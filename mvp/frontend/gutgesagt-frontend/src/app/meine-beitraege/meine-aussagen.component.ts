import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ROUTES } from '../shared/constants/app.constants';
import { AntwortAufAussage, EigeneAussagen, MeineAussagenService } from './meine-aussagen.service';

const DATUM = new Intl.DateTimeFormat('de-DE', { day: 'numeric', month: 'long', year: 'numeric' });

/** Sichtbare Namen der Beitragstypen einer Antwort. */
const TYP: Record<string, string> = {
  commentary: 'Kommentar',
  generic_text: 'Hintergrundinfo',
  post: 'Post',
  image: 'Bild',
};

/**
 * „Meine Aussagen“ (#760, Folge #741): die eigenen Aussagen mit ihren Antworten, Ziel der Kachel
 * „neue Antworten auf deine Aussagen“. Neue Antworten anderer tragen „Neu“ als Symbol mit Text.
 * Nur mit dem Schalter „antworten_hinweis“; ohne ihn zeigt Meine Beiträge den Reiter nicht.
 */
@Component({
  selector: 'app-meine-aussagen',
  standalone: true,
  imports: [CommonModule, RouterLink, MatButtonModule, MatIconModule, MatProgressSpinnerModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div *ngIf="laedt" class="laedt" role="status">
      <mat-spinner diameter="32" aria-hidden="true"></mat-spinner>
      <span>Lade deine Aussagen …</span>
    </div>

    <div *ngIf="fehler" class="hinweis" role="alert">
      <p>Deine Aussagen sind gerade nicht erreichbar.</p>
      <button mat-stroked-button type="button" (click)="laden()">
        <mat-icon aria-hidden="true">refresh</mat-icon>
        Noch einmal versuchen
      </button>
    </div>

    <ng-container *ngIf="daten">
      <p *ngIf="!daten.aussagen.length" class="hinweis" data-testid="keine-aussagen">
        Du hast noch keine Aussage angelegt. Aussagen legst du an, wenn du beim Schreiben eine neue Aussage
        einträgst, auf die dein Beitrag antwortet.
      </p>
      <p *ngIf="daten.aussagen.length" class="einleitung">
        Was andere auf deine Aussagen geantwortet haben. „Neu“ heißt: in den letzten {{ daten.zeitraum_tage }} Tagen.
      </p>
      <ul class="aussagen">
        <li *ngFor="let aussage of daten.aussagen; trackBy: kennung" class="aussage" data-testid="eigene-aussage">
          <p class="aussage-kopf">
            <mat-icon aria-hidden="true">record_voice_over</mat-icon>
            <span class="visually-hidden">Aussage: </span>
            <q class="aussage-text">{{ aussage.text }}</q>
          </p>
          <p class="aussage-datum">Angelegt am {{ datum(aussage.created) }}</p>
          <p *ngIf="!aussage.antworten.length" class="keine-antwort">Noch keine Antwort.</p>
          <ul *ngIf="aussage.antworten.length" class="antworten" [attr.aria-label]="anzahl(aussage.antworten.length)">
            <li *ngFor="let antwort of aussage.antworten; trackBy: kennung" class="antwort" data-testid="antwort">
              <span *ngIf="antwort.neu" class="neu" data-testid="neu">
                <mat-icon aria-hidden="true">fiber_new</mat-icon>
                Neu
              </span>
              <a [routerLink]="[beitragPfad, antwort.id]">{{ antwort.titel || 'Beitrag ohne Titel' }}</a>
              <span class="antwort-angaben">{{ typ(antwort) }}{{ antwort.von_dir ? ' · von dir' : '' }}</span>
            </li>
          </ul>
        </li>
      </ul>
    </ng-container>
  `,
  styles: [`
    :host { display: block; }
    .laedt { display: flex; align-items: center; gap: 12px; margin: 24px 0; }
    .hinweis, .einleitung { color: var(--text-leise); }
    .einleitung { margin: 0 0 12px; }
    .aussagen, .antworten { list-style: none; margin: 0; padding: 0; }
    .aussage {
      margin: 0 0 12px; padding: 12px 16px; background: var(--flaeche);
      border-radius: var(--border-radius-large); box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12); overflow-wrap: anywhere;
    }
    .aussage p { margin: 0; }
    .aussage-kopf { display: flex; align-items: flex-start; gap: 8px; font-weight: 700; }
    .aussage-kopf mat-icon { flex-shrink: 0; color: var(--akzent-schrift); }
    .aussage-datum, .keine-antwort, .antwort-angaben { font-size: 0.875rem; color: var(--text-leise); }
    .aussage-datum { margin: 2px 0 8px 32px !important; }
    .keine-antwort { margin-left: 32px !important; }
    .antworten { margin-left: 32px; }
    .antwort { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; padding: 8px 0; border-top: 1px solid var(--linie); }
    .antwort a { color: var(--primaer-text); text-decoration: underline; min-height: 24px; display: inline-flex; align-items: center; }
    .neu {
      display: inline-flex; align-items: center; gap: 2px; padding: 0 8px 0 4px; border-radius: 12px;
      background: var(--primaer-tint); color: var(--akzent-schrift); font-size: 0.8125rem; font-weight: 700;
    }
    .neu mat-icon { font-size: 18px; width: 18px; height: 18px; }
    @media (max-width: 479px) {
      .aussage-datum, .keine-antwort { margin-left: 0 !important; }
      .antworten { margin-left: 0; }
    }
  `],
})
export class MeineAussagenComponent implements OnInit {
  daten: EigeneAussagen | null = null;
  laedt = false;
  fehler = false;
  readonly beitragPfad = ROUTES.BEITRAG;

  private readonly dienst = inject(MeineAussagenService);
  private readonly cdr = inject(ChangeDetectorRef);

  ngOnInit(): void {
    this.laden();
  }

  laden(): void {
    this.laedt = this.daten === null;
    this.fehler = false;
    this.dienst.laden().subscribe({
      next: (daten) => {
        this.daten = daten;
        this.laedt = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.laedt = false;
        this.fehler = this.daten === null;
        this.cdr.markForCheck();
      },
    });
  }

  datum(wert: string): string {
    return DATUM.format(new Date(wert));
  }

  typ(antwort: AntwortAufAussage): string {
    return TYP[antwort.content_type] ?? 'Beitrag';
  }

  anzahl(zahl: number): string {
    return zahl === 1 ? '1 Antwort' : `${zahl} Antworten`;
  }

  kennung(_: number, eintrag: { id: string }): string {
    return eintrag.id;
  }
}
