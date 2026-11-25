import { ChangeDetectionStrategy, ChangeDetectorRef, Component, DestroyRef, OnInit, inject } from '@angular/core';

import { SaisonBalken, SaisonService } from '../services/saison.service';
import { selbstNachladen } from '../shared/selbst-nachladen';

/** So oft lädt der Balken nach: Die Zahl ändert sich nur einmal je Woche, der Schalter selten. */
export const SAISON_NACHLADEN_MS = 5 * 60 * 1000;

const zahl = (wert: number): string => wert.toLocaleString('de-DE');

/**
 * Gemeinschaftsziel der laufenden Saison auf der Startseite (#782, Schalter „saison_ziel“).
 *
 * Für alle, auch ohne Konto, aber erst ab der Schwelle (das entscheidet der Server). Gezählt
 * werden Widerspruchs-Wochen: je Woche jede Person einmal, die nach dem Kopieren „Ja,
 * gepostet“ meldet. Darum heißt es „N-mal widersprochen“, nie „N Menschen“. Kein Ende, keine
 * Frist: Die Saison nennt nur ihren Namen. Kommt nichts, gibt es den Bereich nicht.
 */
@Component({
  selector: 'app-saison-ziel',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (balken; as b) {
      <section class="saison-ziel" aria-labelledby="saison-ziel-titel" data-testid="saison-ziel">
        <h2 id="saison-ziel-titel">Gemeinsam widersprechen, Antwort für Antwort</h2>
        <p class="satz" data-testid="saison-ziel-satz">
          Saison {{ b.name }}: Woche für Woche zusammen <strong>{{ zahl(b.erreicht) }}-mal</strong> öffentlich widersprochen.
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
        <p class="erklaerung">
          Jede Woche zählt jede Person einmal, die nach dem Kopieren „Ja, gepostet“ meldet. Wer mehrere Wochen
          dabei ist, zählt mehrmals.
        </p>
      </section>
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

  protected readonly zahl = zahl;

  private readonly saisons = inject(SaisonService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    const folgen = {
      next: (balken: SaisonBalken | null) => {
        this.balken = balken;
        this.cdr.markForCheck();
      },
      // Nach einem Fehler bleibt der letzte Stand; ohne Stand gibt es den Bereich nicht.
      error: () => undefined,
    };
    this.saisons.aktuell().subscribe(folgen);
    selbstNachladen(() => this.saisons.aktuell(), this.destroyRef, folgen, SAISON_NACHLADEN_MS);
  }

  /** Über dem Ziel bleibt der Balken voll, die Zahl darunter nennt den echten Stand. */
  gefuellt(b: SaisonBalken): number {
    return Math.min(b.erreicht, b.ziel);
  }
}
