import { Component, DestroyRef, OnInit, ViewChild, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { selbstNachladen } from '../../shared/selbst-nachladen';
import { NachladeHinweisComponent } from '../../shared/components/nachlade-hinweis/nachlade-hinweis.component';
import { FormsModule, NgForm } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatRadioModule } from '@angular/material/radio';
import {
  EINLADUNG_EINLOESUNGEN_MAX,
  EINLADUNG_NOTIZ_MAX,
  Einladung,
  EinladungListe,
  EinladungService,
  EinladungTeamFelder,
  einladungslink,
} from '../../shared/einladung/einladung.service';
import { MotivAuswahlComponent } from '../../shared/teams/motiv-auswahl.component';
import { TeamPilleComponent } from '../../shared/teams/team-pille.component';
import {
  TEAMNAME_HINWEIS,
  TEAM_ARTEN,
  TEAM_GRUPPENNAME_HINWEIS,
  TEAM_GRUPPENNAME_LABEL,
  TEAM_ZUSTIMMUNG_LABEL,
  TeamArt,
  TEAM_NAME_MAX,
  TEAM_SAISON_MAX,
  TeamMotivEintrag,
  TeamMotivKategorie,
  motivName,
  teamSaisonGueltig,
  teamTextGueltig,
} from '../../shared/teams/teams';

/** Vorauswahl des Motivs: grün, ohne Bedeutung über das Team hinaus. */
const MOTIV_VORSCHLAG = '🌱';

/** Heute plus n Tage als JJJJ-MM-TT, im Kalender des Browsers. */
function inTagen(tage: number, heute = new Date()): string {
  const d = new Date(heute.getFullYear(), heute.getMonth(), heute.getDate() + tage);
  const zwei = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${zwei(d.getMonth() + 1)}-${zwei(d.getDate())}`;
}

/**
 * Einladungen verwalten (#429): anlegen, abschalten, Zaehler sehen. Gruppenlink und
 * persoenlicher Link sind dieselbe Einladung, nur mit anderen Zahlen; der Standard ist
 * der persoenliche (eine Einloesung, zwei Wochen).
 */
@Component({
  selector: 'app-einladungen',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatRadioModule,
    MotivAuswahlComponent,
    NachladeHinweisComponent,
    TeamPilleComponent,
  ],
  templateUrl: './einladungen.component.html',
  styleUrls: ['./einladungen.component.css'],
})
export class EinladungenComponent implements OnInit {
  readonly NOTIZ_MAX = EINLADUNG_NOTIZ_MAX;
  readonly EINLOESUNGEN_MAX = EINLADUNG_EINLOESUNGEN_MAX;
  readonly TEAM_NAME_MAX = TEAM_NAME_MAX;
  readonly TEAM_SAISON_MAX = TEAM_SAISON_MAX;

  einladungen: Einladung[] | null = null;
  einloesenEingerichtet = true;
  fehler = false;
  schaltenFehler = false;
  kopierenFehler = false;
  anlegenFehler = false;
  /** Text des Servers bei 422 (etwa: diese Saison gibt es nicht), sonst null. */
  anlegenFehlerText: string | null = null;
  speichert = false;
  kopiert: string | null = null;

  notiz = '';
  erlaubteEinloesungen = 1;
  gueltigBis = inTagen(14);

  /** Schalter teams wirkt (Server): nur dann Teamblock und Spalten Team und Mitglieder. */
  teamsAktiv = false;
  /** Die feste Emoji-Liste vom Server (domain/team_emoji.py); ohne sie kein Teamlink. */
  motive: readonly TeamMotivEintrag[] = [];
  motivKategorien: readonly TeamMotivKategorie[] = [];
  teamnameHinweis = TEAMNAME_HINWEIS;
  teamName = '';
  /** Vorauswahl, bis die Admin etwas anderes wählt: der Spross, sonst das erste Emoji. */
  teamMotiv = '';
  /** Teamart; Standard „Team nach Anlass, Ort oder Saison“. */
  readonly teamArten = TEAM_ARTEN;
  readonly zustimmungLabel = TEAM_ZUSTIMMUNG_LABEL;
  readonly gruppennameLabel = TEAM_GRUPPENNAME_LABEL;
  readonly gruppennameHinweis = TEAM_GRUPPENNAME_HINWEIS;
  teamArt: TeamArt = 'anlass';
  /** Bei „Team nach Gruppe“ Pflicht: Tag der schriftlichen Zustimmung (JJJJ-MM-TT), nicht in der Zukunft. */
  teamZustimmungAm = '';
  /** Höchstes erlaubtes Datum der Zustimmung: heute nach UTC, wie der Server prüft (heute_utc). */
  get heute(): string {
    return new Date().toISOString().slice(0, 10);
  }
  /**
   * Vorschlag vom Server, bis jemand selbst etwas einträgt: die laufende oder nächste angelegte
   * Saison (Schalter → Saisons), ohne angelegte Saison die Einstellung „Rückfall-Saisonname“.
   */
  teamSaison = '';
  private saisonVorschlag = '';

  private readonly destroyRef = inject(DestroyRef);

  /** Das Formular „Einladung anlegen“: nach dem Anlegen ohne Fehleranzeige zurueckgesetzt. */
  @ViewChild('formular') private formular?: NgForm;

  constructor(private einladungService: EinladungService) {}

  /** Die Liste laedt selbst nach, solange der Reiter sichtbar ist; das Formular bleibt unberuehrt. */
  ngOnInit() {
    this.laden();
    selbstNachladen(() => this.einladungService.liste(true), this.destroyRef, {
      next: (liste) => this.uebernehmen(liste),
      error: () => (this.fehler = true),
    });
  }

  private laden() {
    this.einladungService.liste().subscribe({
      next: (liste) => this.uebernehmen(liste),
      error: () => (this.fehler = true),
    });
  }

  private uebernehmen(liste: EinladungListe) {
    this.einladungen = liste.einladungen;
    this.einloesenEingerichtet = liste.einloesen_eingerichtet;
    this.teamsAktiv = liste.teams_aktiv === true;
    if (liste.motive?.length) {
      this.motive = liste.motive;
      this.motivKategorien = liste.motiv_kategorien ?? [];
      // Eine Wahl bleibt beim Nachladen stehen, solange es sie in der Liste gibt
      if (!this.motive.some((m) => m.schluessel === this.teamMotiv)) {
        this.teamMotiv = this.motivVorschlag;
      }
    }
    this.teamnameHinweis = liste.teamname_hinweis || TEAMNAME_HINWEIS;
    const vorschlag = liste.saison_vorschlag ?? liste.aktuelle_saison ?? '';
    // Das Formular bleibt unberuehrt: nur ein unveraenderter Vorschlag folgt dem Server
    if (this.teamSaison === this.saisonVorschlag) {
      this.teamSaison = vorschlag;
    }
    this.saisonVorschlag = vorschlag;
    this.fehler = false;
  }

  /** Ein Teamname ist eingetragen: dann sind Saison und Motiv Pflicht. */
  get mitTeam(): boolean {
    return this.teamsAktiv && this.teamName.trim().length > 0;
  }

  get teamNameUngueltig(): boolean {
    return this.mitTeam && !teamTextGueltig(this.teamName, TEAM_NAME_MAX);
  }

  get teamSaisonUngueltig(): boolean {
    return this.mitTeam && !teamSaisonGueltig(this.teamSaison, TEAM_SAISON_MAX);
  }

  /** Team nach Gruppe ohne Datum der Zustimmung, oder mit einem Datum in der Zukunft. */
  get teamZustimmungFehlt(): boolean {
    return (
      this.mitTeam &&
      this.teamArt === 'gruppe' &&
      (!/^\d{4}-\d{2}-\d{2}$/.test(this.teamZustimmungAm) || this.teamZustimmungAm > this.heute)
    );
  }

  get kannAnlegen(): boolean {
    if (!this.notiz.trim() || this.speichert) {
      return false;
    }
    return (
      !this.mitTeam ||
      (!this.teamNameUngueltig &&
        !this.teamSaisonUngueltig &&
        this.motive.some((m) => m.schluessel === this.teamMotiv) &&
        !this.teamZustimmungFehlt)
    );
  }

  /** Vorauswahl im Formular: der Spross, wenn es ihn gibt, sonst das erste Emoji. */
  get motivVorschlag(): string {
    return (this.motive.find((m) => m.schluessel === MOTIV_VORSCHLAG) ?? this.motive[0])?.schluessel ?? '';
  }

  /** Name des Motivs einer Einladung in der Liste: vom Server, sonst aus der Liste. */
  motivNameZu(motiv: string | null, name?: string | null): string | null {
    return name ?? this.motive.find((m) => m.schluessel === motiv)?.name ?? motivName(motiv);
  }

  anlegen() {
    if (!this.kannAnlegen) {
      return;
    }
    const team: EinladungTeamFelder | undefined = this.mitTeam
      ? {
          team_name: this.teamName.trim(),
          team_motiv: this.teamMotiv,
          team_saison: this.teamSaison.trim(),
          team_art: this.teamArt,
          ...(this.teamArt === 'gruppe' ? { team_zustimmung_am: this.teamZustimmungAm } : {}),
        }
      : undefined;
    this.speichert = true;
    this.anlegenFehler = false;
    this.anlegenFehlerText = null;
    this.einladungService.anlegen(this.notiz.trim(), this.erlaubteEinloesungen, this.gueltigBis, team).subscribe({
      next: (neu) => {
        this.einladungen = [neu, ...(this.einladungen ?? [])];
        this.speichert = false;
        this.zuruecksetzen();
      },
      error: (fehler: { status?: number; error?: { detail?: unknown } }) => {
        this.anlegenFehler = true;
        // 422 mit Text: etwa eine Saison, die es nicht gibt (Befund 6); der Server sagt, was zu tun ist.
        const detail = fehler?.error?.detail;
        this.anlegenFehlerText = fehler?.status === 422 && typeof detail === 'string' ? detail : null;
        this.speichert = false;
      },
    });
  }

  /**
   * Alles wieder auf Standard (persoenlicher Link, zwei Wochen, Saison-Vorschlag, erstes Motiv).
   * resetForm nimmt auch "abgeschickt" und "beruehrt" zurueck: Sonst stand die geleerte
   * Pflicht-Notiz sofort rot im Fehlerzustand. Felder ohne Steuerelement (Teamblock aus)
   * bekommen den Wert direkt. Ein neues Formularfeld gehoert hier mit hinein: Fehlt es, setzt
   * resetForm es auf null, und kannAnlegen scheitert an null.trim().
   */
  private zuruecksetzen() {
    const standard = {
      notiz: '',
      erlaubteEinloesungen: 1,
      gueltigBis: inTagen(14),
      teamName: '',
      teamArt: 'anlass' as TeamArt,
      teamZustimmungAm: '',
      teamSaison: this.saisonVorschlag,
      teamMotiv: this.motivVorschlag,
    };
    this.formular?.resetForm(standard);
    Object.assign(this, standard);
  }

  schalten(einladung: Einladung) {
    this.schaltenFehler = false;
    this.einladungService.schalten(einladung.id, !einladung.abgeschaltet).subscribe({
      next: (neu) => {
        this.einladungen = (this.einladungen ?? []).map((e) => (e.id === neu.id ? neu : e));
      },
      error: () => (this.schaltenFehler = true),
    });
  }

  link(einladung: Einladung): string {
    return einladungslink(einladung.code);
  }

  /** Der Link in zwei Teilen: Ursprung (gleich in jeder Zeile, wird zuerst gekuerzt) und Pfad mit Code. */
  ursprung(einladung: Einladung): string {
    const link = this.link(einladung);
    return link.slice(0, link.lastIndexOf('/einladung#'));
  }

  pfad(einladung: Einladung): string {
    const link = this.link(einladung);
    return link.slice(link.lastIndexOf('/einladung#'));
  }

  kopieren(einladung: Einladung) {
    this.kopierenFehler = false;
    const kopieren = navigator.clipboard?.writeText(this.link(einladung)) ?? Promise.reject();
    kopieren.then(
      () => (this.kopiert = einladung.id),
      () => (this.kopierenFehler = true),
    );
  }

  /** JJJJ-MM-TT als TT.MM.JJJJ, ohne Umweg ueber Date und Zeitzone. */
  tag(iso: string): string {
    const [jahr, monat, tag] = iso.split('-');
    return `${tag}.${monat}.${jahr}`;
  }
}
