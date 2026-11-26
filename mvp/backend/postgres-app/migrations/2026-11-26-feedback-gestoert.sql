-- Feedback-Kategorie "gestoert": Knopf "Was hat dich gestört?" fuer die Startphase
--
-- Der Knopf (Schalter feedback_gestoert) oeffnet dasselbe Formular wie
-- "Feedback", nur mit Freitext ohne Kontakt, und speichert die Zeile mit
-- kategorie = 'gestoert'. Ohne Kategorie (NULL) ist es Feedback ueber den Knopf
-- "Feedback" wie bisher. Ab dem 31.12.2026 (UTC) loescht der taegliche
-- Loeschlauf des Feedbacks alle Zeilen der Kategorie, unabhaengig von der Frist
-- von 180 Tagen (domain/feedback_gestoert.py, docs/LOESCHKONZEPT.md).
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt die Tabelle
-- mit der Spalte an (infrastructure/database/connection.py), und das Skript
-- laeuft dann ohne Wirkung durch. Bestehende Datenbanken brauchen es, denn
-- create_all ergaenzt keine Spalten. Vorhandenes Feedback bleibt ohne
-- Kategorie. Wiederholbar.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

ALTER TABLE feedback ADD COLUMN IF NOT EXISTS kategorie TEXT;

COMMIT;
