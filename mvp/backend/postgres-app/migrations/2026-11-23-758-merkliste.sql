-- Merkliste (#758)
--
-- Je Person und Beitrag eine Zeile: wann die Person ihn zuletzt gemerkt hat. Nur die
-- Person selbst sieht ihre Merkliste (api/v1/merkliste.py), hinter dem Schalter
-- merkliste (services/schalter_service.py).
--
-- Neue Datenbanken brauchen dieses Skript nicht: create_all legt die Tabelle beim
-- Start an. Vorhandene Daten: keine. Ein zweiter Lauf aendert nichts.
--
-- Loeschen (docs/LOESCHKONZEPT.md): mit dem Konto (person_loeschen.sql), beim Widerruf
-- der Art.-9-Einwilligung und mit dem endgueltig entfernten Beitrag.
--
-- Anwenden: siehe README.md in diesem Verzeichnis.

BEGIN;

CREATE TABLE IF NOT EXISTS merkliste (
    user_id VARCHAR(255) NOT NULL,
    content_id UUID NOT NULL,
    gemerkt_am TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (user_id, content_id)
);
CREATE INDEX IF NOT EXISTS idx_merkliste_user_gemerkt ON merkliste (user_id, gemerkt_am);
CREATE INDEX IF NOT EXISTS idx_merkliste_content ON merkliste (content_id);

COMMIT;
