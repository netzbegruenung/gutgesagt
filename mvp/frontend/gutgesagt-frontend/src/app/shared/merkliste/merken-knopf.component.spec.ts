import { ComponentFixture, TestBed } from '@angular/core/testing';
import { WritableSignal, computed, signal } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { BehaviorSubject, of, throwError } from 'rxjs';

import { AuthService } from '../../auth/auth.service';
import { Gemerkt, MerklisteService } from '../../services/merkliste.service';
import { MERKEN_TEXTE, MerkenKnopfComponent } from './merken-knopf.component';

describe('MerkenKnopfComponent (#758)', () => {
  let fixture: ComponentFixture<MerkenKnopfComponent>;
  let an: WritableSignal<boolean>;
  let eingewilligt: WritableSignal<boolean>;
  let eintraege: WritableSignal<Gemerkt[]>;
  let nutzer: BehaviorSubject<{ isAuthenticated: boolean } | null>;
  let merkliste: { bereit: unknown; eintraege: unknown; istGemerkt: jasmine.Spy; sicherstellen: jasmine.Spy; umschalten: jasmine.Spy };
  let snackBar: jasmine.SpyObj<MatSnackBar>;

  beforeEach(async () => {
    an = signal(true);
    eingewilligt = signal(true);
    eintraege = signal([]);
    nutzer = new BehaviorSubject<{ isAuthenticated: boolean } | null>({ isAuthenticated: true });
    const ids = computed(() => new Set(eintraege().map((e) => e.content_id)));
    merkliste = {
      bereit: () => an() && eingewilligt(),
      eintraege: eintraege.asReadonly(),
      istGemerkt: jasmine.createSpy('istGemerkt').and.callFake((id: string) => ids().has(id)),
      sicherstellen: jasmine.createSpy('sicherstellen'),
      umschalten: jasmine.createSpy('umschalten'),
    };
    snackBar = jasmine.createSpyObj('MatSnackBar', ['open']);
    await TestBed.configureTestingModule({
      imports: [MerkenKnopfComponent],
      providers: [
        { provide: MerklisteService, useValue: merkliste },
        { provide: AuthService, useValue: { userInfo$: nutzer.asObservable(), getUserInfo: () => nutzer.value } },
        { provide: MatSnackBar, useValue: snackBar },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(MerkenKnopfComponent);
    fixture.componentRef.setInput('inhaltId', 'a');
    fixture.detectChanges();
  });

  const knopf = () => fixture.nativeElement.querySelector('.merken-knopf') as HTMLButtonElement | null;

  it('zeigt bei eingeschaltetem Schalter „Merken“ mit Symbol und laedt die Liste', () => {
    expect(knopf()?.textContent?.replace(/\s+/g, ' ').trim()).toBe(`bookmark_border${MERKEN_TEXTE.merken}`);
    expect(merkliste.sicherstellen).toHaveBeenCalled();
  });

  it('zeigt nichts bei ausgeschaltetem Schalter', () => {
    an.set(false);
    fixture.detectChanges();

    expect(knopf()).toBeNull();
  });

  it('zeigt nichts und laedt nichts ohne Art.-9-Einwilligung', () => {
    merkliste.sicherstellen.calls.reset();
    eingewilligt.set(false);
    fixture.detectChanges();

    expect(knopf()).toBeNull();
    expect(merkliste.sicherstellen).not.toHaveBeenCalled();
  });

  it('zeigt nichts ohne Anmeldung', () => {
    nutzer.next({ isAuthenticated: false });
    fixture.detectChanges();

    expect(knopf()).toBeNull();
  });

  it('heisst nach dem Merken „Gemerkt“ und sagt, wo es steht', () => {
    merkliste.umschalten.and.callFake(() => {
      eintraege.set([{ content_id: 'a', gemerkt_am: '' }]);
      return of(true);
    });

    knopf()!.click();
    fixture.detectChanges();

    expect(knopf()?.textContent).toContain(MERKEN_TEXTE.gemerkt);
    expect(snackBar.open).toHaveBeenCalledWith(MERKEN_TEXTE.gemerktMeldung, 'OK', jasmine.anything());
  });

  it('meldet eine volle Merkliste', () => {
    merkliste.umschalten.and.returnValue(throwError(() => ({ status: 409 })));

    knopf()!.click();

    expect(snackBar.open).toHaveBeenCalledWith(MERKEN_TEXTE.voll, 'OK', jasmine.anything());
  });

  it('ist mindestens 44 px hoch', () => {
    expect(knopf()!.getBoundingClientRect().height).toBeGreaterThanOrEqual(44);
  });
});
