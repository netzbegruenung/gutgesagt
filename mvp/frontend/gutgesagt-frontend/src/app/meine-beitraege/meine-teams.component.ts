import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  DestroyRef,
  ElementRef,
  Injectable,
  Injector,
  OnInit,
  ViewChild,
  afterNextRender,
  inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatSlideToggleChange, MatSlideToggleModule } from '@angular/material/slide-toggle';
import { RouterLink } from '@angular/router';
import { Subject } from 'rxjs';
import { filter } from 'rxjs/operators';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { MeinTeam, MeineTeams, TeamsService } from '../services/teams.service';
import { AUS_NACHLADEN_MS, NACHLADEN_MS, nachladeStrom, ohneRechte } from '../shared/selbst-nachladen';
import { TeamPilleComponent } from '../shared/teams/team-pille.component';
import {
  MEINE_TEAMS_TITEL,
  TEAM_ERSTE_WOCHE,
  TEAM_LIVE_HINWEIS,
  TEAM_LIVE_HINWEIS_MEHR,
  TEAM_LIVE_LAEUFT_NOCH,
  TEAM_LIVE_STUNDE_LAEUFT_NOCH,
  TEAM_VERLASSEN,
  TEAM_WAECHST_NOCH,
  teamLiveMitglieder,
  teamLiveTag,
  teamQuestGeschafft,
  teamQuestStufe,
  teamQuestZiel,
  teamWocheTitel,
  wocheVorBeitritt,
} from '../shared/team-texte';
import {
  BestaetigungsDialogComponent,
  BestaetigungsDialogDaten,
} from '../shared/components/bestaetigungs-dialog/bestaetigungs-dialog.component';

/**
 * Für welche Teams der Hinweis an Bestandsmitglieder (team_live) in dieser Sitzung der App
 * schon stand: nur im Arbeitsspeicher, nichts auf dem Gerät (ein Merker im Speicher des
 * Geräts bräuchte eine Prüfung nach § 25 TDDDG und einen Absatz in der Erklärung).
 */
@Injectable({ providedIn: 'root' })
export class TeamLiveHinweisMerker {
  private readonly gezeigt = new Set<string>();

  /** True beim ersten Mal je Team und Sitzung (und merkt es). */
  erstmals(teamId: string): boolean {
    if (this.gezeigt.has(teamId)) {
      return false;
    }
    this.gezeigt.add(teamId);
    return true;
  }
}

/** Die Rückfrage vor „Team verlassen“: endgültig, die Nummer wird nicht neu vergeben. */
export function verlassenFrage(team: MeinTeam): BestaetigungsDialogDaten {
  return {
    titel: `Team ${team.team_name} verlassen?`,
    text:
      `Wir löschen sofort, dass du im Team ${team.team_name} (Saison ${team.saison}) bist, samt deiner Nr. ${team.nummer}. ` +
      'Die Nummer vergeben wir nicht neu. Damit widerrufst du deine Einwilligung für dieses Team.',
    ja: TEAM_VERLASSEN,
    nein: 'Abbrechen',
    warnung: true,
  };
}

/**
 * „Meine Teams“ in „Meine Beiträge“, unter den Meilensteinen (Glossar „Team“): die
 * eigenen Teams als Medaillon-Pillen mit Motiv, Name, „Nr. N“ und Saison; die der
 * aktuellen Saison oben, vergangene Saisons darunter als Abzeichen. Sichtbar nur für die
 * Person selbst; je Team „Team verlassen“ (mit Rückfrage, löscht sofort).
 *
 * Wirkt der Schalter teams_oeffentlich, steht darunter der Umschalter „Öffentlich am Namen
 * zeigen“ mit dem Wortlaut der Einwilligung davor; sonst fehlt er. Ist der Schalter teams
 * aus, stehen die eigenen Teams weiter da, mit „Team verlassen“ (Widerruf so leicht wie die
 * Einwilligung); ohne eigene Teams (`teams: []`, `teams_aktiv: false`) fehlt die Karte. Die
 * Karte lädt selbst nach, auch nach jeder Handlung; ohne Schalter und ohne eigene Teams nur
 * alle AUS_NACHLADEN_MS.
 *
 * Unter einem Team der aktuellen Saison steht, was der Server dazu liefert: der
 * Team-Fortschritt der letzten abgeschlossenen Woche (nur gerundet, unter 5 Mitgliedern
 * „Euer Team wächst noch …“) und die Team-Quest (Ziel der Woche ohne Stand, nach
 * Wochenende nur „geschafft“). Ohne die Schalter fehlen beide.
 *
 * Mit dem Schalter team_live (Jura-Akte 28.11.2026) steht in Teams ab 20 Mitgliedern
 * daneben der Stand des Tages, etwa „Heute bis 14 Uhr: rund 80“, die Zahl der Mitglieder
 * und die Quest in Dritteln, alles vom Server vorberechnet. Wer vor dem Einschalten
 * eingewilligt hat, sieht dazu einmal je Sitzung den Hinweis aus der Akte.
 */
@Component({
  selector: 'app-meine-teams',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatDialogModule, MatSlideToggleModule, RouterLink, TeamPilleComponent],
  templateUrl: './meine-teams.component.html',
  styleUrls: ['./meine-teams.component.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MeineTeamsComponent implements OnInit {
  /** null: (noch) nichts zu zeigen, etwa Schalter aus oder nicht angemeldet. */
  stand: MeineTeams | null = null;
  /** Eine Handlung läuft (verlassen oder umschalten). */
  laeuft = false;
  fehler: string | null = null;
  /** Ansage nach einer Handlung, für Screenreader (role="status"). */
  ansage = '';
  readonly titel = MEINE_TEAMS_TITEL;
  readonly verlassenText = TEAM_VERLASSEN;
  readonly waechstNoch = TEAM_WAECHST_NOCH;
  readonly questGeschafft = teamQuestGeschafft;
  readonly wocheTitel = teamWocheTitel;
  readonly questZiel = teamQuestZiel;
  readonly ersteWoche = TEAM_ERSTE_WOCHE;
  readonly liveTag = teamLiveTag;
  readonly liveLaeuftNoch = TEAM_LIVE_LAEUFT_NOCH;
  readonly liveStundeLaeuftNoch = TEAM_LIVE_STUNDE_LAEUFT_NOCH;
  readonly liveMitglieder = teamLiveMitglieder;
  readonly questStufe = teamQuestStufe;
  readonly liveHinweis = TEAM_LIVE_HINWEIS;
  readonly liveHinweisMehr = TEAM_LIVE_HINWEIS_MEHR;
  /** Teams, unter denen in dieser Karte der Hinweis an Bestandsmitglieder steht. */
  readonly hinweisFuer = new Set<string>();

  private readonly teamsService = inject(TeamsService);
  private readonly dialog = inject(MatDialog);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly destroyRef = inject(DestroyRef);
  private readonly injector = inject(Injector);
  private readonly hinweisMerker = inject(TeamLiveHinweisMerker);
  /** Ziel des Fokus, nachdem ein Team verlassen ist: Knopf und Eintrag sind dann weg (WCAG 2.4.3). */
  @ViewChild('titelElement') private titelElement?: ElementRef<HTMLElement>;
  private readonly anstoss$ = new Subject<void>();
  private erstes = true;

  ngOnInit(): void {
    const abo = nachladeStrom(() => this.teamsService.meine(!this.erstes), {
      sofort: true,
      ms: () => (this.stand?.teams_aktiv === false && this.stand.teams.length === 0 ? AUS_NACHLADEN_MS : NACHLADEN_MS),
      aufhoerenBei: ohneRechte,
      anstoss$: this.anstoss$,
    }).subscribe((lauf) => {
      this.erstes = false;
      if (lauf.fehler === null) {
        this.stand = lauf.daten;
        this.hinweiseMerken(lauf.daten);
      } else {
        const status = (lauf.fehler as { status?: number } | null)?.status;
        // Schalter aus (älteres Backend: 404) oder abgemeldet: keine Karte. Sonst bleibt der letzte Stand stehen.
        if (status === 404 || status === 401 || status === 403) {
          this.stand = null;
        }
      }
      this.cdr.markForCheck();
    });
    this.destroyRef.onDestroy(() => abo.unsubscribe());
  }

  /**
   * Der Hinweis an Bestandsmitglieder steht unter einem Live-Team, sobald der Server ihn
   * meldet, einmal je Sitzung; in dieser Karte bleibt er stehen, bis sie geschlossen wird.
   */
  private hinweiseMerken(stand: MeineTeams | null): void {
    for (const team of stand?.teams ?? []) {
      if (team.aktuelle_saison && team.live?.hinweis_neu && this.hinweisMerker.erstmals(team.id)) {
        this.hinweisFuer.add(team.id);
      }
    }
  }

  /** Die Woche ab ``montag`` endete vor dem eigenen Beitritt: dann „Eure erste gemeinsame Woche läuft.“ */
  vorBeitritt(montag: string, team: MeinTeam): boolean {
    return wocheVorBeitritt(montag, team.eingetreten_am);
  }

  /**
   * Die Woche vor der Quest-Woche ``montag`` endete vor dem eigenen Beitritt: dann kein
   * „Euer Wochenziel letzte Woche ist geschafft“ aus der Zeit vor einem selbst.
   */
  vorigeVorBeitritt(montag: string | null, team: MeinTeam): boolean {
    const teile = /^(\d{4})-(\d{2})-(\d{2})$/.exec(montag ?? '');
    if (!teile) {
      return false;
    }
    const vorige = new Date(Date.UTC(+teile[1], +teile[2] - 1, +teile[3] - 7)).toISOString().slice(0, 10);
    return wocheVorBeitritt(vorige, team.eingetreten_am);
  }

  /** Bei Schalter teams aus nur mit eigenen Teams, etwa nachdem das letzte verlassen wurde. */
  get sichtbar(): boolean {
    return !!this.stand && (this.stand.teams_aktiv !== false || this.stand.teams.length > 0);
  }

  get aktuelle(): MeinTeam[] {
    return this.stand?.teams.filter((t) => t.aktuelle_saison) ?? [];
  }

  get vergangene(): MeinTeam[] {
    return this.stand?.teams.filter((t) => !t.aktuelle_saison) ?? [];
  }

  /** Andere Angemeldete sehen die Teams der aktuellen Saison am Namen. */
  get oeffentlich(): boolean {
    return this.stand?.oeffentlich_verfuegbar === true && this.stand.oeffentlich_zeigen === true;
  }

  verlassen(team: MeinTeam): void {
    if (this.laeuft) {
      return;
    }
    this.dialog
      .open(BestaetigungsDialogComponent, { data: verlassenFrage(team), autoFocus: 'dialog' })
      .afterClosed()
      .pipe(filter((ja) => ja === true))
      .subscribe(() => {
        this.laeuft = true;
        this.fehler = null;
        this.cdr.markForCheck();
        this.teamsService.verlassen(team.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
          next: () => {
            this.laeuft = false;
            if (this.stand) {
              this.stand = { ...this.stand, teams: this.stand.teams.filter((t) => t.id !== team.id) };
            }
            this.ansage = `Team ${team.team_name} verlassen. Der Eintrag ist gelöscht.`;
            this.cdr.markForCheck();
            // Der Knopf, der den Fokus hatte, ist mit dem Eintrag verschwunden; sonst fiele
            // der Fokus auf <body>. Fehlt die ganze Karte (letztes Team, Schalter aus), bleibt er.
            // Nur wenn der Fokus verloren ist: Hat die Person ihn inzwischen woanders hin gesetzt, bleibt er dort.
            afterNextRender(
              () => {
                if (!document.activeElement || document.activeElement === document.body) {
                  this.titelElement?.nativeElement.focus();
                }
              },
              { injector: this.injector },
            );
            this.anstoss$.next();
          },
          error: (fehler: { status?: number }) => {
            this.laeuft = false;
            // 404: schon weg (etwa in einem anderen Fenster verlassen); der Stand lädt nach.
            this.fehler = fehler?.status === 404 ? null : 'Das Team ließ sich gerade nicht verlassen. Bitte versuch es noch einmal.';
            this.cdr.markForCheck();
            this.anstoss$.next();
          },
        });
      });
  }

  oeffentlichSchalten(ereignis: MatSlideToggleChange): void {
    const stand = this.stand;
    if (!stand?.oeffentlich_kennung || this.laeuft) {
      ereignis.source.checked = this.oeffentlich;
      return;
    }
    const zeigen = ereignis.checked;
    this.laeuft = true;
    this.fehler = null;
    this.teamsService.oeffentlich(zeigen, stand.oeffentlich_kennung).subscribe({
      next: () => {
        this.laeuft = false;
        this.stand = { ...stand, oeffentlich_zeigen: zeigen };
        this.ansage = zeigen
          ? 'Deine Teams der aktuellen Saison stehen jetzt an deinem Namen.'
          : 'Deine Teams stehen nicht mehr an deinem Namen.';
        this.cdr.markForCheck();
        this.anstoss$.next();
      },
      error: () => {
        this.laeuft = false;
        ereignis.source.checked = this.oeffentlich;
        this.fehler = 'Das hat nicht geklappt. Bitte versuch es noch einmal.';
        this.cdr.markForCheck();
        this.anstoss$.next();
      },
    });
  }

  /** JJJJ-MM-TT als TT.MM.JJJJ, ohne Umweg über Date und Zeitzone. */
  tag(iso: string): string {
    const [jahr, monat, tag] = iso.split('-');
    return `${tag}.${monat}.${jahr}`;
  }
}
