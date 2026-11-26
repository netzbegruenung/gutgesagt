import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  computed,
  effect,
  inject,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { from, of } from 'rxjs';
import { catchError, map, mergeMap, toArray } from 'rxjs/operators';

import { BeitragskarteComponent } from '../beitragskarte/beitragskarte.component';
import { KartenDaten, ausEinzelansicht } from '../beitragskarte/karten-daten';
import { zurEinwilligungFuehren } from '../services/art9-einwilligung.service';
import { ContentService } from '../services/content.service';
import { Gemerkt, MerklisteService } from '../services/merkliste.service';

/** So viele Beitraege laedt der Reiter zugleich. */
export const LADEN_PARALLEL = 6;
/** So viele Karten laedt der Reiter auf einmal; „Weitere laden“ holt die naechsten. */
export const SEITE = 30;

export const GEMERKT_TEXTE = {
  laedt: 'Lade deine Merkliste …',
  leer: 'Noch nichts gemerkt. Tipp an einer Antwort auf „Merken“, dann steht sie hier.',
  fehler: 'Deine Merkliste ließ sich gerade nicht laden.',
  nochmal: 'Noch einmal versuchen',
  einwilligung: 'Die Merkliste gibt es mit deiner Einwilligung, wie Bewerten und Beitragen.',
  einwilligen: 'Einwilligen',
  weitere: 'Weitere laden',
  wegEntfernen: 'Aus der Merkliste entfernen',
  weg: (n: number) =>
    n === 1
      ? 'Ein gemerkter Beitrag ist nicht mehr da (gelöscht oder gesperrt).'
      : `${n} gemerkte Beiträge sind nicht mehr da (gelöscht oder gesperrt).`,
} as const;

/** Ergebnis je Eintrag: die Karte, „nicht mehr da“ (404) oder ein anderer Fehler. */
type Geladen = { id: string; karte: KartenDaten | null; fehler: boolean };

/**
 * Der Reiter „Gemerkt“ in Meine Beiträge (#758): die eigene Merkliste als volle Karten,
 * zuletzt gemerkt zuerst, je SEITE auf einmal. Die Beiträge kommen über ihre eigene
 * Adresse (wie /beitrag/:id); was dort nicht mehr da ist (404), fehlt hier, steht in einer
 * Zeile und lässt sich aus der Liste entfernen. Entfernen geht sonst am Knopf „Gemerkt“
 * der Karte; die Karte verschwindet sofort, der Fokus geht auf die Liste.
 *
 * Seit der Navigation #752 ist „Meine“ ein Ziel der unteren Leiste und des Kopfs, das zu
 * Meine Beiträge führt; der Reiter steht dort neben „Meine Beiträge“ und „Meine Einwürfe“.
 */
@Component({
  selector: 'app-gemerkt',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatProgressSpinnerModule, BeitragskarteComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div *ngIf="merkliste.einwilligungOffen()" class="gemerkt-laedt" role="status">
      <mat-spinner diameter="32"></mat-spinner><span>{{ texte.laedt }}</span>
    </div>
    <p *ngIf="!merkliste.einwilligungOffen() && !merkliste.eingewilligt()" class="hinweis-box gemerkt-einwilligung">
      {{ texte.einwilligung }}
      <button mat-button type="button" class="einwilligen-knopf" (click)="einwilligen()">{{ texte.einwilligen }}</button>
    </p>
    <ng-container *ngIf="merkliste.eingewilligt()">
      <div *ngIf="laedt()" class="gemerkt-laedt" role="status">
        <mat-spinner diameter="32"></mat-spinner><span>{{ texte.laedt }}</span>
      </div>
      <p *ngIf="!laedt() && fehler()" class="hinweis-box" role="alert">
        {{ texte.fehler }}
        <button mat-button type="button" class="nochmal-knopf" (click)="laden()">{{ texte.nochmal }}</button>
      </p>
      <ng-container *ngIf="!laedt() && !fehler()">
        <p *ngIf="!karten().length" class="gemerkt-leer" tabindex="-1" #leer>{{ texte.leer }}</p>
        <ul class="gemerkt-liste" *ngIf="karten().length" aria-label="Gemerkte Beiträge" tabindex="-1" #liste>
          <li *ngFor="let karte of karten(); trackBy: kennung">
            <app-beitragskarte [daten]="karte"></app-beitragskarte>
          </li>
        </ul>
        <button *ngIf="weitere()" mat-stroked-button type="button" class="weitere-knopf" (click)="weiterLaden()">
          {{ texte.weitere }}
        </button>
        <p *ngIf="weg().length" class="gemerkt-weg">
          {{ texte.weg(weg().length) }}
          <button mat-button type="button" class="weg-entfernen" (click)="wegEntfernen()">{{ texte.wegEntfernen }}</button>
        </p>
      </ng-container>
    </ng-container>
  `,
  styles: [
    `
      .gemerkt-laedt { display: flex; align-items: center; gap: 12px; margin: 16px 0; }
      .gemerkt-liste { list-style: none; margin: 0; padding: 0; display: grid; gap: 16px; }
      .gemerkt-liste:focus, .gemerkt-leer:focus { outline: none; }
      .gemerkt-leer, .gemerkt-weg { color: var(--text-leise); }
      .nochmal-knopf, .einwilligen-knopf, .weitere-knopf, .weg-entfernen { min-height: 44px; }
      .weitere-knopf { display: block; margin: 16px auto; }
    `,
  ],
})
export class GemerktComponent {
  readonly texte = GEMERKT_TEXTE;
  readonly laedt = signal(true);
  readonly fehler = signal(false);
  /** IDs, deren Beitrag beim Laden nicht mehr da war (404). */
  readonly weg = signal<string[]>([]);

  readonly merkliste = inject(MerklisteService);
  private readonly content = inject(ContentService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private readonly liste = viewChild<ElementRef<HTMLElement>>('liste');
  private readonly leer = viewChild<ElementRef<HTMLElement>>('leer');
  /** Geladene Karten je Beitrag; die Reihenfolge kommt aus der Merkliste. */
  private readonly geladen = signal(new Map<string, KartenDaten>());
  /** Wie viele Eintraege der Merkliste bisher geladen sind. */
  private readonly bis = signal(0);

  /** In der Reihenfolge der Merkliste; Entfernte verschwinden sofort. */
  readonly karten = computed(() => {
    const karten = this.geladen();
    return this.merkliste
      .eintraege()
      .map((e) => karten.get(e.content_id))
      .filter((k): k is KartenDaten => !!k);
  });

  /** Ob es noch nicht geladene Eintraege gibt. */
  readonly weitere = computed(() => this.merkliste.eintraege().length > this.bis());

  constructor() {
    // Verschwindet eine Karte (Knopf „Gemerkt“), fiele der Fokus sonst auf die Seite
    let vorher = 0;
    effect(() => {
      const jetzt = this.karten().length;
      if (jetzt < vorher) {
        untracked(() => setTimeout(() => (this.liste() ?? this.leer())?.nativeElement.focus()));
      }
      vorher = jetzt;
    });
    // Laden, sobald Schalter und Einwilligung feststehen, auch wenn der Stand der
    // Einwilligung erst nach dem Öffnen des Reiters kommt (?tab=gemerkt, Neuladen):
    // sonst bliebe „Noch nichts gemerkt“ stehen, bis jemand von Hand neu lädt.
    effect(() => {
      if (this.merkliste.bereit()) {
        untracked(() => this.laden());
      }
    });
  }

  laden(): void {
    this.laedt.set(true);
    this.fehler.set(false);
    this.geladen.set(new Map());
    this.weg.set([]);
    this.bis.set(0);
    this.merkliste
      .laden()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (eintraege) => this.seiteLaden(eintraege.slice(0, SEITE)),
        error: () => {
          this.fehler.set(true);
          this.laedt.set(false);
        },
      });
  }

  weiterLaden(): void {
    const start = this.bis();
    this.seiteLaden(this.merkliste.eintraege().slice(start, start + SEITE));
  }

  wegEntfernen(): void {
    const ids = this.weg();
    this.merkliste.entfernen(ids).subscribe({
      next: () => this.weg.set([]),
      error: () => this.fehler.set(true),
    });
  }

  einwilligen(): void {
    zurEinwilligungFuehren(this.router);
  }

  kennung(_: number, karte: KartenDaten): string {
    return karte.id;
  }

  private seiteLaden(seite: Gemerkt[]): void {
    // Was der Suchindex schon als gesperrt oder gelöscht meldet, nicht abfragen: Das
    // gäbe bei jedem Öffnen ein 404 je Eintrag (fail2ban im Saal-WLAN).
    const nichtDa = seite.filter((e) => e.sichtbar === false).map((e) => e.content_id);
    const eintraege = seite.filter((e) => e.sichtbar !== false);
    from(eintraege)
      .pipe(
        // Hoechstens LADEN_PARALLEL Abrufe zugleich; die Reihenfolge kommt aus der Merkliste
        mergeMap(
          (e) =>
            this.content.beitragLaden(e.content_id).pipe(
              map((beitrag): Geladen => ({ id: e.content_id, karte: ausEinzelansicht(beitrag), fehler: false })),
              catchError((f) => of<Geladen>({ id: e.content_id, karte: null, fehler: f?.status !== 404 })),
            ),
          LADEN_PARALLEL,
        ),
        toArray(),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((ergebnisse) => {
        const karten = new Map(this.geladen());
        ergebnisse.forEach((e) => e.karte && karten.set(e.id, e.karte));
        this.geladen.set(karten);
        this.weg.update((w) => [
          ...w,
          ...nichtDa,
          ...ergebnisse.filter((e) => !e.karte && !e.fehler).map((e) => e.id),
        ]);
        this.bis.update((b) => b + seite.length);
        // Nur 404 heisst „nicht mehr da“; jeder andere Fehler ist ein Ladefehler
        if (ergebnisse.some((e) => e.fehler)) {
          this.fehler.set(true);
        }
        this.laedt.set(false);
      });
  }
}
