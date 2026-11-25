-- Meldungen ohne Konto (#799): "Ja, gepostet" ohne Anmeldung als reiner Wochenzaehler
--
-- gepostet_ohne_konto_wochen: je Kalenderwoche (Montag, UTC) nur die Zahl der Klicks.
-- Keine Kennung, kein Pruefwert, kein Beitrag, keine Adresse. Getrennt von
-- gepostet_wochen (verschiedene Menschen mit Konto, der Nordstern), damit die beiden
-- Zahlen nie addiert werden (docs/LOESCHKONZEPT.md: ohne Personenbezug, keine Frist).
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt die Tabelle beim
-- Start an, auch in bestehenden Datenbanken, vor dem Einspielen der Migrationen.
-- Das Skript dokumentiert das Schema und laeuft dann ohne Wirkung durch.
-- Vorhandene Daten gibt es keine.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

CREATE TABLE IF NOT EXISTS gepostet_ohne_konto_wochen (
    woche DATE NOT NULL,
    meldungen INTEGER NOT NULL,
    PRIMARY KEY (woche)
);

COMMIT;
