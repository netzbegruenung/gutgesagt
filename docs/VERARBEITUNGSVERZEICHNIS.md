# Verzeichnis der Verarbeitungstätigkeiten (Art. 30 DSGVO)

> **Entwurf, nicht juristisch geprüft, nicht beschlossen.** Keine Rechtsberatung. Führen muss das
> Verzeichnis der Verantwortliche (Art. 30 Abs. 1); dieser Entwurf leitet es aus Code und Doku
> ab, damit der Vorstand es übernehmen kann. Aussagen ohne Beleg im Repo stehen als **offen** da.

Stand 27.11.2026, Code `main` @ `bdc2093d` (letzter Tag `v0.9.14`). Grundlage sind die
Datenschutz-Folgenabschätzung ([`docs/DSFA.md`](./DSFA.md), Verarbeitungen V1 bis V22 in
Abschnitt 8.2) mit dem Nachtrag Spielgefühl
([`docs/DSFA_NACHTRAG_SPIELGEFUEHL.md`](./DSFA_NACHTRAG_SPIELGEFUEHL.md), V28 bis V31), das
Löschkonzept ([`docs/LOESCHKONZEPT.md`](./LOESCHKONZEPT.md), `LK`), die
Art.-9-Einwilligung ([`docs/ART9_EINWILLIGUNG.md`](./ART9_EINWILLIGUNG.md)) und die
Datenschutzerklärung (`mvp/frontend/gutgesagt-frontend/src/app/datenschutz/datenschutz.component.html`, `DSE`).
Die Datenschutzerklärung zitieren wir mit dem Titel ihres Abschnitts, das Löschkonzept ebenso.
Begriffe wie in [`GLOSSARY.md`](../GLOSSARY.md).

**Warum ein Verzeichnis:** Die Ausnahme für Stellen unter 250 Beschäftigten (Art. 30 Abs. 5)
greift nicht: Gut gesagt verarbeitet Daten nach Art. 9 Abs. 1 (politische Meinung) und das nicht
nur gelegentlich.

**Pflege:** Wer eine Verarbeitung neu baut oder ändert, zieht im selben PR die DSFA (Abschnitt
8.2) und dieses Verzeichnis mit; Fristen stehen nur im Löschkonzept, hier steht der Verweis.

## Allgemeine Angaben (Art. 30 Abs. 1 lit. a, d, e, g)

- **Verantwortlicher:** NETZBEGRÜNUNG — Verein für grüne Netzkultur e. V., vertreten durch den
  Vorstand nach § 26 BGB. Anschrift, Registereintrag und Kontakt wie im Impressum und in der
  Datenschutzerklärung, Abschnitt „Verantwortlicher“ (Angaben aus
  `mvp/frontend/gutgesagt-frontend/src/app/shared/legal-entity.ts`).
  **Bewusste Lücke:** Dieses Verzeichnis liegt in einem öffentlichen Repository und nennt deshalb
  weder Namen noch Kontaktdaten. In der Fassung, die der Verein führt und der Aufsicht auf
  Anfrage vorlegt (Art. 30 Abs. 4), trägt er Name und Kontakt des Verantwortlichen und des
  Datenschutzbeauftragten selbst ein.
- **Gemeinsam Verantwortliche, Vertreter (Art. 27):** keine.
- **Datenschutzbeauftragter:** benannt; Kontakt wie in der Datenschutzerklärung, Abschnitt
  „Datenschutzbeauftragter“ (Angabe `DSB_KONTAKT` in
  `mvp/frontend/gutgesagt-frontend/src/app/datenschutz/datenschutz.component.ts`).
- **Empfänger, für alle Tätigkeiten gleich:**
  - verdigado eG als Auftragsverarbeiterin für Server, Anmeldedienst und Mailversand des
    Anmeldedienstes; laut Datenschutzerklärung mit der Hetzner Online GmbH als
    Unterauftragsverarbeiterin, Rechenzentrum in Deutschland (DSE „Wo deine Daten liegen“).
    **Offen:** ob ein AV-Vertrag nach Art. 28 Abs. 3 Gut gesagt mit Zweck, Datenarten (auch
    Art. 9) und Betroffenen erfasst, und welche Rolle Hetzner hat (DSFA 8.6, F1; #506).
  - SMTP-Server für Mails zu Meldungen und Entscheidungen, aus der Konfiguration
    (`smtp_host` in `mvp/backend/semantic-search-service/app/core/config.py`). **Offen:** welcher Server in Produktion, wer ihn
    betreibt (DSFA 8.6, F2).
  - Intern: Admins der Plattform (Rolle aus dem Anmeldedienst oder der Liste `admin_users`,
    `docs/ARCHITECTURE.md`). **Offen:** wer Admin ist und wer Zugang zu Host, Datenbank und
    Konfiguration hat (DSFA 8.6, F4).
  - Keine Weitergabe an Dritte, keine Analysedienste, kein KI-Anbieter (DSE „Wo deine Daten
    liegen“, `CLAUDE.md` „Datenschutz — keine KI-Anbieter“).
- **Übermittlung in Drittländer (lit. e):** keine (DSE „Keine Übermittlung außerhalb der EU“).
  Bilder von fremden Servern lädt der Browser der Person erst nach Klick (DSE „Bilder von fremden
  Servern“, T11).
- **Technische und organisatorische Maßnahmen (lit. g, Art. 32 Abs. 1):** je Tätigkeit unter
  „TOM“ mit Verweis auf die Maßnahmen der DSFA. Für alle gelten:
  - Pseudonymisierung: In der Datenbank steht die Kennung des Kontos, kein Name und keine
    E-Mail-Adresse; Prüfwerte und Tagespseudonyme als HMAC, die Schlüssel der Prüfwerte und der
    Besucher nur im Arbeitsspeicher (DSFA V7, V9, V11).
  - Datenminimierung: Zähler statt Einzelzeilen, wo möglich (DSFA 8.5).
  - Automatische Löschung nach Fristen durch einen täglichen Task (LK „Fristen“), Löschen einer
    Person von Hand nach dem Löschkonzept (LK „Ablauf“).
  - Zugriffsschutz: Kennungen, Meldungen und Muster-Hinweise nur für Admins; Mitwirkung nur mit
    Art.-9-Einwilligung, durch einen Test abgesichert (`docs/ART9_EINWILLIGUNG.md` „Sperren“).
  - Protokolle der Anwendung ohne Suchtexte und mit gekürzter Kennung (LK „Was nicht gelöscht
    wird“).
  - Sicherungen täglich, 7 Tages- und 4 Wochenstände (`mvp/scripts/backup/backup.sh`).
  - **Offen:** Verschlüsselung der Sicherungen (das Skript verschlüsselt nicht; DSFA 8.6, F3),
    Rollen- und Zugriffskonzept (F4), Frist der Protokolle am Host (F6).

## Verarbeitungstätigkeiten (Art. 30 Abs. 1 lit. b, c, d, f)

Rechtsgrundlagen wie in der Datenschutzerklärung; juristisch geprüft hat sie niemand (#296).
„Art.-9-Einwilligung“ heißt Art. 9 Abs. 2 lit. a DSGVO, eingeholt nach dem ersten Anmelden
(`docs/ART9_EINWILLIGUNG.md`).

### T1 Konten, Anmeldung und Anzeigename

- **Zweck:** Anmelden, Mitwirkung einem Konto zuordnen, Anzeigename an Beiträgen; Konten auf
  Einladung einrichten; Bedienung im Browser.
- **Rechtsgrundlage:** Art. 6 Abs. 1 lit. b (Konto, Einladung, Beta-Zugang), lit. f
  (Anzeigename, Missbrauchsabwehr bei Einladungen); § 25 Abs. 2 TDDDG für Einträge im Browser.
- **Betroffene:** Mitglieder der Netzbegrünung mit Netzbegrünung-Login, Personen mit Konto aus
  einer Einladung, Personen mit Beta-Zugang.
- **Daten:** Kennung, Anzeigename (Vorname und Initial); Kennung, E-Mail-Adresse und Name im
  verschlüsselten Anmelde-Cookie; bei Konten aus Einladungen im Anmeldedienst E-Mail-Adresse,
  Vor- und Nachname und Passwort-Hash (DSE „Konto aus einer Einladung“); in der Plattform die
  Zustimmung zu den Nutzungsbedingungen (Kennung, Zeitpunkt, Stand) und das Archiv der bis zur
  Umstellung im Anmeldedienst gespeicherten Zustimmungszeitpunkte; beim Beta-Zugang E-Mail-Adresse, Anzeigename und Prüfsumme des
  Passworts in einer Konfigurationsdatei; Anmelde-Cookie; an Einladungen nur Zähler und Notiz, bei
  einem Teamlink dazu Teamname, Motiv, Saison und Teamart, bei einem Team nach Gruppe der Tag
  der schriftlichen Zustimmung der Gruppenleitung ohne Namen (Mitgliedschaften unter T13).
  Im Browser bis zum Tabschluss, höchstens eine Stunde, ein angefangener Kommentar mit Prüfwert
  des Kontos (DSE „Weitere Einträge“, E1).
  Schon das Konto kann eine politische Nähe erkennen lassen (Art. 9).
- **Empfänger:** wie oben; der Anzeigename ist für andere Angemeldete sichtbar, nicht für
  Besucher.
- **Fristen:** LK „Fristen“ (nie benutzte Konten aus Einladungen) und „Ablauf“
  (Kontolöschung); LK „Fristen außerhalb des täglichen Tasks“: Anmelde-Cookie 14 Tage nach
  letzter Nutzung, Beta-Zugänge bis von Hand entfernt.
- **TOM:** DSFA V1, V15, V19, V21. **Offen:** Anzeigename entsteht vor der
  Art.-9-Einwilligung (DSFA V1, Abschnitt 4).

### T2 Einwilligungen

- **Zweck:** Rechtsgrundlage der Mitwirkung einholen und nachweisen; gesonderte Zustimmung zur
  Sichtbarkeit der Meilenstein-Abzeichen; Zustimmung zu den Nutzungsbedingungen (auf derselben
  Seite, eigenes Häkchen) nachweisen.
- **Rechtsgrundlage:** Art. 9 Abs. 2 lit. a, Nachweis nach Art. 7 Abs. 1; für die
  Abzeichen Art. 6 Abs. 1 lit. a und Art. 9 Abs. 2 lit. a; für die Zustimmung zu den
  Nutzungsbedingungen Art. 6 Abs. 1 lit. b.
- **Betroffene:** angemeldete Personen.
- **Daten:** Kennung, Zeitpunkt, Kennung des Wortlauts, Zeitpunkt des Widerrufs; je Antwort zur
  Sichtbarkeit Kennung, Ja/Nein, Wortlaut, Zeitpunkt; je Widerruf ein Löschauftrag mit Kennung,
  Zeitpunkt, Frist und Zeitpunkt der Ausführung; je Zustimmung zu den Nutzungsbedingungen
  Kennung, Zeitpunkt und Stand (`nutzungsbedingungen_zustimmungen`).
- **Empfänger:** wie oben, nur Admins in der Datenbank.
- **Fristen:** solange das Konto besteht, auch widerrufene (LK „Ablauf“, Schritt 2; für die
  Abzeichen auch LK „Fristen“); Löschaufträge offen bis zur Ausführung, erledigte nach LK
  „Fristen“, alle mit dem Konto.
- **TOM:** DSFA V2, V22. Mit #658 löscht ein Widerruf die Stimmen der Person (T4). Für Beiträge,
  Einwürfe und Sätze legt er einen Löschauftrag an, den ein Admin binnen sieben Tagen ausführt
  (DSFA V2, R9, Maßnahme R9b); bis dahin behalten sie ihren Personenbezug.

### T3 Beiträge, Einwürfe und Gegenlesen

- **Zweck:** durchsuchbarer Bestand an Argumenten, Rohmaterial im Fangkorb, Herkunft und
  Änderungsverlauf nachvollziehen; beim Schreiben Anmerkungen, Sprachhinweis und
  Kürzungsvorschlag zeigen.
- **Rechtsgrundlage:** Art. 6 Abs. 1 lit. b, lit. f für Herkunft und Änderungsverlauf;
  zusätzlich Art.-9-Einwilligung. Gegenlesen: lit. b, ohne Speicherung.
- **Betroffene:** Mitwirkende; Dritte, die in Beiträgen, Links oder „Gepostet von“ genannt
  sind.
- **Daten:** Text, Kennung von Autor und letzter Änderung, Zeitpunkte, Änderungsverlauf ohne
  alten Wortlaut, Kennung des CC0-Hinweises; Einwürfe mit Hinweis, Link, Weg, bis zu zwei Themen und Kennungen der
  einwerfenden Person und der Personen mit Sätzen; Kontoname des ursprünglichen Posters. Daten
  Dritter, auch deren politische Zuordnung.
- **Empfänger:** Beiträge für alle, auch Besucher; der Anzeigename daran nur für Angemeldete;
  Einwürfe nur für Angemeldete; wegen CC0 darf jede Person Beiträge weiterverwenden.
- **Fristen:** LK „Fristen“ (gelöschte Beiträge, Einwürfe) und LK „Zwei Wege, einen Beitrag zu
  löschen“; Beiträge ohne Frist. Bei Kontolöschung werden Beiträge anonymisiert (LK „Ablauf“,
  Schritt 3), Sätze an fremden Einwürfen bekommen einen Platzhalter, eigene Einwürfe werden
  gelöscht (Schritt 2); dasselbe mit dem Löschauftrag nach einem Widerruf der Art.-9-Einwilligung
  (T2), dann bleibt das Konto.
- **TOM:** DSFA V3, V4, V20. **Offen:** Information der Dritten nach Art. 14 (DSFA V3, R3).

### T4 Bewertungen und Güte

- **Zweck:** Beiträge nach Brauchbarkeit sortieren, Güte im Siegel zeigen.
- **Rechtsgrundlage:** Art. 6 Abs. 1 lit. b, zusätzlich Art.-9-Einwilligung.
- **Betroffene:** angemeldete Personen, die bewerten.
- **Daten:** Kennung, Beitrag, Richtung, Zeitpunkt; Güte und Summen nicht gespeichert.
- **Empfänger:** Summen und Güte für alle ab drei Stimmenden; Einzelstimmen nur Admins in der
  Datenbank.
- **Fristen:** LK „Fristen“ (Stimmen); mit #658 zusätzlich sofort beim Widerruf der
  Art.-9-Einwilligung.
- **TOM:** DSFA V5 (M5), R8.

### T5 Suche und Messung der Suche

- **Zweck:** Bestand aufbauen aus dem, was gesucht wird; Personen pro Tag zählen, die suchen;
  erkennen, wo Antworten fehlen.
- **Rechtsgrundlage:** Art. 6 Abs. 1 lit. f. Für das Tagespseudonym der Besucher **offen**
  mit § 25 TDDDG (DSFA V7, Abschnitt 6, Frage 3).
- **Betroffene:** alle, die suchen, angemeldet oder nicht; Dritte, die in Suchtexten genannt
  sind.
- **Daten:** Suchtext als Aussage ohne Autor; Suchereignisse mit Tag, Trefferzahl und
  Tagespseudonym (Besucher: aus Anschluss und Tag, ohne User-Agent; Angemeldete: aus Kennung und
  Tag); je Aussage und Woche Zahl der Suchen und Personen ohne Treffer.
- **Empfänger:** unbeantwortete Suchanfragen für alle, sobald jemand antwortet oder, wenn zwei
  Personen ohne Treffer danach suchten, nach Freigabe durch Admins (Vormoderation seit
  13.11.2026); Zähler für Angemeldete und Admins.
- **Fristen:** LK „Fristen“ (Suchereignisse bis zum Ende ihres Tages, dann zu Tageszählern
  verdichtet) und „Was nicht gelöscht wird“ (Suchanfragen als Aussage, Suchen ohne Treffer).
- **TOM:** DSFA V6, V7, V8. **Offen:** Schlüssel des Pseudonyms der Angemeldeten in Produktion
  gesetzt (DSFA 8.6, F5).

### T6 Messung der Nutzung und Rückmeldungen

- **Zweck:** erkennen, welche Beiträge gebraucht werden; Mitwirkenden zeigen, dass ihre Beiträge
  helfen; Zahl der Menschen je Woche, die nach dem Kopieren „Ja, gepostet“ melden.
- **Rechtsgrundlage:** Art. 6 Abs. 1 lit. f; für „Ja, gepostet“ zusätzlich
  Art.-9-Einwilligung.
- **Betroffene:** alle, die kopieren oder teilen; Mitwirkende, deren Beiträge genutzt werden.
- **Daten:** Nutzungsereignisse ohne Kennung (Beitrag, Art, Zeitpunkt, Geräteklasse, Fassung);
  Prüfwert der entdoppelten Nutzung; je Kennung zwei Zählerstände für die Rückmeldung und „Seit deinem letzten Besuch“ (Nutzung, Einwürfe anderer; kein Zeitpunkt, aus dem Einwurf-Stand und `raw_inputs.created_at` nur grob ableitbar, für Admins mit DB-Zugriff; zwei weitere Zahlen über 7 Tage nur beim Besuch berechnet, nicht gespeichert, #741; mit dem Schalter `antworten_hinweis` eine dritte: neue Antworten anderer auf eigene Aussagen, ebenso nur berechnet, und die Liste „Meine Aussagen“ nur für die Person selbst, #760); je Person und
  Woche ein Prüfwert „Ja, gepostet“, danach nur die Zahl der Woche.
- **Empfänger:** Zähler an der Karte für alle; die Rückmeldung nur für die Person; Zahlen je
  Woche für Admins.
- **Fristen:** LK „Fristen“ (Prüfwerte, „Ja, gepostet“); Nutzungsereignisse 90 Tage als
  Einzelzeilen, danach nur Zähler je Beitrag (LK „Fristen außerhalb des täglichen Tasks“;
  `usage_retention_days` in `mvp/backend/semantic-search-service/app/core/config.py`, wirkt
  über den abschaltbaren Bereinigungsjob, Standard an; DSE „Verwendung von Beiträgen“); Zahl
  Zählerstände für die Rückmeldung bis zur Kontolöschung (LK „Ablauf“, Schritt 2).
- **TOM:** DSFA V9, V9a, V10. „Ja, gepostet“ hinter dem Schalter `gepostet_aktiv`.

### T7 Punkte, Meilensteine, Abzeichen und Muster-Hinweise (gebaut, ausgeschaltet)

- **Zweck:** Wirkung der Mitwirkung zeigen, Anerkennung sichtbar machen, Punkte gegen Absprachen
  schützen.
- **Rechtsgrundlage:** Art. 6 Abs. 1 lit. a und Art. 9 Abs. 2 lit. a über die eigene, freiwillige
  Einwilligung „Punkte und Meilensteine“ (`punkte_einwilligung`, #351), getrennt von der
  Art.-9-Einwilligung zum Beitragen (seit deren Wortlaut `2026-11-13`, Entscheidung Maintainer
  13.11.2026; Kopplungsverbot, Art. 7 Abs. 4); Sichtbarkeit der Abzeichen mit gesonderter
  Zustimmung (T2).
- **Betroffene:** angemeldete Personen mit Einwilligung „Punkte und Meilensteine“, ohne
  Startkonten; Muster-Hinweise nur, wenn beide Konten eingewilligt haben.
- **Daten:** Punkte und Meilensteine nicht gespeichert, bei jedem Abruf berechnet, seit
  20.11.2026 auch aus den eigenen Bewertungen (T4) je Tag; Paar-Prüfwerte; Muster-Hinweise mit zwei Kennungen; je Antwort auf die Einwilligung eine
  Zeile mit Kennung, ja/nein, Wortlaut und Zeitpunkt.
- **Empfänger:** Punkte nur für die Person; Abzeichen für andere Angemeldete mit Zustimmung;
  Muster-Hinweise nur für Admins.
- **Fristen:** LK „Fristen“ (Paar-Prüfwerte, Muster-Hinweise, Abzeichen).
- **TOM:** DSFA Abschnitt 3, V11, V22. Eigene Einwilligung „Punkte und Meilensteine“ gebaut (#668, `PUNKTE_EINWILLIGUNG_GEBAUT`). Schalter `punkte_aktiv` und `abzeichen_sichtbar_aktiv`,
  Standard aus; einschalten erst nach Übernahme der DSFA (DSFA Abschnitt 7). Mit Schalter
  `spielgefuehl_buehne` gelten T16 (Punkte, Rangliste) und T18 (Muster-Hinweise).

### T8 Meldungen, Sperren und Widerspruch

- **Zweck:** gemeldete Inhalte prüfen, Entscheidungen mitteilen, Widerspruch prüfen (DSA).
- **Rechtsgrundlage:** Art. 6 Abs. 1 lit. c mit Art. 16, 17 und 20 DSA; lit. f für
  Rate-Limit und Tagespseudonym.
- **Betroffene:** meldende Personen, angemeldet oder nicht; Autorinnen und Autoren gemeldeter
  oder gesperrter Beiträge; Admins.
- **Daten:** Beitrag, Grund, Freitext, Erklärung guten Glaubens, freiwillig Name und
  E-Mail-Adresse, Kennung oder Tagespseudonym, Bearbeitungsvermerk; Sperrgrund, Begründung,
  Kennungen, Widerspruch, Prüfergebnis.
- **Empfänger:** Admins; Mails an die meldende Person über den SMTP-Server (siehe oben); die
  Entscheidung an die betroffene Person.
- **Fristen:** LK „Fristen“ (Meldungen, Sperren, Tagespseudonym an Meldungen).
- **TOM:** DSFA V12, V13; Auskunft und Löschung für Personen ohne Konto über „Nach Person“
  (LK „Fristen“, Meldungen).

### T9 Feedback

- **Zweck:** Plattform verbessern, auf Feedback antworten.
- **Rechtsgrundlage:** Art. 6 Abs. 1 lit. f.
- **Betroffene:** Personen, die Feedback geben.
- **Daten:** Text, freiwillige Kontaktangabe, Tag; keine Kennung.
- **Empfänger:** Admins.
- **Fristen:** LK „Feedback“.
- **TOM:** DSFA V14.

### T10 Betrieb: Protokolle, Sicherungen, Schutz vor Missbrauch

- **Zweck:** Betrieb, Fehlersuche, Abwehr von Angriffen und Überlastung, Wiederherstellung.
- **Rechtsgrundlage:** Art. 6 Abs. 1 lit. f (DSE „Protokolldateien“); Sicherungen teilen die
  Rechtsgrundlage der gesicherten Daten und dienen Art. 32 Abs. 1 lit. c.
- **Betroffene:** alle, die die Plattform aufrufen.
- **Daten:** im vorgelagerten Webserver volle IP-Adresse, Zeitpunkt, aufgerufene Adresse,
  verweisende Seite, Angaben zu Browser und Betriebssystem (User-Agent); im Webserver der
  Anwendung Zeitpunkt, aufgerufene Seite ohne Suchtext, Ergebnis und User-Agent, ohne die
  IP-Adresse der Person und ohne verweisende Seite, für Suchen keine Zeile (DSE „Zugriffe
  innerhalb der Anwendung“); in den Protokollen der Anwendung gekürzte Kennung ohne Suchtext; für Rate-Limits gekürzte Adresse oder Kennung nur im
  Arbeitsspeicher; in Sicherungen alle Datenbanken.
- **Empfänger:** wie oben (Betrieb bei der Auftragsverarbeiterin).
- **Fristen:** LK „Fristen außerhalb des täglichen Tasks“: vorgelagerter Webserver 14 Tage,
  Rate-Limits höchstens etwa 16 Minuten, Sicherungen bis zu 28 Tage. **Offen:** Protokolle der Anwendung und des Frontend-nginx haben in Produktion keine
  Frist (DSFA V16, 8.6, F6; #485, #336).
- **TOM:** DSFA V16, V17, V18. **Offen:** Verschlüsselung der Sicherungen (DSFA 8.6, F3).

### T11 Bilder von fremden Servern

- **Zweck:** ein Bild zeigen, das in einem Beitrag über eine Adresse eingebunden ist.
- **Rechtsgrundlage:** Art. 6 Abs. 1 lit. f (DSE „Bilder von fremden Servern“).
- **Betroffene:** alle, die ein solches Bild laden, angemeldet oder nicht.
- **Daten:** IP-Adresse und Angaben zum Browser, die der Browser beim Laden an den fremden
  Server schickt; bei Gut gesagt wird der Klick nicht gespeichert.
- **Empfänger:** der Betreiber des fremden Servers, den die einstellende Person eingetragen hat;
  welcher, steht vorher nicht fest. Der Browser der Person spricht ihn direkt an; dass er außerhalb
  der EU sitzt, ist nicht ausgeschlossen (lit. e oben).
- **Fristen:** bei Gut gesagt keine Speicherung; beim fremden Server unbekannt.
- **TOM:** Platzhalter „Bild laden“, das Bild lädt erst nach Klick und nur für dieses eine Bild;
  der Klick wird nicht gemerkt (DSE „Bilder von fremden Servern“).

### T12 Herkunft prüfen (gebaut, ausgeschaltet)

- **Zweck:** tote oder umgezogene Links unter „Herkunft“ für Admins auflisten (#759).
- **Personenbezug:** keiner. Der Dienst ruft die Adressen der Herkünfte nachts selbst ab, ohne
  Bezug zu einer Person: kein Cookie, ein User-Agent nur mit dem Namen des Werkzeugs
  (`GutGesagt-Herkunftspruefung/1.0`). Der fremde Server sieht die IP-Adresse des Servers von
  Gut gesagt, nicht die einer Person. Gespeichert werden Adresse, Ergebnis, Status, Ziel und
  Zeitpunkte (`herkunft_pruefung`), ohne Kennung oder Beitrag.
- **TOM:** Schalter `herkunft_pruefen` (Standard aus); nur http/https, keine internen Adressen,
  auch nicht nach Weiterleitungen (`utils/sicherer_abruf.py`); höchstens ein Abruf je Sekunde.
  Als Eintrag geführt, weil der Dienst damit fremde Server anspricht.

### T13 Teams über Einladungen (gebaut, ausgeschaltet)

- **Zweck:** der Person zeigen, in welchen Teams sie dabei ist, und die Nummer im Team vergeben
  (GLOSSARY „Team“, „Teamlink“, „Mitgliedschaft“, „Saison“); mit derselben Einwilligung die
  Zahl der Beiträge, Bewertungen und Kommentare und der Meldungen „Ja, gepostet“ in eine Summe
  des Teams einbeziehen (gebaut, T17); später, mit eigener Einwilligung
  und eigenem Schalter, die Teams der aktuellen Saison am Anzeigenamen zeigen.
- **Rechtsgrundlage:** Art. 6 Abs. 1 lit. a und Art. 9 Abs. 2 lit. a über eine eigene,
  ausdrückliche Einwilligung je Team (Wortlaut `team-2026-11-26`, Knopf „Ja, speichert, dass ich
  im Team X bin“, gleichwertig „Nein, ohne Team weiter“), getrennt von der Art.-9-Einwilligung
  und von „Punkte und Meilensteine“; für die Anzeige am Namen eine zweite, eigene Einwilligung
  (`team-oeffentlich-2026-11-25`). DSE „Teams“.
- **Betroffene:** angemeldete Personen, die über einen Teamlink beitreten oder ein Konto
  anlegen und einwilligen.
- **Daten:** je Mitgliedschaft Kennung, Teamname, Motiv, Saison, laufende Nummer, Tag des
  Beitritts, Kennung des Wortlauts und Zeitpunkt der Einwilligung (`team_mitgliedschaften`),
  ohne Bezug zur Einladung; je Konto die jüngste Antwort auf die Anzeige am Namen
  (`team_oeffentlich`); Zähler je Team und Saison ohne Kennung (`team_nummern`); die aktuelle
  Saison mit der Kennung des ändernden Admins (`einstellungen`). Zusammen mit dem Teamnamen
  kann die Mitgliedschaft auf politische Haltung und Ort schließen lassen (Art. 9).
- **Empfänger:** die Person selbst („Meine Teams“); Admins nur die Zahl der Mitglieder je
  Team, keine Liste, kein Export, keine API; am Namen für andere Angemeldete nur mit Schalter
  `teams_oeffentlich` und zweiter Einwilligung, Besucher nie; die Summe des Teams (gebaut,
  T17) nur Mitglieder des Teams, nur für abgeschlossene Wochen, erst ab fünf Einwilligenden,
  gerundet und ohne Namen.
- **Fristen:** LK „Teams“ und „Fristen“: „Team verlassen“ löscht sofort, die Kontolöschung
  alle Mitgliedschaften (LK „Ablauf“, Schritt 2); Sicherungskopien bis zu ihrem Ablauf.
- **TOM:** DSFA-Nachtrag „Teams“. Schalter `teams` (Obergrenze `SEMANTIC_SEARCH_TEAMS_AKTIV`) und
  `teams_oeffentlich` (eigene Obergrenze `SEMANTIC_SEARCH_TEAMS_OEFFENTLICH_AKTIV`, nicht an die
  Abzeichen gekoppelt), beide Standard aus; die Anzeige am Namen bleibt aus, bis der
  Datenschutzbeauftragte geraten hat. Teamnamen nach Anlass, Ort oder Saison oder, als Team
  nach Gruppe, nach einer Gruppe, die öffentlich unter diesem Namen auftritt, mit vorheriger
  schriftlicher, widerruflicher Zustimmung der Gruppenleitung (Tag der Zustimmung an der
  Einladung, nur für Admins; nach Widerruf wird das Team umbenannt,
  `mvp/scripts/manual/team_umbenennen.sql`); die Gruppe bekommt nie Namen, Listen oder
  eigene Zahlen und steuert nichts; keine Namen, die eine weitere besondere Kategorie erkennen
  lassen (Hinweis im Admin-Formular, GLOSSARY „Team“). Keine Nummer am Namen.

### T14 Merkliste (gebaut, ausgeschaltet)

- **Zweck:** Beiträge, die eine Person öfter braucht, für sie selbst vormerken und unter „Meine
  Beiträge“, „Gemerkt“ wiederfinden (#758).
- **Rechtsgrundlage:** Art. 6 Abs. 1 lit. b, zusätzlich Art.-9-Einwilligung: Was jemand merkt,
  kann politische Meinungen erkennen lassen. Ohne Einwilligung kein Merken (403). Offen vor
  dem Einschalten (neuer Zweck): eigener Einwilligungswortlaut, DSFA-Abschnitt und Absatz der
  Datenschutzerklärung; Entwürfe im PR zu #758.
- **Betroffene:** angemeldete Personen, die etwas merken.
- **Daten:** Kennung, Beitrag, Zeitpunkt des letzten Merkens (Tabelle `merkliste`).
- **Empfänger:** nur die Person selbst; keine Zähler für andere. Admins nur in der Datenbank.
- **Fristen:** LK „Fristen“: bis die Person den Eintrag entfernt, mit dem Konto, sofort beim
  Widerruf der Art.-9-Einwilligung und mit dem endgültig entfernten Beitrag; höchstens 500
  Einträge je Person.
- **TOM:** hinter dem Schalter `merkliste` (Standard aus), nur über die eigene Kennung aus der
  Anmeldung erreichbar (`X-User`, #284).

### T15 Seitenaufrufe und Besucher je Tag (gebaut, ausgeschaltet)

- **Zweck:** zählen, wie viele Menschen die App an einem Tag öffnen, auch ohne Suche (#761).
- **Rechtsgrundlage:** Art. 6 Abs. 1 lit. f; für das Tagespseudonym der Besucher **offen** mit
  § 25 TDDDG wie T5 (DSFA V7, `docs/FRAGEN_DATENSCHUTZBEAUFTRAGTE.md` Frage 2). Gezählt wird am
  Server aus Abrufen, die die App ohnehin macht; der Browser schickt keine eigene Zähl-Anfrage.
- **Betroffene:** alle, die die Startseite, eine Suche, ein Thema oder einen Beitrag abrufen,
  angemeldet oder nicht.
- **Daten:** je Besucher und laufendem Tag ein Tagespseudonym aus Anschluss und Tag (eigener
  Raum, nicht verknüpfbar mit dem an Suchereignissen) und die Zahl der Aufrufe; keine
  IP-Adresse, keine Kennung, kein Pfad, nichts im Browser. Im Arbeitsspeicher bis Mitternacht
  ein Prüfwert aus Pseudonym und Seite (Wiederholsperre). Danach je Tag zwei Zahlen.
- **Empfänger:** Admins (Kennzahlen).
- **Fristen:** LK „Fristen“ (Pseudonyme bis zum Ende ihres Tages).
- **TOM:** Schalter `aufrufe_zaehlen`, Obergrenze Standard aus, mit Einschalt-Hinweis;
  dieselbe Seite binnen 5 Minuten zählt einmal; höchstens 500 Aufrufe je Besucher und Tag;
  Rate-Limit je Anschluss.

### T16 Spielgefühl, Rangliste und Punkte (DSFA V28; gebaut, ausgeschaltet)

- **Zweck:** Mitwirkenden auf Wunsch die Wirkung ihrer Mitwirkung als Punkte zeigen und, wenn sie
  es wählen, in einer Saison-Rangliste mit anderen Mitspielenden vergleichen.
- **Rechtsgrundlage:** Art. 6 Abs. 1 lit. a und Art. 9 Abs. 2 lit. a über eine eigene,
  freiwillige Einwilligung, die Frage „Spielgefühl“ (Wortlaut `spielgefuehl-2026-11-28`, eine
  Fassung mit Quest-Punkten und Zustimmungen, die die Frage immer zeigt;
  `spielgefuehl-2026-11-26` und `spielgefuehl-2026-11-27` gelten weiter, bis neu gefragt wird).
  Drei gleichwertige Knöpfe ohne Vorauswahl: „Aus“, „Nur für mich“, „In der
  Saison-Rangliste mitspielen“. Getrennt von der Art.-9-Einwilligung zum Beitragen (Art. 7
  Abs. 4). Ersetzt mit Schalter `spielgefuehl_buehne` die Einwilligungen „Punkte und
  Meilensteine“, Abzeichen am Namen und Rangliste (T7). DSE „Spielgefühl“.
- **Betroffene:** angemeldete Personen mit Stufe „Nur für mich“ oder „Saison-Rangliste“, ohne
  Startkonten. In der Rangliste sichtbar nur Personen der Stufe 3.
- **Daten:** je Antwort eine Zeile mit Kennung, Stufe, Namenswahl (Anzeigename oder
  Zufallsname), Ranglistenname, Kennung des Wortlauts und Zeitpunkt (`spielgefuehl`, auch
  „Aus“). Punkte, Plätze und Abzeichen werden nicht gespeichert, sondern bei jedem Abruf
  berechnet: aus der Nutzung der eigenen Beiträge (`usage_events`), aus Zustimmung anderer,
  eigenen Beiträgen, Einwürfen und Bewertungen fremder Beiträge (Richtung zählt nicht, höchstens
  3 je Tag (Standardwert der Konfiguration)) und aus Team-Quests (T17). Die Kombination kann politische Haltung und Aktivität
  erkennen lassen (Art. 9).
- **Empfänger:** Punkte nur die Person selbst. Rangliste (Name, Platz, Punkte, Abzeichen) nur
  angemeldete Mitspielende der Stufe 3, erst ab 10 Teilnehmenden, kein Abruf ohne Anmeldung.
  Admins nur in der Datenbank.
- **Fristen:** LK „Fristen“: `spielgefuehl` als Nachweis (Art. 7 Abs. 1), solange das Konto
  besteht. Nutzungsereignisse 90 Tage als Einzelzeilen. Widerruf („Aus“) nimmt die Person sofort
  aus Rangliste, Punkten und Abzeichen.
- **TOM:** DSFA-Nachtrag Spielgefühl, Zeilen V28. Schalter `punkte`, `rangliste`,
  `spielgefuehl_buehne`, Standard aus. Widerruf jederzeit auch bei ausgeschaltetem Schalter
  speicherbar, sichtbar auf der Datenschutzseite („Einwilligung widerrufen“) und in „Meine
  Beiträge“ (#862, #864). Rangliste nur mit Anmeldung (BFF und `require_user`), Mindestzahl 10.
  Zufallsname wählbar.

### T17 Team-Fortschritt und Team-Quests (DSFA V29; gebaut, ausgeschaltet)

- **Zweck:** Mitgliedern eines Teams zeigen, was das Team in der letzten abgeschlossenen Woche
  gemeinsam bewirkt hat, und ihnen ein gemeinsames Wochenziel aus dem Bedarf geben.
- **Rechtsgrundlage:** die Team-Einwilligung aus T13 (Wortlaut `team-2026-11-26`), die die
  Team-Summe ausdrücklich nennt (Art. 6 Abs. 1 lit. a, Art. 9 Abs. 2 lit. a). Für Quest-Punkte
  an der Person zusätzlich die Einwilligung aus T16 im Wortlaut `spielgefuehl-2026-11-28`, der
  die Quest-Punkte nennt (siehe „Offen“).
- **Betroffene:** Mitglieder von Teams mit Team-Einwilligung, ohne Startkonten.
- **Daten:** Wochenzähler je Team, Saison und Woche (Zahl der Beiträge einschließlich
  Kommentaren, Bewertungen und Meldungen „Ja, gepostet“, `team_wochen`). Je Team und Woche eine
  Quest mit Thema und Ziel (`team_quests`). Beides ohne Kennung, Beitrag und Zeitpunkt. Entdoppelt wird über
  einen Wochen-Prüfwert nur im Arbeitsspeicher, der Schlüssel entsteht jede Woche neu.
  Quest-Punkte werden beim Abruf berechnet und nicht gespeichert.
- **Empfänger:** nur Mitglieder des Teams, nur die letzte abgeschlossene Woche, erst ab 5
  Mitgliedern mit Einwilligung, gerundet, ohne Namen. Admins keine Liste. Bekannte
  Restinformation: „geschafft“ und das Ziel verraten grob die Zahl der Mitglieder mit
  Einwilligung.
- **Fristen:** LK „Fristen“: `team_wochen` und `team_quests` ohne Personenbezug, unbefristet,
  gehen mit dem Team (eine Team-Löschung gibt es noch nicht). Prüfwerte verfallen mit dem
  Wochenwechsel. „Team verlassen“ und die Kontolöschung lassen die Zähler stehen; das geht, weil
  sie keiner Person zugeordnet sind.
- **TOM:** DSFA-Nachtrag „Teams“ und Spielgefühl V23/V29. Schalter `team_fortschritt` (nur mit
  `teams`) und `team_quests` (nur mit `team_fortschritt`), Standard aus. Schwelle 5, Rundung,
  keine laufende Woche (gegen Rückschluss aus der Differenz zweier Stände).

### T18 Muster-Hinweise gegen Absprachen, auch aus Zustimmungen (DSFA V30; gebaut, ausgeschaltet)

- **Zweck:** Punkte und Rangliste vor Zweitkonten und Absprachen schützen. Admins einen Hinweis
  geben, wenn sich zwei Konten auffällig oft gegenseitig nutzen oder einander zustimmen;
  Letzteres nur mit Schalter `muster_stimmen`.
- **Rechtsgrundlage:** Art. 6 Abs. 1 lit. a und Art. 9 Abs. 2 lit. a über den Absatz zu
  Absprachen in der Einwilligung „Spielgefühl“ ab „Nur für mich“ (T16). Für Zustimmungen der
  Wortlaut `spielgefuehl-2026-11-27` oder `spielgefuehl-2026-11-28` plus die
  Art.-9-Einwilligung, beide bei beiden Konten. Ohne `spielgefuehl_buehne` gilt weiter T7.
- **Betroffene:** Paare angemeldeter Konten, die beide aktuell eingewilligt haben.
- **Daten:** Paar-Prüfwerte (HMAC, keinem Konto zuordenbar, Schlüssel nur im Arbeitsspeicher,
  `muster_pruefwerte`). Muster-Hinweise mit den Kennungen beider Konten, Art (Nutzung oder
  Zustimmung), erstem und letztem Tag und der Zahl der Tage mit gegenseitiger Nutzung bzw.
  Zustimmung (`muster_hinweise`). Ablehnungen zählen nicht.
- **Empfänger:** nur Admins; das Admin-Dashboard zeigt Anzeigename und Kennung beider Konten und
  prüft beim Zeigen erneut die Einwilligungen. Ein Mensch entscheidet; keine Wirkung auf Punkte
  oder Rangliste, keine automatische Sperre (Art. 22 greift nicht).
- **Fristen:** LK „Fristen“: Paar-Prüfwerte 7 Tage, Hinweise höchstens 56 Tage nach dem letzten
  Tag. Sofort gelöscht: alle Hinweise, die eine Person nennen, wenn sie „Aus“ wählt; die Hinweise
  aus Zustimmungen, wenn sie die Art.-9-Einwilligung widerruft oder auf einen Wortlaut ohne
  Zustimmungen zurückgeht. Im Übrigen spätestens im nächsten täglichen Lauf, sobald nicht mehr
  beide Konten wirksam eingewilligt haben.
- **TOM:** DSFA-Nachtrag V30, DSFA V11. Admins prüfen jeden Hinweis selbst und halten fest, wie
  sie geprüft haben (sonst kann trotz menschlicher Entscheidung Art. 22 greifen, EuGH
  C-634/21). Hinweise gehören zur Auskunft nach Art. 15; sie wird von Hand erteilt. Schalter
  `muster_stimmen`
  (Obergrenze aus, wirkt nur mit `spielgefuehl_buehne`); Einwilligung beim Erzeugen und beim
  Zeigen geprüft; täglicher Löschlauf unabhängig vom abschaltbaren Bereinigungsjob.

### T19 Wirkungs-Echo und Danke (DSFA V31; gebaut, ausgeschaltet)

- **Zweck:** Schreibenden zeigen, dass ihre Beiträge anderen helfen: wie oft sie öffentlich
  gepostet wurden und wie oft sich jemand bedankt hat.
- **Rechtsgrundlage:** getrennt nach Seite. Das Danke selbst samt Tages-Prüfwert: Art. 9 Abs. 2
  lit. a über die Art.-9-Einwilligung (403 ohne sie), weil ein Danke Zustimmung zu einem
  politischen Inhalt zeigt; offen ist, ob „Mitwirkung“ im Wortlaut `2026-11-13` das Danke trägt,
  obwohl die Aufzählung nur „Beiträge, Einwürfe, Sätze und Bewertungen“ nennt. Die Anzeige der
  Summen ohne Personenbezug an die Schreibenden und deren eigener Zählerstand: Art. 6 Abs. 1
  lit. f (DSE „Rückmeldung zur Nutzung deiner Beiträge“). Danke ohne Konto bleibt aus
  (`danke_ohne_konto`), deshalb hier kein § 25 TDDDG.
- **Betroffene:** Schreibende (Empfang der Summen); angemeldete Dankende mit
  Art.-9-Einwilligung; Personen, die „Ja, gepostet“ melden (T6).
- **Daten:** je Beitrag zwei Summen ohne Kennung und Zeitpunkt (`wirkung_je_beitrag`). Für das
  Danke ein Tages-Prüfwert in `nutzung_heute`, gelöscht mit dem Tageswechsel; beim Echo nur im
  Arbeitsspeicher. Je Konto ein Zählerstand „Echo beim letzten Besuch“ (`gesehene_nutzung`,
  Spalte `echo`).
- **Empfänger:** die schreibende Person sieht nur Summen, nie, wer gedankt oder gepostet hat.
  Admins nur in der Datenbank.
- **Fristen:** LK „Fristen“: Summen ohne Frist, ohne Personenbezug; Tages-Prüfwerte bis zum
  Tageswechsel; `gesehene_nutzung` geht mit dem Konto.
- **TOM:** DSFA-Nachtrag V31. Schalter `wirkungs_echo` und `danke_knopf`, nur zusammen, Standard
  aus. Höchstens ein Danke je Person, Beitrag und Tag; eigene Beiträge und Startkonten zählen
  nicht; Rate-Limit; keine Punkte für Danke.

## Offen

Gesammelt in DSFA 8.6: AV-Vertrag (F1), SMTP-Server (F2), Verschlüsselung der Sicherungen (F3),
Rollen und Zugriff (F4), Schlüssel des Tagespseudonyms (F5), Frist der Protokolle (F6). Dazu
die Lücken aus DSFA 8.5: Anzeigename vor der Einwilligung (T1), Widerruf ohne volle Folgen (T2, nach #658 nur Stimmen gelöscht).

Aus dem DSFA-Nachtrag Spielgefühl (T16 bis T19):

- Mindestalter 16 für Spielgefühl ab Stufe 2 (Art. 8), falls Mitglieder unter 16 die App
  nutzen.
- Rechtsgrundlage für Quest-Punkte: Wortlaut `spielgefuehl-2026-11-28` (T16).
- Danke (T19): im Art.-9-Wortlaut nicht ausdrücklich genannt. Mindestens die DSE ergänzen, dass
  das Danke auf der Einwilligung nach Art. 9 beruht; bei der nächsten Änderung des
  Art.-9-Wortlauts „Danke“ aufnehmen.
- DSE „Teams“: Satz ergänzen, dass Zahlen, die schon in die Team-Summe eingegangen sind, nach
  „Team verlassen“ als Zahl ohne Namen bleiben (Art. 7 Abs. 3, Art. 13 Abs. 2).
