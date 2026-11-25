-- Teams nach Gruppe
--
-- Eine Einladung mit Team traegt jetzt eine Teamart: "anlass" (Team nach Anlass, Ort
-- oder Saison, wie bisher) oder "gruppe" (Team nach Gruppe, benannt nach einer
-- Gruppe, die oeffentlich unter diesem Namen auftritt und vorher schriftlich und
-- widerruflich zugestimmt hat). Bei "gruppe" steht der Tag, an dem die schriftliche
-- Zustimmung der Gruppenleitung vorlag, an der Einladung: nur als Nachweis fuer
-- Admins, ohne Namen (GLOSSARY.md "Team",
-- mvp/backend/semantic-search-service/app/api/v1/einladungen.py).
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt einladungen mit den
-- Spalten an. Bestehende Datenbanken brauchen es fuer die zwei neuen Spalten.
--
-- Vorhandene Daten: Bestehende Einladungen mit Team bekommen die Art "anlass", alle
-- anderen bleiben leer. Ein zweiter Lauf aendert nichts.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

SET LOCAL lock_timeout = '5s';

ALTER TABLE einladungen ADD COLUMN IF NOT EXISTS team_art VARCHAR(16);
ALTER TABLE einladungen ADD COLUMN IF NOT EXISTS team_zustimmung_am DATE;

UPDATE einladungen SET team_art = 'anlass'
    WHERE team_name IS NOT NULL AND team_art IS NULL;

COMMIT;
