/** Ein Thema aus der festen Liste (domain/themen.json im Backend). */
export interface Thema {
    /** Was an der Aussage gespeichert wird. */
    schluessel: string;
    /** Die Anzeige. */
    name: string;
    /**
     * Pfad eines SVG unter public/, etwa „themen/klima.svg“: rein dekorativ, der Name
     * steht immer daneben. Einzige Quelle ist domain/themen.json im Backend.
     */
    motiv?: string;
}

export interface ThemenResponse {
    themen: Thema[];
    /** Ob Themenvorschlaege (#401) an sind; fehlt bei aelteren Diensten (dann aus). */
    vorschlaege?: boolean;
}

export interface ThemenZuordnenRequest {
    statement_id: string;
    themen: string[];
}

export interface ThemenZuordnenResponse {
    statement_id: string;
    themen: Thema[];
}

export interface AussageMitThemen {
    statement_id: string;
    statement_text: string;
    themen: Thema[];
    /** Ob die Zuordnung von Hand ins Testset geht; Aussagen aus Suchanfragen nicht. */
    im_testset: boolean;
}

export interface AussagenMitThemenResponse {
    aussagen: AussageMitThemen[];
}

/** Eine Zeile des Testsets, ohne Autor, Kennung und Zeitpunkt. */
export interface ThemenZuordnung {
    statement_id: string;
    text: string;
    themen: string[];
    zuordnungsart: string;
}

export interface ThemenTestsetResponse {
    zuordnungen: ThemenZuordnung[];
}

/** Themenvorschlaege (#401): Text und wie viele hoechstens (Aussage 3, Einwurf 2). */
export interface ThemenVorschlagRequest {
    text: string;
    hoechstens: number;
}

export interface ThemenVorschlagResponse {
    /** Die vorgeschlagenen Schluessel, das naechste zuerst. */
    themen: string[];
}
