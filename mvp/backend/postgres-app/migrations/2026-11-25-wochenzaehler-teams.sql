-- Team-Fortschritt und Team-Quests: Wochenzaehler je Team
--
-- team_wochen: je Team, Saison und Woche (Montag, UTC) nur die Zahl der Beitraege,
-- Bewertungen und Meldungen "Ja, gepostet" der Mitglieder mit Team-Einwilligung
-- team-2026-11-26. Keine Kennung, kein Beitrag, kein Zeitpunkt; entdoppelt wird im
-- Arbeitsspeicher, nicht hier
-- (mvp/backend/semantic-search-service/app/services/team_fortschritt_service.py).
-- team_quests: je Team und Woche das Thema und das Ziel der Team-Quest, nichts zur
-- Person.
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt die Tabellen beim
-- Start an, auch in bestehenden Datenbanken, vor dem Einspielen der Migrationen.
-- Das Skript dokumentiert das Schema und laeuft dann ohne Wirkung durch.
--
-- Vorhandene Daten gibt es keine. Rueckweg: Die beiden Tabellen haengen an nichts
-- und lassen sich mit DROP TABLE team_quests, team_wochen entfernen; ohne sie zeigt
-- "Meine Teams" bei eingeschalteten Schaltern nur, dass das Team noch waechst.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

CREATE TABLE IF NOT EXISTS team_wochen (
    team_name VARCHAR(40) NOT NULL,
    saison VARCHAR(20) NOT NULL,
    woche DATE NOT NULL,
    beitraege INTEGER DEFAULT 0 NOT NULL,
    bewertungen INTEGER DEFAULT 0 NOT NULL,
    gepostet INTEGER DEFAULT 0 NOT NULL,
    PRIMARY KEY (team_name, saison, woche)
);

CREATE TABLE IF NOT EXISTS team_quests (
    team_name VARCHAR(40) NOT NULL,
    saison VARCHAR(20) NOT NULL,
    woche DATE NOT NULL,
    thema VARCHAR(64),
    ziel INTEGER NOT NULL,
    PRIMARY KEY (team_name, saison, woche)
);

COMMIT;
