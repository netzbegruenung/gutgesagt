import { Component, DestroyRef, Injector, afterNextRender, computed, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { take } from 'rxjs/operators';
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
import { KURZFASSUNG, KURZFASSUNG_SCHLUSS, KurzfassungSatz, kurzfassungFertig } from './dse-kurzfassung';

@Component({
  selector: 'app-datenschutz',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatDividerModule,
    RouterModule
  ],
  templateUrl: './datenschutz.component.html',
  styleUrls: ['./datenschutz.component.scss']
})
export class DatenschutzComponent {
  readonly VEREIN = LEGAL_ENTITY;
  private readonly funktionen = inject(FunktionenService);
  /** Sätze des Kastens „Kurz gesagt“ (dse-kurzfassung.ts). */
  readonly kurzfassungSaetze: readonly KurzfassungSatz[] = inject(KURZFASSUNG);
  /** Schlusssatz unter den drei Sätzen des Kastens (Wortlaut Jura). */
  readonly kurzfassungSchluss = KURZFASSUNG_SCHLUSS;
  private readonly kurzfassungAn = this.funktionen.an('dse_kurzfassung');
  /**
   * Kasten „Kurz gesagt“ oben: nur mit Schalter dse_kurzfassung und nur, wenn alle drei
   * Sätze den Wortlaut von Jura tragen, nie mit Platzhalter.
   */
  readonly kurzfassungZeigen = computed(
    () => this.kurzfassungAn() && kurzfassungFertig(this.kurzfassungSaetze)
  );

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
   * Spielgefühl als eine Frage (Schalter spielgefuehl_buehne): der Absatz „Spielgefühl“
   * ersetzt unter „Punkte“ die Einwilligungsteile zu Punkten, Abzeichen und Rangliste.
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
  /**
   * Karte „Dein nächster Schritt“ (#789): der Satz unter „Rückmeldung zur Nutzung“ steht,
   * solange der Schalter an ist; der Absatz zum Eintrag auf dem Gerät immer, weil ein
   * Eintrag nach dem Ausschalten noch bis zu sieben Tage liegen kann.
   */
  readonly naechsterSchritt = this.funktionen.an('naechster_schritt');
  /** „Danach wurde schon N-mal gesucht“ (#362): der Absatz unter „Suchen ohne Treffer“ steht, solange der Schalter an ist. */
  readonly nullTrefferAnzahl = this.funktionen.an('null_treffer_anzahl');
  /**
   * Stimmenverfall bei ganz anderem Text (#636): der Halbsatz unter „Bewertungen“ steht nur,
   * solange der Schalter stimmen_text_verfall an ist; sonst verfallen Stimmen nur beim Titel.
   */
  readonly textVerfall = inject(FunktionenService).an('stimmen_text_verfall');

  /*
   * Absätze und Sätze, die an einem Schalter hängen (Grundsatz: kein Schalter ohne seinen
   * Absatz, vorläufige juristische Einschätzung 26.11.2026). Jeder Schalter hier muss in
   * services/schalter_service.py öffentlich sein, sonst meldet GET /api/v1/funktionen ihn
   * nicht und der Absatz bliebe auch bei eingeschaltetem Schalter weg.
   */
  /** Punkte: der Vorbehalt „noch nicht eingeschaltet“ entfällt, die Muster-Hinweise gelten. */
  readonly punkte = this.funktionen.an('punkte');
  /** Rangliste (#793): Absatz statt des Hinweises „noch nicht eingeschaltet“. */
  readonly rangliste = this.funktionen.an('rangliste');
  /** Team-Summe (#784): der Satz „noch nicht eingeschaltet“ entfällt. */
  readonly teamFortschritt = this.funktionen.an('team_fortschritt');
  /** Team-Quests (#792): Absatz unter „Teams“; wirkt nur mit team_fortschritt. */
  readonly teamQuests = this.funktionen.an('team_quests');
  /** Wirkungs-Echo (#790): dritte gespeicherte Zahl und der Zählerstand des Echos. */
  readonly wirkungsEcho = this.funktionen.an('wirkungs_echo');
  /** Danke-Knopf (#791): die Sätze zum Danke und zum Tages-Prüfwert. */
  readonly dankeKnopf = this.funktionen.an('danke_knopf');
  /** „Ja, gepostet“ ohne Konto (#799). */
  readonly gepostetOhneKonto = this.funktionen.an('gepostet_ohne_konto');
  /** Neue Antworten auf eigene Aussagen (#760). */
  readonly antwortenHinweis = this.funktionen.an('antworten_hinweis');
  /** „Melden“ in der Meta-Zeile und „Melden & Kontakt“ im Fuß (#843). */
  readonly meldewegSichtbar = this.funktionen.an('meldeweg_sichtbar');
  /** „Was hat dich gestört?“ in der Startphase. */
  readonly feedbackGestoert = this.funktionen.an('feedback_gestoert');
  /** Begrüßung nach dem Kampagnenwort ?k=. */
  readonly kBegruessung = this.funktionen.an('k_begruessung');
  /** Bestandszahl samt Zuwachs der letzten sieben Tage auf der Startseite. */
  readonly bestandszahlZuwachs = this.funktionen.an('bestandszahl_zuwachs');
  /**
   * „Ton bei Erfolgen“ (#787) gibt es nur im großen Moment „Lücke zu!“ hinter dem Schalter
   * luecke_zu_gross; der Absatz zu seinem Eintrag im Browser steht, solange der Schalter an ist
   * oder der Browser den Eintrag noch hat (Schalter später wieder aus).
   */
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
