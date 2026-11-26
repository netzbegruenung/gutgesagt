-- Seitenaufrufe und Besucher je Tag (#761)
--
-- aufrufe_heute: je Tagespseudonym (#446) die Zahl der Seitenaufrufe des laufenden
-- Tages. Das Pseudonym lebt nur bis zum Ende seines Tages: Danach verdichtet der Takt
-- (mvp/backend/semantic-search-service/app/services/aufrufe_service.py) den Tag zu
-- einer Zeile in aufrufe_tage (Aufrufe, Besucher) und loescht die Pseudonyme. Keine
-- IP-Adresse, keine Kennung.
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt die Tabellen beim
-- Start an, auch in bestehenden Datenbanken, vor dem Einspielen der Migrationen.
--
-- Vorhandene Daten: keine. Die Tabellen fuellen sich erst, wenn der Schalter
-- "aufrufe_zaehlen" wirksam ist. Ein zweiter Lauf aendert nichts.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

CREATE TABLE IF NOT EXISTS aufrufe_heute (
    tag DATE NOT NULL,
    pseudonym VARCHAR(64) NOT NULL,
    aufrufe INTEGER NOT NULL,
    PRIMARY KEY (tag, pseudonym)
);

CREATE TABLE IF NOT EXISTS aufrufe_tage (
    tag DATE NOT NULL,
    aufrufe INTEGER NOT NULL,
    besucher INTEGER NOT NULL,
    PRIMARY KEY (tag)
);

COMMIT;
