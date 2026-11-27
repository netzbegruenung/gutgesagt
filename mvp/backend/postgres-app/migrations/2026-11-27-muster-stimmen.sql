-- Muster-Hinweise auch aus gegenseitigen Zustimmungen (Schalter muster_stimmen)
--
-- Bisher nannte ein Muster-Hinweis nur zwei Konten, die sich gegenseitig genutzt
-- haben, eine Zeile je Paar. Mit dem Schalter muster_stimmen faellt ein Paar auch auf,
-- wenn beide Konten einander innerhalb von sieben Tagen zustimmen; dafuer ein eigener
-- Hinweis je Art (services/muster_hinweise_service.py). Die neue Spalte art ("nutzung"
-- oder "zustimmung") gehoert deshalb in den Primaerschluessel.
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt muster_hinweise mit
-- der Spalte und dem Schluessel an. Bestehende Datenbanken brauchen es fuer beides.
--
-- Vorhandene Daten: Alle bestehenden Hinweise stammen aus Nutzungen und bekommen den
-- Standard "nutzung". Der Schluessel wird ersetzt, nicht ergaenzt; ein zweiter Lauf
-- legt ihn gleich wieder an und aendert nichts.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

SET LOCAL lock_timeout = '5s';

ALTER TABLE muster_hinweise
    ADD COLUMN IF NOT EXISTS art VARCHAR(16) NOT NULL DEFAULT 'nutzung';

ALTER TABLE muster_hinweise DROP CONSTRAINT IF EXISTS muster_hinweise_pkey;
ALTER TABLE muster_hinweise
    ADD CONSTRAINT muster_hinweise_pkey PRIMARY KEY (konto_a, konto_b, art);

COMMIT;
