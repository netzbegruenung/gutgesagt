import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { CommonModule } from '@angular/common';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { signal } from '@angular/core';
import { Observable, of, throwError } from 'rxjs';

import { KonterProbeComponent } from './konter-probe.component';
import { KonterProbeEinstiegComponent } from './konter-probe-einstieg.component';
import {
  KONTER_PROBE_PFAD,
  KonterProbe,
  KonterProbeAntwort,
  KonterProbeService,
  ausAntwort,
  besteAntwort,
  ergebnisSatz,
  nutzungText,
} from './konter-probe';
import { KartenlisteComponent } from '../beitragskarte/kartenliste.component';
import { BeitragskarteStubComponent } from '../beitragskarte/beitragskarte.stub';
import { FunktionenService } from '../services/funktionen.service';

function roh(id: string, style: string, usage_count: number, extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id,
    result_type: 'commentary',
    content_type: 'commentary',
    title: `Titel ${id}`,
    text: `Text ${id}`,
    style,
    usage_count,
    ...extra,
  };
}

function antwort(text = 'Wärmepumpen lohnen sich nie'): KonterProbeAntwort {
  return {
    aussage: { id: 'a-1', text },
    antworten: [
      roh('k-1', 'sachlich', 3),
      roh('k-2', 'humorvoll', 14, { short_text: 'Kurz und lustig' }),
      roh('k-3', 'brueckenbauend', 1),
    ],
  };
}

function probe(text?: string): KonterProbe {
  return ausAntwort(antwort(text))!;
}

describe('Konter-Probe: Auflösung im Browser', () => {
  it('liest Stil, Nutzung und die kurze Fassung als Vorschau', () => {
    const p = probe();
    expect(p.spruch).toBe('Wärmepumpen lohnen sich nie');
    expect(p.antworten.map((a) => [a.stilName, a.nutzung])).toEqual([
      ['sachlich', 3],
      ['humorvoll', 14],
      ['freundlich', 1],
    ]);
    expect(p.antworten[1].vorschau).toBe('Kurz und lustig');
    expect(p.antworten[0].vorschau).toBe('Text k-1');
  });

  it('verwirft Proben mit weniger als drei bekannten Stilen', () => {
    const a = antwort();
    a.antworten[2] = roh('k-3', 'unbekannt', 1);
    expect(ausAntwort(a)).toBeNull();
  });

  it('nennt die meistgenutzte als Spitzenreiter, getroffen oder nicht', () => {
    const p = probe();
    expect(besteAntwort(p).stil).toBe('humorvoll');
    expect(ergebnisSatz(p, p.antworten[1])).toBe('Getroffen, die humorvolle läuft am besten.');
    expect(ergebnisSatz(p, p.antworten[0])).toBe('Diesmal läuft die humorvolle am besten.');
  });

  it('nennt Nutzung ehrlich als Zahl der Nutzungen', () => {
    expect(nutzungText(14)).toBe('14-mal genutzt');
    expect(nutzungText(0)).toBe('noch nicht genutzt');
  });
});

describe('KonterProbeService', () => {
  it('fragt nur lesend und schickt keinen Tipp mit', () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const service = TestBed.inject(KonterProbeService);
    const http = TestBed.inject(HttpTestingController);
    let proben: KonterProbe[] = [];

    service.proben().subscribe((p) => (proben = p));
    const anfrage = http.expectOne((r) => r.url.endsWith(KONTER_PROBE_PFAD));
    expect(anfrage.request.method).toBe('GET');
    expect(anfrage.request.params.keys()).toEqual([]);
    anfrage.flush({ proben: [antwort()] });

    expect(proben.length).toBe(1);
    http.verify();
  });
});

describe('KonterProbeComponent', () => {
  let fixture: ComponentFixture<KonterProbeComponent>;
  let service: jasmine.SpyObj<KonterProbeService>;

  function erstellen(proben: Observable<KonterProbe[]>): void {
    service.proben.and.returnValue(proben);
    fixture = TestBed.createComponent(KonterProbeComponent);
    fixture.detectChanges();
  }

  function alle(selektor: string): HTMLElement[] {
    return Array.from(fixture.nativeElement.querySelectorAll(selektor));
  }

  function text(selektor: string): string {
    return (fixture.nativeElement.querySelector(selektor) as HTMLElement).textContent!.replace(/\s+/g, ' ').trim();
  }

  beforeEach(async () => {
    service = jasmine.createSpyObj('KonterProbeService', ['proben']);
    spyOn(window.localStorage, 'setItem').and.callThrough();
    spyOn(window.sessionStorage, 'setItem').and.callThrough();
    await TestBed.configureTestingModule({
      imports: [KonterProbeComponent],
      providers: [provideRouter([]), { provide: KonterProbeService, useValue: service }],
    })
      .overrideComponent(KartenlisteComponent, { set: { imports: [CommonModule, BeitragskarteStubComponent] } })
      .compileComponents();
  });

  it('zeigt Spruch und drei Antworten mit Namen der Tonlage, ohne Nutzung vor dem Tipp', () => {
    erstellen(of([probe()]));

    expect(text('[data-testid="spruch"]')).toBe('Wärmepumpen lohnen sich nie');
    const knoepfe = alle('[data-testid="tipp"]');
    expect(knoepfe.length).toBe(3);
    expect(knoepfe.map((k) => k.querySelector('.stil')!.textContent!.trim())).toEqual(['sachlich', 'humorvoll', 'freundlich']);
    expect(fixture.nativeElement.textContent).not.toContain('-mal genutzt');
    expect(alle('app-beitragskarte').length).toBe(0);
  });

  it('löst nach dem Tipp mit der echten Nutzung aller drei auf und lädt zum Kopieren ein', () => {
    erstellen(of([probe()]));

    alle('[data-testid="tipp"]')[1].click();
    fixture.detectChanges();

    expect(text('[data-testid="ergebnis"]')).toBe('Getroffen, die humorvolle läuft am besten.');
    const zeilen = alle('[data-testid="aufloesung"]').map((z) => z.textContent!.replace(/\s+/g, ' ').trim());
    expect(zeilen[0]).toContain('3-mal genutzt');
    expect(zeilen[1]).toContain('14-mal genutzt');
    expect(zeilen[1]).toContain('Dein Tipp');
    expect(zeilen[1]).toContain('läuft am besten');
    expect(zeilen[2]).toContain('1-mal genutzt');
    expect(alle('[data-testid="tipp"]').length).toBe(0);
    // Die Karten zum Kopieren, die meistgenutzte zuerst
    expect(alle('app-beitragskarte').length).toBe(3);
    // Der Tipp landet nirgends im Browser-Speicher und geht an keinen Server.
    expect(window.localStorage.setItem).not.toHaveBeenCalled();
    expect(window.sessionStorage.setItem).not.toHaveBeenCalled();
    expect(service.proben).toHaveBeenCalledTimes(1);
  });

  it('wertet daneben ohne Tadel aus', () => {
    erstellen(of([probe()]));
    alle('[data-testid="tipp"]')[0].click();
    fixture.detectChanges();
    expect(text('[data-testid="ergebnis"]')).toBe('Diesmal läuft die humorvolle am besten.');
  });

  it('führt zum nächsten Spruch, solange es einen gibt', () => {
    erstellen(of([probe('Erster Spruch'), probe('Zweiter Spruch')]));
    alle('[data-testid="tipp"]')[0].click();
    fixture.detectChanges();

    (fixture.nativeElement.querySelector('[data-testid="naechste"]') as HTMLElement).click();
    fixture.detectChanges();

    expect(text('[data-testid="spruch"]')).toBe('Zweiter Spruch');
    expect(alle('[data-testid="tipp"]').length).toBe(3);
    alle('[data-testid="tipp"]')[0].click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[data-testid="naechste"]')).toBeNull();
  });

  it('sagt ohne passende Aussage, dass es gerade keinen Spruch gibt', () => {
    erstellen(of([]));
    expect(text('[data-testid="leer"]')).toContain('Gerade gibt es keinen Spruch');
    expect(alle('[data-testid="tipp"]').length).toBe(0);
  });

  it('behandelt den ausgeschalteten Schalter (404) wie keine passende Aussage', () => {
    erstellen(throwError(() => ({ status: 404 })));
    expect(text('[data-testid="leer"]')).toContain('Gerade gibt es keinen Spruch');
  });

  it('versucht es nach einem Fehler selbst wieder', fakeAsync(() => {
    service.proben.and.returnValues(throwError(() => ({ status: 503 })), of([probe()]));
    fixture = TestBed.createComponent(KonterProbeComponent);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('versucht es weiter');

    tick(2000);
    fixture.detectChanges();
    expect(alle('[data-testid="tipp"]').length).toBe(3);
    fixture.destroy();
  }));
});

describe('KonterProbeEinstiegComponent', () => {
  let service: jasmine.SpyObj<KonterProbeService>;
  const an = signal(false);

  function erstellen(): ComponentFixture<KonterProbeEinstiegComponent> {
    const fixture = TestBed.createComponent(KonterProbeEinstiegComponent);
    fixture.detectChanges();
    return fixture;
  }

  beforeEach(async () => {
    an.set(false);
    service = jasmine.createSpyObj('KonterProbeService', ['proben']);
    await TestBed.configureTestingModule({
      imports: [KonterProbeEinstiegComponent],
      providers: [
        provideRouter([]),
        { provide: KonterProbeService, useValue: service },
        { provide: FunktionenService, useValue: { an: () => an } },
      ],
    }).compileComponents();
  });

  it('erscheint bei eingeschaltetem Schalter mit passender Aussage', () => {
    service.proben.and.returnValue(of([probe()]));
    an.set(true);
    const fixture = erstellen();
    const link = fixture.nativeElement.querySelector('a') as HTMLAnchorElement;
    expect(fixture.nativeElement.querySelector('h2').textContent.trim()).toBe('Konter-Probe');
    expect(link.textContent!.trim()).toBe('Mitspielen');
    expect(link.getAttribute('href')).toBe('/konter-probe');
  });

  it('erscheint ohne passende Aussage nicht', () => {
    service.proben.and.returnValue(of([]));
    an.set(true);
    const fixture = erstellen();
    expect(fixture.nativeElement.querySelector('section')).toBeNull();
  });

  it('fragt bei ausgeschaltetem Schalter gar nicht erst und kommt beim Umschalten', () => {
    service.proben.and.returnValue(of([probe()]));
    const fixture = erstellen();
    expect(service.proben).not.toHaveBeenCalled();
    expect(fixture.nativeElement.querySelector('section')).toBeNull();

    an.set(true);
    fixture.detectChanges();
    expect(service.proben).toHaveBeenCalledTimes(1);
    expect(fixture.nativeElement.querySelector('section')).not.toBeNull();
  });
});
