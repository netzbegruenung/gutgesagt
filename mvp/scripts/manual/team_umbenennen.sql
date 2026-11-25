-- Ein Team umbenennen, etwa nach dem Widerruf der Zustimmung einer Gruppe
-- (Team nach Gruppe, GLOSSARY.md "Team", Bedingung 2).
--
-- Der Teamname steht als Kopie an drei Stellen: an den Einladungen, an jeder
-- Mitgliedschaft und am Zaehler der Nummern. Das Skript benennt alle drei in einer
-- Transaktion um, in allen Saisons, und macht die Einladungen zu einem Team nach
-- Anlass, Ort oder Saison (das Datum der Zustimmung wird geleert). Nummern, Tag des
-- Beitritts und die Einwilligungen der Mitglieder bleiben.
--
-- Der neue Name darf in keiner betroffenen Saison schon vergeben sein; sonst bricht
-- das Skript an einer Eindeutigkeitsregel ab und aendert nichts. Neuer Name nach den
-- Regeln des Admin-Formulars: hoechstens 40 Zeichen, keines von < > & " \ /.
--
-- Aufruf auf dem Host der App-Datenbank (wie person_loeschen.sql, docs/LOESCHKONZEPT.md):
--   docker exec -i gutgesagt-app-postgres psql -U app_user -d gutgesagt_app \
--     -v ON_ERROR_STOP=1 -v alt='Netzfeuerwehr' -v neu='Team Herbst 2026' < team_umbenennen.sql
-- Wiederholbar: Ein zweiter Lauf findet den alten Namen nicht mehr.
-- Getestet in tests/integration/test_teams.py.

BEGIN;
UPDATE einladungen
   SET team_name = :'neu', team_art = 'anlass', team_zustimmung_am = NULL
 WHERE team_name = :'alt';
UPDATE team_mitgliedschaften SET team_name = :'neu' WHERE team_name = :'alt';
UPDATE team_nummern SET team_name = :'neu' WHERE team_name = :'alt';
COMMIT;
