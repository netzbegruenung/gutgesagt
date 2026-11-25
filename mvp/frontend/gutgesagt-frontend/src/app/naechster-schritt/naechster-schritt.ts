import { AUSSAGE_PARAM, FORMULAR_PFAD } from '../shared/formular-adresse';
import { ROUTES } from '../shared/constants/app.constants';
import {
  GESUCHT_PARAM,
  VON_HIER_FEHLT_EINE_ANTWORT,
  VON_PARAM,
} from '../beitragsformular/beitrag-gespeichert/gespeichert-adresse';

/** Schalter der Karte (#789), wie im Backend (services/naechster_schritt.py). */
export const NAECHSTER_SCHRITT_SCHALTER = 'naechster_schritt';

export type VorschlagArt = 'suchen' | 'einwerfen' | 'bewerten' | 'brachflaeche' | 'kurzfassung';

/** Ein Vorschlag aus GET /api/v1/usage/users/me/naechster-schritt. */
export interface Vorschlag {
  art: VorschlagArt;
  anzahl?: number | null;
  brachflaeche?: { statement_id: string; statement_text: string; personen_ohne_treffer: number } | null;
  kommentar?: { content_id: string; titel: string; nutzung: number } | null;
}

export interface NaechsterSchrittAntwort {
  vorschlaege: Vorschlag[];
}

/** Was die Karte zeigt: ein Satz, wahlweise ein Zitat, und ein Knopf mit Ziel. */
export interface Anzeige {
  satz: string;
  /** Der Spruch ohne Antwort, als Zitat unter dem Satz. */
  zitat?: string;
  /** Ein zweiter, kleiner Satz, etwa wo sich etwas aendern laesst. */
  hinweis?: string;
  knopf: string;
  /** Ohne Ziel: Der Knopf setzt den Fokus ins Suchfeld der Startseite. */
  ziel?: string;
  queryParams?: Record<string, string>;
  fragment?: string;
}

/** Die id des Suchfelds der Startseite (search-view, feldId). */
export const SUCHFELD_ID = 'suche';

/**
 * Fragment der Startseite, das den Fokus ins Suchfeld setzt (/search#suchen, „Ersten Spruch
 * suchen“). Bewusst nicht die id des Feldes: Sonst scrollte der Router (anchorScrolling) das
 * Feld an den oberen Rand und Titel und Untertitel aus dem Bild.
 */
export const SUCHFELD_FOKUS_FRAGMENT = 'suchen';

const ZAHLWORTE: Record<number, string> = {
  2: 'Zwei',
  3: 'Drei',
  4: 'Vier',
  5: 'Fünf',
  6: 'Sechs',
  7: 'Sieben',
  8: 'Acht',
  9: 'Neun',
  10: 'Zehn',
  11: 'Elf',
  12: 'Zwölf',
};

/** „Drei“ am Satzanfang; ohne Zahlwort die Ziffer. */
export function zahlAmSatzanfang(zahl: number): string {
  return ZAHLWORTE[zahl] ?? `${zahl}`;
}

/** Was die Karte zu einem Vorschlag sagt; null bei unbekannter Art oder fehlenden Daten. */
export function anzeige(vorschlag: Vorschlag): Anzeige | null {
  switch (vorschlag.art) {
    case 'suchen':
      return { satz: 'Such den Spruch, der dich zuletzt geärgert hat.', knopf: 'Zur Suche' };
    case 'einwerfen':
      return {
        satz: 'Spruch gesehen, der dich nervt? Wirf ihn ein, das dauert nur ein paar Sekunden.',
        knopf: 'Einwerfen',
        ziel: ROUTES.RAW_INPUT,
      };
    case 'bewerten': {
      const anzahl = vorschlag.anzahl ?? 3;
      return {
        satz:
          anzahl === 1
            ? 'Eine frische Antwort wartet auf deine Einschätzung.'
            : `${zahlAmSatzanfang(anzahl)} frische Antworten warten auf deine Einschätzung.`,
        knopf: 'Frisch aus der Community',
        // Die Startseite ist /search; '/' leitet um und verliert dabei den Anker
        ziel: ROUTES.SEARCH,
        fragment: 'recent-content',
      };
    }
    case 'brachflaeche': {
      const aussage = vorschlag.brachflaeche;
      if (!aussage) {
        return null;
      }
      const personen = aussage.personen_ohne_treffer;
      const satz =
        personen > 1
          ? `Nach diesem Spruch haben ${personen} Leute gesucht. Magst du antworten?`
          : 'Auf diesen Spruch gibt es noch keine Antwort. Magst du antworten?';
      return {
        satz,
        zitat: aussage.statement_text,
        knopf: 'Antworten',
        ziel: FORMULAR_PFAD.commentary,
        // Wie „Antworten“ in „Hier fehlt eine Antwort“ (beantwortenParams): mit der
        // Nachfrage, damit die Ergebnisseite nach dem Speichern „Lücke zu“ sagen kann
        queryParams: {
          [AUSSAGE_PARAM]: aussage.statement_id,
          [VON_PARAM]: VON_HIER_FEHLT_EINE_ANTWORT,
          ...(personen > 0 ? { [GESUCHT_PARAM]: String(personen) } : {}),
        },
      };
    }
    case 'kurzfassung': {
      const kommentar = vorschlag.kommentar;
      if (!kommentar) {
        return null;
      }
      return {
        satz: `Deine Antwort „${kommentar.titel}“ wurde ${kommentar.nutzung}-mal genutzt. Mit einer Kurzfassung passt sie auch in einen Chat.`,
        // Ändern geht nur im eigenen Album: Stift-Knopf „Ändern“ an der Karte
        hinweis: 'In „Meine Beiträge“ ergänzt du sie über den Stift „Ändern“ an der Karte.',
        knopf: 'Kurzfassung ergänzen',
        ziel: ROUTES.MEINE_BEITRAEGE,
      };
    }
    default:
      return null;
  }
}

/**
 * „Weggeklickt“ merkt sich nur der Browser (#789): unter diesem festen Schlüssel je Art
 * des Vorschlags der Tag des Wegklickens, ohne Kennung und ohne Prüfwert. Nach
 * WEGGEKLICKT_TAGE kommt der Vorschlag wieder. Der Eintrag steht in der
 * Datenschutzerklärung unter „Speicherung auf deinem Gerät“; ändert sich hier Schlüssel,
 * Inhalt oder Dauer, muss sich der Absatz dort mit ändern.
 */
export const WEGGEKLICKT_SCHLUESSEL = 'gutgesagt-naechster-schritt-weggeklickt';
export const WEGGEKLICKT_TAGE = 7;

/** Tag als JJJJ-MM-TT in Ortszeit. */
export function tagVon(datum: Date): string {
  const zwei = (n: number) => `${n}`.padStart(2, '0');
  return `${datum.getFullYear()}-${zwei(datum.getMonth() + 1)}-${zwei(datum.getDate())}`;
}

const ARTEN: readonly VorschlagArt[] = ['suchen', 'einwerfen', 'bewerten', 'brachflaeche', 'kurzfassung'];

/**
 * Die noch geltenden Einträge. Abgelaufenes und Unbekanntes fällt weg und wird dabei auch
 * aus dem Speicher gelöscht (ohne geltende Einträge der ganze Schlüssel), damit nichts
 * länger liegt als WEGGEKLICKT_TAGE.
 */
export function weggeklicktLesen(heute: Date = new Date()): Partial<Record<VorschlagArt, string>> {
  const gelesen = gespeichert();
  if (gelesen === null) {
    return {};
  }
  const geltend = nurGeltende(gelesen.werte, heute);
  if (Object.keys(geltend).length !== gelesen.anzahl) {
    schreiben(geltend);
  }
  return geltend;
}

/** Was unter dem Schlüssel steht, mit der Zahl seiner Einträge; null ohne Eintrag oder Speicher. */
function gespeichert(): { werte: Record<string, unknown>; anzahl: number } | null {
  let roh: string | null = null;
  try {
    roh = localStorage.getItem(WEGGEKLICKT_SCHLUESSEL);
  } catch {
    return null;
  }
  if (!roh) {
    return null;
  }
  let gelesen: unknown;
  try {
    gelesen = JSON.parse(roh);
  } catch {
    return { werte: {}, anzahl: -1 };
  }
  if (!gelesen || typeof gelesen !== 'object' || Array.isArray(gelesen)) {
    // Unlesbar: als leer behandeln, beim Aufräumen fällt es weg
    return { werte: {}, anzahl: -1 };
  }
  return { werte: gelesen as Record<string, unknown>, anzahl: Object.keys(gelesen).length };
}

function nurGeltende(gelesen: Record<string, unknown>, heute: Date): Partial<Record<VorschlagArt, string>> {
  const grenze = new Date(heute.getFullYear(), heute.getMonth(), heute.getDate() - WEGGEKLICKT_TAGE);
  const ergebnis: Partial<Record<VorschlagArt, string>> = {};
  for (const art of ARTEN) {
    const tag = gelesen[art];
    if (typeof tag !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(tag)) {
      continue;
    }
    const [j, m, t] = tag.split('-').map(Number);
    const tagDatum = new Date(j, m - 1, t);
    // Ein Tag in der Zukunft (verstellte Uhr) gilt nicht, sonst laege er beliebig lange
    if (tagDatum > grenze && tagDatum <= heute) {
      ergebnis[art] = tag;
    }
  }
  return ergebnis;
}

/**
 * Merkt das Wegklicken einer Art für heute; schreibt dabei nur noch geltende Einträge
 * zurück, damit nichts länger liegt als WEGGEKLICKT_TAGE. Ohne Speicher passiert nichts.
 */
export function wegklicken(art: VorschlagArt, heute: Date = new Date()): Partial<Record<VorschlagArt, string>> {
  const neu = { ...weggeklicktLesen(heute), [art]: tagVon(heute) };
  schreiben(neu);
  return neu;
}

/** Schreibt die Einträge, ohne Einträge entfernt es den Schlüssel; ohne Speicher nichts. */
function schreiben(werte: Partial<Record<VorschlagArt, string>>): void {
  try {
    if (Object.keys(werte).length) {
      localStorage.setItem(WEGGEKLICKT_SCHLUESSEL, JSON.stringify(werte));
    } else {
      localStorage.removeItem(WEGGEKLICKT_SCHLUESSEL);
    }
  } catch {
    // Ohne Speicher gilt das Wegklicken nur bis zum Neuladen.
  }
}

/** Löscht den Eintrag ganz, etwa beim Abmelden; ohne Speicher passiert nichts. */
export function weggeklicktEntfernen(): void {
  try {
    localStorage.removeItem(WEGGEKLICKT_SCHLUESSEL);
  } catch {
    // Ohne Speicher gibt es nichts zu löschen.
  }
}

/** Die Vorschläge ohne die weggeklickten, in der Reihenfolge des Servers. */
export function offeneVorschlaege(
  vorschlaege: readonly Vorschlag[],
  weggeklickt: Partial<Record<VorschlagArt, string>>,
): Vorschlag[] {
  return vorschlaege.filter((v) => !weggeklickt[v.art] && anzeige(v) !== null);
}
