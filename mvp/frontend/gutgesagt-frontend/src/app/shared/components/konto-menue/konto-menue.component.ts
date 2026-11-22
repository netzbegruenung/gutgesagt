import { Component, ViewChild, inject } from '@angular/core';
import { Router } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatMenu, MatMenuModule } from '@angular/material/menu';
import { MatDialog } from '@angular/material/dialog';

import { AuthService } from '../../../auth/auth.service';
import { EINWILLIGUNG_PFAD } from '../../../services/art9-einwilligung.service';
import { profilbildDialogOeffnen } from '../../profilbild/profilbild-dialog.component';
import { DATENSCHUTZ_EINSTELLUNGEN } from '../../fangkorb-texte';

/**
 * Das Profilmenü am Profilbild, Desktop und mobil (Navigation Variante 3, 22.11.2026):
 * nur noch das eigene Konto. Die Ziele (Einwerfen, Fangkorb, Meine Beiträge) stehen
 * sichtbar im Kopf bzw. in der unteren Leiste, Hilfe und Co. unter „Mehr“.
 *
 * Der Auslöser sitzt beim Aufrufer: `<app-konto-menue #konto>` und
 * `[matMenuTriggerFor]="konto.menue"`.
 */
@Component({
  selector: 'app-konto-menue',
  standalone: true,
  imports: [MatIconModule, MatMenuModule],
  template: `
    <mat-menu #menue="matMenu" xPosition="before" class="konto-menue">
      <button mat-menu-item type="button" class="profilmenue-eintrag" (click)="profilbild()">
        <mat-icon aria-hidden="true">face</mat-icon>
        <span>Profilbild wählen</span>
      </button>
      <button mat-menu-item type="button" class="profilmenue-eintrag" (click)="einwilligung()">
        <mat-icon aria-hidden="true">fact_check</mat-icon>
        <span>{{ datenschutzEinstellungen }}</span>
      </button>
      <button mat-menu-item type="button" class="profilmenue-eintrag" (click)="abmelden()">
        <mat-icon aria-hidden="true">logout</mat-icon>
        <span>Abmelden</span>
      </button>
    </mat-menu>
  `,
  styles: [
    `
      :host {
        display: contents;
      }
    `,
  ],
})
export class KontoMenueComponent {
  @ViewChild('menue', { static: true }) menue!: MatMenu;

  readonly datenschutzEinstellungen = DATENSCHUTZ_EINSTELLUNGEN;
  private readonly dialog = inject(MatDialog);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);

  profilbild(): void {
    profilbildDialogOeffnen(this.dialog);
  }

  einwilligung(): void {
    this.router.navigate([EINWILLIGUNG_PFAD]);
  }

  abmelden(): void {
    this.auth.logout();
  }
}
