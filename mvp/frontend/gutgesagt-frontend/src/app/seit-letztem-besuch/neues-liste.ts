import { BesuchResponse } from '../services/usage-tracking.service';
import { MEINE_TAB_PARAM } from '../services/navigation.service';
import { PAGE_TITLES, ROUTES } from '../shared/constants/app.constants';
import { LUECKE } from '../shared/luecke-texte';
import { MENUE_ICONS } from '../shared/fangkorb-texte';

/**
 * Was „Seit deinem letzten Besuch“ zeigt und wann es „Dein nächster Schritt“ vorgeht, ohne
 * Angular: reine Funktionen, die Block, Karte und SeitLetztemBesuchService teilen. Die
 * Reihenfolge der Startseite steht in docs/ARCHITECTURE.md.
 */

/** Ein Link, der nach dem Klick fuer diesen App-Start verschwindet. */
export type NeuesArt = 'antworten' | 'nutzung' | 'echo' | 'ausformuliert' | 'einwuerfe' | 'aussagen' | 'beitraege';

/**
 * Kacheln mit Neuem über die eigenen Beiträge, Aussagen und Einwürfe. Nur sie gehen
 * „Dein nächster Schritt“ vor; die übrigen (neue Einwürfe anderer, wartende Aussagen,
 * neue Beiträge) treten hinter dessen einen Vorschlag zurück (Review Spielgefühl 25.11.).
 */
export const EIGENES_NEUES: ReadonlySet<NeuesArt> = new Set<NeuesArt>(['antworten', 'nutzung', 'echo', 'ausformuliert']);

/** Hoechstens so viele Kacheln nebeneinander (Entscheidung 20.11.). */
export const MAX_KACHELN = 4;

/**
 * Zeitraum der Kacheln ohne Zaehlerstand, wie BESUCH_ZEITRAUM_TAGE im Backend
 * (api/v1/usage.py): Dafuer wird nichts gespeichert, deshalb nennt die Kachel ihn.
 */
export const ZEITRAUM = 'letzte 7 Tage';

/** Eine Kachel im Block: was neu ist und wohin es fuehrt. */
export interface NeuesEintrag {
  /** Grosse Zahl auf der Kachel, an der Grenze der Lueckenliste etwa „50+“. */
  zahl: string;
  /** Kurzer sichtbarer Text unter der Zahl. */
  wort: string;
  /** Nur bei Zahlen ueber einen Zeitraum statt seit dem letzten Besuch: welcher. */
  zeitraum?: string;
  /**
   * Der ganze Satz fuer Screenreader (aria-label). Er enthaelt Zahl, Wort und Zeitraum so,
   * wie sie sichtbar sind, damit auch Sprachsteuerung die Kachel unter ihrem Text findet.
   */
  satz: string;
  /** Ist sie allein, eine breite Zeile: der Satz nach der Zahl … */
  zeile: string;
  /** … und der Knopf zum Ziel. */
  knopf: string;
  /** Material-Icon links neben der Zahl. */
  icon: string;
  ziel: string;
  queryParams?: Record<string, string>;
  fragment?: string;
  /** Fuer Tests und Styles, und welche Kachel nach dem Klick verschwindet. */
  art: NeuesArt;
}

/** Die Zahlen aus der Antwort des Besuchs, die der Block braucht. */
export type NeuesStand = Partial<BesuchResponse>;

/** Nur echte positive Zahlen; alles andere (null, fehlend, negativ) zaehlt als 0. */
const positiv = (wert: number | null | undefined): number => (wert && wert > 0 ? wert : 0);

/**
 * Alle Kacheln mit Neuem (Zahl groesser 0), in der Reihenfolge, in der sie stehen und
 * in der sie bei mehr als MAX_KACHELN wegfallen: zuerst, was die eigenen Aussagen, Beitraege
 * und Einwuerfe betrifft, zuletzt die neuen Beitraege, die „Frisch aus der Community“ direkt
 * darunter ohnehin zeigt.
 */
export function neuesListe(stand: NeuesStand): NeuesEintrag[] {
  const liste: NeuesEintrag[] = [];

  // Antworten auf eigene Aussagen (#760): zuerst, sie betreffen die Person am meisten
  const antworten = positiv(stand.antworten_auf_eigene_aussagen);
  if (antworten) {
    const eine = antworten === 1;
    const wort = eine ? 'neue Antwort auf deine Aussagen' : 'neue Antworten auf deine Aussagen';
    liste.push({
      art: 'antworten',
      ziel: ROUTES.MEINE_BEITRAEGE,
      queryParams: { [MEINE_TAB_PARAM]: 'aussagen' },
      icon: 'forum',
      zahl: `${antworten}`,
      wort,
      zeitraum: ZEITRAUM,
      satz: `${antworten} ${wort}, ${ZEITRAUM}`,
      zeile: eine
        ? 'neue Antwort auf deine Aussagen in den letzten 7 Tagen.'
        : 'neue Antworten auf deine Aussagen in den letzten 7 Tagen.',
      knopf: 'Meine Aussagen',
    });
  }

  const nutzung = positiv(stand.nutzung_seit_letztem_besuch);
  if (nutzung) {
    const wort = nutzung === 1 ? 'Nutzung deiner Beiträge' : 'Nutzungen deiner Beiträge';
    liste.push({
      art: 'nutzung',
      ziel: ROUTES.MEINE_BEITRAEGE,
      icon: 'trending_up',
      zahl: `${nutzung}`,
      wort,
      satz: `${nutzung} ${wort}`,
      zeile: `${wort}. Sieh nach, welche genutzt werden.`,
      knopf: PAGE_TITLES.MEINE_BEITRAEGE,
    });
  }

  // Wirkungs-Echo (#790): nur der Zuwachs seit dem letzten Besuch, als Zaehlerstand wie die
  // Nutzung; ohne Neues keine Kachel. Nur mit Schalter.
  const echo = positiv(stand.neu_oeffentlich_gepostet);
  if (echo) {
    const wort = 'mal öffentlich gepostet';
    liste.push({
      art: 'echo',
      ziel: ROUTES.MEINE_BEITRAEGE,
      icon: 'campaign',
      zahl: `${echo}`,
      wort,
      satz: `${echo} ${wort}`,
      zeile: 'mal wurden deine Beiträge öffentlich gepostet.',
      knopf: PAGE_TITLES.MEINE_BEITRAEGE,
    });
  }

  const ausformuliert = positiv(stand.ausformulierte_einwuerfe);
  if (ausformuliert) {
    const eins = ausformuliert === 1;
    const wort = eins ? 'Einwurf von dir ausformuliert' : 'Einwürfe von dir ausformuliert';
    liste.push({
      art: 'ausformuliert',
      ziel: ROUTES.MEINE_BEITRAEGE,
      queryParams: { [MEINE_TAB_PARAM]: 'einwuerfe' },
      icon: 'task_alt',
      zahl: `${ausformuliert}`,
      wort,
      zeitraum: ZEITRAUM,
      satz: `${ausformuliert} ${wort}, ${ZEITRAUM}`,
      zeile: eins
        ? 'Einwurf von dir hat jemand in den letzten 7 Tagen ausformuliert.'
        : 'Einwürfe von dir haben andere in den letzten 7 Tagen ausformuliert.',
      knopf: 'Meine Einwürfe',
    });
  }

  const einwuerfe = positiv(stand.neue_einwuerfe);
  if (einwuerfe) {
    const eins = einwuerfe === 1;
    const wort = eins ? 'neuer Einwurf im Fangkorb' : 'neue Einwürfe im Fangkorb';
    liste.push({
      art: 'einwuerfe',
      ziel: ROUTES.RAW_INPUT_LIST,
      icon: MENUE_ICONS.einwerfen,
      zahl: `${einwuerfe}`,
      wort,
      satz: `${einwuerfe} ${wort}`,
      zeile: eins ? 'neuer Einwurf wartet im Fangkorb.' : 'neue Einwürfe warten im Fangkorb.',
      knopf: `Zum ${PAGE_TITLES.RAW_INPUT_LIST}`,
    });
  }

  const aussagen = positiv(stand.unbeantwortete_aussagen);
  if (aussagen) {
    const mehr = stand.unbeantwortete_aussagen_mehr ?? false;
    const zahl = mehr ? `${aussagen}+` : `${aussagen}`;
    const eine = aussagen === 1 && !mehr;
    const wort = eine ? 'Aussage ohne Antwort' : 'Aussagen ohne Antwort';
    liste.push({
      art: 'aussagen',
      ziel: ROUTES.HIER_FEHLT_EINE_ANTWORT,
      icon: 'question_answer',
      zahl,
      wort,
      // Beginnt mit dem sichtbaren Text, damit Sprachsteuerung ihn trifft (WCAG 2.5.3)
      satz: `${zahl} ${wort}: ${eine ? LUECKE.einzahl : LUECKE.mehrzahl} in „${PAGE_TITLES.HIER_FEHLT_EINE_ANTWORT}“`,
      zeile: eine ? 'Aussage wartet auf eine Antwort.' : 'Aussagen warten auf eine Antwort.',
      knopf: PAGE_TITLES.HIER_FEHLT_EINE_ANTWORT,
    });
  }

  const beitraege = positiv(stand.neue_beitraege);
  if (beitraege) {
    const wort = beitraege === 1 ? 'neuer Beitrag' : 'neue Beiträge';
    liste.push({
      art: 'beitraege',
      // Die Startseite ist /search; '/' leitet um und verliert dabei den Anker
      ziel: ROUTES.SEARCH,
      fragment: 'recent-content',
      icon: 'feed',
      zahl: `${beitraege}`,
      wort,
      zeitraum: ZEITRAUM,
      satz: `${beitraege} ${wort}, ${ZEITRAUM}`,
      zeile: `${wort} aus der Community in den letzten 7 Tagen.`,
      knopf: 'Frisch aus der Community',
    });
  }

  return liste;
}

/**
 * Ob der Block Neues ueber die eigenen Beitraege zeigt (EIGENES_NEUES), nach den Klicks
 * dieses App-Starts. Beim ersten Besuch nie.
 */
export function eigenesNeuesSichtbar(stand: NeuesStand | null, erledigt: ReadonlySet<NeuesArt>): boolean {
  if (!stand || stand.erster_besuch) {
    return false;
  }
  return neuesListe(stand).some((e) => EIGENES_NEUES.has(e.art) && !erledigt.has(e.art));
}

/**
 * Wer auf der Startseite die eine Stelle mit neuer Richtung bekommt (Review Spielgefühl
 * 25.11.): der Block „Seit deinem letzten Besuch“, die Karte „Heute im Saal gehört:“
 * („spruch“, Schalter saal_spruch) oder die Karte „Dein nächster Schritt“, nie zwei davon.
 * „offen“: Es fehlt noch eine der Antworten (Besuch, Vorschläge, Saal-Spruch), dann zeigt
 * keiner etwas, statt dass eine Karte erscheint und gleich wieder verschwindet.
 */
export type StartVorrang = 'offen' | 'block' | 'spruch' | 'karte';

/**
 * Vorrang: Neues zu eigenen Beiträgen geht vor (es ist, was die Person bewirkt hat), dann
 * der eine Vorschlag, dann an seinen Tagen der Saal-Spruch, sonst der Block mit den
 * allgemeinen Zahlen. Der Saal-Spruch verdrängt also nur die allgemeinen Zahlen (Auftrag
 * Strategiewichtel Nr. 3, #846), nichts Persönliches. `undefined` heißt „Antwort steht
 * noch aus“ (beim Saal-Spruch 'offen'; auf ihn wird nur gewartet, wenn kein Vorschlag da
 * ist), null beim Stand „keine Antwort“ (Fehler, Zeitgrenze). Ohne Angabe zum Saal-Spruch
 * gibt es heute keinen.
 */
export function startVorrang(
  stand: NeuesStand | null | undefined,
  erledigt: ReadonlySet<NeuesArt>,
  naechsterSchrittDa: boolean | undefined,
  saalSpruchDa: boolean | 'offen' = false,
): StartVorrang {
  if (stand === undefined || naechsterSchrittDa === undefined) {
    return 'offen';
  }
  if (eigenesNeuesSichtbar(stand, erledigt)) {
    return 'block';
  }
  if (naechsterSchrittDa) {
    return 'karte';
  }
  if (saalSpruchDa === 'offen') {
    return 'offen';
  }
  return saalSpruchDa ? 'spruch' : 'block';
}

/**
 * Was der Block zeigt: beim allerersten Besuch nichts, denn es gibt keinen letzten Besuch;
 * sonst nur, wenn er den Vorrang hat. Sonst stuenden zwei Karten mit zwei Richtungen
 * untereinander.
 */
export function startKacheln(
  stand: NeuesStand | null | undefined,
  erledigt: ReadonlySet<NeuesArt>,
  vorrang: StartVorrang,
): NeuesEintrag[] {
  if (!stand || stand.erster_besuch || vorrang !== 'block') {
    return [];
  }
  return neuesListe(stand)
    .filter((e) => !erledigt.has(e.art))
    .slice(0, MAX_KACHELN);
}
