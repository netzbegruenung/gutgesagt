import { Component, DestroyRef, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { selbstNachladen } from '../../shared/selbst-nachladen';
import { NachladeHinweisComponent } from '../../shared/components/nachlade-hinweis/nachlade-hinweis.component';
import { FormsModule } from '@angular/forms';
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
import { TeamPilleComponent } from '../../shared/teams/team-pille.component';
import {
  TEAMNAME_HINWEIS,
  TEAM_ARTEN,
  TEAM_GRUPPENNAME_HINWEIS,
  TEAM_GRUPPENNAME_LABEL,
  TEAM_MOTIVE,
  TEAM_ZUSTIMMUNG_LABEL,
  TeamArt,
  TEAM_NAME_MAX,
  TEAM_SAISON_MAX,
  TeamMotiv,
  motivBild,
  teamTextGueltig,
} from '../../shared/teams/teams';

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
  speichert = false;
  kopiert: string | null = null;

  notiz = '';
  erlaubteEinloesungen = 1;
  gueltigBis = inTagen(14);

  /** Schalter teams wirkt (Server): nur dann Teamblock und Spalten Team und Mitglieder. */
  teamsAktiv = false;
  motive: readonly TeamMotiv[] = TEAM_MOTIVE;
  teamnameHinweis = TEAMNAME_HINWEIS;
  teamName = '';
  teamMotiv = TEAM_MOTIVE[0].schluessel;
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
  /** Vorschlag aus der Admin-Einstellung „aktuelle Saison“, bis jemand selbst etwas einträgt. */
  teamSaison = '';
  private saisonVorschlag = '';

  private readonly destroyRef = inject(DestroyRef);

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
      // Nur Motive, deren Bild es gibt: der Name steht immer daneben
      const bekannt = liste.motive.filter((m) => motivBild(m.schluessel) !== null);
      this.motive = bekannt.length ? bekannt : TEAM_MOTIVE;
    }
    this.teamnameHinweis = liste.teamname_hinweis || TEAMNAME_HINWEIS;
    const vorschlag = liste.aktuelle_saison ?? '';
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
    return this.mitTeam && !teamTextGueltig(this.teamSaison, TEAM_SAISON_MAX);
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
      (!this.teamNameUngueltig && !this.teamSaisonUngueltig && !!this.teamMotiv && !this.teamZustimmungFehlt)
    );
  }

  motivBild(schluessel: string): string | null {
    return motivBild(schluessel);
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
    this.einladungService.anlegen(this.notiz.trim(), this.erlaubteEinloesungen, this.gueltigBis, team).subscribe({
      next: (neu) => {
        this.einladungen = [neu, ...(this.einladungen ?? [])];
        this.notiz = '';
        this.teamName = '';
        this.teamArt = 'anlass';
        this.teamZustimmungAm = '';
        this.speichert = false;
      },
      error: () => {
        this.anlegenFehler = true;
        this.speichert = false;
      },
    });
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
