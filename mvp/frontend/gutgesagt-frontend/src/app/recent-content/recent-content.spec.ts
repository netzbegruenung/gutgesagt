import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { BreakpointObserver } from '@angular/cdk/layout';
import { CommonModule } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { of, throwError } from 'rxjs';
import {
  FRISCH_TAGE,
  MOBIL_ANZAHL,
  RecentContentComponent,
  TEASER_ANZAHL,
  ZULETZT_ANZAHL,
  istFrisch,
} from './recent-content.component';
import { ContentRefreshService } from '../services/content-refresh.service';
import { ContentService } from '../services/content.service';
import { LoggingService } from '../services/logging.service';
import { KartenlisteComponent } from '../beitragskarte/kartenliste.component';
import { ResultCarouselComponent } from '../result-carousel/result-carousel.component';
import { BeitragskarteStubComponent } from '../beitragskarte/beitragskarte.stub';
import { By } from '@angular/platform-browser';

describe('RecentContentComponent', () => {
  let component: RecentContentComponent;
  let fixture: ComponentFixture<RecentContentComponent>;
  let contentService: jasmine.SpyObj<ContentService>;
  let mobil: boolean;

  const TAG = 24 * 60 * 60 * 1000;
  /** Vor so vielen Tagen ergaenzt, als Zeitstempel wie von /recent. */
  const vorTagen = (tage: number) => new Date(Date.now() - tage * TAG).toISOString();

  function eintraege(anzahl: number, created: string = vorTagen(1)): any[] {
    return Array.from({ length: anzahl }, (_, i) => ({
      id: `c-${i}`,
      result_type: i % 2 ? 'generictext' : 'commentary',
      content_type: i % 2 ? 'generic_text' : 'commentary',
      title: `Titel ${i}`,
      text: 'Text',
      created,
      references: [],
      usage_count: 0,
    }));
  }

  function erstellen(results: any[] = []): void {
    contentService.getRecentContent.and.returnValue(of({ results, results_count: results.length }));
    fixture = TestBed.createComponent(RecentContentComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  function titel(): string {
    return fixture.nativeElement.querySelector('h2').textContent.trim();
  }

  function text(): string {
    return fixture.nativeElement.textContent;
  }

  function alle(selektor: string): Element[] {
    return Array.from(fixture.nativeElement.querySelectorAll(selektor));
  }

  beforeEach(async () => {
    mobil = false;
    contentService = jasmine.createSpyObj('ContentService', ['getRecentContent']);
    const loggingServiceSpy = jasmine.createSpyObj('LoggingService', ['info', 'error', 'debug', 'warn']);

    await TestBed.configureTestingModule({
      imports: [RecentContentComponent, HttpClientTestingModule],
      providers: [
        { provide: ContentService, useValue: contentService },
        { provide: LoggingService, useValue: loggingServiceSpy },
        { provide: BreakpointObserver, useValue: { observe: () => of({ matches: mobil, breakpoints: {} }) } },
      ]
    })
      .overrideComponent(KartenlisteComponent, { set: { imports: [CommonModule, BeitragskarteStubComponent] } })
      .overrideComponent(ResultCarouselComponent, {
        set: { imports: [CommonModule, MatIconModule, MatTooltipModule, BeitragskarteStubComponent] },
      })
      .compileComponents();
  });

  it('should create', () => {
    erstellen();
    expect(component).toBeTruthy();
  });

  it('laedt fuer den Teaser fuenf Beitraege', () => {
    erstellen();

    expect(TEASER_ANZAHL).toBe(5);
    expect(contentService.getRecentContent).toHaveBeenCalledWith(TEASER_ANZAHL);
  });

  it('baut aus Kommentar und Hintergrundinfo je eine Karte', () => {
    erstellen(eintraege(2));

    expect(component.karten.map((karte) => [karte.id, karte.typ])).toEqual([
      ['c-0', 'commentary'],
      ['c-1', 'generictext'],
    ]);
  });

  it('zeigt mobil eine Liste statt des Karussells', () => {
    mobil = true;
    erstellen(eintraege(3));

    expect(alle('app-kartenliste').length).toBe(1);
    expect(alle('app-result-carousel').length).toBe(0);
    expect(alle('app-beitragskarte').length).toBe(3);
  });

  it('zeigt mobil hoechstens die neuesten drei Karten (#599)', () => {
    mobil = true;
    erstellen(eintraege(5));

    expect(MOBIL_ANZAHL).toBe(3);
    expect(alle('app-beitragskarte').length).toBe(3);
  });

  it('zeigt ab 600 px alle fuenf im Karussell', () => {
    erstellen(eintraege(5));

    expect(alle('app-beitragskarte').length).toBe(5);
  });

  // Startseite 16.11.: ohne "passt auf Mastodon/Bluesky/X" und Alter, nur in diesem Streifen
  it('zeigt die Karten schlank, in der Liste wie im Karussell', () => {
    const schlank = () =>
      fixture.debugElement
        .queryAll(By.directive(BeitragskarteStubComponent))
        .map((karte) => (karte.componentInstance as BeitragskarteStubComponent).schlank);

    erstellen(eintraege(3));
    expect(schlank()).toEqual([true, true, true]);

    mobil = true;
    erstellen(eintraege(3));
    expect(schlank()).toEqual([true, true, true]);
  });

  it('zeigt ab 600 px das Karussell', () => {
    erstellen(eintraege(3));

    expect(alle('app-result-carousel').length).toBe(1);
    expect(alle('app-kartenliste').length).toBe(0);
    expect(alle('app-beitragskarte').length).toBe(3);
  });

  // Entscheidung 26.11.: der Bereich zeigt nie „Noch keine neuen Beiträge.“
  describe('nie leer', () => {
    it('bleibt mit frischen Beitraegen wie bisher: alter Titel, alle fuenf', () => {
      erstellen(eintraege(5));

      expect(component.stand).toBe('frisch');
      expect(titel()).toBe('Frisch aus der Community');
      expect(alle('app-beitragskarte').length).toBe(5);
    });

    it('zaehlt als frisch, sobald einer der Beitraege frisch ist', () => {
      erstellen([...eintraege(1), ...eintraege(4, vorTagen(30)).map((e, i) => ({ ...e, id: `alt-${i}` }))]);

      expect(titel()).toBe('Frisch aus der Community');
      expect(alle('app-beitragskarte').length).toBe(5);
    });

    it('zeigt ohne Frisches die letzten drei als „Zuletzt ergänzt“', () => {
      erstellen(eintraege(5, vorTagen(FRISCH_TAGE + 1)));

      expect(component.stand).toBe('zuletzt');
      expect(titel()).toBe('Zuletzt ergänzt');
      expect(ZULETZT_ANZAHL).toBe(3);
      expect(component.karten.map((karte) => karte.id)).toEqual(['c-0', 'c-1', 'c-2']);
      expect(alle('app-beitragskarte').length).toBe(3);
      expect(text()).not.toContain('Noch keine');
      expect(alle('.empty-state').length).toBe(0);
    });

    it('zeigt auch mobil hoechstens drei zuletzt ergaenzte', () => {
      mobil = true;
      erstellen(eintraege(5, vorTagen(60)));

      expect(titel()).toBe('Zuletzt ergänzt');
      expect(alle('app-beitragskarte').length).toBe(3);
    });

    it('zeigt ganz ohne Beitraege einen Anfang statt eines Misserfolgs', () => {
      erstellen([]);

      expect(component.stand).toBe('anfang');
      expect(titel()).toBe('Frisch aus der Community');
      expect(text()).toContain('Hier wächst bald was');
      expect(text()).not.toContain('Noch keine');
      expect(text()).toContain('Fang an');
      expect(alle('app-beitragskarte').length).toBe(0);
    });

    it('zeigt den Anfang nicht waehrend des Ladens oder bei einem Fehler', () => {
      erstellen([]);
      component.loading = true;
      fixture.detectChanges();
      expect(alle('.empty-state').length).toBe(0);

      component.loading = false;
      component.error = 'kaputt';
      fixture.detectChanges();
      expect(alle('.empty-state').length).toBe(0);
    });

    it('zeigt bei einem Fehler nach dem Nachladen wieder den alten Titel', () => {
      erstellen(eintraege(3, vorTagen(30)));
      expect(titel()).toBe('Zuletzt ergänzt');

      contentService.getRecentContent.and.returnValue(throwError(() => new Error('weg')));
      TestBed.inject(ContentRefreshService).triggerRefresh();
      fixture.detectChanges();

      expect(component.error).toBeTruthy();
      expect(titel()).toBe('Frisch aus der Community');
      expect(alle('.empty-state').length).toBe(0);
    });

    it('wechselt nach dem Nachladen ohne Neuladen der Seite', () => {
      erstellen([]);
      expect(component.stand).toBe('anfang');

      contentService.getRecentContent.and.returnValue(of({ results: eintraege(2), results_count: 2 }));
      TestBed.inject(ContentRefreshService).triggerRefresh();
      fixture.detectChanges();

      expect(titel()).toBe('Frisch aus der Community');
      expect(alle('.empty-state').length).toBe(0);
      expect(alle('app-beitragskarte').length).toBe(2);

      contentService.getRecentContent.and.returnValue(
        of({ results: eintraege(4, vorTagen(20)), results_count: 4 }),
      );
      TestBed.inject(ContentRefreshService).triggerRefresh();
      fixture.detectChanges();

      expect(titel()).toBe('Zuletzt ergänzt');
      expect(alle('app-beitragskarte').length).toBe(3);
    });
  });
});

describe('istFrisch', () => {
  const jetzt = Date.parse('2026-11-26T12:00:00Z');

  it('gilt bis einschliesslich sieben Tage', () => {
    expect(istFrisch('2026-11-19T12:00:00Z', jetzt)).toBeTrue();
    expect(istFrisch('2026-11-19T11:59:59Z', jetzt)).toBeFalse();
  });

  it('liest auch Zeitstempel ohne Zeitzone, wie sie /recent fuer aeltere Beitraege liefert', () => {
    // Ohne Offset liest der Browser Ortszeit; an der Grenze macht das hoechstens die Zeitverschiebung aus.
    expect(istFrisch('2026-11-25T08:00:00', jetzt)).toBeTrue();
    expect(istFrisch('2026-11-01T08:00:00', jetzt)).toBeFalse();
  });

  it('gilt ohne oder mit unlesbarem Datum nicht', () => {
    expect(istFrisch(undefined, jetzt)).toBeFalse();
    expect(istFrisch('', jetzt)).toBeFalse();
    expect(istFrisch('kein Datum', jetzt)).toBeFalse();
  });
});
