-- Themen an Einwuerfen
--
-- Beim Einwerfen lassen sich bis zu zwei Themen aus der festen Liste waehlen
-- (domain/themen.json im Semantic-Service). Je Wahl eine Zeile mit Einwurf und
-- Thema; die Zeilen gehen per CASCADE mit dem Einwurf (Loeschfrist, Loeschkommando,
-- docs/LOESCHKONZEPT.md). Die Tabelle traegt weder Kennung noch Zeitpunkt.
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt die Tabelle beim
-- Start an, auch in bestehenden Datenbanken, vor dem Einspielen der Migrationen.
-- Das Skript dokumentiert das Schema und laeuft dann ohne Wirkung durch.
--
-- Vorhandene Daten: keine. Einwuerfe von davor haben kein Thema. Ein zweiter Lauf
-- aendert nichts.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

CREATE TABLE IF NOT EXISTS einwurf_themen (
    raw_input_id UUID NOT NULL,
    thema VARCHAR(40) NOT NULL,
    PRIMARY KEY (raw_input_id, thema),
    FOREIGN KEY (raw_input_id) REFERENCES raw_inputs (id) ON DELETE CASCADE
);

COMMIT;
