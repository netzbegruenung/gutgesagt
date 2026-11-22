import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { from, of } from 'rxjs';
import { catchError, map, mergeMap, switchMap, toArray } from 'rxjs/operators';

import { BeitragskarteComponent } from '../beitragskarte/beitragskarte.component';
import { KartenDaten, ausEinzelansicht } from '../beitragskarte/karten-daten';
import { ContentService } from '../services/content.service';
import { MerklisteService } from '../services/merkliste.service';

/** So viele Beitraege laedt der Reiter zugleich. */
export const LADEN_PARALLEL = 6;

export const GEMERKT_TEXTE = {
  laedt: 'Lade deine Merkliste …',
  leer: 'Noch nichts gemerkt. Tipp an einer Antwort auf „Merken“, dann steht sie hier.',
  fehler: 'Deine Merkliste ließ sich gerade nicht laden.',
  nochmal: 'Noch einmal versuchen',
  weg: (n: number) =>
    n === 1
      ? 'Ein gemerkter Beitrag ist nicht mehr da (gelöscht oder gesperrt).'
      : `${n} gemerkte Beiträge sind nicht mehr da (gelöscht oder gesperrt).`,
} as const;

/**
 * Der Reiter „Gemerkt“ in Meine Beiträge (#758): die eigene Merkliste als volle Karten,
 * zuletzt gemerkt zuerst. Die Beiträge kommen über ihre eigene Adresse (wie /beitrag/:id);
 * was dort nicht mehr da ist, fehlt hier und wird in einer Zeile genannt. Entfernen geht
 * am Knopf „Gemerkt“ der Karte; die Karte verschwindet dann sofort aus der Liste.
 *
 * Steht als Reiter in Meine Beiträge, solange es „Meine“ als eigenes Menü noch nicht gibt
 * (Navigation #752); danach wandert er dorthin.
 */
@Component({
  selector: 'app-gemerkt',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatProgressSpinnerModule, BeitragskarteComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div *ngIf="laedt()" class="gemerkt-laedt" role="status">
      <mat-spinner diameter="32"></mat-spinner><span>{{ texte.laedt }}</span>
    </div>
    <p *ngIf="!laedt() && fehler()" class="hinweis-box" role="alert">
      {{ texte.fehler }}
      <button mat-button type="button" class="nochmal-knopf" (click)="laden()">{{ texte.nochmal }}</button>
    </p>
    <ng-container *ngIf="!laedt() && !fehler()">
      <p *ngIf="!karten().length" class="gemerkt-leer">{{ texte.leer }}</p>
      <ul class="gemerkt-liste" *ngIf="karten().length" aria-label="Gemerkte Beiträge">
        <li *ngFor="let karte of karten(); trackBy: kennung">
          <app-beitragskarte [daten]="karte"></app-beitragskarte>
        </li>
      </ul>
      <p *ngIf="weg() > 0" class="gemerkt-weg">{{ texte.weg(weg()) }}</p>
    </ng-container>
  `,
  styles: [
    `
      .gemerkt-laedt { display: flex; align-items: center; gap: 12px; margin: 16px 0; }
      .gemerkt-liste { list-style: none; margin: 0; padding: 0; display: grid; gap: 16px; }
      .gemerkt-leer, .gemerkt-weg { color: var(--text-leise); }
      .nochmal-knopf { min-height: 44px; }
    `,
  ],
})
export class GemerktComponent implements OnInit {
  readonly texte = GEMERKT_TEXTE;
  readonly laedt = signal(true);
  readonly fehler = signal(false);
  /** Beitraege, die beim Laden nicht mehr da waren. */
  readonly weg = signal(0);

  private readonly merkliste = inject(MerklisteService);
  private readonly content = inject(ContentService);
  private readonly destroyRef = inject(DestroyRef);
  /** Geladene Karten je Beitrag; die Reihenfolge kommt aus der Merkliste. */
  private readonly geladen = signal(new Map<string, KartenDaten>());

  /** In der Reihenfolge der Merkliste; Entfernte verschwinden sofort. */
  readonly karten = computed(() => {
    const karten = this.geladen();
    return this.merkliste
      .eintraege()
      .map((e) => karten.get(e.content_id))
      .filter((k): k is KartenDaten => !!k);
  });

  ngOnInit(): void {
    this.laden();
  }

  laden(): void {
    this.laedt.set(true);
    this.fehler.set(false);
    this.merkliste
      .laden()
      .pipe(
        switchMap((eintraege) =>
          // Hoechstens LADEN_PARALLEL Abrufe zugleich; die Reihenfolge kommt aus der Merkliste
          from(eintraege).pipe(
            mergeMap(
              (e) =>
                this.content.beitragLaden(e.content_id).pipe(
                  map((beitrag): KartenDaten | null => ausEinzelansicht(beitrag)),
                  catchError(() => of(null)),
                ),
              LADEN_PARALLEL,
            ),
            toArray(),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (karten) => {
          this.geladen.set(new Map(karten.filter((k): k is KartenDaten => !!k).map((k) => [k.id, k])));
          this.weg.set(karten.filter((k) => !k).length);
          this.laedt.set(false);
        },
        error: () => {
          this.fehler.set(true);
          this.laedt.set(false);
        },
      });
  }

  kennung(_: number, karte: KartenDaten): string {
    return karte.id;
  }
}
