-- Teamlink verweist auf die Saison per ID
--
-- Bisher trug ein Teamlink nur den Namen der Saison als Kopie (team_saison). Teams
-- zaehlen nur, wenn dieser Name der aktuellen Saison entspricht; ein Link mit einem
-- Namen, den es als Saison nicht gibt (etwa "2026" vor der ersten Saison), fiel aus der
-- Zaehlung, und eine umbenannte geplante Saison liess ihre Links zurueck
-- (Gamification-Check 26.11., Befund 6). Jetzt traegt der Link zusaetzlich die ID der
-- Saison (services/team_service.py ``team_festlegen``); der Name bleibt als Kopie fuer
-- Anzeige und Zaehler und wird beim Umbenennen nachgezogen
-- (repositories/saison_repository.py).
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt einladungen mit der
-- Spalte an. Bestehende Datenbanken brauchen es fuer die neue Spalte.
--
-- Vorhandene Daten: Links, deren Saisonname einer Saison entspricht, bekommen deren
-- ID; alle anderen bleiben ohne ID und verhalten sich wie bisher. Ohne Fremdschluessel
-- (wie team_saison): Wird eine noch nicht begonnene Saison geloescht, leert
-- saison_repository.py die ID, der Link behaelt den Namen. Ein zweiter Lauf
-- aendert nichts.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

SET LOCAL lock_timeout = '5s';

ALTER TABLE einladungen ADD COLUMN IF NOT EXISTS team_saison_id UUID;

-- saisons gibt es schon: create_all legt sie vor den Migrationen an.
UPDATE einladungen e SET team_saison_id = s.id
    FROM saisons s
    WHERE e.team_saison = s.name AND e.team_saison_id IS NULL;

COMMIT;
