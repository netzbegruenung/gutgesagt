import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  DestroyRef,
  ElementRef,
  OnInit,
  QueryList,
  ViewChild,
  ViewChildren,
  inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { RouterLink } from '@angular/router';
import { Subject } from 'rxjs';
import { take } from 'rxjs/operators';

import {
  SpielgefuehlService,
  SpielgefuehlStand,
  SpielgefuehlStufe,
  SpielgefuehlStufenText,
  stufenRang,
} from '../services/spielgefuehl.service';
import { EinwilligungsBudgetService } from '../shared/einwilligungs-budget/einwilligungs-budget.service';
import { EinwilligungsMoment } from '../shared/einwilligungs-budget/einwilligungs-budget';
import { AUS_NACHLADEN_MS, NACHLADEN_MS, nachladeStrom, ohneRechte } from '../shared/selbst-nachladen';

/** Was nach einer Wahl per role="status" angesagt wird. */
export const ANSAGE_STUFE: Record<SpielgefuehlStufe, string> = {
  rangliste: 'Du spielst in der Saison-Rangliste mit.',
  fuer_mich: 'Punkte und Meilensteine sind an, nur für dich.',
  aus: 'Spielgefühl ist aus.',
};

/** Allgemeiner Fehlertext nach Wahl oder Würfeln. */
export const FEHLER_TEXT = 'Das hat nicht geklappt. Bitte versuch es noch einmal.';
/** Würfeln zu schnell hintereinander (429): höchstens ein Wurf je 10 Sekunden. */
export const ZU_SCHNELL_TEXT = 'Du hast gerade erst neu gewürfelt. Warte ein paar Sekunden, dann klappt es wieder.';

/**
 * Text, wenn die gewählte Stufe gerade nicht angeboten wird. Bisher kann das nur die
 * Rangliste sein (Schalter rangliste aus); Punkte und Meilensteine laufen dann weiter.
 */
export const NICHT_ANGEBOTEN_TEXT: Partial<Record<SpielgefuehlStufe, string>> = {
  rangliste:
    'Du hast gewählt, in der Saison-Rangliste mitzuspielen. Die Rangliste ist gerade ausgeschaltet; ' +
    'solange siehst du deine Punkte und Meilensteine nur für dich.',
};
const NICHT_ANGEBOTEN_STANDARD = 'Deine Wahl wird gerade nicht angeboten. Du kannst sie hier ändern.';

/**
 * Spielgefühl als eine Einstellung in „Meine Beiträge“ (Schalter `spielgefuehl_buehne`,
 * GLOSSARY.md „Spielgefühl“): eine Frage mit drei gleich großen Knöpfen ohne
 * Vorauswahl, Gemeinschaft zuerst (In der Saison-Rangliste mitspielen, Nur für mich,
 * Aus). Der Wortlaut kommt unverändert vom Server.
 *
 * - Stufe Rangliste braucht eine Pflichtwahl „In der Rangliste als: mein Anzeigename /
 *   ein Zufallsname“ ohne Vorauswahl; ohne Wahl ist „Mitspielen“ nicht absendbar
 *   (Jura 26.11.). Anzeigename zuerst, beide gleich groß, der Datenschutz-Tipp als
 *   neutraler Hilfetext.
 * - Ändern an derselben Stelle: Herabstufen und Namenswechsel mit einem Klick, sofort
 *   wirksam; Heraufstufen öffnet die Frage, damit der Wortlaut vor Augen steht.
 *   „Neuen Namen würfeln“ nur bei Stufe Rangliste.
 * - Ohne Antwort im neuen Modell fragt die Seite; mit Schalter `einwilligung_im_gewinn`
 *   erst nach dem ersten Gewinn und höchstens eine Frage je Besuch
 *   (shared/einwilligungs-budget, Frage „punkte“).
 *
 * Ohne Schalter (`aktiv: false`) zeigt die Komponente nichts; dann gilt das bisherige
 * Modell mit drei Einwilligungen. Sie lädt selbst nach.
 */
@Component({
  selector: 'app-spielgefuehl',
  standalone: true,
  imports: [CommonModule, MatButtonModule, RouterLink],
  templateUrl: './spielgefuehl.component.html',
  styleUrls: ['./spielgefuehl.component.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SpielgefuehlComponent implements OnInit {
  stand: SpielgefuehlStand | null = null;
  /** Heraufstufen aus dem Stand: Frage mit Wortlaut offen. */
  frageOffen = false;
  /** Stufe Rangliste gewählt, Namenswahl offen. */
  namenswahlOffen = false;
  /** Die Namenswahl in der Frage: null = noch keine (keine Vorauswahl). */
  namenswahl: boolean | null = null;
  speichert = false;
  fehler = false;
  /** Text zum Fehler: bei 429 beim Würfeln ein eigener. */
  fehlerText = FEHLER_TEXT;
  ansage = '';
  /** Mit Schalter einwilligung_im_gewinn: Die Frage darf in diesem Besuch stehen. */
  budgetFrei = false;
  @ViewChild('titel') titel?: ElementRef<HTMLElement>;
  /** Die beiden Knöpfe für den Namen im Stand; nach einem Fehler zurück auf die gespeicherte Wahl. */
  @ViewChildren('nameWahl') nameWahl?: QueryList<ElementRef<HTMLInputElement>>;

  private readonly service = inject(SpielgefuehlService);
  private readonly budget = inject(EinwilligungsBudgetService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly destroyRef = inject(DestroyRef);
  private readonly anstoss$ = new Subject<void>();
  private erstes = true;
  private aus = false;
  private moment: EinwilligungsMoment | null = null;
  private momentGeladen = false;

  ngOnInit(): void {
    // Der schon bekannte Stand sofort: Wechselt die Karte ihren Platz (Meine Beiträge), steht
    // sie ohne Aufblitzen da; das Laden gleich danach bringt den frischen.
    this.service.stand$.pipe(take(1)).subscribe((stand) => {
      if (stand !== undefined) {
        this.stand = stand;
      }
    });
    const abo = nachladeStrom(() => this.service.laden(!this.erstes), {
      sofort: true,
      ms: () => (this.aus ? AUS_NACHLADEN_MS : NACHLADEN_MS),
      aufhoerenBei: ohneRechte,
      anstoss$: this.anstoss$,
    }).subscribe((lauf) => {
      this.erstes = false;
      this.aus = lauf.fehler === null && lauf.daten === null;
      if (lauf.fehler === null) {
        this.stand = lauf.daten;
      } else {
        const status = (lauf.fehler as { status?: number } | null)?.status;
        if (status === 404 || status === 401 || status === 403) {
          this.stand = null;
        }
      }
      this.entscheiden();
      this.cdr.markForCheck();
    });
    const momentAbo = this.budget.moment().subscribe((moment) => {
      this.moment = moment;
      this.momentGeladen = true;
      this.entscheiden();
      this.cdr.markForCheck();
    });
    // Ein Lob (Stimme, „Ja, gepostet“): Die Frage kommt nie direkt danach.
    const gewinnAbo = this.budget.gewinn$.subscribe(() => {
      this.entscheiden();
      this.cdr.markForCheck();
    });
    this.destroyRef.onDestroy(() => {
      abo.unsubscribe();
      momentAbo.unsubscribe();
      gewinnAbo.unsubscribe();
    });
  }

  /**
   * Gefragt wird nach dem Budget (höchstens eine neue Frage je Besuch, vier im ersten
   * Monat), seit dem Schalter-Umbau immer. Ohne Moment (Fehler, Zeitüberschreitung) fragt
   * die Seite in diesem Besuch nicht: Die Grenzen lassen sich dann nicht prüfen.
   */
  private entscheiden(): void {
    if (!this.momentGeladen || !this.stand || this.stand.stufe !== null) {
      return;
    }
    if (!this.moment) {
      this.budgetFrei = false;
      return;
    }
    const faellig = this.budget.punkteFaellig(this.moment);
    if (faellig && !this.budgetFrei) {
      this.budget.gezeigt('punkte');
    }
    this.budgetFrei = faellig;
  }

  /** Die Frage steht: noch keine Antwort (und das Budget erlaubt sie) oder Heraufstufen. */
  get fragen(): boolean {
    if (!this.stand) {
      return false;
    }
    return this.frageOffen || (this.stand.stufe === null && this.budgetFrei);
  }

  /** Die drei Stufen in der Reihenfolge vom Server: Gemeinschaft zuerst. */
  get stufen(): SpielgefuehlStufenText[] {
    return this.stand?.aktueller_wortlaut.stufen ?? [];
  }

  /** Titel der gewählten Stufe; leer, wenn der Server sie gerade nicht anbietet. */
  get gewaehlt(): string {
    return this.stufen.find((s) => s.stufe === this.stand?.stufe)?.titel ?? '';
  }

  /** Ersatz für „Deine Wahl“, wenn die gewählte Stufe gerade nicht angeboten wird. */
  get nichtAngebotenText(): string {
    const stufe = this.stand?.stufe;
    return (stufe && NICHT_ANGEBOTEN_TEXT[stufe]) || NICHT_ANGEBOTEN_STANDARD;
  }

  /** Die anderen Stufen zum Wechseln, in derselben Reihenfolge. */
  get andere(): SpielgefuehlStufenText[] {
    return this.stufen.filter((s) => s.stufe !== this.stand?.stufe);
  }

  /** Ein Knopf der Frage. Rangliste öffnet die Pflichtwahl des Namens. */
  stufeWaehlen(stufe: SpielgefuehlStufe): void {
    if (stufe === 'rangliste') {
      const vorbelegung = this.stand?.aktueller_wortlaut.namenswahl.vorbelegung_anzeigename ?? null;
      if (vorbelegung !== null) {
        this.speichern('rangliste', vorbelegung);
        return;
      }
      this.namenswahlOffen = true;
      return;
    }
    this.namenswahlOffen = false;
    this.speichern(stufe, null);
  }

  /** Aus dem Stand: herabstufen gilt sofort, heraufstufen zeigt erst den Wortlaut. */
  wechseln(stufe: SpielgefuehlStufe): void {
    if (stufenRang(stufe) > stufenRang(this.stand?.stufe ?? null)) {
      this.frageOffen = true;
      this.namenswahl = null;
      this.namenswahlOffen = stufe === 'rangliste' && this.stand?.aktueller_wortlaut.namenswahl.vorbelegung_anzeigename == null;
      this.cdr.markForCheck();
      return;
    }
    this.speichern(stufe, null);
  }

  /** „Mitspielen“ nach der Namenswahl; ohne Wahl nicht absendbar. */
  mitspielen(): void {
    if (this.namenswahl === null) {
      return;
    }
    this.speichern('rangliste', this.namenswahl);
  }

  /** Im Stand: Anzeigename oder Zufallsname, ein Klick, sofort wirksam. */
  nameUmstellen(mitAnzeigename: boolean): void {
    if (!this.stand || this.stand.mit_anzeigename === mitAnzeigename) {
      return;
    }
    if (this.speichert) {
      // Während des Speicherns keine zweite Wahl: die angeklickte zurücksetzen.
      this.nameWahlZuruecksetzen();
      return;
    }
    this.speichern('rangliste', mitAnzeigename);
  }

  /** Abbrechen des Heraufstufens: zurück zum Stand. */
  abbrechen(): void {
    this.frageOffen = false;
    this.namenswahlOffen = false;
    this.namenswahl = null;
    this.cdr.markForCheck();
  }

  wuerfeln(): void {
    const stand = this.stand;
    if (!stand || this.speichert) {
      return;
    }
    this.speichert = true;
    this.fehler = false;
    this.fehlerText = FEHLER_TEXT;
    this.ansage = '';
    this.service.wuerfeln().subscribe({
      next: ({ ranglistenname }) => {
        this.speichert = false;
        this.stand = { ...stand, ranglistenname };
        this.ansage = `Dein neuer Zufallsname: ${ranglistenname}.`;
        this.cdr.markForCheck();
      },
      error: (fehler: { status?: number } | null) => {
        this.speichert = false;
        this.fehler = true;
        this.fehlerText = fehler?.status === 429 ? ZU_SCHNELL_TEXT : FEHLER_TEXT;
        this.cdr.markForCheck();
      },
    });
  }

  private speichern(stufe: SpielgefuehlStufe, mitAnzeigename: boolean | null): void {
    const stand = this.stand;
    if (!stand || this.speichert) {
      return;
    }
    this.speichert = true;
    this.fehler = false;
    this.fehlerText = FEHLER_TEXT;
    this.ansage = '';
    this.service.waehlen(stufe, mitAnzeigename, stand.aktueller_wortlaut.kennung).subscribe({
      next: () => {
        this.speichert = false;
        this.frageOffen = false;
        this.namenswahlOffen = false;
        this.namenswahl = null;
        const neu: SpielgefuehlStand = {
          ...stand,
          stufe,
          mit_anzeigename: stufe === 'rangliste' ? mitAnzeigename : null,
          abzeichen_hinweis: null,
        };
        this.stand = neu;
        this.service.melden(neu);
        const nurName = stufe === 'rangliste' && stand.stufe === 'rangliste';
        this.ansage = nurName ? this.namensAnsage(mitAnzeigename) : ANSAGE_STUFE[stufe];
        this.cdr.detectChanges();
        // Beim Namenswechsel bleibt der Fokus in der Gruppe; nur eine neue Stufe springt zur Überschrift.
        if (!nurName) {
          this.titel?.nativeElement.focus();
        }
        // Den Zufallsnamen beim ersten Mitspielen vergibt der Server: frisch holen.
        this.anstoss$.next();
      },
      error: () => {
        this.speichert = false;
        this.fehler = true;
        this.fehlerText = FEHLER_TEXT;
        // [checked] hat sich nicht geändert, Angular setzt den angeklickten Knopf also nicht
        // zurück: Sonst sähe die Person eine Wahl, die nicht gespeichert ist.
        this.nameWahlZuruecksetzen();
        this.cdr.markForCheck();
      },
    });
  }

  private nameWahlZuruecksetzen(): void {
    const gespeichert = this.stand?.mit_anzeigename ? 'anzeigename' : 'zufall';
    this.nameWahl?.forEach((ref) => (ref.nativeElement.checked = ref.nativeElement.value === gespeichert));
  }

  private namensAnsage(mitAnzeigename: boolean | null): string {
    return mitAnzeigename ? 'In der Rangliste steht jetzt dein Anzeigename.' : 'In der Rangliste steht jetzt dein Zufallsname.';
  }
}
