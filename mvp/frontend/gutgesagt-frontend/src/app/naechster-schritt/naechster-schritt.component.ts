import { ChangeDetectionStrategy, Component, Injector, afterNextRender, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { of } from 'rxjs';
import { catchError, distinctUntilChanged, map, switchMap } from 'rxjs/operators';

import { environment } from '../../environments/environment';
import { AuthService } from '../auth/auth.service';
import { stillerKontext } from '../shared/selbst-nachladen';
import { SeitLetztemBesuchService } from '../seit-letztem-besuch/seit-letztem-besuch.service';
import {
  NaechsterSchrittAntwort,
  SUCHFELD_ID,
  Vorschlag,
  anzeige,
  offeneVorschlaege,
  weggeklicktEntfernen,
  weggeklicktLesen,
  wegklicken,
} from './naechster-schritt';

export const NAECHSTER_SCHRITT_URL = `${environment.baseUrl}/api/v1/usage/users/me/naechster-schritt`;

/**
 * Karte „Dein nächster Schritt“ auf der Startseite (#789), nur für Angemeldete
 * (Basisfunktion seit dem Schalter-Umbau 27.11.): genau ein Vorschlag aus dem eigenen Stand, ohne
 * Frist, ohne Zähler. Der Server liefert alle passenden Vorschläge in ihrer Reihenfolge
 * (services/naechster_schritt.py); die Karte zeigt den ersten, den die Person nicht
 * weggeklickt hat. „Anderer Vorschlag“ zeigt den nächsten; was weggeklickt ist, merkt sich
 * nur der Browser für sieben Tage (naechster-schritt.ts). Scheitert der Abruf, steht
 * nichts da: Die Karte ist Beiwerk.
 *
 * Nie zugleich mit „Seit deinem letzten Besuch“ (Review Spielgefühl 25.11.): Wer Vorrang
 * hat, entscheidet SeitLetztemBesuchService.start$ an einer Stelle; die Karte meldet dorthin
 * nur, ob sie einen Vorschlag hat. Die Reihenfolge der Startseite steht in
 * docs/ARCHITECTURE.md.
 */
@Component({
  selector: 'app-naechster-schritt',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MatButtonModule, MatIconModule],
  template: `
    @if (sichtbar(); as eintrag) {
      <section class="naechster-schritt" aria-labelledby="naechster-schritt-titel">
        <h2 id="naechster-schritt-titel" tabindex="-1">Dein nächster Schritt</h2>
        <p class="naechster-schritt-satz">{{ eintrag.anzeige.satz }}</p>
        @if (eintrag.anzeige.zitat) {
          <blockquote class="naechster-schritt-zitat">„{{ eintrag.anzeige.zitat }}“</blockquote>
        }
        @if (eintrag.anzeige.hinweis) {
          <p class="naechster-schritt-hinweis">{{ eintrag.anzeige.hinweis }}</p>
        }
        <div class="naechster-schritt-knoepfe">
          @if (eintrag.anzeige.ziel) {
            <!-- Hauptknopf voll wie „Antworten ansehen“, Nebenknopf Kontur (Rundgang 2, V15) -->
            <a mat-raised-button class="gutgesagt-primary-dark naechster-schritt-los" [routerLink]="eintrag.anzeige.ziel"
               [queryParams]="eintrag.anzeige.queryParams" [fragment]="eintrag.anzeige.fragment">
              {{ eintrag.anzeige.knopf }}
              <mat-icon iconPositionEnd aria-hidden="true">arrow_forward</mat-icon>
            </a>
          } @else {
            <button mat-raised-button type="button" class="gutgesagt-primary-dark naechster-schritt-los" (click)="zurSuche()">
              {{ eintrag.anzeige.knopf }}
            </button>
          }
          <button mat-stroked-button type="button" class="naechster-schritt-weg" (click)="weg(eintrag.vorschlag)">
            {{ eintrag.weitere ? 'Anderer Vorschlag' : 'Ausblenden' }}
          </button>
        </div>
      </section>
    }
    <span class="visually-hidden" aria-live="polite">{{ ansage() }}</span>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      /* Kanten wie „Seit deinem letzten Besuch“: 16 px Einzug, ab 752 px die 720er-Spalte */
      .naechster-schritt {
        margin: var(--spacing-xl, 32px) max(var(--spacing-md, 16px), calc((100% - var(--lesespalte, 720px)) / 2)) 0;
        padding: var(--spacing-md, 16px) var(--spacing-lg, 24px);
        border: 2px solid var(--kachel-rand, var(--linie-tanne));
        border-radius: 12px;
        background: var(--karte-kommentar, var(--flaeche));
        color: var(--text);
      }

      .naechster-schritt h2 {
        margin: 0 0 var(--spacing-sm, 8px);
      }

      .naechster-schritt h2:focus {
        outline: none;
      }

      .naechster-schritt h2:focus-visible {
        outline: 2px solid var(--akzent-tanne);
        outline-offset: 2px;
      }

      .naechster-schritt-satz {
        margin: 0 0 var(--spacing-sm, 8px);
        font-size: 17px;
      }

      .naechster-schritt-zitat {
        margin: 0 0 var(--spacing-sm, 8px);
        padding-left: 12px;
        border-left: 3px solid var(--akzent-tanne);
        font-style: italic;
        overflow-wrap: anywhere;
      }

      .naechster-schritt-hinweis {
        margin: 0 0 var(--spacing-sm, 8px);
        font-size: 15px;
      }

      .naechster-schritt-knoepfe {
        display: flex;
        flex-wrap: wrap;
        gap: var(--spacing-sm, 8px);
        margin-top: var(--spacing-md, 16px);
      }

      .naechster-schritt-knoepfe a,
      .naechster-schritt-knoepfe button {
        min-height: 48px;
      }

      /* Sichtbarer Tastaturfokus (WCAG 2.4.7): Material nimmt den Rahmen weg, nur ein Grau
         blieb (Rundgang 2, V15); 3 px wie in Garten und Profilbild */
      .naechster-schritt-knoepfe a:focus-visible,
      .naechster-schritt-knoepfe button:focus-visible {
        outline: 3px solid var(--akzent-tanne);
        outline-offset: 2px;
      }
    `,
  ],
})
export class NaechsterSchrittComponent {
  private readonly http = inject(HttpClient);

  private readonly vorschlaege = signal<Vorschlag[]>([]);
  private readonly weggeklickt = signal<ReturnType<typeof weggeklicktLesen>>({});
  /** Für Screenreader nach dem Wegklicken. */
  readonly ansage = signal('');

  readonly aktuell = computed(() => {
    const offen = offeneVorschlaege(this.vorschlaege(), this.weggeklickt());
    const erster = offen[0];
    const daten = erster ? anzeige(erster) : null;
    return erster && daten ? { vorschlag: erster, anzeige: daten, weitere: offen.length > 1 } : null;
  });

  private readonly neues = inject(SeitLetztemBesuchService);
  /** Vorrang und Kacheln des Blocks darüber, aus derselben Quelle wie der Block selbst. */
  private readonly start = toSignal(this.neues.start$);

  /** Was die Karte zeigt: der aktuelle Vorschlag, nur wenn die Karte den Vorrang hat. */
  readonly sichtbar = computed(() => (this.start()?.vorrang === 'karte' ? this.aktuell() : null));

  private readonly injector = inject(Injector);

  constructor() {
    // Rückkehr auf die Startseite: die letzten Vorschläge sofort, damit nichts springt;
    // die neue Antwort ersetzt sie still.
    const gemerkt = this.neues.naechsterSchrittGemerkt;
    if (gemerkt) {
      this.vorschlaege.set(gemerkt);
    }
    // Aufräumen bei jedem Laden der Startseite, auch ohne Anmeldung:
    // Abgelaufenes fällt weg, damit kein Eintrag länger als sieben Tage liegt.
    this.weggeklickt.set(weggeklicktLesen());
    if (gemerkt) {
      this.melden();
    }
    const angemeldet$ = inject(AuthService).userInfo$.pipe(
      map((info) => info?.isAuthenticated === true),
      distinctUntilChanged(),
    );
    angemeldet$
      .pipe(
        switchMap((angemeldet) => {
          if (!angemeldet) {
            return of([] as Vorschlag[]);
          }
          return this.http.get<NaechsterSchrittAntwort>(NAECHSTER_SCHRITT_URL, { context: stillerKontext() }).pipe(
            map((antwort) => antwort?.vorschlaege ?? []),
            catchError(() => of([] as Vorschlag[])),
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((liste) => {
        this.vorschlaege.set(liste);
        this.neues.naechsterSchrittGemerkt = liste;
        this.melden();
      });
    // Rückweg (Rundgang 28.11.): „Vorschlag holen“ im Block darüber leert den Merker im
    // Browser; die Karte zeigt wieder den ersten Vorschlag, der Fokus geht auf ihre Überschrift.
    this.neues.vorschlagHolen$.pipe(takeUntilDestroyed()).subscribe(() => this.wiederHolen());
  }

  private wiederHolen(): void {
    weggeklicktEntfernen();
    this.weggeklickt.set({});
    this.melden();
    const erster = this.aktuell();
    this.ansage.set(erster ? `Dein nächster Schritt: ${erster.anzeige.satz}` : '');
    afterNextRender(
      () => {
        const titel = document.getElementById('naechster-schritt-titel');
        if (titel) {
          titel.scrollIntoView?.({ block: 'nearest' });
          titel.focus({ preventScroll: true });
        }
      },
      { injector: this.injector },
    );
  }

  /**
   * Dem Block melden, ob es einen Vorschlag gibt. Nur aus der Antwort und aus Klicks, nie
   * während der Change Detection: Der Block steht im Template davor.
   */
  private melden(): void {
    this.neues.naechsterSchrittHolbar$.next(this.holbar());
    this.neues.naechsterSchrittDa$.next(this.aktuell() !== null);
  }

  /** Ob ein weggeklickter Vorschlag wieder gezeigt werden könnte (Rückweg im Block). */
  private holbar(): boolean {
    const alle = offeneVorschlaege(this.vorschlaege(), {});
    return alle.length > offeneVorschlaege(this.vorschlaege(), this.weggeklickt()).length;
  }

  /** „Zur Suche“: Fokus ins Suchfeld der Startseite, ohne die Seite zu wechseln. */
  zurSuche(): void {
    const feld = document.getElementById(SUCHFELD_ID);
    feld?.scrollIntoView?.({ block: 'center' });
    feld?.focus();
  }

  /** Wegklicken: nur im Browser gemerkt, dann der nächste Vorschlag oder nichts mehr. */
  weg(vorschlag: Vorschlag): void {
    this.weggeklickt.set(wegklicken(vorschlag.art));
    this.melden();
    // Die Karte bleibt stehen, der Fokus auf dem Knopf; neu ist nur der Satz, die Ansage
    // liest ihn vor. Ohne Vorschlag kann darüber der Block „Seit deinem letzten Besuch“
    // erscheinen: Das sagt die Ansage mit.
    const naechster = this.aktuell();
    this.ansage.set(
      naechster
        ? `Anderer Vorschlag: ${naechster.anzeige.satz}`
        : this.start()?.kacheln.length
          ? 'Vorschlag ausgeblendet. Neues seit deinem letzten Besuch steht darüber.'
          : 'Vorschlag ausgeblendet.',
    );
    if (!naechster) {
      // Der Knopf verschwindet mit der Karte: Der Fokus geht ins Suchfeld darüber, nicht an
      // den Anfang der Seite (WCAG 2.4.3).
      document.getElementById(SUCHFELD_ID)?.focus({ preventScroll: true });
    }
  }
}
