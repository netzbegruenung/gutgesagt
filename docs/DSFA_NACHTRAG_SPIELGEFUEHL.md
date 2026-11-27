# DSFA-Nachtrag: Spielgefühl und Wirkung (Vorstands-Go)

> **KI-gestützter Entwurf, keine Rechtsberatung, zur Prüfung durch Vorstand und DSB.**
> Herkunft: Jura-Entwurf vom 27.11.2026, Teil A, inhaltlich unverändert übernommen.
> Einschübe in eckigen Klammern [Prüfvermerk …] sind nachträglich ergänzt und verweisen auf
> die Prüfvermerke am Code am Ende. Mit ❔ markierte Stellen sind **offen** und brauchen den
> Rat der Datenschutzbeauftragten; wo ein Prüfvermerk eine ❔-Frage am Code beantwortet,
> steht das in der Klammer dahinter.

Ergänzt [`docs/DSFA.md`](./DSFA.md) um die Daten, die mit dem Spielgefühl-Modell und den
Wirkungs-Funktionen dazukommen. Die Nummern sind die der Verarbeitungen in `docs/DSFA.md`:
V9a, V10 und V21 stehen dort und im Verzeichnis
([`docs/VERARBEITUNGSVERZEICHNIS.md`](./VERARBEITUNGSVERZEICHNIS.md)); V23 kommt mit dem
DSFA-Stand vom 25.11. (#780, Zählung bis V27) in die DSFA, ins Verzeichnis noch nicht;
V28 bis V31 sind neu und dort noch **offen**, bis die DSFA sie als eigene Verarbeitungen
beschreibt. Eine Zeile je Datum: Risiko · Maßnahme · Restrisiko. Fundstellen auf `main` @
`d3b3def7` (27.11.2026), `ss/` = `mvp/backend/semantic-search-service/app/`.

Rahmen: alles Opt-in, Standard aus; Art.-9-Nähe, weil Nutzung auf politische Haltung schließen
lässt; Rechtsgrundlage Art. 9 Abs. 2 lit. a (Einwilligung), wo Profil oder Vergleich entsteht,
sonst Art. 6 Abs. 1 lit. f mit Art.-9-Mitwirkung wie V10.

| # | Datum (neu) | Risiko | Maßnahme | Restrisiko |
|---|---|---|---|---|
| V28 | Spielgefühl-Stufe (aus / nur für mich / Saison-Rangliste), Namenswahl, Zufallsname, Kennung des Wortlauts, Zeitpunkt (#849) | Vorbelegung, gebündelte Einwilligung | eine Frage, drei gleichwertige Knöpfe, keine Vorauswahl; Namenswahl Pflicht ohne Vorauswahl; Hinweis vor den Knöpfen; Kennung spielgefuehl-2026-11-26 | gering |
| V28 | Rangliste: Name, Platz, Punkte, Abzeichen, sichtbar nur für angemeldete Mitspielende | Offenlegung von Aktivität und Parteinähe ggü. Dritten (Art. 9) | nur Stufe 3; Zufallsname wählbar; erst ab 10 Teilnehmenden sichtbar; kein Abruf ohne Anmeldung (Code prüfen ❔) [Prüfvermerk 1: bestätigt]; im Wortlaut: Mitspielende sehen deinen Namen, ein Zufallsname erschwert das Erkennen, schützt aber nicht sicher; Übergang: alle zurückgesetzt und neu gefragt | gering bis mittel |
| V28 | Widerruf (#853) | Widerruf schwerer als Erteilung (Art. 7 Abs. 3) | Nein/Aus/Widerruf immer speicherbar, auch bei Schalter aus; Widerruf entfernt Rangliste, Punkte, Abzeichen sofort; sichtbarer Weg auf der Datenschutzseite (Folge-PR) **Bedingung fürs Go**, spätestens vor Vorhut-Ausweitung | gering, sobald Folge-PR da |
| V28 | Punkte aus Nutzungsereignissen, 90 Tage (ab 2. Saison 100) | Profilbildung über Zeit | nur mit Stufe ≥2; Löschung nach Frist (LOESCHKONZEPT); 100 Tage nur für neu erhobene Ereignisse, DSE vorher | gering |
| V28 | Punkt je Bewertung fremder Beiträge, ≤3/Tag, Richtung zählt nicht | Rückschluss auf Meinung | Richtung fließt nicht ein; Deckel | gering |
| V30 | Muster-Hinweise und Paar-Prüfwerte (Zweitkonten/Absprachen; ab Kennung spielgefuehl-2026-11-27 auch Zustimmungen, nur Admin-Hinweis, keine Wirkung auf Punkte/Rangliste) | Verdacht gegen Einzelne, Art.-9-Profil | nur wenn beide aktuell eingewilligt (auch beim Erzeugen geprüft); Paar-Prüfwerte ohne Kontozuordnung, Schlüssel nur im Arbeitsspeicher, nicht einzeln löschbar, Verfall nach 7 Tagen; Hinweise (am Konto) höchstens 56 Tage, beim Widerruf sofort gelöscht; Zustimmungen nur für Konten mit neuer Kennung, eigener Schalter [Prüfvermerk 2: auf `main` noch nicht gebaut]; nur Admin, ein Mensch entscheidet, keine automatische Sperre (Art. 22 greift nicht ❔) | gering |
| V9a | Nutzung ohne Anmeldung: Tages-Prüfwert aus dem Anschluss (IPv6 /64, Schlüssel je Tag nur im Speicher, nach Tageswechsel verworfen, Adresse nicht gespeichert; bestehend, M2) [Prüfvermerk 3: bestätigt] plus Deckel (#857): Platz-Prüfwert aus Beitrag, Tag, Platznummer | Erfassung Besuchender | Deckel ohne Besuchermerkmal; kein Speicherzugriff im Endgerät (kein § 25 TDDDG ❔); ≤1 je Anschluss und ≤3 insgesamt je Beitrag und Tag | gering |
| V9a | öffentliche Saison-Summe (#814), Zähler „Meldungen ohne Konto“ | Einzelne erkennbar bei kleinen Zahlen | erst ab 3 Wochen × 25 Personen; Drosselung insgesamt, ohne Adresse | gering |
| V10 | „Dein nächster Schritt“ (#789/#816), Antworten-Hinweis (#760) | Profil aus eigenem Verhalten | beim Abruf berechnet, nichts gespeichert; Weggeklicktes nur im Browser 7 Tage | gering |
| V21 | Profilbildwahl, „schon gesehen“, „Ton bei Erfolgen“ (#809) | Speicher im Endgerät | vom Nutzer gewünscht (§ 25 Abs. 2 Nr. 2 TDDDG ❔) | gering |
| V23/V29 | Teams nach Gruppe, Team-Fortschritt/Quests (#813/#815) | Rückschluss auf Einzelne im Team (auch aus der Differenz zweier Stände) | Team-Summe erst ab 5 Mitgliedern; Gruppenname nur mit schriftlicher Zustimmung; Option: Summe nur wöchentlich | gering |
| V31 | Wirkungs-Echo, Danke-Knopf (#817), Spalte gesehene_nutzung.echo | Autor erfährt Nutzung | nur Zahlen, keine Personen; danke_ohne_konto bleibt aus | gering |

**Schwelle (Art. 35 Abs. 1):** DSFA durchgeführt, weil zwei Kriterien vorliegen (Daten zu
politischer Meinung, Bewertung/Scoring); dagegen stehen kleiner Kreis, Freiwilligkeit,
Voreinstellung aus, Pseudonymwahl.

**Bedingungen fürs Go:** sichtbarer Widerrufsweg (#853-Folge-PR), Rangliste ohne Abruf ohne
Anmeldung (✅ belegt im Code: require_user, test_rangliste_api.py:215) [Prüfvermerk 1],
Wortlaut Stufe 3 (✅ selbst gelesen, spielgefuehl.py:93–104 origin/main 27.11.)
[`ss/domain/spielgefuehl.py`], DSE und VVT ergänzt vor dem Einschalten.
Offen ❔: Mindestalter 16 für Stufe ≥2 (Art. 8, falls Mitglieder unter 16 die App nutzen).

**Restrisiko gesamt:** kein hohes. Begründung: Jede Verarbeitung mit Profil- oder
Vergleichscharakter hängt an einer gesonderten, widerrufbaren Einwilligung ohne Vorauswahl.
Sichtbar wird nur, wer es wählt, auf Wunsch unter Zufallsnamen. Fristen sind kurz (7 bis 100
Tage), Ereignisse ohne Konto tragen kein Besuchermerkmal [Prüfvermerk 3: gilt für den Deckel; der Tages-Prüfwert entsteht aus dem Merkmal und gilt bis zum Tageswechsel], und kleine Zahlen sind gesperrt.
**Ausgenommen** und deshalb aus: teams_oeffentlich, merkliste, aufrufe_zaehlen. Für sie wäre
ein hohes Restrisiko möglich, also gesonderte Prüfung und gegebenenfalls Konsultation der
Aufsicht (Art. 36, bis 8 Wochen 📖) nach der BDK.

## Prüfvermerke am Code

1. **Rangliste ohne Anmeldung nicht abrufbar: bestätigt.** Beide Endpunkte
   (`GET /api/v1/rangliste` und `PUT /api/v1/rangliste/einwilligung`) hängen an
   `Depends(require_user)` (`ss/api/v1/rangliste.py:161` und `:211`). `require_user`
   antwortet 401, wenn `X-User` fehlt oder `anonymous` ist, wie es das BFF für öffentliche
   Aufrufe setzt (`ss/dependencies.py:769–779`). Der Test `test_ohne_anmeldung_401`
   (`ss/tests/unit/api/test_rangliste_api.py:215`) prüft beide Endpunkte ohne `X-User` auf
   401; den Fall `X-User: anonymous` deckt er nicht eigens ab. Davor sperrt schon das BFF:
   `/api/v1/rangliste` steht nicht in `EndpointPolicy.AllowAnonymous`
   (`mvp/backend/BFF/Proxy/EndpointPolicy.cs:24`), ohne Anmeldung antwortet es 401
   (`mvp/backend/BFF/Program.cs:537–540`). Andere Wege zur Rangliste gibt es nicht: Die übrigen
   Aufrufer des Ranglisten-Dienstes nehmen nur Einträge zurück (Widerruf). Die Rangliste
   selbst liefert der Dienst nur Teilnehmenden und erst ab `MIN_TEILNEHMENDE` = 10
   (`ss/services/rangliste_service.py:104`, `ss/domain/rangliste.py:44`).
2. **Zustimmungen als Merkmal der Muster-Prüfung (V30): auf `main` noch nicht gebaut.**
   Die Tabelle beschreibt den Stand ab Kennung `spielgefuehl-2026-11-27` mit eigenem
   Schalter. Auf `main` gibt es weder diese Kennung noch einen Schalter dafür; aktuell ist
   `spielgefuehl-2026-11-26` (`ss/domain/spielgefuehl.py:38`). Muster-Hinweise entstehen bisher
   nur aus Nutzungen: Der einzige Aufruf von `nutzung_melden` steht im Zähl-Endpunkt
   `POST /content/{content_id}/usage` (`ss/api/v1/usage.py:521–533`), nur mit eingeschalteten
   Punkten und wenn beide Konten in die Punkte eingewilligt haben (die Prüfung „beim
   Erzeugen“). Bewertungen, also auch Stimmen (Zustimmung oder Ablehnung, GLOSSARY.md), rufen
   die Muster-Prüfung nirgends auf. Die Fristen der Zeile stimmen: Paar-Prüfwerte 7 Tage
   (`MUSTER_FENSTER_TAGE`, `ss/services/entdoppelung.py:49`), Hinweise höchstens 56 Tage
   (`MUSTER_FRIST_TAGE`, `ss/services/muster_hinweise_service.py:54`).
3. **Nutzung ohne Anmeldung (V9a): bestätigt.** Ohne Anmeldung bildet der Zähl-Endpunkt den
   Tages-Prüfwert aus dem Besuchermerkmal (`ss/api/v1/usage.py:485`). Das Merkmal ist der
   Anschluss, bei IPv6 sein /64, unter einem HMAC mit einem Schlüssel, der je Tag zufällig
   entsteht und nur im Speicher liegt; die Adresse wird weder gespeichert noch geloggt
   (`ss/utils/besucher_pseudonym.py`, Kopf). Dazu kommt der Deckel je Beitrag und Tag
   (`deckel_pruefwerte`, `ss/api/v1/usage.py:488–490`; `punkte_nutzung_ohne_anmeldung_je_tag`
   = 3 in `ss/core/config.py:459`). Der Tages-Prüfwert liegt in der Tabelle `nutzung_heute`;
   `pruefwerte_verwerfen_im_takt` verwirft die Zeilen nach jedem Tageswechsel
   (`ss/services/entdoppelung.py:17–19`, `:190`).
