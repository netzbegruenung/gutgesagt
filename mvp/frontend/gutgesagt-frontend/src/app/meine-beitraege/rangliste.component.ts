import { ChangeDetectionStrategy, ChangeDetectorRef, Component, DestroyRef, ElementRef, OnInit, QueryList, ViewChild, ViewChildren, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { RouterLink } from '@angular/router';
import { Subject } from 'rxjs';

import { RanglisteService, RanglisteStand, RanglistenPlatz } from '../services/rangliste.service';
import { nachladeStrom, ohneRechte } from '../shared/selbst-nachladen';

export const RANGLISTE_JA = 'Ja, zeigt mich in der Rangliste';
export const RANGLISTE_NEIN = 'Nein, ohne Rangliste';

/**
 * Rangliste der laufenden Saison in „Meine Beiträge“ (#793), unter den Meilensteinen.
 *
 * - Gefragt wird einmal, sobald es eine laufende Saison gibt und beide Voraussetzungen
 *   gelten (Art.-9-Einwilligung, „Punkte und Meilensteine“): der volle Wortlaut und
 *   zwei gleichwertige Knöpfe, nichts vorbelegt. Die Frage steht unter den Punkten,
 *   nie davor: Punkte gibt es auch ohne Rangliste.
 * - Wer mitmacht, sieht die ersten zehn Plätze und den eigenen, erst ab zehn
 *   Teilnehmenden; darunter vergangene Saisons nur als eigene Summe. Der Name ist der
 *   zufällige Ranglistenname, außer die Person wählt hier aktiv ihren Anzeigenamen.
 * - „Aus der Rangliste nehmen“ wirkt sofort, ohne Rückfrage, so leicht wie das Ja.
 *
 * Ohne Schalter (404) oder ohne Anmeldung zeigt die Komponente nichts. Sie lädt selbst
 * nach, auch nach jeder Antwort.
 */
@Component({
  selector: 'app-rangliste',
  standalone: true,
  imports: [CommonModule, MatButtonModule, RouterLink],
  templateUrl: './rangliste.component.html',
  styleUrls: ['./rangliste.component.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RanglisteComponent implements OnInit {
  stand: RanglisteStand | null = null;
  /** Nach einem Nein erneut gefragt („Doch mitmachen“): Zustimmen nur mit dem Wortlaut vor Augen. */
  frageOffen = false;
  speichert = false;
  fehler = false;
  ansage = '';
  readonly ja = RANGLISTE_JA;
  readonly nein = RANGLISTE_NEIN;
  /** Nach einer Antwort verschwinden die Knöpfe; der Fokus geht auf die Überschrift. */
  @ViewChild('titel') titel?: ElementRef<HTMLElement>;
  /** Die beiden Knöpfe für den Namen; nach einem Fehler zurück auf die gespeicherte Wahl. */
  @ViewChildren('nameWahl') nameWahl?: QueryList<ElementRef<HTMLInputElement>>;

  private readonly service = inject(RanglisteService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly destroyRef = inject(DestroyRef);
  private readonly anstoss$ = new Subject<void>();
  private erstes = true;

  ngOnInit(): void {
    const abo = nachladeStrom(() => this.service.laden(!this.erstes), {
      sofort: true,
      aufhoerenBei: ohneRechte,
      anstoss$: this.anstoss$,
    }).subscribe((lauf) => {
      this.erstes = false;
      if (lauf.fehler === null) {
        this.stand = lauf.daten;
      } else {
        const status = (lauf.fehler as { status?: number } | null)?.status;
        // Schalter aus oder abgemeldet: nichts zeigen. Sonst bleibt der letzte Stand stehen.
        if (status === 404 || status === 401 || status === 403) {
          this.stand = null;
        }
      }
      this.cdr.markForCheck();
    });
    this.destroyRef.onDestroy(() => abo.unsubscribe());
  }

  /** Nimmt teil und erfüllt die Voraussetzungen. */
  get dabei(): boolean {
    return !!this.stand && this.stand.teilnehmen === true && this.stand.voraussetzungen;
  }

  /** Einmal fragen: laufende Saison, Voraussetzungen erfüllt, noch nie geantwortet. */
  get fragen(): boolean {
    const stand = this.stand;
    if (!stand || !stand.voraussetzungen || !stand.saison) {
      return false;
    }
    return this.frageOffen || !stand.gefragt;
  }

  /** Etwas zu zeigen: die Frage, die eigene Teilnahme oder ein früheres Nein zum Ändern. */
  get sichtbar(): boolean {
    const stand = this.stand;
    if (!stand) {
      return false;
    }
    return this.fragen || this.dabei || this.ruhend || (stand.gefragt && stand.voraussetzungen && !!stand.saison);
  }

  /**
   * Ja gegeben, aber eine Voraussetzung fehlt gerade: nicht in der Rangliste, der
   * Widerruf bleibt trotzdem hier erreichbar.
   */
  get ruhend(): boolean {
    return !!this.stand && this.stand.teilnehmen === true && !this.stand.voraussetzungen;
  }

  /** Gespeichert ist der Anzeigename als Name in der Rangliste (und es gibt einen). */
  get mitAnzeigename(): boolean {
    return !!this.stand && this.stand.mit_anzeigename && !!this.stand.anzeigename;
  }

  /** Der eigene Platz unter den ersten zehn oder darunter. */
  get eigener(): RanglistenPlatz | null {
    const liste = this.stand?.rangliste;
    return liste ? (liste.oben.find((p) => p.ich) ?? liste.eigener) : null;
  }

  doch(): void {
    this.frageOffen = true;
    this.cdr.markForCheck();
  }

  antworten(teilnehmen: boolean): void {
    this.speichern(teilnehmen, false, teilnehmen ? 'Du bist in der Rangliste.' : 'Du bist nicht in der Rangliste.');
  }

  /** Ranglistenname oder Anzeigename; nur auf aktive Wahl der Anzeigename. */
  nameWaehlen(mitAnzeigename: boolean): void {
    if (!this.stand || this.stand.mit_anzeigename === mitAnzeigename) {
      return;
    }
    this.speichern(
      true,
      mitAnzeigename,
      mitAnzeigename ? 'In der Rangliste steht jetzt dein Anzeigename.' : 'In der Rangliste steht jetzt dein Ranglistenname.',
    );
  }

  private speichern(teilnehmen: boolean, mitAnzeigename: boolean, ansage: string): void {
    const stand = this.stand;
    if (!stand || this.speichert) {
      return;
    }
    this.speichert = true;
    this.fehler = false;
    this.ansage = '';
    this.service.antworten(teilnehmen, mitAnzeigename, stand.aktueller_wortlaut.kennung).subscribe({
      next: () => {
        this.speichert = false;
        this.frageOffen = false;
        this.stand = { ...stand, gefragt: true, teilnehmen, mit_anzeigename: teilnehmen && mitAnzeigename };
        this.ansage = ansage;
        this.cdr.detectChanges();
        this.titel?.nativeElement.focus();
        this.anstoss$.next();
      },
      error: () => {
        this.speichert = false;
        this.fehler = true;
        // Die Bindung [checked] hat sich nicht geändert, also setzt Angular den angeklickten
        // Knopf nicht zurück: Sonst sähe die Person eine Wahl, die nicht gespeichert ist.
        this.nameWahlZuruecksetzen();
        this.cdr.markForCheck();
      },
    });
  }

  private nameWahlZuruecksetzen(): void {
    const gespeichert = this.mitAnzeigename ? 'anzeigename' : 'zufall';
    this.nameWahl?.forEach((ref) => (ref.nativeElement.checked = ref.nativeElement.value === gespeichert));
  }
}
