-- Herkunft pruefen (#759)
--
-- Je Herkunft mit Link das Ergebnis der naechtlichen Pruefung: Adresse, Ergebnis
-- (ok, umgezogen, tot, fehler, nicht_erreichbar, gesperrt), HTTP-Status,
-- Weiterleitungsziel, Zeitpunkt der Pruefung und seit wann der Link auffaellt
-- (mvp/backend/semantic-search-service/app/services/herkunft_pruefen.py). Nichts zur
-- Person: keine Kennung, kein Beitrag.
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt die Tabelle beim
-- Start an, auch in bestehenden Datenbanken, vor dem Einspielen der Migrationen.
--
-- Vorhandene Daten: keine. Die Tabelle fuellt sich erst, wenn ein Admin den Schalter
-- "herkunft_pruefen" einschaltet. Ein zweiter Lauf aendert nichts.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

CREATE TABLE IF NOT EXISTS herkunft_pruefung (
    herkunft_id UUID NOT NULL,
    adresse VARCHAR(2048) NOT NULL,
    ergebnis VARCHAR(32) NOT NULL,
    http_status INTEGER,
    ziel VARCHAR(2048),
    geprueft_am TIMESTAMP WITH TIME ZONE NOT NULL,
    auffaellig_seit TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (herkunft_id)
);
CREATE INDEX IF NOT EXISTS idx_herkunft_pruefung_ergebnis
    ON herkunft_pruefung (ergebnis);

COMMIT;
