import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { AufrufeComponent } from './aufrufe.component';
import { environment } from '../../../environments/environment';

const URL = `${environment.baseUrl}/api/v1/aufrufe`;

describe('AufrufeComponent (#761)', () => {
  let fixture: ComponentFixture<AufrufeComponent>;
  let http: HttpTestingController;

  beforeEach(async () => {
    spyOnProperty(document, 'visibilityState', 'get').and.returnValue('hidden');
    await TestBed.configureTestingModule({
      imports: [AufrufeComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(AufrufeComponent);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => {
    fixture.destroy();
    http.verify();
  });

  function el(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  it('zeigt bei ausgeschaltetem Schalter gar nichts', () => {
    http.expectOne(URL).flush({ aktiv: false, heute: null, tage: [] });
    fixture.detectChanges();

    expect(el().querySelector('mat-card')).toBeNull();
  });

  it('zeigt heute zuerst, dann die Tage, Zahlen als Text', () => {
    http.expectOne(URL).flush({
      aktiv: true,
      heute: { tag: '2026-11-22', aufrufe: 1234, besucher: 40 },
      tage: [{ tag: '2026-11-21', aufrufe: 300, besucher: 80 }],
    });
    fixture.detectChanges();

    const zeilen = Array.from(el().querySelectorAll('[data-testid="aufruf-tag"]')) as HTMLElement[];
    expect(zeilen.length).toBe(2);
    expect(zeilen[0].textContent).toContain('Heute bisher');
    expect(zeilen[0].textContent).toContain('1.234');
    expect(zeilen[1].textContent).toContain('21.11.');
    expect(zeilen[1].textContent).toContain('80');
    expect((zeilen[1].querySelector('.balken') as HTMLElement).style.width).toBe('100%');
    expect((zeilen[0].querySelector('.balken') as HTMLElement).style.width).toBe('50%');
  });

  it('sagt, wann die ersten abgeschlossenen Tage kommen', () => {
    http.expectOne(URL).flush({ aktiv: true, heute: { tag: '2026-11-22', aufrufe: 1, besucher: 1 }, tage: [] });
    fixture.detectChanges();

    expect(el().textContent).toContain('ab morgen');
  });
});
