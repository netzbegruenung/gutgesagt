import { Component, OnInit, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { Observable, of } from 'rxjs';
import { catchError, map, switchMap } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import { keycloakAnmelden } from '../login/keycloak-anmeldung';
import { sitzungPruefen } from '../auth/sitzung';
import { teamMerkerLesen } from './team-merker';

/** Pfad der Seite; das Backend setzt ihn als Ziel des Links in der Mail (ANMELDEN_PFAD in keycloak_konten.py). */
export const EINLADUNG_ANMELDEN_PFAD = 'einladung/anmelden';

/** Wohin es nach der Anmeldung geht; ohne Einwilligung leitet die App von dort auf /einwilligung (#489). */
const ZIEL = '/';
/**
 * Ziel, wenn eine Einladung mit Team mitgetragen wird (team-merker): zurück auf die Einladung,
 * die dort das Team zeigt. Der Code bleibt im Merker; als returnUrl stünde er in den Protokollen.
 */
const ZIEL_MIT_TEAM = '/einladung';

type Weiter = 'angemeldet' | 'keycloak' | 'auswahl';

/**
 * Ziel des Links in der Mail „Passwort festlegen“ (Einladung, #429): Nach Passwort und
 * Nutzungsbedingungen endet Keycloak ohne Anmeldung und verweist hierher. Die Seite
 * startet gleich die Anmeldung, statt die Person abgemeldet auf der Startseite stehen zu
 * lassen. Wer schon angemeldet ist, geht auf die Startseite, oder mit einer Einladung mit
 * Team (team-merker) zurück auf /einladung, die das Team zeigt.
 *
 * Die Mail-Adresse geht bewusst nicht als login_hint mit: Sie stuende dann in den
 * Adressen zu BFF und Keycloak und damit in deren Zugriffsprotokollen.
 */
@Component({
  selector: 'app-einladung-anmelden',
  standalone: true,
  imports: [MatButtonModule, MatCardModule],
  template: `
    <mat-card class="einladung">
      <mat-card-header>
        <mat-card-title>Dein Konto ist bereit</mat-card-title>
      </mat-card-header>
      <mat-card-content>
        <p role="status">Gleich geht es zur Anmeldung …</p>
        <button mat-raised-button color="primary" type="button" (click)="anmelden()">Jetzt anmelden</button>
      </mat-card-content>
    </mat-card>
  `,
  styles: [
    `
      .einladung {
        max-width: 560px;
        margin: 24px auto;
      }
    `,
  ],
})
export class EinladungAnmeldenComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  /** Fenster, über das die Anmeldung die Seite verlässt; Tests ersetzen es. */
  fenster: Pick<Window, 'location'> = window;
  private mitKeycloak = true;

  ngOnInit(): void {
    this.weiter().subscribe((weiter) => {
      if (weiter === 'angemeldet') {
        void this.router.navigateByUrl(this.ziel());
        return;
      }
      this.mitKeycloak = weiter === 'keycloak';
      this.anmelden();
    });
  }

  /** Auch der Knopf, falls die Weiterleitung nicht von selbst losgeht. */
  anmelden(): void {
    const ziel = this.ziel();
    if (this.mitKeycloak) {
      keycloakAnmelden(ziel, this.fenster);
    } else if (ziel === ZIEL) {
      void this.router.navigate(['/login']);
    } else {
      void this.router.navigate(['/login'], { queryParams: { returnUrl: ziel } });
    }
  }

  private ziel(): string {
    return teamMerkerLesen() ? ZIEL_MIT_TEAM : ZIEL;
  }

  private weiter(): Observable<Weiter> {
    return sitzungPruefen(this.http).pipe(
      switchMap((angemeldet) =>
        angemeldet
          ? of<Weiter>('angemeldet')
          : // Wie auf „Das erwartet dich mit Konto“: im Zweifel die Keycloak-Anmeldung.
            this.http.get<{ keycloakEnabled: boolean }>(`${environment.baseUrl}/api/auth/modes`).pipe(
              map((m): Weiter => (m?.keycloakEnabled === false ? 'auswahl' : 'keycloak')),
              catchError(() => of<Weiter>('keycloak')),
            ),
      ),
    );
  }
}
