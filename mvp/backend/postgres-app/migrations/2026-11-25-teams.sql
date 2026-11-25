-- Teams ueber Einladungen
--
-- Eine Einladung kann zu einem Team gehoeren: Name (hoechstens 40 Zeichen), Motiv
-- und Saison stehen an der Einladung (neue Spalten in einladungen, leer heisst
-- reiner Kontolink wie bisher). Sagt die Person ausdruecklich ja, entsteht eine
-- Mitgliedschaft (team_mitgliedschaften) mit Kennung, Teamname, Motiv, Saison,
-- laufender Nummer, Tag des Beitritts sowie Kennung des Wortlauts und Zeitpunkt der
-- Einwilligung. Welche Einladung genutzt wurde, steht nirgends. team_nummern zaehlt
-- je Team und Saison die zuletzt vergebene Nummer, damit eine Nummer nach "Team
-- verlassen" nicht neu vergeben wird. team_oeffentlich haelt die eigene Einwilligung
-- "Team oeffentlich am Namen zeigen". einstellungen haelt Admin-Einstellungen mit
-- Textwert, zuerst die aktuelle Saison
-- (mvp/backend/semantic-search-service/app/services/team_service.py).
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt die neuen Tabellen
-- beim Start an. Bestehende Datenbanken brauchen es fuer die drei Spalten an
-- einladungen; die Tabellen legt es nur an, wenn create_all sie nicht schon angelegt
-- hat.
--
-- Vorhandene Daten: Bestehende Einladungen bekommen kein Team (Spalten leer). Ein
-- zweiter Lauf aendert nichts. Mitgliedschaften und die Einwilligung gehen mit dem
-- Konto (mvp/scripts/manual/person_loeschen.sql), die Kennung des Admins an
-- einstellungen wird dort geleert.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

SET LOCAL lock_timeout = '5s';

ALTER TABLE einladungen ADD COLUMN IF NOT EXISTS team_name VARCHAR(40);
ALTER TABLE einladungen ADD COLUMN IF NOT EXISTS team_motiv VARCHAR(32);
ALTER TABLE einladungen ADD COLUMN IF NOT EXISTS team_saison VARCHAR(20);

CREATE TABLE IF NOT EXISTS team_mitgliedschaften (
    id UUID NOT NULL,
    konto_kennung VARCHAR(255) NOT NULL,
    team_name VARCHAR(40) NOT NULL,
    team_motiv VARCHAR(32),
    saison VARCHAR(20) NOT NULL,
    nummer INTEGER NOT NULL,
    eingetreten_am DATE NOT NULL,
    einwilligung_kennung VARCHAR(64) NOT NULL,
    einwilligung_zeitpunkt TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_team_mitgliedschaften_konto_team_saison
        UNIQUE (konto_kennung, team_name, saison),
    CONSTRAINT uq_team_mitgliedschaften_team_saison_nummer
        UNIQUE (team_name, saison, nummer)
);

CREATE TABLE IF NOT EXISTS team_nummern (
    team_name VARCHAR(40) NOT NULL,
    saison VARCHAR(20) NOT NULL,
    letzte_nummer INTEGER NOT NULL,
    PRIMARY KEY (team_name, saison)
);

CREATE TABLE IF NOT EXISTS team_oeffentlich (
    konto_kennung VARCHAR(255) NOT NULL,
    zeigen BOOLEAN NOT NULL,
    einwilligung_kennung VARCHAR(64) NOT NULL,
    beantwortet_am TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (konto_kennung)
);

CREATE TABLE IF NOT EXISTS einstellungen (
    name VARCHAR(64) NOT NULL,
    wert VARCHAR(255) NOT NULL,
    geaendert_am TIMESTAMP WITH TIME ZONE NOT NULL,
    geaendert_von VARCHAR(255),
    PRIMARY KEY (name)
);

COMMIT;
