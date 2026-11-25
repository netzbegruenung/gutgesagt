import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { Observable, of } from 'rxjs';
import { distinctUntilChanged, map, switchMap } from 'rxjs/operators';

import { AuthService } from '../auth/auth.service';
import { SeitLetztemBesuchService } from './seit-letztem-besuch.service';
import { NeuesEintrag } from './neues-liste';

// Die reinen Funktionen stehen in neues-liste.ts; hier weiter erreichbar fuer bestehende Importe.
export {
  EIGENES_NEUES,
  MAX_KACHELN,
  ZEITRAUM,
  eigenesNeuesSichtbar,
  neuesListe,
  startKacheln,
  startVorrang,
} from './neues-liste';
export type { NeuesArt, NeuesEintrag, NeuesStand, StartVorrang } from './neues-liste';

/**
 * „Seit deinem letzten Besuch“ auf der Startseite, nur fuer Angemeldete (Nutzerfuehrung
 * 13.11.): bis zu vier kleine Kacheln mit Zahl im Stil der Mitmachen-Kacheln, die ganze
 * Kachel ist der Link (Entscheidungen 18.11. und 20.11.). Bleibt nur eine, wird sie eine
 * breite Zeile mit Satz und Knopf. Ohne Neues steht nichts da, beim ersten Besuch auch
 * nicht, und neben „Dein nächster Schritt“ nur mit eigenem Neuem (Vorrang im
 * SeitLetztemBesuchService, neues-liste.ts). Kein roter Zaehler,
 * nichts, das verfaellt. Alle Zahlen stammen aus der Antwort des Besuchs beim App-Start
 * (RueckmeldungService), ohne eigenen Abruf.
 */
@Component({
  selector: 'app-seit-letztem-besuch',
  standalone: true,
  imports: [AsyncPipe, RouterLink, MatButtonModule, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (eintraege$ | async; as eintraege) {
      @if (eintraege.length) {
        <nav class="seit-besuch" aria-labelledby="seit-besuch-titel">
          <h2 id="seit-besuch-titel">Seit deinem letzten Besuch</h2>
          @if (eintraege.length === 1) {
            @let eintrag = eintraege[0];
            <div [class]="'seit-besuch-zeile ' + eintrag.art">
              <mat-icon class="seit-besuch-icon" aria-hidden="true">{{ eintrag.icon }}</mat-icon>
              <p class="seit-besuch-satz" id="seit-besuch-satz">
                <span class="seit-besuch-zahl">{{ eintrag.zahl }}</span> {{ eintrag.zeile }}
              </p>
              <a mat-flat-button class="seit-besuch-knopf" [routerLink]="eintrag.ziel"
                 [queryParams]="eintrag.queryParams" [fragment]="eintrag.fragment"
                 aria-describedby="seit-besuch-satz" (click)="neues.erledigen(eintrag.art)">
                {{ eintrag.knopf }}
                <mat-icon iconPositionEnd aria-hidden="true">arrow_forward</mat-icon>
              </a>
            </div>
          } @else {
            <ul class="seit-besuch-kacheln" [class.vier]="eintraege.length === 4"
                [style.--seit-besuch-spalten]="eintraege.length">
              @for (eintrag of eintraege; track eintrag.art) {
                <li>
                  <a [routerLink]="eintrag.ziel" [queryParams]="eintrag.queryParams" [fragment]="eintrag.fragment"
                     [class]="'seit-besuch-kachel ' + eintrag.art"
                     [attr.aria-label]="eintrag.satz" (click)="neues.erledigen(eintrag.art)">
                    <span class="seit-besuch-kopf">
                      <mat-icon class="seit-besuch-icon" aria-hidden="true">{{ eintrag.icon }}</mat-icon>
                      <span class="seit-besuch-zahl">{{ eintrag.zahl }}</span>
                    </span>
                    <span class="seit-besuch-wort">{{ eintrag.wort }}</span>
                    @if (eintrag.zeitraum) {
                      <span class="seit-besuch-zeitraum">{{ eintrag.zeitraum }}</span>
                    }
                  </a>
                </li>
              }
            </ul>
          }
        </nav>
      }
    }
  `,
  styleUrls: ['./seit-letztem-besuch.component.css'],
})
export class SeitLetztemBesuchComponent {
  protected readonly neues = inject(SeitLetztemBesuchService);

  /** Je Konto: Wechselt die Kennung, kommt ein neuer Besuch und die Klicks gelten nicht mehr. */
  readonly eintraege$: Observable<NeuesEintrag[]> = inject(AuthService).userInfo$.pipe(
    map((info) => (info?.isAuthenticated && info.userId ? info.userId : null)),
    distinctUntilChanged(),
    switchMap((kennung) => {
      if (!kennung) {
        return of([]);
      }
      this.neues.fuer(kennung);
      return this.neues.start$.pipe(map((start) => start.kacheln));
    }),
  );
}
