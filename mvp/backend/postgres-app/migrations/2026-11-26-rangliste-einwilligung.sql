-- Einwilligung zur Rangliste je Saison (#793)
--
-- Je Antwort eine Zeile: ob die Person in der Rangliste der laufenden Saison
-- erscheint (teilnehmen), ob sie dort ihren Anzeigenamen statt des zufaelligen
-- Ranglistennamens gewaehlt hat (mit_anzeigename), die Kennung des Wortlauts
-- (mvp/backend/semantic-search-service/app/domain/rangliste.py) und wann sie
-- geantwortet hat. Es gilt die juengste Zeile einer Kennung; jede Aenderung ist eine
-- neue Zeile. Plaetze und Punkte werden nicht gespeichert, sondern je Abruf berechnet.
-- Geloescht werden alle Zeilen mit dem Konto (docs/LOESCHKONZEPT.md, Schritt 2).
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt die Tabelle beim
-- Start an, auch in bestehenden Datenbanken, vor dem Einspielen der Migrationen.
-- Das Skript dokumentiert das Schema und laeuft dann ohne Wirkung durch.
-- Vorhandene Daten gibt es keine.
--
-- Rueckweg: Die Tabelle steht fuer sich, kein anderer Teil des Schemas verweist auf
-- sie. Ein aelterer Dienst ignoriert sie; wer sie loswerden will, loescht nur die
-- Tabelle rangliste_einwilligung (DROP TABLE). Damit sind alle Antworten und ihr
-- Nachweis weg; die Rangliste fragt dann jede Person neu.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

CREATE TABLE IF NOT EXISTS rangliste_einwilligung (
    id UUID NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    teilnehmen BOOLEAN NOT NULL,
    mit_anzeigename BOOLEAN NOT NULL,
    wortlaut VARCHAR(64) NOT NULL,
    beantwortet_am TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS idx_rangliste_einwilligung_user
    ON rangliste_einwilligung (user_id, beantwortet_am);

COMMIT;
