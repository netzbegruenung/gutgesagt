import { Component, DestroyRef, Injector, afterNextRender, computed, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable, toSignal } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { of } from 'rxjs';
import { catchError, map, switchMap, take } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import { dseMusterStimmen } from './dse-muster-stimmen';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';
import { ActivatedRoute, RouterModule } from '@angular/router';
import {
  DSE_SPIELGEFUEHL_AUS,
  DSE_SPIELGEFUEHL_EINLEITUNG,
  DSE_SPIELGEFUEHL_NUR_FUER_MICH,
  DSE_SPIELGEFUEHL_OHNE_RANGLISTE,
  DSE_SPIELGEFUEHL_RANGLISTE,
  DSE_SPIELGEFUEHL_SCHLUSS,
  DSE_SPIELGEFUEHL_SOCKEL,
  DSE_SPIELGEFUEHL_TITEL,
} from './dse-spielgefuehl';
import { LEGAL_ENTITY } from '../shared/legal-entity';
import { HOME_HINWEIS_MERKER, MEILENSTEIN_MERKER } from '../shared/geraetespeicher-schalter';
import { FunktionenService } from '../services/funktionen.service';
import { AuthService } from '../auth/auth.service';
import { WiderrufbarComponent } from '../einwilligung/widerrufbar.component';
import { KURZFASSUNG, KURZFASSUNG_SCHLUSS, KurzfassungSatz, kurzfassungFertig } from './dse-kurzfassung';

@Component({
  selector: 'app-datenschutz',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatDividerModule,
    RouterModule,
    WiderrufbarComponent
  ],
  templateUrl: './datenschutz.component.html',
  styleUrls: ['./datenschutz.component.scss']
})
export class DatenschutzComponent {
  readonly VEREIN = LEGAL_ENTITY;
  private readonly funktionen = inject(FunktionenService);
  /**
   * Angemeldet? null, solange die App es noch nicht weiß: dann steht im Kasten
   * „Einwilligung widerrufen“ weder Knopf noch Anmeldehinweis. Folgt dem Stand, ohne Neuladen.
   */
  readonly angemeldet = toSignal(
    inject(AuthService).userInfo$.pipe(map((info) => (info ? info.isAuthenticated : null))),
    { initialValue: null }
  );
  /**
   * Zurück vom Anmelden (returnUrl …#einwilligung-widerrufen): Sobald der Anmeldestand da ist,
   * einmal wie ein Sprunglink zum Kasten, mit scroll-padding und Fokus (WCAG 2.4.3); das
   * anchorScrolling des Routers kennt beides nicht.
   */
  private kastenAngesprungen = false;
  /** Zeilen „Ausschalten“ im Kasten; -1: noch nicht geladen. */
  readonly widerrufZeilen = signal(-1);
  private readonly zumKasten = effect(() => {
    if (this.angemeldet() === null || this.kastenAngesprungen || location.hash !== '#einwilligung-widerrufen') {
      return;
    }
    this.kastenAngesprungen = true;
    setTimeout(() => {
      const ziel = document.getElementById('einwilligung-widerrufen');
      ziel?.scrollIntoView({ block: 'start' });
      ziel?.focus({ preventScroll: true });
    });
  });
  /** Sätze des Kastens „Kurz gesagt“ (dse-kurzfassung.ts). */
  readonly kurzfassungSaetze: readonly KurzfassungSatz[] = inject(KURZFASSUNG);
  /** Schlusssatz unter den drei Sätzen des Kastens (Wortlaut Jura). */
  readonly kurzfassungSchluss = KURZFASSUNG_SCHLUSS;
  /**
   * Kasten „Kurz gesagt“ oben (Basisfunktion seit dem Schalter-Umbau 27.11.): nur, wenn alle
   * drei Sätze den Wortlaut von Jura tragen, nie mit Platzhalter (Schutzgrenze ohne Schalter).
   */
  readonly kurzfassungZeigen = computed(() => kurzfassungFertig(this.kurzfassungSaetze));

  /**
   * Sprunglink der Kurzfassung: scrollIntoView statt Router-Fragment, weil der
   * ViewportScroller scroll-padding (styles.css, klebender Kopf am Handy) nicht beachtet und
   * die Überschrift sonst unter dem Kopf läge. Die Adresse bekommt den Anker trotzdem.
   * Der Fokus geht auf den Absatz (tabindex="-1" im Template), damit Tab dort weitergeht
   * wie nach einem echten Fragment-Sprung (WCAG 2.4.3).
   */
  springen(ereignis: MouseEvent, anker: string): void {
    const ziel = document.getElementById(anker);
    if (!ziel || ereignis.button !== 0 || ereignis.ctrlKey || ereignis.metaKey || ereignis.shiftKey) {
      return;
    }
    ereignis.preventDefault();
    ziel.scrollIntoView({ block: 'start' });
    ziel.focus({ preventScroll: true });
    history.replaceState(history.state, '', `${location.pathname}${location.search}#${anker}`);
  }
  /**
   * Anker hinter einem Schalter (etwa #spielgefuehl, #rangliste): Beim Aufruf mit Fragment
   * steht der Absatz oft noch nicht, weil GET /api/v1/funktionen erst antworten muss; der
   * Router scrollt dann ins Leere und die Person landet oben in der langen Erklärung.
   * Fehlt das Ziel beim ersten Zeichnen, springt die Seite einmal dorthin, sobald die
   * Schalter da sind.
   */
  private readonly injector = inject(Injector);
  private readonly destroyRef = inject(DestroyRef);

  constructor() {
    const anker = inject(ActivatedRoute).snapshot.fragment;
    if (!anker) {
      return;
    }
    afterNextRender(
      () => {
        if (document.getElementById(anker)) {
          return;
        }
        this.funktionen
          .stand$('spielgefuehl_buehne')
          .pipe(take(1), takeUntilDestroyed(this.destroyRef))
          .subscribe(() =>
            afterNextRender(
              () => {
                const ziel = document.getElementById(anker);
                if (!ziel) {
                  return;
                }
                // Wie springen(): Fokus mit, damit Tab dort weitergeht (WCAG 2.4.3).
                ziel.scrollIntoView({ block: 'start' });
                if (!ziel.hasAttribute('tabindex')) {
                  ziel.setAttribute('tabindex', '-1');
                }
                ziel.focus({ preventScroll: true });
              },
              { injector: this.injector },
            ),
          );
      },
      { injector: this.injector },
    );
  }

  /** Merker der Meilensteine im Browser; der Absatz dazu steht erst, wenn er an ist (§ 25 TDDDG). */
  readonly meilensteinMerker = inject(MEILENSTEIN_MERKER);
  /**
   * Paket Spielgefühl (spielgefuehl_buehne: Punkte, Spielgefühl als eine Frage, Rangliste;
   * Schalter-Umbau 27.11.): der Absatz „Spielgefühl“ ersetzt unter „Punkte“ die
   * Einwilligungsteile zu Punkten, Abzeichen und Rangliste. Die früheren Schalter punkte und
   * rangliste fragt die Seite nicht mehr, ihre Absätze hängen am Paket.
   */
  readonly spielgefuehlBuehne = this.funktionen.an('spielgefuehl_buehne');
  readonly spielgefuehlTitel = DSE_SPIELGEFUEHL_TITEL;
  readonly spielgefuehlEinleitung = DSE_SPIELGEFUEHL_EINLEITUNG;
  readonly spielgefuehlAus = DSE_SPIELGEFUEHL_AUS;
  readonly spielgefuehlNurFuerMich = DSE_SPIELGEFUEHL_NUR_FUER_MICH;
  readonly spielgefuehlRangliste = DSE_SPIELGEFUEHL_RANGLISTE;
  readonly spielgefuehlOhneRangliste = DSE_SPIELGEFUEHL_OHNE_RANGLISTE;
  readonly spielgefuehlSchluss = DSE_SPIELGEFUEHL_SCHLUSS;
  readonly spielgefuehlSockel = DSE_SPIELGEFUEHL_SOCKEL;
  /** Merker „Hinweis Home-Bildschirm ausgeblendet“; der Absatz dazu steht nur, wenn er an ist. */
  readonly homeHinweisMerker = inject(HOME_HINWEIS_MERKER);

  /*
   * Absätze und Sätze, die an einem Schalter hängen (Grundsatz: kein Schalter ohne seinen
   * Absatz, vorläufige juristische Einschätzung 26.11.2026). Jeder Schalter hier muss in
   * services/schalter_service.py öffentlich sein, sonst meldet GET /api/v1/funktionen ihn
   * nicht und der Absatz bliebe auch bei eingeschaltetem Schalter weg. Absätze der
   * Basisfunktionen (Schalter-Umbau 27.11.) stehen ohne Bedingung, auch die mit Not-Aus
   * (gepostet_ohne_konto, null_treffer_anzahl, feedback_gestoert).
   */
  /**
   * Zustimmungen in den Muster-Hinweisen (Schalter muster_stimmen): ein Satz unter
   * „Muster-Hinweise“ mit dem Einschalttag, den die Seite erst fragt, wenn der Schalter an ist.
   */
  readonly musterStimmen = this.funktionen.an('muster_stimmen');
  private readonly http = inject(HttpClient, { optional: true });
  private readonly musterStimmenSeit = toSignal(
    toObservable(this.musterStimmen).pipe(
      switchMap((an) =>
        an && this.http
          ? this.http
              .get<{ seit: string | null }>(`${environment.baseUrl}/api/v1/funktionen/muster_stimmen/seit`)
              .pipe(
                map((antwort) => antwort?.seit ?? null),
                catchError(() => of(null)),
              )
          : of(null),
      ),
    ),
    { initialValue: null },
  );
  readonly musterStimmenSatz = computed(() => dseMusterStimmen(this.musterStimmenSeit()));
  /** Paket Teams (#784): mit ihm entfällt der Satz „Die Team-Summe ist noch nicht eingeschaltet“. */
  readonly teams = this.funktionen.an('teams');
  /** Team-Quests (#792): Absatz unter „Teams“; wirkt nur mit dem Paket teams. */
  readonly teamQuests = this.funktionen.an('team_quests');
  /**
   * Paket Wirkungs-Echo (#790, #791): dritte gespeicherte Zahl, der Zählerstand des Echos und
   * die Sätze zum Danke und zum Tages-Prüfwert.
   */
  readonly wirkungsEcho = this.funktionen.an('wirkungs_echo');
  /** Paket BDK-Begrüßung: Begrüßung nach dem Kampagnenwort ?k=. */
  readonly kBegruessung = this.funktionen.an('k_begruessung');
  readonly KONTAKT_MAIL = LEGAL_ENTITY.KONTAKT_MAIL;

  // Der Datenschutzbeauftragte ist ueber die Vereinsadresse erreichbar, nicht privat.
  readonly DSB_KONTAKT = `Sven Seeberg, erreichbar über ${LEGAL_ENTITY.KONTAKT_MAIL}`;

  // Zustaendig ist die Aufsichtsbehoerde am Sitz des Verantwortlichen: der Verein sitzt in
  // Donauwoerth, das Vereinsregister liegt beim Amtsgericht Augsburg -- beides Bayern, und
  // fuer nichtoeffentliche Stellen ist dort das BayLDA zustaendig.
  readonly BEHOERDE_NAME = 'Bayerisches Landesamt für Datenschutzaufsicht (BayLDA)';
  readonly BEHOERDE_ANSCHRIFT = 'Promenade 18, 91522 Ansbach';
  readonly BEHOERDE_TELEFON = '+49 981 180093-0';
  readonly BEHOERDE_URL = 'https://www.lda.bayern.de';
}
