import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { BehaviorSubject, Observable, Subject, of } from 'rxjs';
import { catchError, concatMap, filter, map, take } from 'rxjs/operators';
import { CONSENT_HINWEIS_SATZ, mitCc0Wortlaut } from '../shared/consent-hinweis';
import { environment } from '../../environments/environment';
import { LoggingService } from './logging.service';
import { Thema } from './dtos/themenDtos';

/** Spiegelt EinwurfWeg im Backend. Ohne Angabe zaehlt der Einwurf als 'web'. */
export type EinwurfWeg = 'web' | 'share';

/**
 * Der Satz im Destillier-Ablauf wird der Titel des Beitrags und hat deshalb
 * dasselbe Limit wie der Titel von Kommentar und Hintergrundinfo.
 */
export const SATZ_LIMIT = 120;

/** Wie im Backend (domain/themen.py): beim Einwerfen hoechstens zwei Themen. */
export const HOECHSTENS_THEMEN_JE_EINWURF = 2;

/**
 * Ein Einwurf in den Fangkorb. Mindestens eines der drei Inhaltsfelder muss
 * gesetzt sein; alles Weitere ist schon Destillieren und passiert spaeter.
 * Optional bis zu zwei Themen; ohne fehlt das Feld.
 */
export interface EinwerfenRequest {
  content?: string;
  url?: string;
  image_url?: string;
  source_channel?: EinwurfWeg;
  themen?: string[];
}

/** Die Antwort auf einen Themen-Auftrag (EinwurfService.themenAendern). */
export interface ThemenErgebnis {
  /** Wie viele Auftraege dieses Einwurfs noch offen sind. */
  offen: number;
  /** Die Themen, die der Einwurf jetzt hat; null, wenn das Speichern scheiterte. */
  themen: Thema[] | null;
  fehler: unknown;
}

interface ThemenAuftrag {
  schluessel: string[];
  fertig: (ergebnis: ThemenErgebnis) => void;
}

interface ThemenWarteschlange {
  auftraege: Subject<ThemenAuftrag>;
  offen: number;
  leer: BehaviorSubject<boolean>;
}

export interface EinwerfenResponse {
  id: string;
}

/** in_progress heisst im UI "destilliert": mindestens ein Satz, noch kein Beitrag. */
export type EinwurfStatus = 'open' | 'in_progress' | 'processed' | 'discarded';

/** Die beiden Ziele, die der Destillier-Ablauf setzen darf. */
export type DestillierStatus = 'discarded' | 'processed';

/** Die Beitragstypen, die aus dem Destillier-Ablauf entstehen (ContentType im Backend). */
export type BeitragsTyp = 'commentary' | 'generic_text' | 'post';

/**
 * Ein Satz zu einem Einwurf. Fuer alle Angemeldeten sichtbar, die Kennung der Person
 * aber nur fuer Admins (#385).
 */
export interface Satz {
  id: string;
  /** Nur fuer Admins, sonst null. */
  user_id: string | null;
  /** Anzeigename der Person ("Anna B."); null ohne gespeicherten Namen. */
  user_name?: string | null;
  /** Ob die anfragende Person den Satz gespeichert hat; vom Server berechnet. */
  ist_eigener_satz?: boolean | null;
  sentence: string;
  updated_at: string;
}

/** Die Zustaende eines Beitrags (Glossar), wie die Einwurf-Antwort sie nennt (#507). */
export type BeitragZustand = 'sichtbar' | 'gesperrt' | 'geloescht';

/** Ausformuliert in (Glossar): ein Beitrag, mit dem der Einwurf verknuepft ist, neu entstanden oder vorhanden. */
export interface AusformuliertIn {
  content_id: string;
  /** Null bei Verknuepfungen aus der Zeit vor Fangkorb v2. */
  content_type: string | null;
  /** Der ausformulierte Satz; null, wenn er spaeter geleert wurde. */
  draft_id: string | null;
  /** Der Ausformulierer, nicht zwingend der Autor des Beitrags; nur fuer Admins. */
  processed_by: string | null;
  processed_at: string;
  /**
   * Der Zustand des Beitrags; null oder fehlend, wenn der Server ihn nicht kannte
   * (dann gilt er wie sichtbar).
   */
  zustand?: BeitragZustand | null;
}

export interface Einwurf {
  id: string;
  content: string | null;
  url: string | null;
  image_url: string | null;
  /** Die Kennung des Einwerfers, nur fuer Admins (#385); sonst null. */
  submitted_by: string | null;
  /** Anzeigename des Einwerfers; null ohne gespeicherten Namen. */
  submitted_by_name?: string | null;
  /** Ob die anfragende Person den Einwurf eingeworfen hat; vom Server berechnet. */
  ist_eigener_einwurf?: boolean | null;
  source_channel: string;
  status: EinwurfStatus;
  created_at: string;
  /** Wer als Erste/r einen Satz gespeichert hat; nur fuer Admins. */
  destilled_by?: string | null;
  /** Der eigene Satz aus ``drafts``. */
  own_draft?: string | null;
  /** Erste Verknuepfung mit einem Beitrag, falls ausformuliert. */
  processed_content_id?: string | null;
  /** Nur fuer Admins. */
  processed_by?: string | null;
  processed_at?: string | null;
  /** Alle Saetze aller Personen, aelteste Aenderung zuerst. */
  drafts?: Satz[];
  /** Alle verknuepften Beitraege, aelteste zuerst. */
  links?: AusformuliertIn[];
  /** Die beim Einwerfen gewaehlten Themen, in der Reihenfolge der Themenliste; fehlt bei aelteren Antworten. */
  themen?: Thema[];
}

/** Eine Seite Einwuerfe, wie Fangkorb und Meine Einwuerfe sie bekommen. */
export interface EinwurfSeite {
  results_count: number;
  results: Einwurf[];
  total_records_count: number;
}

export interface GleicherLinkResponse {
  results: Einwurf[];
}

export interface SatzResponse {
  raw_input_id: string;
  sentence: string | null;
  updated_at: string | null;
}

@Injectable({
  providedIn: 'root',
})
export class EinwurfService {
  private baseApiUrl = `${environment.baseUrl}/api/v1/rawinput`;

  /**
   * Einwuerfe, die in dieser Runde mit "Spaeter" zurueckgestellt wurden.
   *
   * Ohne Satz unterscheidet sich ein zurueckgestellter Einwurf serverseitig nicht
   * von einem unberuehrten - "Spaeter" lief deshalb bei zwei solchen Einwuerfen
   * endlos zwischen beiden hin und her. Die Liste lebt nur im Speicher der
   * laufenden App: nichts davon landet im Browser-Speicher oder auf dem Server.
   */
  private readonly zurueckgestellt = new Set<string>();

  constructor(
    private http: HttpClient,
    private logger: LoggingService,
  ) {}

  /** Fuer den Rest der Runde nicht mehr automatisch anbieten. */
  zurueckstellen(id: string): void {
    this.zurueckgestellt.add(id);
  }

  /** Neue Runde: Zurueckgestelltes wird wieder angeboten. */
  rundeBeginnen(): void {
    this.zurueckgestellt.clear();
  }

  einwerfen(request: EinwerfenRequest): Observable<EinwerfenResponse> {
    this.logger.debug('Einwurf wird eingeworfen');
    return this.http.post<EinwerfenResponse>(`${this.baseApiUrl}/addRawInput`, mitCc0Wortlaut(request));
  }

  /**
   * Einwuerfe mit gleichem Link (Glossar), neueste zuerst (#263). Was gleich ist,
   * entscheidet der Server.
   *
   * POST, damit der Link nicht in Adresse und Protokollen steht. Nebenbei greift
   * so der GET-Cache nicht, der sonst nach dem Einwerfen fuenf Minuten lang
   * "kein gleicher Link" festhielte.
   */
  mitGleichemLink(url: string): Observable<Einwurf[]> {
    return this.http
      .post<GleicherLinkResponse>(`${this.baseApiUrl}/gleicherLink`, { url })
      .pipe(map((antwort) => antwort.results));
  }

  /** Der Fangkorb, eigene Einwuerfe zuerst (sortiert der Server). */
  fangkorbLaden(page: number, pageSize: number): Observable<EinwurfSeite> {
    const params = new HttpParams().set('page', page).set('page_size', pageSize);
    return this.http.get<EinwurfSeite>(`${this.baseApiUrl}/getRawInputs`, {
      params,
    });
  }

  /**
   * Meine Einwuerfe: nur die selbst eingeworfenen, neueste zuerst. Immer frisch,
   * denn der Cache laesst den Fangkorb aus (NIE_CACHEN in auth/cache.interceptor.ts).
   */
  eigeneLaden(page: number, pageSize: number): Observable<EinwurfSeite> {
    const params = new HttpParams().set('page', page).set('page_size', pageSize);
    return this.http.get<EinwurfSeite>(`${this.baseApiUrl}/getOwnRawInputs`, {
      params,
    });
  }

  /** Ein Einwurf mit allen Saetzen und dem eigenen als own_draft. */
  einwurfLaden(id: string): Observable<Einwurf> {
    return this.http.get<Einwurf>(this.einwurfUrl(id));
  }

  /**
   * Die Themen eines Einwurfs ersetzen (hoechstens zwei, leer entfernt alle). Darf jede
   * angemeldete Person, wie das Destillieren; liefert den Einwurf mit den neuen Themen.
   */
  themenSetzen(id: string, themen: string[]): Observable<Einwurf> {
    return this.http.put<Einwurf>(`${this.einwurfUrl(id)}/themen`, { themen });
  }

  /**
   * Die Themen eines Einwurfs aendern, wie sie ein Themen-Waehler meldet: je Einwurf der
   * Reihe nach, damit am Ende der letzte Klick gilt. Die Warteschlange lebt hier im
   * Dienst, nicht in der Komponente: Schliesst jemand das Sheet oder wechselt den Schritt,
   * bevor die Antwort da ist, wird trotzdem gespeichert. `fertig` kommt nach jeder Antwort
   * mit der Zahl noch offener Auftraege dieses Einwurfs.
   */
  themenAendern(id: string, schluessel: string[], fertig: (ergebnis: ThemenErgebnis) => void): void {
    const warteschlange = this.themenWarteschlangen.get(id) ?? this.themenWarteschlangeAnlegen(id);
    // Beim Einreihen zaehlen, nicht beim Senden: sonst gaelte der Einwurf zwischen zwei
    // Auftraegen als fertig.
    warteschlange.offen++;
    warteschlange.leer.next(false);
    warteschlange.auftraege.next({ schluessel, fertig });
  }

  /** Meldet einmal, sobald alle Themen-Auftraege dieses Einwurfs beantwortet sind (sofort ohne). */
  themenGespeichert(id: string): Observable<void> {
    const warteschlange = this.themenWarteschlangen.get(id);
    if (!warteschlange) {
      return of(undefined);
    }
    return warteschlange.leer.pipe(
      filter((leer) => leer),
      take(1),
      map(() => undefined),
    );
  }

  private readonly themenWarteschlangen = new Map<string, ThemenWarteschlange>();

  private themenWarteschlangeAnlegen(id: string): ThemenWarteschlange {
    const warteschlange: ThemenWarteschlange = {
      auftraege: new Subject<ThemenAuftrag>(),
      offen: 0,
      leer: new BehaviorSubject(true),
    };
    warteschlange.auftraege
      .pipe(
        concatMap((auftrag) =>
          this.themenSetzen(id, auftrag.schluessel).pipe(
            map((einwurf) => ({ auftrag, themen: einwurf.themen ?? [], fehler: null as unknown })),
            catchError((fehler) => of({ auftrag, themen: null, fehler })),
          ),
        ),
      )
      .subscribe(({ auftrag, themen, fehler }) => {
        warteschlange.offen--;
        auftrag.fertig({ offen: warteschlange.offen, themen, fehler });
        if (warteschlange.offen === 0) {
          // Leer: wer wartet (themenGespeichert), erfaehrt es; dann weg, bis zum naechsten Klick.
          this.themenWarteschlangen.delete(id);
          warteschlange.leer.next(true);
          warteschlange.auftraege.complete();
        }
      });
    this.themenWarteschlangen.set(id, warteschlange);
    return warteschlange;
  }

  /** Den eigenen Satz speichern; ein leerer Satz loescht ihn. */
  satzSpeichern(id: string, sentence: string): Observable<SatzResponse> {
    return this.http.put<SatzResponse>(
      `${this.einwurfUrl(id)}/draft`,
      mitCc0Wortlaut({ sentence }, CONSENT_HINWEIS_SATZ),
    );
  }

  /**
   * Den eigenen Satz sichern, wenn die Seite gleich eingefroren oder beendet wird.
   *
   * Android raeumt die PWA beim Wechsel in eine andere App weg; ein normaler
   * XHR wird dabei abgebrochen. fetch mit keepalive darf die Seite ueberleben.
   * HttpClient laeuft hier ohne Fetch-Backend und kann das nicht - daher direkt.
   * Fehler werden verschluckt: mehr als versuchen geht in diesem Moment nicht.
   * Am Cache-Interceptor vorbei leert dieser Weg den GET-Cache nicht. Das ist nur
   * unschaedlich, weil der Fangkorb nie im Cache liegt (NIE_CACHEN in
   * auth/cache.interceptor.ts); wer das aendert, muss hier selbst leeren.
   */
  satzSpeichernKeepalive(id: string, sentence: string): void {
    try {
      fetch(`${this.einwurfUrl(id)}/draft`, {
        method: 'PUT',
        keepalive: true,
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mitCc0Wortlaut({ sentence }, CONSENT_HINWEIS_SATZ)),
      }).catch((error) => this.logger.warn('Satz konnte nicht gesichert werden', error));
    } catch (error) {
      this.logger.warn('Satz konnte nicht gesichert werden', error);
    }
  }

  /**
   * Verwerfen oder mit einem Beitrag verknuepfen - dann mit dem verknuepften Beitrag
   * und seinem Typ, nach dem sich die Fangkorb-Karte faerbt.
   */
  updateStatus(
    id: string,
    status: DestillierStatus,
    contentId?: string,
    contentType?: BeitragsTyp,
  ): Observable<Einwurf> {
    const body: Record<string, string> = { status };
    if (contentId) {
      body['content_id'] = contentId;
    }
    if (contentType) {
      body['content_type'] = contentType;
    }
    return this.http.patch<Einwurf>(`${this.einwurfUrl(id)}/status`, body);
  }

  /**
   * Der naechste Einwurf fuer den Destillier-Ablauf: offen oder destilliert, ohne
   * eigenen Satz.
   *
   * Destilliert heisst nur, dass jemand anderes schon einen Satz hat - es gibt
   * keine Sperre, der eigene Satz kann trotzdem kommen. Einwuerfe mit eigenem
   * Satz hat man mit "Spaeter" zurueckgestellt; sie bleiben antippbar, werden
   * aber nicht automatisch wieder angeboten. Dasselbe gilt fuer Einwuerfe, die in
   * dieser Runde ohne Satz zurueckgestellt wurden (``zurueckstellen``). Die
   * Reihenfolge (eigene zuerst, dann neueste) kommt vom Server.
   */
  naechsterOffenerEinwurf(ausser?: string | null): Observable<Einwurf | null> {
    return this.fangkorbLaden(1, 100).pipe(
      map(
        (daten) =>
          daten.results.find(
            (einwurf) =>
              (einwurf.status === 'open' || einwurf.status === 'in_progress') &&
              !einwurf.own_draft &&
              einwurf.id !== ausser &&
              !this.zurueckgestellt.has(einwurf.id),
          ) ?? null,
      ),
    );
  }

  /**
   * Der naechste Einwurf fuer die Serie beim Ausformulieren: einer aus dem Tab
   * "Ausformulieren" (destilliert, nicht verworfen), den eigenen Satz zuerst, dann wie
   * der Server sortiert. ``ausser`` und Zurueckgestelltes werden uebersprungen.
   */
  naechsterZumAusformulieren(ausser?: string | null): Observable<Einwurf | null> {
    return this.fangkorbLaden(1, 100).pipe(
      map((daten) => {
        const kandidaten = daten.results.filter(
          (einwurf) =>
            (einwurf.status === 'open' || einwurf.status === 'in_progress') &&
            (!!einwurf.own_draft || (einwurf.drafts ?? []).length > 0) &&
            !(einwurf.links ?? []).length &&
            einwurf.id !== ausser &&
            !this.zurueckgestellt.has(einwurf.id),
        );
        return kandidaten.find((einwurf) => !!einwurf.own_draft) ?? kandidaten[0] ?? null;
      }),
    );
  }

  private einwurfUrl(id: string): string {
    return `${this.baseApiUrl}/${encodeURIComponent(id)}`;
  }
}
