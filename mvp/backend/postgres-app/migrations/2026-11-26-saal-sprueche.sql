-- Saal-Spruch des Tages (Schalter saal_spruch)
--
-- saal_sprueche: je Tag (Europe/Berlin) hoechstens ein oeffentlicher Spruch, den ein
-- Admin vorab festlegt (mvp/backend/semantic-search-service/app/services/
-- saal_spruch_service.py). Nur Datum, Text und Zeitpunkt der letzten Aenderung;
-- nichts zur Person, auch nicht, welcher Admin ihn festgelegt hat.
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt die Tabelle beim
-- Start an, auch in bestehenden Datenbanken, vor dem Einspielen der Migrationen. Das
-- Skript dokumentiert das Schema und laeuft dann ohne Wirkung durch.
--
-- Rueckweg: Die Tabelle steht fuer sich, kein anderer Teil des Schemas verweist auf
-- sie. Ein aelterer Dienst ignoriert sie; wer sie loswerden will, loescht nur die
-- Tabelle saal_sprueche.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

CREATE TABLE IF NOT EXISTS saal_sprueche (
    datum DATE NOT NULL,
    text VARCHAR(200) NOT NULL,
    geaendert_am TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (datum)
);

COMMIT;
