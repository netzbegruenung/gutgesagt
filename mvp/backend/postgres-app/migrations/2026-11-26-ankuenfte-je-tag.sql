-- Ankuenfte je Kampagnenwort und Tag (GLOSSARY.md "Ankunft", "Kampagnenwort")
--
-- ankuenfte_je_tag: je Kampagnenwort aus der Positivliste (SEMANTIC_SEARCH_K_WOERTER) und
-- UTC-Tag nur die Zahl, wie oft die App mit ?k=<wort> geoeffnet wurde. Keine Kennung,
-- kein Konto, keine Adresse, kein Beitrag (vorlaeufige Jura-Einschaetzung 26.11.2026).
-- Frist zwoelf Monate nach dem Tag (docs/LOESCHKONZEPT.md), geloescht vom Task der
-- Loeschfristen.
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt die Tabelle beim
-- Start an, auch in bestehenden Datenbanken, vor dem Einspielen der Migrationen.
-- Das Skript dokumentiert das Schema und laeuft dann ohne Wirkung durch.
-- Vorhandene Daten gibt es keine.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

CREATE TABLE IF NOT EXISTS ankuenfte_je_tag (
    k VARCHAR(20) NOT NULL,
    tag DATE NOT NULL,
    anzahl INTEGER NOT NULL,
    PRIMARY KEY (k, tag)
);

COMMIT;
