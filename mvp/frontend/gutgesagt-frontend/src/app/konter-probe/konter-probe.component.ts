import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  Injector,
  OnInit,
  afterNextRender,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { Subject, Subscription } from 'rxjs';

import { KartenlisteComponent } from '../beitragskarte/kartenliste.component';
import { LadeWiederholung } from '../shared/lade-wiederholung';
import { ROUTES } from '../shared/constants/app.constants';
import {
  KonterProbe,
  KonterProbeService,
  ProbeAntwort,
  besteAntwort,
  ergebnisSatz,
  nutzungText,
} from './konter-probe';

/**
 * Konter-Probe (#786): ein Spruch, drei echte Antworten in verschiedenen Stilen. Wer
 * spielt, tippt an, welche bei Mitlesenden am besten wirkt, und sieht danach die echte
 * Nutzung aller drei, mit den Karten zum Kopieren.
 *
 * Der Tipp wird nur hier ausgewertet: Er geht an keinen Server und wird nirgends
 * gespeichert, auch nicht im Browser. Keine Punkte, kein Countdown, keine Rangliste.
 * Ohne Konto spielbar. Ist der Schalter aus oder passt keine Aussage, sagt die Seite
 * das; der Einstieg auf der Startseite erscheint dann gar nicht.
 */
@Component({
  selector: 'app-konter-probe',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MatButtonModule, MatProgressSpinnerModule, KartenlisteComponent],
  templateUrl: './konter-probe.component.html',
  styleUrls: ['./konter-probe.component.css'],
})
export class KonterProbeComponent implements OnInit {
  private readonly service = inject(KonterProbeService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly injector = inject(Injector);

  readonly suche = ROUTES.SEARCH;
  readonly nutzungText = nutzungText;

  /** null: lädt noch (oder erneut nach einem Fehler). */
  readonly proben = signal<KonterProbe[] | null>(null);
  readonly ladefehler = signal(false);
  readonly index = signal(0);
  /** Die angetippte Antwort; nur in diesem Signal, nirgends sonst. */
  readonly tipp = signal<ProbeAntwort | null>(null);

  readonly probe = computed(() => this.proben()?.[this.index()] ?? null);
  readonly beste = computed(() => {
    const probe = this.probe();
    return probe ? besteAntwort(probe) : null;
  });
  readonly satz = computed(() => {
    const probe = this.probe();
    const tipp = this.tipp();
    return probe && tipp ? ergebnisSatz(probe, tipp) : '';
  });
  /** Nach dem Tipp: die Karten zum Kopieren, die meistgenutzte zuerst. */
  readonly karten = computed(() =>
    [...(this.probe()?.antworten ?? [])].sort((a, b) => b.nutzung - a.nutzung).map((a) => a.karte),
  );
  readonly hatWeitere = computed(() => this.index() + 1 < (this.proben()?.length ?? 0));

  private readonly ergebnis = viewChild<ElementRef<HTMLElement>>('ergebnis');
  private readonly spruch = viewChild<ElementRef<HTMLElement>>('spruch');

  private readonly ende$ = new Subject<void>();
  private readonly wiederholung = new LadeWiederholung(this.ende$);
  private anfrage: Subscription | null = null;

  constructor() {
    this.destroyRef.onDestroy(() => {
      this.ende$.next();
      this.ende$.complete();
      this.anfrage?.unsubscribe();
    });
  }

  ngOnInit(): void {
    this.laden();
  }

  laden(): void {
    this.wiederholung.abbrechen();
    this.anfrage?.unsubscribe();
    this.anfrage = this.service.proben().subscribe({
      next: (proben) => {
        this.wiederholung.erfolg();
        this.ladefehler.set(false);
        this.index.set(0);
        this.tipp.set(null);
        this.proben.set(proben);
      },
      error: (fehler) => {
        // 404: Schalter aus. Dann gibt es nichts zu spielen, wie ohne passende Aussage.
        if (fehler?.status === 404) {
          this.wiederholung.erfolg();
          this.proben.set([]);
          return;
        }
        this.ladefehler.set(true);
        this.wiederholung.fehlgeschlagen(fehler, () => this.laden());
      },
    });
  }

  tippen(antwort: ProbeAntwort): void {
    if (this.tipp()) {
      return;
    }
    this.tipp.set(antwort);
    // Die Knöpfe verschwinden: Fokus auf das Ergebnis, damit Tastatur und Screenreader folgen.
    this.fokus(() => this.ergebnis());
  }

  naechste(): void {
    this.tipp.set(null);
    this.index.update((i) => i + 1);
    this.fokus(() => this.spruch());
  }

  istBeste(antwort: ProbeAntwort): boolean {
    return antwort === this.beste();
  }

  /** Breite des Balkens in Prozent der meistgenutzten Antwort; nur Schmuck, die Zahl steht daneben. */
  balken(antwort: ProbeAntwort): number {
    const hoechste = this.beste()?.nutzung ?? 0;
    return hoechste > 0 ? Math.round((antwort.nutzung / hoechste) * 100) : 0;
  }

  private fokus(ziel: () => ElementRef<HTMLElement> | undefined): void {
    afterNextRender(() => ziel()?.nativeElement.focus(), { injector: this.injector });
  }
}
