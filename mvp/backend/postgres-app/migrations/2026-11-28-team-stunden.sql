-- Team-Fortschritt quasi-live (Schalter team_live, Jura-Akte 28.11.2026)
--
-- team_stunden: je Team, Saison und Stundenblock (Beginn in UTC, volle Stunde) nur die
-- Zahl der gezaehlten Ereignisse der Mitglieder mit Team-Einwilligung team-2026-11-26,
-- dazu der Stand der Vorberechnung (offen, uebertragen, freigegeben), die freigegebene
-- Zahl und die Zahl der Mitglieder mit Einwilligung zum Zeitpunkt der Vorberechnung.
-- Keine Kennung, kein Beitrag; die verschiedenen Beitragenden je Block zaehlt der
-- Dienst nur im Arbeitsspeicher
-- (mvp/backend/semantic-search-service/app/services/team_fortschritt_service.py).
-- Geloescht mit dem Wochenwechsel (services/loeschfristen_service.py), danach bleibt
-- nur der Wochenzaehler team_wochen.
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt die Tabelle beim
-- Start an, auch in bestehenden Datenbanken, vor dem Einspielen der Migrationen.
-- Das Skript dokumentiert das Schema und laeuft dann ohne Wirkung durch.
--
-- Vorhandene Daten gibt es keine. Rueckweg: Die Tabelle haengt an nichts und laesst
-- sich mit DROP TABLE team_stunden entfernen; ohne sie zeigt "Meine Teams" nur die
-- abgeschlossene Woche.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

CREATE TABLE IF NOT EXISTS team_stunden (
    team_name VARCHAR(40) NOT NULL,
    saison VARCHAR(20) NOT NULL,
    block_beginn TIMESTAMP WITH TIME ZONE NOT NULL,
    anzahl INTEGER DEFAULT 0 NOT NULL,
    stand VARCHAR(12) DEFAULT 'offen' NOT NULL,
    freigabe INTEGER,
    mitglieder INTEGER,
    PRIMARY KEY (team_name, saison, block_beginn)
);

CREATE INDEX IF NOT EXISTS idx_team_stunden_block_beginn ON team_stunden (block_beginn);

COMMIT;
