import { ChangeDetectionStrategy, ChangeDetectorRef, Component, DestroyRef, OnInit, inject } from '@angular/core';

import { Observable, of } from 'rxjs';
import { catchError, map, switchMap } from 'rxjs/operators';

import { MetricsService } from '../services/metrics.service';
import { SaisonBalken, SaisonService } from '../services/saison.service';
import { selbstNachladen } from '../shared/selbst-nachladen';
import { Bestandszahl, bestandszahl } from './bestandszahl';

/**
 * So oft lädt der Balken nach: Die Zahl ändert sich nur einmal je Woche, der Schalter selten.
 * Die Bestandszahl ist abgerundet und zuckt deshalb auch nur selten.
 */
export const SAISON_NACHLADEN_MS = 5 * 60 * 1000;

const zahl = (wert: number): string => wert.toLocaleString('de-DE');

/**
 * Gemeinschaftsziel der laufenden Saison auf der Startseite (#782, Schalter „saison_ziel“).
 *
 * Für alle, auch ohne Konto, aber erst ab der Schwelle (das entscheidet der Server). Gezählt
 * werden Widerspruchs-Wochen: je Woche jede Person einmal, die nach dem Kopieren „Ja,
 * gepostet“ meldet. Darum heißt es „N-mal widersprochen“, nie „N Menschen“. Kein Ende, keine
 * Frist: Die Saison nennt nur ihren Namen. Kommt nichts, gibt es den Bereich nicht. Steht die
 * Zahl noch bei 0 (Saisonstart; die Schwelle kann aus Wochen vor der Saison stammen), lädt ein
 * Startsatz ein statt „0-mal“ und leerem Balken.
 *
 * Solange der Balken nicht öffentlich ist (Schalter an, aber keine laufende Saison oder Schwelle
 * nicht erreicht), steht an seinem Platz die Bestandszahl (bestandszahl.ts): wie viele Antworten
 * auf wie viele Sprüche schon da sind, ohne Personen. Bei Schalter aus gibt es auch sie nicht.
 */
interface Anzeige {
  balken: SaisonBalken | null;
  bestand: Bestandszahl | null;
}

const LEER: Anzeige = { balken: null, bestand: null };

@Component({
  selector: 'app-saison-ziel',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (balken; as b) {
      <section class="saison-ziel" aria-labelledby="saison-ziel-titel" data-testid="saison-ziel">
        <h2 id="saison-ziel-titel">Gemeinsam widersprechen, Antwort für Antwort</h2>
        @if (b.erreicht > 0) {
          <p class="satz" data-testid="saison-ziel-satz">
            Saison {{ b.name }}: Woche für Woche zusammen <strong>{{ zahl(b.erreicht) }}-mal</strong> öffentlich
            widersprochen.
          </p>
          <progress
            [max]="b.ziel"
            [value]="gefuellt(b)"
            [attr.aria-label]="'Gemeinschaftsziel der Saison ' + b.name"
            aria-describedby="saison-ziel-stand"
          ></progress>
          <p id="saison-ziel-stand" class="stand" data-testid="saison-ziel-stand">
            @if (b.erreicht >= b.ziel) {
              Gemeinsames Ziel geschafft: {{ zahl(b.ziel) }} Widerspruchs-Wochen. Danke an alle, die mitmachen!
            } @else {
              {{ zahl(b.erreicht) }} von {{ zahl(b.ziel) }} Widerspruchs-Wochen, unser gemeinsames Ziel.
            }
          </p>
        } @else {
          <!-- Saisonstart: kein „0-mal“ und kein leerer Balken, sondern eine Einladung (Review 25.11., Vorschlag 4) -->
          <p class="satz" data-testid="saison-ziel-satz">
            Saison {{ b.name }} hat begonnen: Jedes „Ja, gepostet“ nach dem Kopieren zählt für unser gemeinsames Ziel.
          </p>
          <p class="stand" data-testid="saison-ziel-stand">
            Ziel: {{ zahl(b.ziel) }} Widerspruchs-Wochen. Sobald die erste Woche gezählt ist, füllt sich hier der
            Balken.
          </p>
        }
        <p class="erklaerung">
          Jede Woche zählt jede Person einmal, die nach dem Kopieren „Ja, gepostet“ meldet. Wer mehrere Wochen
          dabei ist, zählt mehrmals.
        </p>
      </section>
    } @else {
      @if (bestand; as z) {
        <!-- Bestandszahl statt Balken unter der Schwelle (Entscheidung 25.11.2026): nur Inhalte, keine Personen -->
        <section class="saison-ziel" aria-labelledby="bestandszahl-titel" data-testid="bestandszahl">
          <h2 id="bestandszahl-titel">
            Schon {{ zahl(z.antworten) }} Antworten auf
            {{ zahl(z.sprueche) }} {{ z.sprueche === 1 ? 'Spruch' : 'Sprüche' }}
          </h2>
          <p class="erklaerung">
            Fertig zum Kopieren und Anpassen. Jede neue Antwort hilft allen, die später danach suchen.
          </p>
        </section>
      }
    }
  `,
  styles: [
    `
      .saison-ziel {
        margin: 2rem var(--page-margin) 0;
        padding: 16px;
        background: var(--flaeche);
        border: 1px solid var(--linie);
        border-radius: var(--border-radius-medium);
      }
      h2 {
        margin: 0 0 8px;
      }
      p {
        margin: 0 0 8px;
      }
      .satz {
        font-size: 1.0625rem;
      }
      progress {
        display: block;
        width: 100%;
        height: 16px;
        margin: 12px 0 8px;
        appearance: none;
        border: 1px solid var(--feldrand);
        border-radius: 8px;
        background: var(--mulde);
        overflow: hidden;
      }
      progress::-webkit-progress-bar {
        background: var(--mulde);
      }
      progress::-webkit-progress-value {
        background: var(--akzent-tanne);
      }
      progress::-moz-progress-bar {
        background: var(--akzent-tanne);
      }
      .stand {
        font-weight: 500;
      }
      .erklaerung {
        margin: 0;
        font-size: 0.875rem;
        color: var(--text-leise);
      }
      @media (max-width: 599px) {
        .saison-ziel {
          margin-top: 1rem;
        }
      }
    `,
  ],
})
export class SaisonZielComponent implements OnInit {
  balken: SaisonBalken | null = null;
  /** Nur ohne öffentlichen Balken und bei Schalter an */
  bestand: Bestandszahl | null = null;

  protected readonly zahl = zahl;

  private readonly saisons = inject(SaisonService);
  private readonly metrics = inject(MetricsService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    const folgen = {
      next: (anzeige: Anzeige) => {
        this.balken = anzeige.balken;
        this.bestand = anzeige.bestand;
        this.cdr.markForCheck();
      },
      // Nach einem Fehler bleibt der letzte Stand; ohne Stand gibt es den Bereich nicht.
      error: () => undefined,
    };
    this.laden().subscribe(folgen);
    selbstNachladen(() => this.laden(), this.destroyRef, folgen, SAISON_NACHLADEN_MS);
  }

  /**
   * Balken, sonst bei Schalter an die Bestandszahl aus /getMetrics (öffentlich, im Server 60 s
   * gecacht, nie 401/404). Ein Fehler beim Saisonstand geht weiter (das Nachladen behält den
   * letzten Stand). Ein Fehler beim Bestand oder eine 0 (so meldet /getMetrics eine gescheiterte
   * Zählung) behält nur die letzte Bestandszahl; der neue Saisonstand gilt trotzdem.
   */
  private laden(): Observable<Anzeige> {
    return this.saisons.zustand().pipe(
      switchMap((stand): Observable<Anzeige> => {
        if (!stand.aktiv) {
          return of(LEER);
        }
        if (stand.balken) {
          return of({ balken: stand.balken, bestand: null });
        }
        return this.metrics.getMetrics(true).pipe(
          map((m): Anzeige => {
            const gezaehlt = !!m?.commentary_count && !!m?.statement_count;
            return {
              balken: null,
              bestand: gezaehlt ? bestandszahl(m.commentary_count, m.statement_count) : this.bestand,
            };
          }),
          catchError(() => of<Anzeige>({ balken: null, bestand: this.bestand })),
        );
      }),
    );
  }

  /** Über dem Ziel bleibt der Balken voll, die Zahl darunter nennt den echten Stand. */
  gefuellt(b: SaisonBalken): number {
    return Math.min(b.erreicht, b.ziel);
  }
}
