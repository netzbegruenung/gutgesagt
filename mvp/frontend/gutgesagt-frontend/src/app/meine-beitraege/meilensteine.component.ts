import { ChangeDetectionStrategy, ChangeDetectorRef, Component, ElementRef, Inject, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { RouterLink } from '@angular/router';
import { Subject, forkJoin } from 'rxjs';
import { takeUntil } from 'rxjs/operators';

import { AbzeichenSichtbarkeit, Meilenstein, UsageTrackingService } from '../services/usage-tracking.service';
import { AuthService } from '../auth/auth.service';
import { gesehenMerken } from './meilenstein-merker';
import { MEILENSTEIN_MERKER } from '../shared/geraetespeicher-schalter';
import { PunkteEinwilligungComponent } from '../shared/punkte-einwilligung/punkte-einwilligung.component';
import {
  PunkteEinwilligungService,
  PunkteEinwilligungStand,
} from '../shared/punkte-einwilligung/punkte-einwilligung.service';
import { EinwilligungsBudgetService } from '../shared/einwilligungs-budget/einwilligungs-budget.service';
import { EinwilligungsMoment } from '../shared/einwilligungs-budget/einwilligungs-budget';

/**
 * Die eigenen Meilensteine in „Meine Beiträge“ (#351): je einer mit Medaillon (Motiv
 * aus Fluent Emoji, erreicht tannengrün, offen grau gestrichelt), sprechendem Namen,
 * Untertitel und Beschreibung; offene mit Stand („3/10“). Was hier zu sehen war, gilt
 * dem Hinweis nach dem Einwerfen als gesehen (meilenstein-hinweis.service.ts).
 *
 * Darunter die Zustimmung zur Sichtbarkeit (GLOSSARY.md): Ab dem ersten erreichten
 * Meilenstein, der fürs Abzeichen zählt (keine Wegmarke), fragt die Seite einmal mit zwei gleichwertigen Knöpfen, ob andere
 * Angemeldete das Abzeichen am Namen sehen; nichts ist vorbelegt, die Antwort lässt
 * sich jederzeit ändern (ADR 0004, docs/VISION.md). Ohne die Schalter liefert der
 * Server keine Sichtbarkeit, dann fragt die Seite nicht und die Meilensteine bleiben
 * nur für die Person.
 *
 * Meilensteine gibt es nur mit der eigenen, freiwilligen Einwilligung „Punkte und
 * Meilensteine“ (#351). Fehlt sie, steht hier eine kurze Einladung mit dem Häkchen;
 * nach dem Haken laden die Meilensteine selbst nach. Ohne eingeschaltete Punkte oder
 * für ein Startkonto zeigt die Komponente nichts.
 *
 * Mit dem Schalter einwilligung_im_gewinn (#788) entscheidet das Einwilligungs-Budget
 * (shared/einwilligungs-budget): Die Einladung kommt dann als Frage mit zwei
 * gleichwertigen Knöpfen und unverändertem Wortlaut, erst nach dem ersten Gewinn und
 * höchstens eine Frage je Besuch; danach fragt die Seite nicht mehr, das Häkchen bleibt
 * in den Datenschutz-Einstellungen. Auch die Frage nach der Sichtbarkeit wartet, wenn
 * im Besuch schon eine andere kam.
 */
@Component({
  selector: 'app-meilensteine',
  standalone: true,
  imports: [CommonModule, MatButtonModule, RouterLink, PunkteEinwilligungComponent],
  templateUrl: './meilensteine.component.html',
  styleUrls: ['./meilensteine.component.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MeilensteineComponent implements OnInit, OnDestroy {
  meilensteine: Meilenstein[] = [];
  sichtbarkeit: AbzeichenSichtbarkeit | null = null;
  speichert = false;
  /** Nach einem Nein erneut gefragt ("Anderen zeigen"): Zustimmen nur mit dem Wortlaut vor Augen. */
  frageOffen = false;
  fehler = false;
  /** Nach einer Antwort verschwinden die Knöpfe der Frage; der Fokus geht hierher. */
  @ViewChild('aendernKnopf', { read: ElementRef }) aendernKnopf?: ElementRef<HTMLElement>;
  /** Punkte an, aber (noch) keine Einwilligung „Punkte und Meilensteine“: Einladung zeigen. */
  einladen = false;
  private eingewilligt: boolean | null = null;
  private destroy$ = new Subject<void>();
  /** Antwort vom Einwilligungs-Moment ist da (auch null: Schalter aus). */
  momentGeladen = false;
  /** Fakten fürs Einwilligungs-Budget; null: Schalter aus, die Seite fragt wie bisher. */
  moment: EinwilligungsMoment | null = null;
  private punkteStand: PunkteEinwilligungStand | null = null;
  /** Mit Schalter: Die Frage nach Punkten und Meilensteinen steht in diesem Besuch. */
  punkteFrageZeigen = false;
  /** Mit Schalter: Die Frage nach der Sichtbarkeit darf in diesem Besuch kommen. */
  sichtbarkeitErlaubt = false;
  punkteSpeichert = false;
  punkteFehler = false;
  /** Gerade beantwortet: Satz zum neuen Stand, per role="status" angesagt. */
  punkteAntwort: 'ja' | 'nein' | null = null;
  @ViewChild('punkteStatus', { read: ElementRef }) punkteStatus?: ElementRef<HTMLElement>;
  /** Nach einem frischen Lob: noch einmal entscheiden, sobald es vorbei ist. */
  private nachLob: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private usageTrackingService: UsageTrackingService,
    private authService: AuthService,
    private cdr: ChangeDetectorRef,
    @Inject(MEILENSTEIN_MERKER) private merkerAktiv: boolean,
    private punkteEinwilligung: PunkteEinwilligungService,
    private budget: EinwilligungsBudgetService,
  ) {}

  ngOnInit(): void {
    this.laden();
    // Die Einwilligung kann hier oder in den Datenschutz-Einstellungen wechseln: Dann
    // laden die Meilensteine selbst nach, ohne Neuladen der Seite.
    this.punkteEinwilligung.stand$.pipe(takeUntil(this.destroy$)).subscribe((stand) => {
      if (stand === undefined) {
        return;
      }
      const eingewilligt = stand?.eingewilligt ?? null;
      this.punkteStand = stand;
      this.einladen = stand !== null && !stand.eingewilligt;
      this.entscheiden();
      if (this.eingewilligt !== null && eingewilligt !== this.eingewilligt) {
        this.laden();
      }
      this.eingewilligt = eingewilligt;
      this.cdr.markForCheck();
    });
    this.punkteEinwilligung.laden().pipe(takeUntil(this.destroy$)).subscribe();
    this.budget
      .moment()
      .pipe(takeUntil(this.destroy$))
      .subscribe((moment) => {
        this.moment = moment;
        this.momentGeladen = true;
        this.entscheiden();
        this.cdr.markForCheck();
      });
    // Ein Lob (Stimme, „Ja, gepostet“) auf dieser Seite: Die offene Frage tritt zurück und
    // kommt erst wieder, wenn das Lob vorbei ist (Lob und Frage getrennt).
    this.budget.gewinn$.pipe(takeUntil(this.destroy$)).subscribe(() => {
      if (this.punkteFrageZeigen) {
        this.punkteFrageZeigen = false;
        this.cdr.markForCheck();
      }
      this.entscheiden();
    });
  }

  /**
   * Mit Schalter: einmal je Besuch entscheiden, welche Frage kommen darf. Eine Frage,
   * die steht, bleibt stehen, bis sie beantwortet ist.
   */
  private entscheiden(): void {
    const moment = this.moment;
    if (!moment) {
      return;
    }
    const stand = this.punkteStand;
    const offen = !this.punkteFrageZeigen && !!stand && !stand.eingewilligt && !stand.wortlaut;
    if (offen && this.budget.punkteFaellig(moment)) {
      this.punkteFrageZeigen = true;
      this.budget.gezeigt('punkte');
    } else if (offen) {
      this.spaeterEntscheiden();
    }
    if (
      !this.sichtbarkeitErlaubt &&
      this.sichtbarkeit &&
      !this.sichtbarkeit.gefragt &&
      this.erreichteFuersAbzeichen > 0 &&
      this.budget.darf('sichtbarkeit', moment)
    ) {
      this.sichtbarkeitErlaubt = true;
      this.budget.gezeigt('sichtbarkeit');
    }
  }

  /** Hält nur ein frisches Lob die Frage zurück, wird danach noch einmal entschieden. */
  private spaeterEntscheiden(): void {
    const warten = this.budget.lobFrischNoch();
    if (warten <= 0 || this.nachLob !== null) {
      return;
    }
    this.nachLob = setTimeout(() => {
      this.nachLob = null;
      this.entscheiden();
      this.cdr.markForCheck();
    }, warten + 50);
  }

  /**
   * Die alte Einladung mit Häkchen: nur ohne Schalter einwilligung_im_gewinn. Ist der
   * Schalter nicht sicher aus (Fehler, keine Antwort), lädt sie niemanden noch einmal ein,
   * der schon geantwortet hat: Ein Nein gilt dauerhaft (#788, Jura 25.11.).
   */
  get haekchenEinladung(): boolean {
    if (!this.einladen || !this.momentGeladen || this.moment) {
      return false;
    }
    return !this.punkteStand?.wortlaut || this.budget.schalterAus;
  }

  /** Text der Frage: der Wortlaut vom Server, unverändert. */
  get punkteWortlaut(): string {
    return this.punkteStand?.aktueller_wortlaut.text ?? '';
  }

  /** Einer der beiden gleichwertigen Knöpfe der Frage nach Punkten und Meilensteinen. */
  punkteAntworten(ja: boolean): void {
    if (this.punkteSpeichert) {
      return;
    }
    this.punkteSpeichert = true;
    this.punkteFehler = false;
    this.punkteEinwilligung
      .setzen(ja)
      .pipe(takeUntil(this.destroy$))
      .subscribe((ok) => {
        this.punkteSpeichert = false;
        if (ok) {
          this.punkteFrageZeigen = false;
          this.punkteAntwort = ja ? 'ja' : 'nein';
        } else {
          this.punkteFehler = true;
        }
        this.cdr.detectChanges();
        if (ok) {
          this.punkteStatus?.nativeElement.focus();
        }
      });
  }

  ngOnDestroy(): void {
    if (this.nachLob !== null) {
      clearTimeout(this.nachLob);
    }
    this.destroy$.next();
    this.destroy$.complete();
  }

  laden(): void {
    forkJoin({
      meilensteine: this.usageTrackingService.getEigeneMeilensteine(),
      sichtbarkeit: this.usageTrackingService.getAbzeichenSichtbarkeit(),
    })
      .pipe(takeUntil(this.destroy$))
      .subscribe(({ meilensteine, sichtbarkeit }) => {
        this.meilensteine = meilensteine;
        this.sichtbarkeit = sichtbarkeit;
        this.entscheiden();
        // Was hier steht, ist angezeigt: Kein späterer Hinweis nennt es noch einmal.
        if (this.merkerAktiv) {
          gesehenMerken(this.authService.getCurrentUserId(), meilensteine);
        }
        this.cdr.markForCheck();
      });
  }

  get erreichte(): number {
    return this.meilensteine.filter((m) => m.erreicht).length;
  }

  /** Die erreichten und der nächste offene, in der Reihenfolge der Liste. */
  get sichtbare(): Meilenstein[] {
    const naechster = this.meilensteine.find((m) => !m.erreicht);
    return this.meilensteine.filter((m) => m.erreicht || m === naechster);
  }

  /** Die übrigen offenen, aufklappbar unter „Weitere Meilensteine“. */
  get weitere(): Meilenstein[] {
    const sichtbar = new Set(this.sichtbare);
    return this.meilensteine.filter((m) => !sichtbar.has(m));
  }

  /** Die Bildnachweise, je einmal; für ein später ersetztes Bild steht dort ein eigener. */
  get bildnachweise(): string[] {
    return [...new Set(this.meilensteine.map((m) => m.bildnachweis).filter((n) => !!n))];
  }

  /** Erreichte, die das Abzeichen am Namen zählt: Wegmarken (eigenes Tun) nicht. */
  get erreichteFuersAbzeichen(): number {
    return this.meilensteine.filter((m) => m.erreicht && m.art !== 'weg').length;
  }

  /** Einmal fragen, sobald es etwas zu zeigen gäbe. */
  get fragen(): boolean {
    if (!this.sichtbarkeit) {
      return false;
    }
    if (this.frageOffen) {
      return true;
    }
    // Mit Schalter einwilligung_im_gewinn nur, wenn das Budget sie in diesem Besuch erlaubt.
    const budgetFrei = this.momentGeladen && (!this.moment || this.sichtbarkeitErlaubt);
    return budgetFrei && !this.sichtbarkeit.gefragt && this.erreichteFuersAbzeichen > 0;
  }

  /** Andere Angemeldete sehen das Abzeichen. */
  get sichtbar(): boolean {
    return this.sichtbarkeit?.zeigen === true;
  }

  /** "Anderen zeigen" fragt noch einmal mit dem Wortlaut; "Nicht mehr zeigen" gilt sofort. */
  aendern(): void {
    if (this.sichtbar) {
      this.antworten(false);
    } else {
      this.frageOffen = true;
    }
  }

  antworten(zeigen: boolean): void {
    const stand = this.sichtbarkeit;
    if (!stand || this.speichert) {
      return;
    }
    this.speichert = true;
    this.fehler = false;
    this.usageTrackingService
      .setAbzeichenSichtbarkeit(zeigen, stand.aktueller_wortlaut.kennung)
      .pipe(takeUntil(this.destroy$))
      .subscribe((ok) => {
        this.speichert = false;
        if (ok) {
          this.sichtbarkeit = { ...stand, gefragt: true, zeigen };
          this.frageOffen = false;
        } else {
          this.fehler = true;
        }
        this.cdr.detectChanges();
        if (ok) {
          this.aendernKnopf?.nativeElement.focus();
        }
      });
  }
}
