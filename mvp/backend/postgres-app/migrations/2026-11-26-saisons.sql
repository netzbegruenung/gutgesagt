-- Saisons mit Gemeinschaftsziel (#782)
--
-- saisons: je Saison Name (hoechstens 20 Zeichen wie die Saison an Teams), erster und
-- letzter Tag und das Gemeinschaftsziel in Widerspruchs-Wochen
-- (mvp/backend/semantic-search-service/app/domain/saisons.py). Dass sich Saisons nicht
-- ueberschneiden, prueft der Dienst unter einer Tabellensperre. Nichts zur Person.
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt die Tabelle beim
-- Start an, auch in bestehenden Datenbanken, vor dem Einspielen der Migrationen. Das
-- Skript dokumentiert das Schema und laeuft dann ohne Wirkung durch.
--
-- Vorhandene Daten gibt es keine; Teams behalten ihre Saison als Text.
--
-- Rueckweg: Die Tabelle steht fuer sich, kein anderer Teil des Schemas verweist auf
-- sie. Ein aelterer Dienst ignoriert sie; wer sie loswerden will, loescht nur die
-- Tabelle saisons. Die aktuelle Saison der Teams gilt dann wieder aus der Einstellung
-- auf der Seite Schalter.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

CREATE TABLE IF NOT EXISTS saisons (
    id UUID NOT NULL,
    name VARCHAR(20) NOT NULL,
    beginn DATE NOT NULL,
    ende DATE NOT NULL,
    ziel INTEGER NOT NULL,
    angelegt_am TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_saisons_name UNIQUE (name),
    CONSTRAINT ck_saisons_ende_nach_beginn CHECK (ende >= beginn),
    CONSTRAINT ck_saisons_ziel_positiv CHECK (ziel > 0)
);

COMMIT;
