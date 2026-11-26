-- Spielgefuehl als eine Einstellung in drei Stufen (Schalter spielgefuehl_buehne)
--
-- Je Antwort eine Zeile: die Stufe (aus, fuer_mich, rangliste), ob die Person in
-- der Rangliste mit ihrem Anzeigenamen statt mit dem Zufallsnamen steht
-- (mit_anzeigename), die Kennung des Wortlauts
-- (mvp/backend/semantic-search-service/app/domain/spielgefuehl.py), wann sie
-- geantwortet hat und ihren zufaelligen Ranglistennamen (beim ersten Mitspielen
-- gewuerfelt, auf Wunsch neu gewuerfelt, in jede weitere Zeile uebernommen; leer
-- davor). Es gilt die juengste Zeile einer Kennung; jede Aenderung ist eine neue
-- Zeile. Punkte und Plaetze werden nicht gespeichert, sondern je Abruf berechnet.
-- Geloescht werden alle Zeilen mit dem Konto (docs/LOESCHKONZEPT.md, Schritt 2).
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt die Tabelle beim
-- Start an, auch in bestehenden Datenbanken, vor dem Einspielen der Migrationen.
-- Das Skript dokumentiert das Schema und laeuft dann ohne Wirkung durch.
-- Vorhandene Daten werden nicht uebernommen: Die Antworten auf die bisherigen
-- Einwilligungen (punkte_einwilligung, abzeichen_sichtbarkeit,
-- rangliste_einwilligung) bleiben als Nachweis stehen, gelten im neuen Modell aber
-- nicht; mit dem Schalter wird jede Person neu gefragt.
--
-- Rueckweg: Die Tabelle steht fuer sich, kein anderer Teil des Schemas verweist auf
-- sie. Ein aelterer Dienst ignoriert sie; wer sie loswerden will, loescht nur die
-- Tabelle spielgefuehl (DROP TABLE). Damit sind alle Antworten und ihr Nachweis weg.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

CREATE TABLE IF NOT EXISTS spielgefuehl (
    id UUID NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    stufe VARCHAR(16) NOT NULL,
    mit_anzeigename BOOLEAN NOT NULL,
    wortlaut VARCHAR(64) NOT NULL,
    beantwortet_am TIMESTAMP WITH TIME ZONE NOT NULL,
    ranglistenname VARCHAR(64),
    PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS idx_spielgefuehl_user
    ON spielgefuehl (user_id, beantwortet_am);

COMMIT;
