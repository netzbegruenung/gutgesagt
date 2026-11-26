import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';
import { RouterModule } from '@angular/router';
import { LEGAL_ENTITY } from '../shared/legal-entity';
import { HOME_HINWEIS_MERKER, MEILENSTEIN_MERKER } from '../shared/geraetespeicher-schalter';
import { FunktionenService } from '../services/funktionen.service';

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
  /** Merker der Meilensteine im Browser; der Absatz dazu steht erst, wenn er an ist (§ 25 TDDDG). */
  readonly meilensteinMerker = inject(MEILENSTEIN_MERKER);
  /** Merker „Hinweis Home-Bildschirm ausgeblendet“; der Absatz dazu steht nur, wenn er an ist. */
  readonly homeHinweisMerker = inject(HOME_HINWEIS_MERKER);
  /**
   * Karte „Dein nächster Schritt“ (#789): der Satz unter „Rückmeldung zur Nutzung“ steht,
   * solange der Schalter an ist; der Absatz zum Eintrag auf dem Gerät immer, weil ein
   * Eintrag nach dem Ausschalten noch bis zu sieben Tage liegen kann.
   */
  readonly naechsterSchritt = inject(FunktionenService).an('naechster_schritt');
  /**
   * Stimmenverfall bei ganz anderem Text (#636): der Halbsatz unter „Bewertungen“ steht nur,
   * solange der Schalter stimmen_text_verfall an ist; sonst verfallen Stimmen nur beim Titel.
   */
  readonly textVerfall = inject(FunktionenService).an('stimmen_text_verfall');
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
