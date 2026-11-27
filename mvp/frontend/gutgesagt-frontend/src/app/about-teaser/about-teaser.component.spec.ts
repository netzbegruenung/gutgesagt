import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { AboutTeaserComponent } from './about-teaser.component';
import { ORGANISATION } from '../shared/organisation';

describe('AboutTeaserComponent', () => {
  let teaser: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AboutTeaserComponent],
      providers: [provideRouter([])],
    }).compileComponents();
    const fixture = TestBed.createComponent(AboutTeaserComponent);
    fixture.detectChanges();
    teaser = fixture.nativeElement;
  });

  // Startseite zur BDK (27.11.): erst die Traegerin, die Person nur klein darunter
  it('stellt die Netzbegrünung als Trägerin vorn und verlinkt ihre Seite in neuem Tab', () => {
    const titel = teaser.querySelector('h2')!;
    expect(titel.textContent).toContain(`Ein Projekt der ${ORGANISATION.vereinsname}`);
    expect(teaser.querySelector('section')!.getAttribute('aria-labelledby')).toBe(titel.id);

    const verein = teaser.querySelector('.traeger-verein')!;
    expect(verein.textContent).toContain(ORGANISATION.beschreibung);
    const link = verein.querySelector('a')!;
    expect(link.getAttribute('href')).toBe(ORGANISATION.url);
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toContain('noopener');
    expect(link.textContent).toContain('(öffnet in neuem Tab)');
  });

  it('fasst die Über-Seite ohne Widerlegen-Rahmen zusammen und verlinkt sie', () => {
    expect(teaser.querySelector('.teaser-text')!.textContent).toContain('sammelt deshalb gute Antworten');
    expect(teaser.querySelector('.cta-container a')!.getAttribute('href')).toBe('/about');
  });

  it('nennt Sebastian nur klein als Idee und Umsetzung, ohne Bild und ohne Zitat', () => {
    const macher = teaser.querySelector('.macher')!;
    expect(macher.textContent!.replace(/\s+/g, ' ')).toContain('Idee und Umsetzung: Sebastian Banach');
    expect(macher.querySelector('a')!.getAttribute('href')).toBe('/about#menschen');
    expect(macher.previousElementSibling!.classList).toContain('cta-container');
    expect(teaser.querySelector('img')).toBeNull();
    expect(teaser.querySelector('blockquote')).toBeNull();
  });
});
