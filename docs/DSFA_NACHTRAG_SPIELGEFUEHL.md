# DSFA-Nachtrag: Spielgefühl und Wirkung (Vorstands-Go)

> **Entwurf des Jurawichtels (KI), keine Rechtsberatung, zur Prüfung durch Vorstand und DSB.**
> Herkunft: Jura-Entwurf vom 27.11.2026, Teil A, inhaltlich unverändert übernommen.
> Mit ❔ markierte Stellen sind **offen** und brauchen den Rat der Datenschutzbeauftragten.

Ergänzt [`docs/DSFA.md`](./DSFA.md) um die Daten, die mit dem Spielgefühl-Modell und den
Wirkungs-Funktionen dazukommen. Die Nummern sind die der Verarbeitungen in `docs/DSFA.md`
und im Verzeichnis ([`docs/VERARBEITUNGSVERZEICHNIS.md`](./VERARBEITUNGSVERZEICHNIS.md)):
V9a, V10 und V21 stehen dort schon, V23 kommt mit dem DSFA-Stand vom 25.11. (#780); V28,
V29 und V31 sind neu und dort noch **offen**, bis die DSFA sie als eigene Verarbeitungen
beschreibt. Eine Zeile je Datum: Risiko · Maßnahme · Restrisiko. Fundstellen auf `main` @ `d3b3def7` (27.11.2026),
`ss/` = `mvp/backend/semantic-search-service/app/`.

Rahmen: alles Opt-in, Standard aus; Art.-9-Nähe, weil Nutzung auf politische Haltung schließen
lässt; Rechtsgrundlage Art. 9 Abs. 2 lit. a (Einwilligung), wo Profil oder Vergleich entsteht,
sonst Art. 6 Abs. 1 lit. f mit Art.-9-Mitwirkung wie V10.

| # | Datum (neu) | Risiko | Maßnahme | Restrisiko |
|---|---|---|---|---|
| V28 | Spielgefühl-Stufe (aus / nur für mich / Saison-Rangliste), Namenswahl, Zufallsname, Kennung des Wortlauts, Zeitpunkt (#849) | Vorbelegung, gebündelte Einwilligung | eine Frage, drei gleichwertige Knöpfe, keine Vorauswahl; Namenswahl Pflicht ohne Vorauswahl; Hinweis vor den Knöpfen; Kennung spielgefuehl-2026-11-26 | gering |
| V28 | Rangliste: Name, Platz, Punkte, Abzeichen, sichtbar nur für angemeldete Mitspielende | Offenlegung von Aktivität und Parteinähe ggü. Dritten (Art. 9) | nur Stufe 3; Zufallsname wählbar; erst ab 10 Teilnehmenden sichtbar; kein Abruf ohne Anmeldung (Code prüfen ❔, geprüft: siehe Prüfvermerk 1); im Wortlaut: Mitspielende sehen deinen Namen, Zufallsname schützt; Übergang: alle zurückgesetzt und neu gefragt | gering bis mittel |
| V28 | Widerruf (#853) | Widerruf schwerer als Erteilung (Art. 7 Abs. 3) | Nein/Aus/Widerruf immer speicherbar, auch bei Schalter aus; Widerruf entfernt Rangliste, Punkte, Abzeichen sofort; sichtbarer Weg auf der Datenschutzseite (Folge-PR) **Bedingung fürs Go**, spätestens vor Vorhut-Ausweitung | gering, sobald Folge-PR da |
| V28 | Punkte aus Nutzungsereignissen, 90 Tage (ab 2. Saison 100) | Profilbildung über Zeit | nur mit Stufe ≥2; Löschung nach Frist (LOESCHKONZEPT); 100 Tage nur für neu erhobene Ereignisse, DSE vorher | gering |
| V28 | Punkt je Bewertung fremder Beiträge, ≤3/Tag, Richtung zählt nicht | Rückschluss auf Meinung | Richtung fließt nicht ein; Deckel | gering |
| V28 | Muster-Hinweise und Paar-Prüfwerte (Zweitkonten/Absprachen) | Verdacht gegen Einzelne, Art.-9-Profil | nur wenn beide aktuell eingewilligt (auch beim Erzeugen geprüft); Prüfwerte ohne Kontozuordnung, Schlüssel nur im Arbeitsspeicher, nicht einzeln löschbar, Verfall 7 Tage; Hinweise (am Konto) beim Widerruf sofort gelöscht; nur Admin, ein Mensch entscheidet, keine automatische Sperre (Art. 22 greift nicht ❔) | gering. Zustimmungen als weiteres Merkmal: **offen**, braucht neue Kennung, bis dahin nicht gebaut (siehe Prüfvermerk 2) |
| V9a | Deckel für Nutzungen ohne Anmeldung (#857): Platz-Prüfwert aus Beitrag, Tag, Platznummer | Erfassung Besuchender | kein Besuchermerkmal, kein Speicherzugriff im Endgerät (also kein § 25 TDDDG ❔); ≤3 je Beitrag und Tag | gering |
| V9a | öffentliche Saison-Summe (#814), Zähler „Meldungen ohne Konto“ | Einzelne erkennbar bei kleinen Zahlen | erst ab 3 Wochen × 25 Personen; Drosselung insgesamt, ohne Adresse | gering |
| V10 | „Dein nächster Schritt“ (#789/#816), Antworten-Hinweis (#760) | Profil aus eigenem Verhalten | beim Abruf berechnet, nichts gespeichert; Weggeklicktes nur im Browser 7 Tage | gering |
| V21 | Profilbildwahl, „schon gesehen“, „Ton bei Erfolgen“ (#809) | Speicher im Endgerät | vom Nutzer gewünscht (§ 25 Abs. 2 Nr. 2 TDDDG ❔) | gering |
| V23/V29 | Teams nach Gruppe, Team-Fortschritt/Quests (#813/#815) | Rückschluss auf Einzelne im Team (auch aus der Differenz zweier Stände) | Team-Summe erst ab 5 Mitgliedern; Gruppenname nur mit schriftlicher Zustimmung; Option: Summe nur wöchentlich | gering |
| V31 | Wirkungs-Echo, Danke-Knopf (#817), Spalte gesehene_nutzung.echo | Autor erfährt Nutzung | nur Zahlen, keine Personen; danke_ohne_konto bleibt aus | gering |

**Schwelle (Art. 35 Abs. 1):** DSFA durchgeführt, weil zwei Kriterien vorliegen (Daten zu
politischer Meinung, Bewertung/Scoring); dagegen stehen kleiner Kreis, Freiwilligkeit,
Voreinstellung aus, Pseudonymwahl.

**Bedingungen fürs Go:** sichtbarer Widerrufsweg (#853-Folge-PR), Rangliste ohne Abruf ohne
Anmeldung (✅, Prüfvermerk 1), Wortlaut Stufe 3 (✅ gelesen am 27.11.2026 in
`ss/domain/spielgefuehl.py`, Zeilen 93–104 auf `main`), DSE und VVT ergänzt vor dem Einschalten.
Offen ❔: Mindestalter 16 für Stufe ≥2 (Art. 8, falls Mitglieder unter 16 die App nutzen).

**Restrisiko gesamt:** kein hohes. Begründung: Jede Verarbeitung mit Profil- oder
Vergleichscharakter hängt an einer gesonderten, widerrufbaren Einwilligung ohne Vorauswahl.
Sichtbar wird nur, wer es wählt, auf Wunsch unter Zufallsnamen. Fristen sind kurz (7 bis 100
Tage), Ereignisse ohne Konto tragen kein Besuchermerkmal, und kleine Zahlen sind gesperrt.
**Ausgenommen** und deshalb aus: teams_oeffentlich, merkliste, aufrufe_zaehlen. Für sie wäre
ein hohes Restrisiko möglich, also gesonderte Prüfung und gegebenenfalls Konsultation der
Aufsicht (Art. 36, bis 8 Wochen 📖) nach der BDK.

## Prüfvermerke am Code

1. **Rangliste ohne Anmeldung nicht abrufbar: bestätigt.** Beide Endpunkte
   (`GET /api/v1/rangliste` und `PUT /api/v1/rangliste/einwilligung`) hängen an
   `Depends(require_user)` (`ss/api/v1/rangliste.py:161` und `:211`). `require_user`
   antwortet 401, wenn `X-User` fehlt oder `anonymous` ist, wie es das BFF für öffentliche
   Aufrufe setzt (`ss/dependencies.py:769–779`). Der Test `test_ohne_anmeldung_401`
   (`ss/tests/unit/api/test_rangliste_api.py:215`) prüft beide Endpunkte auf 401.
2. **Zustimmungen in der Muster-Prüfung: nicht gebaut.** Muster-Hinweise entstehen nur aus
   Nutzungen: Der einzige Aufruf von `nutzung_melden` steht im Zähl-Endpunkt
   `POST /content/{content_id}/usage` (`ss/api/v1/usage.py:521–533`), und zwar nur mit
   eingeschalteten Punkten und wenn beide Konten in die Punkte eingewilligt haben (die
   Prüfung „beim Erzeugen“ aus der Tabelle). Bewertungen und Zustimmungen rufen die
   Muster-Prüfung nirgends auf (`ss/services/muster_hinweise_service.py`, Kopf und
   `nutzung_melden`).
