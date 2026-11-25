import { Injectable } from '@angular/core';
import { CanActivate } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { AuthService } from './auth.service';
import { sitzungPruefen } from './sitzung';

@Injectable({
  providedIn: 'root',
})
export class PublicGuard implements CanActivate {
  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) {}

  canActivate(): Observable<boolean> {
    // Ob angemeldet, steht im Feld der Antwort (sitzung.ts); durch geht es in jedem Fall.
    return sitzungPruefen(this.http).pipe(
      map((angemeldet) => {
        if (angemeldet) {
          this.authService.fetchUserInfo().subscribe();
        } else {
          this.authService.setUserInfo({
            isAuthenticated: false,
            userId: null,
            userName: null,
            claims: null
          });
        }
        return true;
      })
    );
  }
}
