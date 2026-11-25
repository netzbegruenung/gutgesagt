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
import { PruefenAntwort, TEAM_MOTIVE, TeamBeimPruefen, teamMotivBild } from '../shared/einladung/team-einladung';
import { ROUTES } from '../shared/constants/app.constants';
import { sitzungPruefen } from '../auth/sitzung';
import { FunktionenService } from '../services/funktionen.service';
import { teamBegruessungSaetze, teamBegruessungTitel } from '../shared/team-texte';
import { TeamMerker, teamMerkerAblegen, teamMerkerLesen, teamMerkerLoeschen, teamMerkerNehmen } from './team-merker';

/**
 * Stände der Seite. Ohne Konto: eingeben … gesendet, bei einer Einladung mit Team mit dem
 * Kasten über dem Formular. Angemeldet (Teams): team_frage → tritt_bei → beigetreten oder
 * beitritt_fehler; ohne_team nach „Nein“; schon_konto bei einer Einladung ohne Team;
 * angekommen nach dem Rücksprung, wenn der Link inzwischen aufgebraucht ist.
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
  | 'angekommen';
/** Warum Einloesen scheiterte, nach dem Status der Antwort (api/v1/einladungen.py). */
type Fehler = 'adresse' | 'name' | 'zu_oft' | 'nicht_eingerichtet' | 'unbekannt';
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
  angekommen: '',
};

/** 422 wegen des Namens statt der Adresse: FastAPI nennt das Feld in detail[].loc. */
function fehlerBei422(e: HttpErrorResponse): Fehler {
  const details: unknown = e.error?.detail;
  const felder = Array.isArray(details) ? details.flatMap((d) => (Array.isArray(d?.loc) ? d.loc : [])) : [];
  return felder.includes('vorname') || felder.includes('nachname') ? 'name' : 'adresse';
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

  /** Begrüßung und Sätze vor der Frage, Wortlaut aus shared/team-texte (Rechtstext). */
  begruessungTitel(team: TeamBeimPruefen): string {
    return teamBegruessungTitel(team.name, team.naechste_nummer);
  }

  begruessungSaetze(team: TeamBeimPruefen): readonly string[] {
    return teamBegruessungSaetze(team.name);
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
      if (!antwort.einloesbar) {
        // Nach „Ja“ beim Anlegen kann der Link inzwischen aufgebraucht sein, etwa ein persönlicher.
        this.stand = merker?.kennung ? 'angekommen' : 'ungueltig';
        return;
      }
      this.team = antwort.team;
      if (!angemeldet) {
        this.stand = 'formular';
      } else if (this.team) {
        this.angemeldetMitTeam(this.team, merker);
      } else {
        this.angemeldetOhneTeam();
      }
    });
  }

  private angemeldetMitTeam(team: TeamBeimPruefen, merker: TeamMerker | null) {
    if (team.eigene_nummer !== null && team.eigene_nummer !== undefined) {
      // Mit Merker: gerade beim Anlegen des Kontos beigetreten; sonst schon länger dabei.
      this.beitritt = { name: team.name, motiv: team.motiv, nummer: team.eigene_nummer, neu: !!merker?.kennung };
      this.stand = 'beigetreten';
      return;
    }
    if (merker?.kennung && merker.kennung === team.einwilligung_kennung) {
      // „Ja“ zu genau diesem Wortlaut kam schon beim Einlösen, aber zur Adresse gab es schon
      // ein Konto: Dann entstand dort keine Mitgliedschaft, sie entsteht jetzt.
      this.beitretenSenden(merker.oeffentlich && !!team.oeffentlich_kennung);
      return;
    }
    this.stand = 'team_frage';
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
    if (antwort === 'ja') {
      this.beitretenSenden(this.teamOeffentlich && !!this.team?.oeffentlich_kennung);
    } else {
      this.ueberschriftFokussieren = true;
      this.stand = 'ohne_team';
    }
  }

  /** Nach einem Fehler beim Beitreten wieder zur Frage. */
  nochmalFragen() {
    this.stand = this.team ? 'team_frage' : 'schon_konto';
  }

  private beitretenSenden(oeffentlich: boolean) {
    if (this.stand === 'tritt_bei') {
      return;
    }
    this.stand = 'tritt_bei';
    this.einladungService.beitreten(this.code, oeffentlich).subscribe({
      next: (antwort) => {
        this.beitritt = { name: antwort.team.name, motiv: antwort.team.motiv, nummer: antwort.nummer, neu: antwort.neu };
        this.ueberschriftFokussieren = true;
        this.stand = 'beigetreten';
      },
      error: (e: HttpErrorResponse) => {
        this.ueberschriftFokussieren = true;
        if (e.status === 410) {
          this.stand = 'ungueltig';
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
    const oeffentlich = ja && this.teamOeffentlich && !!team?.oeffentlich_kennung;
    const teamAntwort = team ? { einwilligung: ja, oeffentlich } : undefined;
    this.einladungService.einloesen(this.code, email, this.vorname.trim(), this.nachname.trim(), teamAntwort).subscribe({
      next: () => {
        // Für den Rücksprung nach der Mail: nur nach „Ja“, nur Code und Kennung des Wortlauts.
        if (team && ja) {
          teamMerkerAblegen({ code: this.code, kennung: team.einwilligung_kennung, oeffentlich });
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
        this.stand = 'fehler';
      },
    });
  }

  get ansage(): string {
    if (this.stand === 'formular' && this.team && !this.angemeldet) {
      return `Einladung ins Team ${this.team.name} gefunden.`;
    }
    return ANSAGE[this.stand];
  }
}
