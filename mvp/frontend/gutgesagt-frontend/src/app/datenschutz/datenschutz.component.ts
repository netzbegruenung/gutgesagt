import { Component, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';
import { RouterModule } from '@angular/router';
import { LEGAL_ENTITY } from '../shared/legal-entity';
import { HOME_HINWEIS_MERKER, MEILENSTEIN_MERKER } from '../shared/geraetespeicher-schalter';
import { FunktionenService } from '../services/funktionen.service';
import { KURZFASSUNG, KurzfassungSatz, kurzfassungFertig } from './dse-kurzfassung';

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
  /** Merker der Meilensteine im Browser; der Absatz dazu steht erst, wenn er an ist (§ 25 TDDDG). */
  readonly meilensteinMerker = inject(MEILENSTEIN_MERKER);
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
