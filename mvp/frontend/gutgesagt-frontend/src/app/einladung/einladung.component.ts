import { Component, ElementRef, Injector, OnInit, ViewChild, afterNextRender, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { EINLADUNG_NAME_MAX, EinladungService, nameGueltig } from '../shared/einladung/einladung.service';
import {
  PruefenAntwort,
  TEAM_MOTIVE,
  TeamAntwort,
  TeamBeimPruefen,
  teamMotivBild,
} from '../shared/einladung/team-einladung';
import { ROUTES } from '../shared/constants/app.constants';
import { sitzungPruefen } from '../auth/sitzung';
import { FunktionenService } from '../services/funktionen.service';
import { teamBegruessungSaetze, teamBegruessungTitel, teamDabeiSatz, teamGruppeSatz } from '../shared/team-texte';
import { teamMerkerAblegen, teamMerkerLesen, teamMerkerLoeschen, teamMerkerNehmen } from './team-merker';
import { ERSTER_SPRUCH } from './erster-spruch';
import { EinwilligungsBudgetService } from '../shared/einwilligungs-budget/einwilligungs-budget.service';

/**
 * Stände der Seite. Ohne Konto: eingeben … gesendet, bei einer Einladung mit Team mit dem
 * Kasten über dem Formular. Angemeldet (Teams): team_frage → tritt_bei → beigetreten oder
 * beitritt_fehler; ohne_team nach „Nein“; schon_konto bei einer Einladung ohne Team;
 * kein_team nach dem Rücksprung mit „Ja“, wenn keine Mitgliedschaft entstand (zur Adresse
 * gab es schon ein Konto) und der Link inzwischen nicht mehr gilt.
 */
type Stand =
  | 'eingeben'
  | 'pruefe'
  | 'ungueltig'
  | 'formular'
  | 'sendet'
  | 'gesendet'
  | 'fehler'
  | 'team_frage'
  | 'tritt_bei'
  | 'beigetreten'
  | 'beitritt_fehler'
  | 'ohne_team'
  | 'schon_konto'
  | 'kein_team';
/** Warum Einloesen scheiterte, nach dem Status der Antwort (api/v1/einladungen.py). */
type Fehler = 'adresse' | 'name' | 'wortlaut' | 'zu_oft' | 'nicht_eingerichtet' | 'unbekannt';
/** Warum Beitreten scheiterte, nach dem Status der Antwort von /beitreten. */
type BeitrittFehler = 'zu_oft' | 'abgemeldet' | 'unbekannt';

/** Das Team, in dem die Person jetzt ist, für die Anzeige nach dem Beitreten. */
interface Beitritt {
  name: string;
  motiv: string | null;
  nummer: number;
  neu: boolean;
}

/** Ziel nach dem Anmelden, wenn ein Team mitgetragen wird; der Code steht im Merker, nicht hier. */
export const EINLADUNG_PFAD = '/einladung';

const FEHLER_NACH_STATUS: Record<number, Fehler> = {
  429: 'zu_oft',
  503: 'nicht_eingerichtet',
};

/** Was der Screenreader beim Wechsel des Stands ansagt; die sichtbaren Texte stehen im Template. */
const ANSAGE: Record<Stand, string> = {
  eingeben: '',
  pruefe: 'Einladung wird geprüft …',
  ungueltig: 'Diese Einladung gilt nicht (mehr).',
  formular: '',
  sendet: 'Konto wird angelegt …',
  gesendet: 'Schau in dein Postfach.',
  // Die Fehlertexte stehen mit role="alert" im Template.
  fehler: '',
  team_frage: '',
  tritt_bei: 'Wird gespeichert …',
  // Die Ergebnisse haben eine Überschrift, die nach einer Handlung den Fokus bekommt.
  beigetreten: '',
  beitritt_fehler: '',
  ohne_team: '',
  schon_konto: '',
  kein_team: '',
};

/**
 * 422 wegen des Namens oder eines inzwischen geänderten Wortlauts statt der Adresse: FastAPI
 * nennt das Feld in detail[].loc.
 */
function felderBei422(e: HttpErrorResponse): unknown[] {
  const details: unknown = e.error?.detail;
  return Array.isArray(details) ? details.flatMap((d) => (Array.isArray(d?.loc) ? d.loc : [])) : [];
}

function fehlerBei422(e: HttpErrorResponse): Fehler {
  const felder = felderBei422(e);
  if (felder.includes('team_einwilligung_kennung') || felder.includes('team_oeffentlich_kennung')) {
    return 'wortlaut';
  }
  return felder.includes('vorname') || felder.includes('nachname') ? 'name' : 'adresse';
}

/** 422 beim Beitreten, weil die gezeigte Kennung nicht mehr gilt (neuer Wortlaut). */
function wortlautBeimBeitretenVeraltet(e: HttpErrorResponse): boolean {
  const felder = felderBei422(e);
  return e.status === 422 && (felder.includes('einwilligung_kennung') || felder.includes('oeffentlich_kennung'));
}

/** Zeichen eines Codes: secrets.token_urlsafe im Backend, hoechstens CODE_MAX (api/v1/einladungen.py). */
const CODE_MUSTER = /^[A-Za-z0-9_-]{1,64}$/;

/**
 * Der Code aus dem, was jemand ins Feld einfuegt: der ganze Link (einladungslink) oder nur
 * das Stueck hinter #. Leerraum faellt weg, etwa ein Umbruch beim Kopieren aus einer Mail.
 * Was kein Code sein kann, gibt null; das Backend lehnte es sonst mit 422 ab, und das
 * Formular meldete eine falsche Mail-Adresse.
 */
export function codeAusEingabe(eingabe: string): string | null {
  const ohneLeerraum = eingabe.replace(/\s+/g, '');
  const raute = ohneLeerraum.lastIndexOf('#');
  const code = raute >= 0 ? ohneLeerraum.slice(raute + 1) : ohneLeerraum;
  return CODE_MUSTER.test(code) ? code : null;
}

/**
 * Eine Einladung einloesen (#429): Name und Mail-Adresse eingeben, Gut gesagt legt das
 * Konto an, Keycloak schickt die Mail zum Festlegen des Passworts. Der Name geht gleich
 * ans Konto, sonst fragte Keycloak beim ersten Anmelden danach; der Link in der Mail
 * bestaetigt die Adresse und fuehrt danach in die Anmeldung (einladung-anmelden). Der Code steht hinter #
 * im Link (einladungslink), damit er in keinem Server-Log landet. Ohne Code, etwa ueber
 * „Einladung einlösen“ auf der Login-Seite, fragt die Seite nach dem Link.
 *
 * Teams: Liefert /pruefen ein Team, steht über dem Formular ein Kasten mit Team, Nummer und
 * der Frage, ob das Team gespeichert werden soll („Ja, speichert, dass ich im Team X bin“ /
 * „Nein, ohne Team weiter“, gleichwertig, nichts vorausgewählt). Gespeichert wird es erst
 * mit „Ja“: beim Anlegen des Kontos (team_einwilligung) oder, angemeldet, über /beitreten.
 * Angemeldet gibt es kein Formular. Ohne wirksamen Schalter teams liefert /pruefen kein
 * Team, und die Seite bleibt wie vorher.
 */
@Component({
  selector: 'app-einladung',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatButtonModule,
    MatCardModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatInputModule,
  ],
  templateUrl: './einladung.component.html',
  styleUrls: ['./einladung.component.css'],
})
export class EinladungComponent implements OnInit {
  stand: Stand = 'pruefe';
  fehler: Fehler = 'unbekannt';
  email = '';
  vorname = '';
  nachname = '';
  readonly nameMax = EINLADUNG_NAME_MAX;
  readonly routen = ROUTES;
  /** Nach dem Teamergebnis: Satz und Hauptknopf zur ersten Suche. */
  readonly ersterSpruch = ERSTER_SPRUCH;

  /** Begrüßung und Sätze vor der Frage, Wortlaut aus shared/team-texte (Rechtstext). */
  begruessungTitel(team: TeamBeimPruefen): string {
    return teamBegruessungTitel(team.name, team.naechste_nummer);
  }

  dabeiSatz(team: TeamBeimPruefen): string {
    return teamDabeiSatz(team.mitglieder, team.naechste_nummer);
  }

  begruessungSaetze(team: TeamBeimPruefen): readonly string[] {
    return teamBegruessungSaetze(team.name);
  }

  /** Nur bei einem Team nach Gruppe: der Satz direkt über der Frage, sonst null. */
  gruppeSatz(team: TeamBeimPruefen): string | null {
    return team.art === 'gruppe' ? teamGruppeSatz(team.name) : null;
  }
  /** Der eingefuegte Link, solange die Seite ohne Code aufgerufen wurde. */
  link = '';
  linkFalsch = false;
  private code = '';
  /** Nach „Anderen Link einfügen“: Fokus ins Feld, sobald es wieder da ist; beim ersten Aufruf nicht. */
  private feldFokussieren = false;
  private readonly injector = inject(Injector);
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly funktionen = inject(FunktionenService);

  /** Das Team der Einladung aus /pruefen; null ohne Team oder bei Schalter aus. */
  team: TeamBeimPruefen | null = null;
  angemeldet = false;
  /** Antwort auf die Frage im Kasten; null: noch nicht gewählt (nichts vorausgewählt). */
  teamWahl: 'ja' | 'nein' | null = null;
  /** Zweite Frage „Team öffentlich am Namen zeigen“, Standard nein. */
  teamOeffentlich = false;
  /** Ohne Konto „Konto anlegen“ gedrückt, ohne oben gewählt zu haben. */
  teamWahlFehlt = false;
  beitritt: Beitritt | null = null;
  beitrittFehler: BeitrittFehler = 'unbekannt';
  /**
   * Nach dem Rücksprung mit „Ja“ vom Anlegen, aber ohne Mitgliedschaft (zur Adresse gab es
   * schon ein Konto): Die Frage kommt noch einmal, gespeichert wird erst mit diesem Klick.
   * Nie automatisch: Auf einem geteilten Gerät könnte jemand anderes angemeldet sein.
   */
  nochmalGefragt = false;
  /**
   * Der gezeigte Wortlaut galt beim Absenden nicht mehr (inzwischen neu): Die Seite hat den
   * neuen selbst geholt und fragt noch einmal, gespeichert ist nichts.
   */
  wortlautNeu = false;
  /** Nach einer Handlung: Fokus auf die Überschrift des neuen Stands. */
  private ueberschriftFokussieren = false;

  @ViewChild('linkFeld')
  set linkFeld(feld: ElementRef<HTMLInputElement> | undefined) {
    if (feld && this.feldFokussieren) {
      this.feldFokussieren = false;
      // Erst nach dem Rendern: Fokus mitten in der Change Detection aendert das Formularfeld
      afterNextRender(() => feld.nativeElement.focus(), { injector: this.injector });
    }
  }

  @ViewChild('ueberschrift')
  set ueberschrift(el: ElementRef<HTMLElement> | undefined) {
    if (el && this.ueberschriftFokussieren) {
      this.ueberschriftFokussieren = false;
      afterNextRender(() => el.nativeElement.focus(), { injector: this.injector });
    }
  }

  constructor(
    private route: ActivatedRoute,
    private einladungService: EinladungService,
  ) {}

  ngOnInit() {
    const code = (this.route.snapshot.fragment ?? '').trim();
    if (code) {
      this.pruefen(code);
      return;
    }
    // Rücksprung nach Mail und Anmeldung (einladung-anmelden): der Code aus dem Merker
    const merker = teamMerkerLesen();
    if (merker) {
      this.pruefen(merker.code);
      return;
    }
    this.stand = 'eingeben';
  }

  /** Den eingefuegten Link uebernehmen und weiter wie beim Aufruf ueber den Link. */
  linkUebernehmen() {
    const code = codeAusEingabe(this.link);
    this.linkFalsch = !code;
    if (code) {
      this.pruefen(code);
    }
  }

  /** Nach einer Einladung, die nicht gilt: einen anderen Link einfuegen. */
  andererLink() {
    this.link = '';
    this.linkFalsch = false;
    this.feldFokussieren = true;
    this.stand = 'eingeben';
  }

  private pruefen(code: string) {
    this.code = code;
    this.stand = 'pruefe';
    this.team = null;
    this.teamWahl = null;
    this.teamOeffentlich = false;
    this.nochmalGefragt = false;
    this.wortlautNeu = false;
    forkJoin({
      // Pruefen ist nur Komfort: Im Zweifel das Formular zeigen, Einloesen prueft erneut.
      antwort: this.einladungService.pruefen(code).pipe(catchError(() => of<PruefenAntwort | null>(null))),
      angemeldet: sitzungPruefen(this.http),
    }).subscribe(({ antwort, angemeldet }) => {
      this.angemeldet = angemeldet;
      // Der Merker gilt einmal und nur für diesen Code; ohne Anmeldung bleibt er für den Rücksprung.
      const merker = angemeldet && teamMerkerLesen()?.code === code ? teamMerkerNehmen() : null;
      if (!antwort) {
        this.stand = 'formular';
        return;
      }
      const mitJa = !!merker?.kennung;
      if (!antwort.einloesbar) {
        if (angemeldet && antwort.team && antwort.team.eigene_nummer != null) {
          // Auch nach Ablauf: Ein Mitglied sieht seine Nummer statt „gilt nicht“.
          this.team = antwort.team;
          this.schonImTeam(antwort.team, mitJa);
          return;
        }
        // Nach „Ja“ beim Anlegen, aber ohne Mitgliedschaft, und der Link gilt nicht mehr.
        this.stand = angemeldet && mitJa ? 'kein_team' : 'ungueltig';
        return;
      }
      this.team = antwort.team;
      if (!angemeldet) {
        this.stand = 'formular';
      } else if (this.team) {
        this.angemeldetMitTeam(this.team, mitJa);
      } else {
        this.angemeldetOhneTeam();
      }
    });
  }

  /** Mit Ja beim Anlegen: gerade beim Anlegen des Kontos beigetreten; sonst schon länger dabei. */
  private schonImTeam(team: TeamBeimPruefen, mitJa: boolean) {
    this.beitritt = { name: team.name, motiv: team.motiv, nummer: team.eigene_nummer ?? 0, neu: mitJa };
    this.stand = 'beigetreten';
  }

  private angemeldetMitTeam(team: TeamBeimPruefen, mitJa: boolean) {
    if (team.eigene_nummer !== null && team.eigene_nummer !== undefined) {
      this.schonImTeam(team, mitJa);
      return;
    }
    // „Ja“ beim Einlösen, aber zur Adresse gab es schon ein Konto: Dort entstand keine
    // Mitgliedschaft. Gefragt wird noch einmal; der Merker sendet nie selbst eine Einwilligung.
    this.nochmalGefragt = mitJa;
    this.stand = 'team_frage';
    // Gehört zum Beitreten und kommt immer, verbraucht aber den Besuch (#788).
    this.injector.get(EinwilligungsBudgetService).gezeigt('team');
  }

  /** Angemeldet und eine Einladung ohne Team: Hinweis statt Formular, nur bei wirksamem Schalter teams. */
  private angemeldetOhneTeam() {
    this.funktionen.frisch('teams').subscribe((teamsAn) => (this.stand = teamsAn ? 'schon_konto' : 'formular'));
  }

  /** Einer der beiden gleichwertigen Knöpfe im Kasten. */
  wahl(antwort: 'ja' | 'nein') {
    if (!this.angemeldet) {
      this.teamWahl = antwort;
      this.teamWahlFehlt = false;
      return;
    }
    if (antwort === 'ja' && this.team) {
      this.beitretenSenden(this.teamAntwort(this.team, true));
    } else {
      this.ueberschriftFokussieren = true;
      this.stand = 'ohne_team';
    }
  }

  /** Nach einem Fehler beim Beitreten wieder zur Frage. */
  nochmalFragen() {
    this.stand = this.team ? 'team_frage' : 'schon_konto';
  }

  /** Antwort mit den Kennungen der gezeigten Wortlaute; die zweite Frage nur, wenn sie gestellt wurde. */
  private teamAntwort(team: TeamBeimPruefen, ja: boolean): TeamAntwort {
    return {
      einwilligung: ja,
      einwilligungKennung: team.einwilligung_kennung,
      oeffentlich: ja && this.teamOeffentlich && !!team.oeffentlich_kennung,
      oeffentlichKennung: team.oeffentlich_kennung,
    };
  }

  private beitretenSenden(antwort: TeamAntwort) {
    if (this.stand === 'tritt_bei') {
      return;
    }
    this.stand = 'tritt_bei';
    this.einladungService.beitreten(this.code, antwort).subscribe({
      next: (antwort) => {
        this.beitritt = { name: antwort.team.name, motiv: antwort.team.motiv, nummer: antwort.nummer, neu: antwort.neu };
        this.ueberschriftFokussieren = true;
        this.stand = 'beigetreten';
      },
      error: (e: HttpErrorResponse) => {
        this.ueberschriftFokussieren = true;
        if (e.status === 410) {
          this.stand = 'ungueltig';
        } else if (wortlautBeimBeitretenVeraltet(e)) {
          this.wortlautNeuHolen();
        } else if (e.status === 404 || e.status === 409) {
          // Schalter inzwischen aus oder das Team an der Einladung entfernt
          this.team = null;
          this.stand = 'schon_konto';
        } else {
          this.beitrittFehler = e.status === 429 ? 'zu_oft' : e.status === 401 ? 'abgemeldet' : 'unbekannt';
          this.stand = 'beitritt_fehler';
        }
      },
    });
  }

  /** „Melde dich an“ im Kasten: nur den Code merken, keine Einwilligung; gefragt wird danach. */
  anmeldenUmBeizutreten(): false {
    teamMerkerAblegen({ code: this.code, kennung: null, oeffentlich: false });
    void this.router.navigate([ROUTES.LOGIN], { queryParams: { returnUrl: EINLADUNG_PFAD } });
    return false;
  }

  /**
   * „Melde dich an“ nach dem Senden: Mit „Ja“ liegt der Merker schon; dann zurück auf diese
   * Seite, wo die Frage für das angemeldete Konto noch einmal kommt. Sonst wie bisher.
   */
  anmeldenNachSenden(): false {
    const mitTeam = !!this.team && this.teamWahl === 'ja' && teamMerkerLesen()?.code === this.code;
    void this.router.navigate([ROUTES.LOGIN], mitTeam ? { queryParams: { returnUrl: EINLADUNG_PFAD } } : {});
    return false;
  }

  get motivBild(): string | null {
    return teamMotivBild(this.beitritt?.motiv ?? this.team?.motiv);
  }

  get motivName(): string {
    const motiv = this.beitritt?.motiv ?? this.team?.motiv;
    return (motiv && TEAM_MOTIVE[motiv]) || '';
  }

  /** Kasten mit der Frage: ohne Konto über dem Formular, angemeldet statt des Formulars. */
  get kastenZeigen(): boolean {
    if (!this.team) {
      return false;
    }
    return this.angemeldet
      ? this.stand === 'team_frage' || this.stand === 'tritt_bei'
      : this.stand === 'formular' || this.stand === 'sendet' || this.stand === 'fehler';
  }

  get vollstaendig(): boolean {
    return !!(this.email.trim() && this.vorname.trim() && this.nachname.trim());
  }

  einloesen() {
    const email = this.email.trim();
    if (!this.vollstaendig || this.stand === 'sendet') {
      return;
    }
    if (this.team && this.teamWahl === null) {
      this.teamWahlFehlt = true;
      return;
    }
    if (!nameGueltig(this.vorname) || !nameGueltig(this.nachname)) {
      this.fehler = 'name';
      this.stand = 'fehler';
      return;
    }
    this.stand = 'sendet';
    const team = this.team;
    const ja = !!team && this.teamWahl === 'ja';
    const teamAntwort = team ? this.teamAntwort(team, ja) : undefined;
    this.einladungService.einloesen(this.code, email, this.vorname.trim(), this.nachname.trim(), teamAntwort).subscribe({
      next: () => {
        // Für den Rücksprung nach der Mail: nur nach „Ja“, nur Code und Kennung des Wortlauts.
        if (team && ja) {
          teamMerkerAblegen({ code: this.code, kennung: team.einwilligung_kennung, oeffentlich: !!teamAntwort?.oeffentlich });
        } else {
          teamMerkerLoeschen();
        }
        this.stand = 'gesendet';
      },
      error: (e: HttpErrorResponse) => {
        if (e.status === 410) {
          this.stand = 'ungueltig';
          return;
        }
        this.fehler = e.status === 422 ? fehlerBei422(e) : (FEHLER_NACH_STATUS[e.status] ?? 'unbekannt');
        if (this.fehler === 'wortlaut') {
          this.wortlautNeuHolen();
          return;
        }
        this.stand = 'fehler';
      },
    });
  }

  /** Neuen Wortlaut holen und noch einmal fragen, ohne dass jemand die Seite neu laden muss. */
  private wortlautNeuHolen() {
    this.pruefen(this.code);
    this.wortlautNeu = true;
  }

  get ansage(): string {
    if (this.stand === 'formular' && this.team && !this.angemeldet) {
      return `Einladung ins Team ${this.team.name} gefunden.`;
    }
    return ANSAGE[this.stand];
  }
}
