// Wire format is snake_case end-to-end (see CONTENT_MODEL.md "Decisions").

import { BaseContentResult, BaseSearchResult, ContentReference } from "./commonDtos";
import type { Stil, Zweck } from "../../shared/zweck-stil";
import type { Thema } from "./themenDtos";

// Request DTOs

export interface SearchByTextRequest {
    query_text: string;
    limit: number;
}


// Response DTOs

export interface SearchResponse {
    query_was_newly_added_as_statement: boolean;
    /** null, wenn die Suchanfrage nicht als Aussage angelegt werden konnte. */
    statement_id: string | null;
    statement_text: string;
    commentary_search_results_count: number;
    commentary_search_results: CommentarySearchResult[];
    generictext_search_results_count: number;
    generictext_search_results: GenerictextSearchResult[];
    post_search_results_count?: number;
    post_search_results?: PostSearchResult[];
    image_search_results_count?: number;
    image_search_results?: ImageSearchResult[];
    /** Ohne Treffer: so oft (je Tagespseudonym und Woche) wurde in vier Wochen ohne Treffer danach gesucht, die eigene Suche eingerechnet; erst ab 3, nur zu einer sichtbaren Aussage und nur mit dem Schalter null_treffer_anzahl (#362). */
    schon_gesucht_anzahl?: number | null;
    /**
     * "Alles zum Thema" (#754): bei Eingaben aus einem bis drei Woertern, die zu einem
     * Thema passen, hoechstens zwei; sonst null oder fehlend.
     */
    passende_themen?: PassendesThema[] | null;
}

/** Eine Aussage eines Themas, meistgenutzte zuerst (#754). */
export interface AussageDesThemas {
    statement_id: string;
    text: string;
    /** Sichtbare Antworten auf die Aussage. */
    antworten: number;
}

/** Ein Thema mit seinen meistgenutzten Aussagen (#754). */
export interface PassendesThema extends Thema {
    aussagen: AussageDesThemas[];
    /** Alle Aussagen des Themas mit Antwort; mehr als `aussagen`: "Alle … zeigen". */
    anzahl_aussagen: number;
}

/** GET /api/v1/search/thema/{schluessel}: alle Aussagen eines Themas. */
export interface AussagenDesThemasResponse {
    thema: PassendesThema;
}

export interface CommentarySearchResult extends BaseSearchResult {
    commentary_result: CommentaryResult;
}

export interface CommentaryResult extends BaseContentResult {
    long_text: string;
    short_text: string;
    /** Ohne Angabe: Kommentarspalte (#357). */
    zweck?: Zweck;
    style?: Stil | null;
}

export interface GenerictextSearchResult extends BaseSearchResult {
    generictext_result: GenerictextResult;
}

export type GenerictextResult = BaseContentResult;

export interface PostSearchResult extends BaseSearchResult {
    post_result: PostResult;
}

export interface PostResult extends BaseContentResult {
    platform: string;
    author?: string | null;
    url?: string;
    engagement: number;
}

export interface ImageSearchResult extends BaseSearchResult {
    image_result: ImageResult;
}

export interface ImageResult extends BaseContentResult {
    image_url: string;
}

// Backwards-compatible aliases: references are structurally identical across types,
// so both now resolve to the shared ContentReference (see commonDtos.ts).
export type CommentaryReference = ContentReference;
export type GenericTextReference = ContentReference;
