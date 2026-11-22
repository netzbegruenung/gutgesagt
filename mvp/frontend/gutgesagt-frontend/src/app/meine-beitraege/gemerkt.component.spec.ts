import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NO_ERRORS_SCHEMA, WritableSignal, signal } from '@angular/core';
import { of, throwError } from 'rxjs';

import { BeitragskarteComponent } from '../beitragskarte/beitragskarte.component';
import { ContentService } from '../services/content.service';
import { Gemerkt, MerklisteService } from '../services/merkliste.service';
import { GEMERKT_TEXTE, GemerktComponent } from './gemerkt.component';

describe('GemerktComponent (#758)', () => {
  let fixture: ComponentFixture<GemerktComponent>;
  let eintraege: WritableSignal<Gemerkt[]>;
  let laden: jasmine.Spy;
  let beitragLaden: jasmine.Spy;

  function beitrag(id: string) {
    return { id, content_type: 'generic_text', title: `Titel ${id}`, text: 'Text', created: '2026-11-01T00:00:00Z' };
  }

  beforeEach(async () => {
    eintraege = signal([]);
    laden = jasmine.createSpy('laden').and.callFake(() => {
      eintraege.set([
        { content_id: 'b', gemerkt_am: '2026-11-22T11:00:00Z' },
        { content_id: 'a', gemerkt_am: '2026-11-22T10:00:00Z' },
        { content_id: 'weg', gemerkt_am: '2026-11-21T10:00:00Z' },
      ]);
      return of(eintraege());
    });
    beitragLaden = jasmine
      .createSpy('beitragLaden')
      .and.callFake((id: string) => (id === 'weg' ? throwError(() => ({ status: 404 })) : of(beitrag(id))));
    await TestBed.configureTestingModule({
      imports: [GemerktComponent],
      providers: [
        { provide: MerklisteService, useValue: { eintraege: eintraege.asReadonly(), laden } },
        { provide: ContentService, useValue: { beitragLaden } },
      ],
    })
      .overrideComponent(GemerktComponent, { remove: { imports: [BeitragskarteComponent] }, add: { schemas: [NO_ERRORS_SCHEMA] } })
      .compileComponents();
    fixture = TestBed.createComponent(GemerktComponent);
  });

  it('zeigt die Karten in der Reihenfolge der Merkliste und nennt, was nicht mehr da ist', () => {
    fixture.detectChanges();

    expect(fixture.componentInstance.karten().map((k) => k.id)).toEqual(['b', 'a']);
    expect(fixture.nativeElement.textContent).toContain(GEMERKT_TEXTE.weg(1));
  });

  it('nimmt eine entfernte Karte sofort heraus', () => {
    fixture.detectChanges();

    eintraege.set([{ content_id: 'a', gemerkt_am: '' }]);

    expect(fixture.componentInstance.karten().map((k) => k.id)).toEqual(['a']);
  });

  it('sagt es, wenn noch nichts gemerkt ist', () => {
    laden.and.returnValue(of([]));
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain(GEMERKT_TEXTE.leer);
  });

  it('bietet nach einem Fehler einen neuen Versuch an', () => {
    laden.and.returnValue(throwError(() => new Error('weg')));
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain(GEMERKT_TEXTE.fehler);
  });
});
