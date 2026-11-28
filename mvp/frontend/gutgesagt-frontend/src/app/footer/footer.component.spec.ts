import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FooterComponent, buildKennung, buildWerteAusSeite } from './footer.component';
import { MatDialogModule } from '@angular/material/dialog';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { signal } from '@angular/core';
import { FunktionenService } from '../services/funktionen.service';
import { LEGAL_ENTITY } from '../shared/legal-entity';
import { of } from 'rxjs';
import paket from '../../../package.json';

describe('FooterComponent', () => {
  let component: FooterComponent;
  let fixture: ComponentFixture<FooterComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        FooterComponent,
        MatDialogModule
      ],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            params: of({}),
            queryParams: of({}),
            snapshot: { params: {}, queryParams: {} }
          }
        }
      ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(FooterComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('nennt Anbieter vor Entwickler, wie das Menue', () => {
    const satz = Array.from(fixture.nativeElement.querySelectorAll('.footer .traeger') as NodeListOf<HTMLElement>)
      .map((span) => span.textContent!.replace(/\s+/g, ' ').trim())
      .find((text) => text.startsWith('Ein Projekt'));

    expect(satz).toBe('Ein Projekt von Netzbegrünung e.V., entwickelt von Sebastian Banach');
  });

  // Design-Audit C2 (#512): Ein "|" hing am Zeilenende, "Nutzungsbedingungen" stand
  // allein in der zweiten Zeile. Jetzt Links oben, Traegerzeile darunter, ohne Striche.
  it('ordnet die Links vor der Traegerzeile, ohne Trennstriche', () => {
    const footer: HTMLElement = fixture.nativeElement.querySelector('.footer');
    const links = Array.from(footer.querySelectorAll('.footer-links > a, .footer-links > button')) as HTMLElement[];

    expect(footer.textContent).not.toContain('|');
    expect(links.map((l) => l.textContent!.trim())).toEqual([
      'Hilfe',
      'Über Gut gesagt',
      'Impressum',
      'Datenschutz',
      'Nutzungsbedingungen',
      'Kontakt',
    ]);
    expect(footer.lastElementChild!.classList).toContain('traeger');
  });

  it('oeffnet die Hilfe ueber einen echten Knopf', () => {
    const hilfe = fixture.nativeElement.querySelector('.help-button') as HTMLElement;
    const oeffnen = spyOn(component, 'openHelpDialog');

    expect(hilfe.tagName).toBe('BUTTON');
    hilfe.click();
    expect(oeffnen).toHaveBeenCalled();
  });

  it('zeigt Version aus package.json und Commit', () => {
    const kennung: HTMLElement = fixture.nativeElement.querySelector('.build-kennung');

    expect(kennung.textContent!.trim()).toMatch(new RegExp(`^v${paket.version.replace(/\./g, '\\.')} · \\S+$`));
  });
});

/** „Kontakt“ im Fuß (Meldeweg, Basisfunktion seit dem Schalter-Umbau 27.11., Name seit dem Rundgang 28.11.). */
describe('FooterComponent - Meldeweg', () => {
  let fixture: ComponentFixture<FooterComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FooterComponent, MatDialogModule],
      providers: [
        provideRouter([]),
        // Alle Schalter aus: der Meldeweg steht trotzdem
        { provide: FunktionenService, useValue: { an: () => signal(false) } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(FooterComponent);
    fixture.detectChanges();
  });

  function linkTexte(): string[] {
    return Array.from(fixture.nativeElement.querySelectorAll('.footer-links > a, .footer-links > button') as NodeListOf<HTMLElement>)
      .map((l) => l.textContent!.trim());
  }

  it('ohne Schalter: „Kontakt“ als letzter Link in der Linkzeile, führt zum Meldeabschnitt im Impressum', () => {
    expect(linkTexte().at(-1)).toBe('Kontakt');
    const link = fixture.nativeElement.querySelector('.footer-links > .melden-link') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe('/impressum#melden');
  });

  it('ohne den Absatz zum Melden (Rundgang 28.11.): nur Links und Trägerzeile, keine Mailadresse', () => {
    expect(fixture.nativeElement.querySelector('.meldeweg')).toBeNull();
    expect(fixture.nativeElement.querySelector('a[href^="mailto:"]')).toBeNull();
    expect(fixture.nativeElement.textContent).not.toContain('Fällt dir ein Beitrag auf');
    expect(fixture.nativeElement.textContent).not.toContain(LEGAL_ENTITY.KONTAKT_MAIL);
    // Die Trägerzeile bleibt die letzte Zeile des Fußes
    expect(fixture.nativeElement.querySelector('.footer').lastElementChild!.classList).toContain('traeger');
  });
});
