-- Gesehenes Wirkungs-Echo: Stand fuer "Seit deinem letzten Besuch" auf der Startseite (#790)
--
-- Neben Nutzung und Einwuerfen haelt gesehene_nutzung je Kennung fest, wie oft die
-- eigenen Beitraege beim letzten Besuch insgesamt als "oeffentlich gepostet" gemeldet
-- waren; die Startseite nennt nur den Zuwachs. Ein Zaehlerstand, kein Zeitpunkt.
--
-- Nachtragen: nichts. NULL gilt als 0; die Summe zaehlt erst seit dem Schalter
-- wirkungs_echo, der naechste Besuch nennt sie einmal und setzt den Stand.
--
-- Loeschen: mit der Zeile, docs/LOESCHKONZEPT.md, Schritt 2.
--
-- Rueckweg: ALTER TABLE gesehene_nutzung DROP COLUMN IF EXISTS echo; nur zusammen
-- mit einem Code-Revert, der die Spalte aus dem Modell nimmt.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

ALTER TABLE gesehene_nutzung ADD COLUMN IF NOT EXISTS echo INTEGER;

COMMIT;
