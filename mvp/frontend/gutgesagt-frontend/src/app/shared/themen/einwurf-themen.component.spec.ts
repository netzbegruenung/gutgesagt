import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { EinwurfThemenComponent } from './einwurf-themen.component';
import { EinwurfService, ThemenErgebnis } from '../../services/einwurf.service';
import { ThemenService } from '../../services/themen.service';
import { Thema } from '../../services/dtos/themenDtos';

const KLIMA: Thema = { schluessel: 'klima', name: 'Klima', motiv: 'themen/klima.svg' };
const VERKEHR: Thema = { schluessel: 'verkehr', name: 'Verkehr', motiv: 'themen/verkehr.svg' };
const EUROPA: Thema = { schluessel: 'europa', name: 'Europa', motiv: 'themen/europa.svg' };

describe('EinwurfThemenComponent', () => {
  let fixture: ComponentFixture<EinwurfThemenComponent>;
  let komponente: EinwurfThemenComponent;
  /** Die offenen Auftraege, wie die Warteschlange des Dienstes sie bekommt. */
  let auftraege: { id: string; schluessel: string[]; fertig: (e: ThemenErgebnis) => void }[];
  let gemeldet: Thema[][];

  function zeigen(themen: Thema[] = [KLIMA]): HTMLElement {
    auftraege = [];
    gemeldet = [];
    const einwurfService = {
      themenAendern: (id: string, schluessel: string[], fertig: (e: ThemenErgebnis) => void) =>
        auftraege.push({ id, schluessel, fertig }),
    };
    TestBed.configureTestingModule({
      imports: [EinwurfThemenComponent],
      providers: [
        { provide: EinwurfService, useValue: einwurfService },
        { provide: ThemenService, useValue: { liste: () => of([KLIMA, VERKEHR, EUROPA]) } },
      ],
    });
    fixture = TestBed.createComponent(EinwurfThemenComponent);
    komponente = fixture.componentInstance;
    fixture.componentRef.setInput('einwurfId', 'e-1');
    fixture.componentRef.setInput('themen', themen);
    fixture.componentRef.setInput('immerOffen', true);
    // Wie die Elternseiten: der gemeldete Stand kommt als Eingabe zurueck
    komponente.themenChange.subscribe((t) => {
      gemeldet.push(t);
      fixture.componentRef.setInput('themen', t);
    });
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  const chip = (e: HTMLElement, name: string) =>
    (Array.from(e.querySelectorAll('.thema-chip')) as HTMLButtonElement[]).find((k) => k.textContent?.trim() === name)!;
  const spinner = (e: HTMLElement) => e.querySelector('.themen-speichert');

  it('zeigt jeden Klick sofort und nach dem letzten den gespeicherten Stand', () => {
    const e = zeigen();

    chip(e, 'Verkehr').click();
    fixture.detectChanges();
    chip(e, 'Klima').click();
    fixture.detectChanges();

    expect(auftraege.map((a) => a.schluessel)).toEqual([['klima', 'verkehr'], ['verkehr']]);
    expect(spinner(e)).toBeTruthy();
    expect(chip(e, 'Klima').getAttribute('aria-pressed')).toBe('false');

    auftraege[0].fertig({ offen: 1, themen: [KLIMA, VERKEHR], fehler: null });
    fixture.detectChanges();
    // Noch einer offen: die Anzeige bleibt beim letzten Klick
    expect(chip(e, 'Klima').getAttribute('aria-pressed')).toBe('false');
    auftraege[1].fertig({ offen: 0, themen: [VERKEHR], fehler: null });
    fixture.detectChanges();

    expect(gemeldet.at(-1)).toEqual([VERKEHR]);
    expect(spinner(e)).toBeNull();
    expect(e.textContent).toContain('Themen gespeichert.');
  });

  it('faellt nach einem Fehler auf den zuletzt gespeicherten Stand zurueck', () => {
    const e = zeigen();

    chip(e, 'Verkehr').click();
    fixture.detectChanges();
    auftraege[0].fertig({ offen: 0, themen: null, fehler: { status: 500 } });
    fixture.detectChanges();

    expect(gemeldet.at(-1)).toEqual([KLIMA]);
    expect(e.querySelector('.themen-fehler')!.textContent).toContain('Themen nicht gespeichert.');
  });

  it('nimmt einen Fehler zurueck, wenn der letzte Klick doch gespeichert ist', () => {
    const e = zeigen();

    chip(e, 'Verkehr').click();
    fixture.detectChanges();
    chip(e, 'Klima').click();
    fixture.detectChanges();
    auftraege[0].fertig({ offen: 1, themen: null, fehler: { status: 500 } });
    fixture.detectChanges();
    auftraege[1].fertig({ offen: 0, themen: [VERKEHR], fehler: null });
    fixture.detectChanges();

    expect(e.querySelector('.themen-fehler')).toBeNull();
    expect(gemeldet.at(-1)).toEqual([VERKEHR]);
  });

  it('setzt bei einem anderen Einwurf Spinner und Stand zurueck und uebergeht spaete Antworten', () => {
    const e = zeigen();
    chip(e, 'Verkehr').click();
    fixture.detectChanges();

    fixture.componentRef.setInput('einwurfId', 'e-2');
    fixture.componentRef.setInput('themen', [EUROPA]);
    fixture.detectChanges();
    expect(spinner(e)).toBeNull();

    const vorher = gemeldet.length;
    auftraege[0].fertig({ offen: 0, themen: [KLIMA, VERKEHR], fehler: null });
    fixture.detectChanges();

    expect(gemeldet.length).toBe(vorher);
    expect(chip(e, 'Europa').getAttribute('aria-pressed')).toBe('true');
    expect(chip(e, 'Verkehr').getAttribute('aria-pressed')).toBe('false');
  });

  it('merkt sich die Aenderung schon beim Klick', () => {
    const e = zeigen();
    expect(komponente.geaendert).toBeFalse();

    chip(e, 'Verkehr').click();

    expect(komponente.geaendert).toBeTrue();
  });
});
