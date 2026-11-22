import { DestroyRef, Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { NavigationEnd, Router } from '@angular/router';
import { Subscription } from 'rxjs';
import { filter } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import { stillerKontext } from '../shared/selbst-nachladen';

/** Pfad ohne Abfrage und Anker: Nur ein Wechsel der Seite zählt, kein Filter, kein Sprung. */
export function seite(url: string): string {
  return url.split(/[?#]/)[0];
}

/**
 * Seitenaufrufe zählen (#761): Je Wechsel der Seite eine leere Anfrage an den Server, ohne Pfad,
 * ohne Kennung, ohne etwas im Browser abzulegen. Wer Besucher ist, bestimmt der Server über das
 * Tagespseudonym (#446). Ist der Schalter „aufrufe_zaehlen“ aus, antwortet er 404; dann hört
 * die App für diesen Start auf zu melden. Admin-Seiten zählen nicht.
 */
@Injectable({ providedIn: 'root' })
export class AufrufeZaehlenService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly url = `${environment.baseUrl}/api/v1/aufrufe/zaehlen`;
  private abo: Subscription | null = null;
  private letzte: string | null = null;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.beenden());
  }

  starten(): void {
    if (this.abo) {
      return;
    }
    this.abo = this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe((e) => this.melden(seite(e.urlAfterRedirects)));
  }

  private melden(pfad: string): void {
    if (pfad.startsWith('/admin')) {
      // Zurueck aus dem Admin-Bereich zaehlt die Seite wieder
      this.letzte = null;
      return;
    }
    if (pfad === this.letzte) {
      return;
    }
    this.letzte = pfad;
    this.http.post(this.url, null, { context: stillerKontext() }).subscribe({
      error: (fehler: { status?: number }) => {
        if (fehler?.status === 404) {
          this.beenden();
        }
      },
    });
  }

  private beenden(): void {
    this.abo?.unsubscribe();
    this.abo = null;
  }
}
