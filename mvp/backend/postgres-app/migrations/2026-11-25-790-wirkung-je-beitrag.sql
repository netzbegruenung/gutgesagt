-- Wirkungs-Echo und Danke je Beitrag (#790, #791)
--
-- wirkung_je_beitrag: je Beitrag zwei Summen fuer die Autorin, wie oft er als
-- "oeffentlich gepostet" gemeldet wurde und wie oft jemand "Danke an die Autorin"
-- gesagt hat. Keine Kennung, kein Pruefwert, kein Zeitpunkt
-- (mvp/backend/semantic-search-service/app/services/wirkung_service.py). Die
-- Entdoppelung des Danke nutzt die vorhandenen Tages-Pruefwerte in nutzung_heute,
-- das Wirkungs-Echo entdoppelt nur im Arbeitsspeicher.
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt die Tabelle beim
-- Start an. Das Skript dokumentiert das Schema und laeuft dann ohne Wirkung durch.
-- Vorhandene Daten gibt es keine.
--
-- Rueckweg: DROP TABLE IF EXISTS wirkung_je_beitrag; entfernt nur die Summen, sonst
-- haengt nichts daran. Danach die Schalter wirkungs_echo und danke_knopf aus lassen,
-- sonst legt create_all die Tabelle beim naechsten Start wieder an.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

CREATE TABLE IF NOT EXISTS wirkung_je_beitrag (
    content_id UUID NOT NULL,
    oeffentlich_gepostet INTEGER DEFAULT 0 NOT NULL,
    danke INTEGER DEFAULT 0 NOT NULL,
    PRIMARY KEY (content_id)
);

COMMIT;
