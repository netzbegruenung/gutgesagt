-- Ein Team umbenennen, etwa nach dem Widerruf der Zustimmung einer Gruppe
-- (Team nach Gruppe, GLOSSARY.md "Team", Bedingung 2).
--
-- Nur in einen neutralen Namen nach Anlass, Ort oder Saison. Eine Umbenennung in
-- eine andere Gruppe braucht eine neue Einwilligung der Mitglieder und geht deshalb
-- nicht mit diesem Skript (juristische Pruefung 25.11.2026): Es verlangt die Angabe
-- art=anlass, bricht bei jeder anderen ab und setzt die Teamart der Einladungen
-- immer auf "anlass" (das Datum der Zustimmung wird geleert).
--
-- Der Teamname steht als Kopie an drei Stellen: an den Einladungen, an jeder
-- Mitgliedschaft und am Zaehler der Nummern. Das Skript benennt alle drei in einer
-- Transaktion um, in allen Saisons. Nummern, Tag des Beitritts und die
-- Einwilligungen der Mitglieder bleiben.
--
-- Der neue Name darf in keiner betroffenen Saison schon vergeben sein; sonst bricht
-- das Skript an einer Eindeutigkeitsregel ab und aendert nichts. Neuer Name nach den
-- Regeln des Admin-Formulars: hoechstens 40 Zeichen, keines von < > & " \ /.
--
-- Aufruf auf dem Host der App-Datenbank (wie person_loeschen.sql, docs/LOESCHKONZEPT.md):
--   docker exec -i gutgesagt-app-postgres psql -U app_user -d gutgesagt_app \
--     -v ON_ERROR_STOP=1 -v art=anlass -v alt='Netzfeuerwehr' -v neu='Team Herbst 2026' \
--     < team_umbenennen.sql
-- Ohne -v art=anlass (fehlend oder anders) bricht das Skript vor jeder Aenderung ab.
-- Wiederholbar: Ein zweiter Lauf findet den alten Namen nicht mehr.
-- Getestet in tests/integration/test_teams.py.

BEGIN;
-- Sperre: Ziel nur ein neutraler Name. Bei art ungleich anlass scheitert die
-- Umwandlung des Textes in eine Zahl, und die Transaktion endet ohne Aenderung.
SELECT CASE WHEN :'art' = 'anlass' THEN 0 ELSE CAST(CAST('Abbruch: nur in einen neutralen Namen (art=anlass)' AS TEXT) AS INTEGER) END AS sperre;
UPDATE einladungen
   SET team_name = :'neu', team_art = 'anlass', team_zustimmung_am = NULL
 WHERE team_name = :'alt';
UPDATE team_mitgliedschaften SET team_name = :'neu' WHERE team_name = :'alt';
UPDATE team_nummern SET team_name = :'neu' WHERE team_name = :'alt';
COMMIT;
