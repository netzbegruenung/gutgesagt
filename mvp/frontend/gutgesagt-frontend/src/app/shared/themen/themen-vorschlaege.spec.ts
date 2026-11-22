import { Component } from '@angular/core';
import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ThemenVorschlaege, VORSCHLAG_PAUSE_MS } from './themen-vorschlaege';

@Component({ standalone: true, template: '' })
class WirtComponent {
  geaendert = 0;
  readonly vorschlaege = new ThemenVorschlaege(2, () => this.geaendert++);
}

describe('ThemenVorschlaege (#401)', () => {
  let http: HttpTestingController;
  let wirt: WirtComponent;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    wirt = TestBed.createComponent(WirtComponent).componentInstance;
  });

  afterEach(() => http.verify());

  function anfrage() {
    return http.expectOne((r) => r.url.endsWith('/api/v1/statement/themen/vorschlaege'));
  }

  it('fragt nach einer Pause beim Tippen, einmal fuer den letzten Text', fakeAsync(() => {
    wirt.vorschlaege.text('Das Tempolimit');
    tick(VORSCHLAG_PAUSE_MS / 2);
    wirt.vorschlaege.text('Das Tempolimit bringt nichts');
    tick(VORSCHLAG_PAUSE_MS);

    const req = anfrage();
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ text: 'Das Tempolimit bringt nichts', hoechstens: 2 });
    req.flush({ themen: ['verkehr', 'klima'] });

    expect(wirt.vorschlaege.vorschlaege).toEqual(['verkehr', 'klima']);
    expect(wirt.geaendert).toBe(1);
  }));

  it('kurzer oder leerer Text: kein Vorschlag, keine Anfrage', fakeAsync(() => {
    wirt.vorschlaege.text('Das Tempolimit bringt nichts');
    tick(VORSCHLAG_PAUSE_MS);
    anfrage().flush({ themen: ['verkehr'] });

    wirt.vorschlaege.text('Tempo');
    tick(VORSCHLAG_PAUSE_MS);

    http.expectNone((r) => r.url.endsWith('/vorschlaege'));
    expect(wirt.vorschlaege.vorschlaege).toEqual([]);
  }));

  it('scheitert die Abfrage, gibt es keinen Vorschlag und keinen Fehler', fakeAsync(() => {
    wirt.vorschlaege.text('Das Tempolimit bringt nichts');
    tick(VORSCHLAG_PAUSE_MS);
    anfrage().flush('kaputt', { status: 500, statusText: 'Server Error' });

    expect(wirt.vorschlaege.vorschlaege).toEqual([]);
  }));

  it('derselbe Text fragt nicht erneut', fakeAsync(() => {
    wirt.vorschlaege.text('Das Tempolimit bringt nichts');
    tick(VORSCHLAG_PAUSE_MS);
    anfrage().flush({ themen: ['verkehr'] });

    wirt.vorschlaege.text('Das Tempolimit bringt nichts ');
    tick(VORSCHLAG_PAUSE_MS);

    http.expectNone((r) => r.url.endsWith('/vorschlaege'));
  }));
});
