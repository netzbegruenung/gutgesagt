import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { distinctUntilChanged, map } from 'rxjs/operators';

import { AuthService } from '../auth/auth.service';
import { RundgangService } from '../rundgang/rundgang.service';
import { SaalSpruchService } from '../services/saal-spruch.service';
import { SeitLetztemBesuchService } from '../seit-letztem-besuch/seit-letztem-besuch.service';
import { ROUTES } from '../shared/constants/app.constants';
import { SUCHTEXT_PARAM } from '../shared/formular-adresse';
import { AUS_NACHLADEN_MS, selbstNachladen } from '../shared/selbst-nachladen';

/** Der Tag im Browser als JJJJ-MM-TT, damit ein gemerkter Spruch nicht über Mitternacht hält. */
export function browserTag(jetzt = new Date()): string {
  const zwei = (n: number) => `${n}`.padStart(2, '0');
  return `${jetzt.getFullYear()}-${zwei(jetzt.getMonth() + 1)}-${zwei(jetzt.getDate())}`;
}

/**
 * Karte „Heute im Netz zur BDK:“ oben auf der Startseite (Schalter „saal_spruch“, Glossar
 * „Saal-Spruch“): der Spruch, den ein Admin für diesen Tag gewählt hat, weil er gerade unter
 * Beiträgen zur BDK im Netz kursiert (im Saal bei den Grünen fallen solche Sprüche nicht,
 * Entscheidung 27.11.2026), und der Knopf „Antworten ansehen“, der die Suche mit dem Spruch
 * startet. Ohne Spruch für heute oder bei Schalter aus gibt es die Karte nicht.
 *
 * Höchstens ein Aufruf über dem Feed (Review Spielgefühl 25.11.): Den Vorrang gegenüber
 * „Seit deinem letzten Besuch“ und „Dein nächster Schritt“ entscheidet
 * SeitLetztemBesuchService.start$ (Regel in neues-liste.ts, startVorrang); die Karte meldet
 * dorthin nur, ob sie heute einen Spruch hat. Eigenes Neues und der Vorschlag gehen ihr
 * vor, nur die allgemeinen Zahlen treten an ihren Tagen zurück. Steht ein Rundgang-Angebot
 * auf der Startseite (Willkommen, Startbildschirm, App installieren), wartet sie, bis es
 * beantwortet ist: Das Angebot ist dann der eine Aufruf; nur neben dem schlanken Willkommen
 * steht sie gleich (UX-Review 26.11.2026). Besucher ohne Konto sehen weder
 * Block noch Vorschlag, deshalb wartet die Karte für sie auf nichts davon.
 *
 * Bekannt: Kommt der Spruch erst nach START_WARTEZEIT_MS (zwei Abrufe nacheinander,
 * Schalterstand und Spruch), zeigen Angemeldete ohne Vorschlag zuerst den Block und dann
 * die Karte; wie beim Vorschlag, im Saal-WLAN nur wahrscheinlicher.
 */
@Component({
  selector: 'app-saal-spruch',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MatButtonModule, MatIconModule],
  template: `
    @if (sichtbar(); as spruch) {
      <section class="saal-spruch" aria-labelledby="saal-spruch-titel" data-testid="saal-spruch">
        <h2 id="saal-spruch-titel" class="saal-spruch-titel">
          <mat-icon aria-hidden="true">campaign</mat-icon>
          Heute im Netz zur BDK:
        </h2>
        <blockquote class="saal-spruch-zitat" data-testid="saal-spruch-text">„{{ spruch }}“</blockquote>
        <p class="saal-spruch-frage">Wie würdest du antworten?</p>
        <a mat-raised-button class="gutgesagt-primary-dark saal-spruch-knopf" data-testid="saal-spruch-knopf"
           [routerLink]="ergebnisse" [queryParams]="suche(spruch)">
          Antworten ansehen
          <mat-icon iconPositionEnd aria-hidden="true">arrow_forward</mat-icon>
        </a>
      </section>
    }
  `,
  styles: [
    `
      :host {
        display: block;
      }

      /* Kanten wie „Dein nächster Schritt“: 16 px Einzug, ab 752 px die 720er-Spalte */
      .saal-spruch {
        margin: var(--spacing-xl, 32px) max(var(--spacing-md, 16px), calc((100% - var(--lesespalte, 720px)) / 2)) 0;
        padding: var(--spacing-md, 16px) var(--spacing-lg, 24px);
        border: 2px solid var(--kachel-rand, var(--linie-tanne));
        border-radius: 12px;
        background: var(--karte-kommentar, var(--flaeche));
        color: var(--text);
      }

      .saal-spruch-titel {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm, 8px);
        margin: 0 0 var(--spacing-sm, 8px);
      }

      .saal-spruch-zitat {
        margin: 0 0 var(--spacing-sm, 8px);
        padding-left: 12px;
        border-left: 3px solid var(--akzent-tanne);
        font-size: 19px;
        font-weight: 600;
        line-height: 1.35;
        overflow-wrap: anywhere;
      }

      .saal-spruch-frage {
        margin: 0 0 var(--spacing-md, 16px);
        font-size: 17px;
      }

      .saal-spruch-knopf {
        min-height: 48px;
      }

      @media (max-width: 599px) {
        .saal-spruch {
          margin-top: var(--spacing-lg, 24px);
          padding: var(--spacing-md, 16px);
        }

        .saal-spruch-knopf {
          width: 100%;
        }
      }
    `,
  ],
})
export class SaalSpruchComponent {
  readonly ergebnisse = ROUTES.RESULT;
  readonly suche = (spruch: string) => ({ [SUCHTEXT_PARAM]: spruch });

  private readonly service = inject(SaalSpruchService);
  private readonly neues = inject(SeitLetztemBesuchService);
  private readonly rundgang = inject(RundgangService);
  private readonly spruch = signal<string | null>(null);

  private readonly start = toSignal(this.neues.start$);
  private readonly anonym = toSignal(
    inject(AuthService).userInfo$.pipe(
      map((info) => info?.isAuthenticated === false),
      distinctUntilChanged(),
    ),
    { initialValue: false },
  );
  /**
   * Ein Rundgang-Angebot (Willkommen, Startbildschirm, App) steht gerade auf der Startseite.
   * Ausnahme: das schlanke Willkommen („Neu hier?“, auch als „Von der BDK?“ nach dem
   * Kampagnenwort). Für genau diese Neuen ist die Karte gebaut; sonst sähen sie sie beim
   * ersten Besuch nie (UX-Review 26.11.2026, Befund 8). Das Willkommen ist eine Zeile, die
   * Karte sagt nichts doppelt.
   */
  private readonly rundgangHier = computed(() => {
    const band = this.rundgang.band();
    return !!band?.imInhalt && !band.schlank;
  });

  /** Der Spruch, wenn die Karte ihn zeigen darf; sonst null. */
  readonly sichtbar = computed(() => {
    const spruch = this.spruch();
    if (!spruch || this.rundgangHier()) {
      return null;
    }
    return this.anonym() || this.start()?.vorrang === 'spruch' ? spruch : null;
  });

  constructor() {
    const heute = browserTag();
    const gemerkt = this.neues.saalSpruchGemerkt;
    if (gemerkt?.tag === heute) {
      // Rückkehr auf die Startseite: der letzte Stand sofort, die neue Antwort ersetzt ihn still
      this.spruch.set(gemerkt.spruch);
      this.neues.saalSpruchDa$.next(gemerkt.spruch !== null);
    } else {
      // Noch keine Antwort: Block und Vorschlag warten kurz, statt aufzublitzen
      this.neues.saalSpruchDa$.next(null);
    }
    const folgen = {
      next: (spruch: string | null) => this.uebernehmen(spruch),
      // Beiwerk der Startseite: ohne Antwort keine Karte, der nächste Takt versucht es neu
      error: () => this.uebernehmen(null),
    };
    const destroyRef = inject(DestroyRef);
    const erste = this.service.heute().subscribe(folgen);
    destroyRef.onDestroy(() => erste.unsubscribe());
    // Selten nachfragen: Der Spruch wechselt nur mit dem Tag, der Schalter selten
    selbstNachladen(() => this.service.heute(), destroyRef, folgen, AUS_NACHLADEN_MS);
  }

  private uebernehmen(spruch: string | null): void {
    this.spruch.set(spruch);
    this.neues.saalSpruchGemerkt = { tag: browserTag(), spruch };
    this.neues.saalSpruchDa$.next(spruch !== null);
  }
}
