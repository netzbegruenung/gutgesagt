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

/** Die Kachel des Rückwegs zu „Dein nächster Schritt“ (Rundgang 28.11.). */
export const RUECKWEG_TITEL = 'Nächster Schritt';
export const RUECKWEG_KNOPF = 'Vorschlag holen';
/** Der Satz der breiten Zeile, wenn der Rückweg allein steht (hinter „Nächster Schritt:“). */
export const RUECKWEG_SATZ = 'Deine Vorschläge hast du ausgeblendet.';

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
    @if (block$ | async; as block) {
      @let eintraege = block.kacheln;
      @if (eintraege.length || block.rueckweg) {
        <nav class="seit-besuch" aria-labelledby="seit-besuch-titel">
          <h2 id="seit-besuch-titel">Seit deinem letzten Besuch</h2>
          @if (!eintraege.length) {
            <!-- Nur der Rückweg: breite Zeile wie eine einzelne Kachel -->
            <div class="seit-besuch-zeile rueckweg">
              <mat-icon class="seit-besuch-icon" aria-hidden="true">lightbulb</mat-icon>
              <p class="seit-besuch-satz" id="seit-besuch-satz"><strong>{{ rueckwegTitel }}:</strong> {{ rueckwegSatz }}</p>
              <button mat-flat-button type="button" class="seit-besuch-knopf" data-testid="vorschlag-holen"
                      aria-describedby="seit-besuch-satz" (click)="neues.vorschlagHolen()">
                {{ rueckwegKnopf }}
              </button>
            </div>
          } @else if (eintraege.length === 1 && !block.rueckweg) {
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
            @let anzahl = eintraege.length + (block.rueckweg ? 1 : 0);
            <ul class="seit-besuch-kacheln" [class.vier]="anzahl === 4"
                [style.--seit-besuch-spalten]="anzahl">
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
              @if (block.rueckweg) {
                <!-- Rückweg zu „Dein nächster Schritt“ (Rundgang 28.11.): ein Knopf, kein Link -->
                <li>
                  <button type="button" class="seit-besuch-kachel rueckweg" data-testid="vorschlag-holen"
                          [attr.aria-label]="rueckwegTitel + ': ' + rueckwegKnopf" (click)="neues.vorschlagHolen()">
                    <span class="seit-besuch-kopf">
                      <mat-icon class="seit-besuch-icon" aria-hidden="true">lightbulb</mat-icon>
                      <span class="seit-besuch-titel">{{ rueckwegTitel }}</span>
                    </span>
                    <span class="seit-besuch-wort">{{ rueckwegKnopf }}</span>
                  </button>
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
  protected readonly rueckwegTitel = RUECKWEG_TITEL;
  protected readonly rueckwegKnopf = RUECKWEG_KNOPF;
  protected readonly rueckwegSatz = RUECKWEG_SATZ;

  /**
   * Je Konto: Wechselt die Kennung, kommt ein neuer Besuch und die Klicks gelten nicht mehr.
   * Die Kacheln und ob der Rückweg zu „Dein nächster Schritt“ dazukommt.
   */
  readonly block$: Observable<{ kacheln: NeuesEintrag[]; rueckweg: boolean }> = inject(AuthService).userInfo$.pipe(
    map((info) => (info?.isAuthenticated && info.userId ? info.userId : null)),
    distinctUntilChanged(),
    switchMap((kennung) => {
      if (!kennung) {
        return of({ kacheln: [], rueckweg: false });
      }
      this.neues.fuer(kennung);
      return this.neues.start$.pipe(map((start) => ({ kacheln: start.kacheln, rueckweg: start.rueckweg })));
    }),
  );
}
