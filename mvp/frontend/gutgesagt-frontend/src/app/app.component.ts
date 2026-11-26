import { Component, DestroyRef, OnDestroy, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';
import { FormsModule } from '@angular/forms';
import { RouterOutlet } from '@angular/router';
import { Router, ActivatedRoute, NavigationEnd } from '@angular/router';
import { NavigationService } from './services/navigation.service';
import { LoggingService } from './services/logging.service';
import { AuthService, UserInfo } from './auth/auth.service';
import { RueckmeldungService } from './services/rueckmeldung.service';
import { Art9EinwilligungService } from './services/art9-einwilligung.service';
import { ProfilbildService } from './services/profilbild.service';
import { rueckkehrzielLesen, rueckkehrzielLoeschen } from './login/rueckkehrziel';
import { hilfeNachAnmeldung } from './help-dialog/help-dialog.component';
import { hinweisNachAnmeldung } from './auth/nach-anmeldung';
import { FooterComponent } from "./footer/footer.component";
import { HauptnavigationComponent } from './shared/components/hauptnavigation/hauptnavigation.component';
import { KontoMenueComponent } from './shared/components/konto-menue/konto-menue.component';
import { MobileHeaderComponent } from './shared/components/mobile-header/mobile-header.component';
import { RouteConfigService } from './shared/services/route-config.service';
import { Subject } from 'rxjs';
import { takeUntil, filter } from 'rxjs/operators';
import { BreakpointObserver, Breakpoints } from '@angular/cdk/layout';
import { PAGE_TITLES, ROUTES } from './shared/constants/app.constants';
import { RundgangComponent } from './rundgang/rundgang.component';
import { RundgangBandComponent } from './rundgang/rundgang-band.component';
import { RundgangService } from './rundgang/rundgang.service';
import { KampagnenwortService } from './shared/kampagnenwort.service';
import { NEU_HINWEIS } from './rundgang/rundgang-daten';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    MatInputModule,
    MatButtonModule,
    MatCardModule,
    MatIconModule,
    MatTooltipModule,
    MatMenuModule,
    FormsModule,
    RouterOutlet,
    FooterComponent,
    MobileHeaderComponent,
    RundgangComponent,
    RundgangBandComponent,
    HauptnavigationComponent,
    KontoMenueComponent,
],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css'],
})
export class AppComponent implements OnInit, OnDestroy {
  title = 'Gut gesagt';
  readonly neuHinweis = NEU_HINWEIS;
  pageTitle: string = 'Gut gesagt';
  showBackButton: boolean = false;
  /** Auf dem Start steht der Skip-Link „Zur Suche“ (#644). */
  aufStart = false;
  /** Auf /login* fehlt der Kopfknopf "Anmelden": Man ist schon da (#645). */
  aufAnmeldeseite = false;
  private destroy$ = new Subject<void>();
  isMobile: boolean = false;
  isTablet: boolean = false;

  /**
   * Am Desktop steht die Marke „Gut gesagt“ im Kopf. Seiten ohne eigenen Titel (Start,
   * Ergebnis, Admin) tragen denselben Namen: Dort nennt die Ueberschrift ihn nur dem
   * Screenreader, statt ihn sichtbar zu wiederholen.
   */
  get titelNurVorgelesen(): boolean {
    return this.pageTitle === PAGE_TITLES.HOME;
  }

  /** Kommt aus dem ProfilbildService: abgeleitet oder selbst gewaehlt (#437). */
  get selectedProfilePictureUrl(): string {
    return this.profilbild.bild();
  }

  userInfo: UserInfo | null = null;

  protected readonly rundgang = inject(RundgangService);
  private readonly kampagnenwort = inject(KampagnenwortService);
  private readonly destroyRef = inject(DestroyRef);

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private authService: AuthService,
    private navigationService: NavigationService,
    private logger: LoggingService,
    private breakpointObserver: BreakpointObserver,
    private routeConfigService: RouteConfigService,
    private rueckmeldung: RueckmeldungService,
    private art9Einwilligung: Art9EinwilligungService,
    private profilbild: ProfilbildService) {
    this.logger.debug('AppComponent created');
    // Nach der Anmeldung aus der Hilfe dorthin zurück; dort startet dann Selbst beitragen
    hilfeNachAnmeldung(this.destroyRef);
    // Nach der Anmeldung zum Abstimmen: ein Satz, dass es jetzt geht
    hinweisNachAnmeldung(this.destroyRef);
  }

  ngOnInit() {
    // Set up responsive breakpoint detection
    this.breakpointObserver.observe([
      '(max-width: 599px)',
      '(min-width: 600px) and (max-width: 959px)'
    ]).pipe(takeUntil(this.destroy$))
      .subscribe(result => {
        this.isMobile = result.breakpoints['(max-width: 599px)'];
        this.isTablet = result.breakpoints['(min-width: 600px) and (max-width: 959px)'];
        this.logger.debug(`Device type - Mobile: ${this.isMobile}, Tablet: ${this.isTablet}`);
      });

    // Subscribe to route changes to update page title
    this.router.events
      .pipe(
        filter(event => event instanceof NavigationEnd),
        takeUntil(this.destroy$)
      )
      .subscribe((event: NavigationEnd) => {
        this.updatePageTitle(event.urlAfterRedirects);
      });

    // Set initial page title
    this.updatePageTitle(this.router.url);

    // Set initial anonymous avatar while checking auth status
    this.profilbild.setzePerson(null);

    // Subscribe to user info changes
    this.authService.userInfo$
      .pipe(takeUntil(this.destroy$))
      .subscribe((userInfo) => {
        this.userInfo = userInfo;
        this.profilbild.setzePerson(userInfo);
      });

    // Willkommen beim ersten Besuch, Mitmachen nach der ersten Anmeldung (#389)
    this.rundgang.beobachten(this.destroyRef);

    // Ankunft mit Kampagnenwort (?k=) melden, einmal je geöffneter Seite (Schalter k_ankuenfte)
    this.kampagnenwort.ankunftMelden();

    // Rueckmeldung beim Anmelden, wie oft die eigenen Beitraege genutzt wurden (#349)
    this.rueckmeldung.starten();

    // Nach dem Anmelden ohne Art.-9-Einwilligung auf /einwilligung (#489)
    this.art9Einwilligung.starten();

    // Try to fetch initial user info but don't redirect on failure
    this.authService.fetchUserInfo()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (userInfo) => {
          this.userInfo = userInfo;
          this.profilbild.setzePerson(userInfo);

          // Besucher bekommen hier 200 mit isAuthenticated = false (keine 401, sitzung.ts).
          // Das Rueckkehrziel gehoert zur Anmeldung und bleibt fuer sie liegen.
          if (!userInfo.isAuthenticated) {
            return;
          }

          // Check if we have a stored return URL from login (including Keycloak)
          const returnUrl = rueckkehrzielLesen();
          if (returnUrl) {
            rueckkehrzielLoeschen();
            // Navigate to the stored URL
            this.router.navigateByUrl(returnUrl);
          }
        },
        error: () => {
          // Set as anonymous user but don't redirect
          this.authService.setUserInfo({
            isAuthenticated: false,
            userId: null,
            userName: null,
            claims: null
          });
          this.profilbild.setzePerson(null);
        },
      });
  }

  navigateToContributeView(): void {
    this.navigationService.navigateToContribute();
  }

  /**
   * Der Pfeil im Desktop-Kopf. Frueher fuehrte er fest auf /search; jetzt eine
   * Ebene hoeher, nach dem Elternziel der Route - dieselbe Methode, die auch der
   * mobile Kopf ruft.
   */
  zurueck(): void {
    this.navigationService.goBack();
  }

  /**
   * Der Haus-Knopf im Desktop-Kopf - wie der Pfeil ueber den NavigationService,
   * damit eine Seite vorher zu Ende bringen kann, was sie angemeldet hat.
   */
  zurStartseite(): void {
    this.navigationService.navigateHome();
  }

  login() {
    // Use current URL as return URL (unless already on login page)
    const currentUrl = this.router.url;
    // Don't set login pages as return URL
    const returnUrl = currentUrl.startsWith('/login') ? '/' : currentUrl;
    this.router.navigate(['/login'], { queryParams: { returnUrl } });
  }

  /** Skip-Link: Fokus ins Suchfeld, ohne die Adresse um #suche zu ergaenzen. */
  zurSuche(event: Event): void {
    event.preventDefault();
    document.getElementById('suche')?.focus();
  }

  private updatePageTitle(url: string): void {
    this.aufStart = url.split(/[?#]/)[0] === '/search';
    const config = this.routeConfigService.getRouteConfig(url);
    this.pageTitle = config.pageTitle;
    this.showBackButton = config.showBackButton;
    this.aufAnmeldeseite = url.split(/[?#]/)[0].startsWith(ROUTES.LOGIN);
    this.logger.debug(`Updated page title to: ${this.pageTitle}, showBackButton: ${this.showBackButton}`);
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
