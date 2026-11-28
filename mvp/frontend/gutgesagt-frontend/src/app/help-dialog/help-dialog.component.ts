import { AfterViewInit, Component, DestroyRef, ElementRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NgFor } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialog, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatDividerModule } from '@angular/material/divider';
import { MatIconModule } from '@angular/material/icon';
import { NavigationEnd, Router, RouterModule } from '@angular/router';
import { combineLatest } from 'rxjs';
import { filter, map } from 'rxjs/operators';
import { CONTENT_TYPE_REGISTRY } from '../shared/content-type-registry';
import { ERFUNDENES_MELDEN, NICHT_JEDE_AUSSAGE, SCHREIBREGELN, SELBST_PRUEFEN } from '../shared/schreibregeln';
import { KEINE_GENERATIVE_KI, SUCHE_MIT_SPRACHMODELLEN } from '../shared/ki-saetze';
import { feedbackDialogOeffnen } from '../shared/feedback/feedback-dialog.component';
import { AuthService } from '../auth/auth.service';
import { Art9EinwilligungService } from '../services/art9-einwilligung.service';
import { RundgangService } from '../rundgang/rundgang.service';
import { AppInstallierenService } from '../rundgang/app-installieren.service';
import { RundgangId, rundgangBeschriftung } from '../rundgang/rundgang-daten';
import { SiegelComponent } from '../shared/components/siegel/siegel.component';
import { FunktionenService } from '../services/funktionen.service';
import { EINLADUNG_EINLOESEN, EINLADUNG_PFAD } from '../shared/einladung/einladung-weg';

/**
 * Rueckkehrziel-Parameter: Nach der Anmeldung aus der Hilfe oeffnet die App sie wieder.
 * Seit Selbst beitragen ohne Konto als Bildergeschichte laeuft (17.11.), setzt die App ihn
 * selbst nicht mehr; Adressen, die ihn noch tragen, wirken weiter.
 */
export const HILFE_PARAM = 'hilfe';

/** Abschnitt „Mitmachen“: wie man ein Konto bekommt (Ziel der Startseite für Abgemeldete). */
export const HILFE_MITMACHEN = 'mitmachen';

/**
 * Während der BDK (Einstellungen bdk_hinweis_von/-bis, Paket k_begruessung; GET
 * /api/v1/funktionen meldet „bdk_hinweis“): wo es einen Einladungslink gibt. Aushänge und
 * Plakate nennt der Satz nicht, deren Erlaubnis ist offen (Sebastian 28.11.).
 */
export const BDK_EINLADUNG_HINWEIS =
  'Während der BDK (4.–6. Dezember): Einen Einladungslink bekommst du am Stand der Netzbegrünung im CityCube.';

/** Was die Hilfe beim Öffnen anspringt: die id eines Abschnitts mit Überschrift. */
export interface HilfeDaten {
  abschnitt?: string;
}

@Component({
  selector: 'app-help-dialog',
  standalone: true,
  imports: [
    MatDialogModule,
    MatButtonModule,
    MatDividerModule,
    MatIconModule,
    RouterModule,
    NgFor,
    SiegelComponent
  ],
  templateUrl: './help-dialog.component.html',
  styleUrls: ['../rundgang/rundgang-knoepfe.css', './help-dialog.component.css']
})
export class HelpDialogComponent implements AfterViewInit {
  readonly typen = (['commentary', 'generictext', 'image', 'post'] as const).map((key) => ({
    ...CONTENT_TYPE_REGISTRY[key],
    artikel: key === 'generictext' ? 'eine' : 'ein',
  }));

  // Dieselben Saetze wie in der Formularhilfe
  readonly schreibregeln = SCHREIBREGELN;
  readonly selbstPruefen = SELBST_PRUEFEN;
  readonly nichtJedeAussage = NICHT_JEDE_AUSSAGE;
  readonly erfundenesMelden = ERFUNDENES_MELDEN;
  readonly keineGenerativeKi = KEINE_GENERATIVE_KI;
  readonly sucheMitSprachmodellen = SUCHE_MIT_SPRACHMODELLEN;

  readonly antwortFinden = rundgangBeschriftung('antwort-finden');
  readonly angemeldet = !!inject(AuthService).getUserInfo()?.isAuthenticated;
  /** Ohne Konto: „Selbst beitragen (3 Bilder)“, die Bildergeschichte statt der echten Oberfläche. */
  readonly selbstBeitragen = rundgangBeschriftung('mitmachen', this.angemeldet);

  private readonly rundgang = inject(RundgangService);
  private readonly dialog = inject(MatDialog);
  /** Derselbe Stand wie im Band: Knopf nur mit Angebot des Browsers, sonst die Anleitung. */
  readonly app = inject(AppInstallierenService);
  private readonly host: ElementRef<HTMLElement> = inject(ElementRef);
  private readonly daten = inject<HilfeDaten | null>(MAT_DIALOG_DATA, { optional: true });
  readonly bdkHinweis = BDK_EINLADUNG_HINWEIS;
  readonly einladungPfad = EINLADUNG_PFAD;
  readonly einladungEinloesen = EINLADUNG_EINLOESEN;
  readonly bdkHinweisAn = inject(FunktionenService).an('bdk_hinweis');

  constructor(
    private dialogRef: MatDialogRef<HelpDialogComponent>,
    private router: Router
  ) {}

  /** Mit Abschnitt geöffnet: dorthin scrollen, Fokus auf seine Überschrift (WCAG 2.4.3). */
  ngAfterViewInit(): void {
    const abschnitt = this.daten?.abschnitt;
    if (!abschnitt) {
      return;
    }
    // Erst nach dem Öffnen: Material setzt den Fokus beim Öffnen auf den Dialog
    this.dialogRef.afterOpened?.().subscribe(() => this.abschnittZeigen(abschnitt));
  }

  private abschnittZeigen(abschnitt: string): void {
    const ziel = this.host.nativeElement.querySelector<HTMLElement>(`#${CSS.escape(abschnitt)}`);
    const titel = ziel?.querySelector<HTMLElement>('h3[tabindex="-1"]');
    ziel?.scrollIntoView?.({ block: 'start' });
    titel?.focus({ preventScroll: true });
  }

  /**
   * Schliesst erst die Hilfe, dann startet der Rundgang: Sonst holte die Hilfe beim
   * Schliessen den Fokus zurueck auf ihren Knopf, weg von der Sprechblase.
   */
  rundgangStarten(id: RundgangId): void {
    this.dialogRef.afterClosed().subscribe(() => void this.rundgang.starten(id));
    this.dialogRef.close();
  }

  /**
   * Links aus der Hilfe auf die Über-Seite, auch mit Anker (/about#siegel, /about#technik).
   * Wie früher „Über Gut gesagt“: erst schliessen, dann navigieren. Die Navigation wartet, bis
   * die Hilfe zu ist, denn beim Schliessen stellt der Dialog die alte Scrollposition wieder her
   * und hebt sonst den Sprung zum Anker auf. Mit Strg/Cmd/Umschalt öffnet der Browser das href.
   */
  zuUeber(event: MouseEvent, fragment?: string): void {
    this.schliessenUndHin(event, '/about', fragment);
  }

  /** „Einladung einlösen“ unter „Mitmachen“: wie zuUeber erst schliessen, dann auf /einladung. */
  zurEinladung(event: MouseEvent): void {
    this.schliessenUndHin(event, this.einladungPfad);
  }

  private schliessenUndHin(event: MouseEvent, pfad: string, fragment?: string): void {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    this.dialogRef.afterClosed().subscribe(() => void this.router.navigate([pfad], { fragment }));
    this.dialogRef.close();
  }

  /**
   * Dialog des Browsers; der Abschnitt zeigt danach „schon als App“ oder wieder die Anleitung.
   * Der Knopf ist dann weg: Der Fokus geht auf die Überschrift des Abschnitts statt auf den Dialog.
   */
  async installieren(): Promise<void> {
    await this.app.installieren();
    this.host.nativeElement.querySelector<HTMLElement>('#hilfe-als-app-titel')?.focus();
  }

  /** Feedback über der Hilfe; nach dem Absenden oder Abbrechen ist die Hilfe wieder da. */
  feedbackOeffnen(): void {
    feedbackDialogOeffnen(this.dialog);
  }
}

/**
 * Oeffnet die Hilfe als Seitenleiste rechts in voller Hoehe, 560 px breit; schmaler
 * als 560 px wird daraus ein Vollbild (#512). Fokus auf dem Dialog selbst: Sonst
 * fokussierte Material den ersten Link und scrollte ans Ende. Mit ``abschnitt`` (id, etwa
 * HILFE_MITMACHEN) springt sie gleich zu diesem Abschnitt.
 */
export function hilfeOeffnen(dialog: MatDialog, abschnitt?: string): MatDialogRef<HelpDialogComponent> {
  return dialog.open<HelpDialogComponent, HilfeDaten>(HelpDialogComponent, {
    data: abschnitt ? { abschnitt } : {},
    autoFocus: 'dialog',
    position: { top: '0', right: '0' },
    width: '560px',
    maxWidth: '100vw',
    height: '100%',
    maxHeight: '100%',
    panelClass: 'hilfe-seitenleiste',
  });
}

/**
 * Öffnet die Hilfe wieder, wenn die Anmeldung aus ihr kam (Parameter HILFE_PARAM), und
 * nimmt den Parameter aus der Adresse. Erst, wenn feststeht, wer da ist, und bei
 * Angemeldeten nach der Art.-9-Einwilligung: Sonst läge die Hilfe über deren Seite.
 */
export function hilfeNachAnmeldung(destroyRef: DestroyRef): void {
  const router = inject(Router);
  const dialog = inject(MatDialog);
  const auth = inject(AuthService);
  const einwilligung = inject(Art9EinwilligungService);
  const adresse$ = router.events.pipe(
    filter((e): e is NavigationEnd => e instanceof NavigationEnd),
    map((e) => router.parseUrl(e.urlAfterRedirects)),
  );
  combineLatest([adresse$, auth.userInfo$, einwilligung.geklaert$])
    .pipe(
      filter(([adresse, info, geklaert]) =>
        adresse.queryParamMap.has(HILFE_PARAM) && !!info && (!info.isAuthenticated || geklaert === info.userId),
      ),
      takeUntilDestroyed(destroyRef),
    )
    .subscribe(() => {
      void router.navigate([], { queryParams: { [HILFE_PARAM]: null }, queryParamsHandling: 'merge', replaceUrl: true });
      if (!dialog.openDialogs.some((d) => d.componentInstance instanceof HelpDialogComponent)) hilfeOeffnen(dialog);
    });
}
