import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { environment } from '../../environments/environment';
import { merkerEntfernen } from '../meine-beitraege/meilenstein-merker';
import { kommentarEntwurfLoeschen } from '../beitragsformular/kommentar-entwurf';
import { weggeklicktEntfernen } from '../naechster-schritt/naechster-schritt';
import { BehaviorSubject, Observable, map, tap } from 'rxjs';
import { ANLASS_PARAM, Anmeldeanlass } from './anmeldeanlass';
import { meldetAnmeldung } from './sitzung';

export interface UserInfo {
  isAuthenticated: boolean;
  userId: string | null;
  userName: string | null;
  isAdmin?: boolean;
  claims: { [key: string]: string } | null;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private userInfoSubject = new BehaviorSubject<UserInfo | null>(null);
  userInfo$ = this.userInfoSubject.asObservable()

  constructor(
    private http: HttpClient,
    private router: Router
  ) { }

  /**
   * Zur Login-Auswahl, mit der jetzigen Seite samt Suche (Query) als Rueckkehrziel; vorher
   * ging es danach immer auf die Startseite. Ein Anlass kommt als Parameter ins Ziel,
   * nach der Rueckkehr sagt die App dazu einen Satz (hinweisNachAnmeldung). Auf der
   * Login-Seite selbst bleibt deren Rueckkehrziel, wie bei AppComponent.loginWithReturnUrl.
   */
  login(anlass?: Anmeldeanlass) {
    if (this.router.url.startsWith('/login')) {
      return;
    }
    const hier = this.router.parseUrl(this.router.url);
    if (anlass) {
      hier.queryParams = { ...hier.queryParams, [ANLASS_PARAM]: anlass };
    }
    this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.serializeUrl(hier) } });
  }

  // Gut gesagt managed login with email and password
  loginWithManagedAuth(email: string, password: string): Observable<any> {
    return this.http.post<any>(`${environment.baseUrl}/api/auth/login/managed`, { email, password }, {
      withCredentials: true // Ensure cookies are sent/received
    }).pipe(
      tap((response) => {
        // Use the response data if available, then fetch full user info
        if (response?.userId) {
          // Set temporary user info from login response
          const tempUserInfo: UserInfo = {
            isAuthenticated: true,
            userId: response.userId,
            userName: response.userName || response.displayName,
            claims: null
          };
          this.setUserInfo(tempUserInfo);
        }
        // Fetch complete user info after a short delay to ensure cookie is set
        setTimeout(() => {
          this.fetchUserInfo().subscribe();
        }, 100);
      })
    );
  }

  // Check available authentication modes
  getAuthModes(): Observable<any> {
    return this.http.get<any>(`${environment.baseUrl}/api/auth/modes`);
  }

  logout() {
    // Der Merker der angezeigten Meilensteine gilt nur für diese Anmeldung (#351).
    merkerEntfernen();
    // Der Kommentar-Entwurf im Tab gehört zu dieser Anmeldung (E1).
    kommentarEntwurfLoeschen();
    // Was auf der Karte „Dein nächster Schritt“ weggeklickt ist, gehört zu dieser Anmeldung (#789).
    weggeklicktEntfernen();
    // Use the API logout endpoint which properly handles both Keycloak and managed users
    this.http.post(`${environment.baseUrl}/api/auth/logout`, {}, {
      withCredentials: true
    }).subscribe({
      next: (response: any) => {
        // Clear local user info
        this.setUserInfo({ isAuthenticated: false, userId: null, userName: null, claims: null });

        // Navigate to home or login page
        const redirectUrl = response?.redirectUrl || '/';
        window.location.href = redirectUrl.startsWith('http') ? redirectUrl : `${window.location.origin}${redirectUrl}`;
      },
      error: (err) => {
        console.error('Logout failed:', err);
        // Fallback to clearing user info and redirecting
        this.setUserInfo({ isAuthenticated: false, userId: null, userName: null, claims: null });
        this.router.navigate(['/']);
      }
    });
  }

  /**
   * Fragt das BFF nach der Person. Besucher bekommen 200 mit isAuthenticated = false statt
   * 401 (sitzung.ts); dann liefert und setzt das hier den Besucher, ohne Kennung und Rechte.
   */
  fetchUserInfo(): Observable<UserInfo> {
    return this.http.get<UserInfo>(`${environment.baseUrl}/api/user-info`, {
      withCredentials: true // Ensure cookies are sent
    }).pipe(
      map((userInfo): UserInfo => meldetAnmeldung(userInfo)
        ? userInfo
        : { isAuthenticated: false, userId: null, userName: null, claims: null }),
      tap((userInfo) => this.userInfoSubject.next(userInfo)) // Update user info
    );
  }

  setUserInfo(userInfo: UserInfo) {
    this.userInfoSubject.next(userInfo);
  }

  getUserInfo(): UserInfo | null {
    return this.userInfoSubject.value;
  }

  getCurrentUserId(): string | null {
    const userInfo = this.getUserInfo();
    return userInfo?.userId || null;
  }
}
