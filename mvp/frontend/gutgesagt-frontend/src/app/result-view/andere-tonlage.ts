import { SearchResponse } from '../services/dtos/searchDtos';
import { BaseSearchResult } from '../services/dtos/commonDtos';
import { ausSuchergebnis } from '../beitragskarte/karten-daten';
import type { AndereTonlage } from '../beitragskarte/karten-aktionen/kopiert-erfolg';
import { aussageSchluessel } from './ergebnis-gruppen';

/**
 * Je Kommentar der Suchantwort eine Antwort zur selben Aussage in anderem Stil, fuer den
 * Hinweis nach dem Kopieren (#785). Gesucht wird in der ganzen Antwort, nicht nur im
 * gefilterten Teil, damit der Hinweis beim Themenfilter nicht wechselt; gewaehlt wird die
 * erste in der Reihenfolge der Suche. Nur Kommentare mit Stil und nur mit demselben Zweck:
 * Eine Antwort fuer die eigenen Leute ist kein Ersatz fuer eine in Kommentarspalten.
 * Kommentare ohne Aussage oder ohne andere Tonlage fehlen in der Map.
 */
export function andereTonlagen(antwort: SearchResponse | null): Map<BaseSearchResult, AndereTonlage> {
  const ergebnis = new Map<BaseSearchResult, AndereTonlage>();
  const jeAussage = new Map<string, { treffer: BaseSearchResult; id: string; stil: AndereTonlage['stil']; eigeneLeute: boolean }[]>();
  for (const treffer of antwort?.commentary_search_results ?? []) {
    const schluessel = aussageSchluessel(treffer);
    if (!schluessel) {
      continue;
    }
    const karte = ausSuchergebnis(treffer);
    const stil = karte.extra?.stil;
    if (!stil || !karte.id) {
      continue;
    }
    const liste = jeAussage.get(schluessel) ?? [];
    liste.push({ treffer, id: karte.id, stil, eigeneLeute: !!karte.extra?.fuerEigeneLeute });
    jeAussage.set(schluessel, liste);
  }
  for (const liste of jeAussage.values()) {
    for (const eintrag of liste) {
      const andere = liste.find((e) => e.stil !== eintrag.stil && e.eigeneLeute === eintrag.eigeneLeute);
      if (andere) {
        ergebnis.set(eintrag.treffer, { id: andere.id, stil: andere.stil });
      }
    }
  }
  return ergebnis;
}
