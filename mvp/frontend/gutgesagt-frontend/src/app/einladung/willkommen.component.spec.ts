import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { WillkommenComponent } from './willkommen.component';
import { ohneEinwilligungsUmleitung } from '../services/art9-einwilligung.service';
import { ROUTES } from '../shared/constants/app.constants';

describe('WillkommenComponent', () => {
  let fixture: ComponentFixture<WillkommenComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [WillkommenComponent],
      providers: [provideNoopAnimations(), provideRouter([])],
    });
    fixture = TestBed.createComponent(WillkommenComponent);
    fixture.detectChanges();
  });

  function el(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  it('begrüßt mit dem Gewinn, ohne Druck und ohne Versprechen zum Beitragen', () => {
    expect(el().querySelector('h2')?.textContent?.trim()).toBe('Schön, dass du dabei bist');
    const text = el().textContent ?? '';
    expect(text).toContain('gute Antworten');
    expect(text).toContain('Such den Spruch, der dich zuletzt geärgert hat');
    // Suchen geht auch ohne Einwilligung; Beitragen nicht
    expect(text).not.toMatch(/beitragen|schreiben|verfehlt/i);
  });

  it('hat genau einen Hauptknopf „Ersten Spruch suchen“ zur Startseite mit Fokus ins Suchfeld', () => {
    const knoepfe = el().querySelectorAll('a[mat-raised-button], a[mat-stroked-button], button');
    expect(knoepfe.length).toBe(1);
    const knopf = el().querySelector<HTMLAnchorElement>('[data-testid="erster-spruch"]')!;
    expect(knopf.textContent?.trim()).toBe('Ersten Spruch suchen');
    expect(knopf.getAttribute('href')).toBe('/search#suchen');
  });

  it('liegt nicht unter den Seiten ohne Umleitung: Die Einwilligung kommt vorher, wie bisher', () => {
    expect(ohneEinwilligungsUmleitung(ROUTES.WILLKOMMEN)).toBeFalse();
  });
});
