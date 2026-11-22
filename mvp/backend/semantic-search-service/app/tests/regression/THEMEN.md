# Messset Themenvorschläge

Grundlage für die Schwellen der Themenvorschläge (#401, `services/themen_vorschlag.py`,
`themen_vorschlag_*` in `core/config.py`) und für jeden Modellwechsel (ADR 0005). Gemessen
wird, wie gut die vorgeschlagenen Themen zu den Themen passen, die ein Mensch einer Aussage
gegeben hat.

| Datei | Inhalt |
|---|---|
| `themen_messset.py` | vorläufiges Messset: 104 Aussagen mit ein bis drei Themen |
| `themen_messen.py` | Leave-one-out: Treffer, Precision und Recall je Schwelle, mit `--nli` auch mit zweiter Meinung, mit `--zeit` Antwortzeit und Speicher |
| `../unit/test_themen_messset_aufbau.py` | Aufbau ohne Modell (in CI) |
| `../integration/test_themen_vorschlag_einbettung.py` | Untergrenze mit echtem Einbettungsmodell |

```bash
cd mvp/backend/semantic-search-service/app
../venv/bin/python -m tests.regression.themen_messen                       # vorläufiges Messset
../venv/bin/python -m tests.regression.themen_messen --testset testset.json # Admin-Export
../venv/bin/python -m tests.regression.themen_messen --nli --zeit
```

## Welche Daten

Maßgeblich ist das **Testset**: die Zuordnungen von Hand aus Produktion, als Datei für Admins
unter `/themen/testset` (Glossar „Testset“). Es hat keine Personendaten, enthält aber Texte
aus Produktion und gehört deshalb nicht ins Repo; gemessen wird es mit `--testset`.

Bis es dort genug Zuordnungen gibt, misst das **vorläufige Messset** (`themen_messset.py`).
Die Themen darin hat ein Agent zugeordnet, nicht die Menschen, die Gut gesagt nutzen; die
Zahlen unten sind deshalb ein Anhaltspunkt, keine Abnahme. Es enthält die 30 Aussagen des
Startbestands und zwei weitere des Seeds wörtlich (von Menschen geschrieben, nicht für die
Messung) und 72 eigens formulierte, je Thema drei bis acht. Die Auswertung nennt beide Teile
getrennt.

## Verfahren

Je Thema ein Prototyp: der Namensvektor (Name und Stichwörter, `namenstext`) mit dem Gewicht
von fünf Beispielen plus die Vektoren der Aussagen, die dieses Thema von Hand haben, alle um
ihre gemeinsame Mitte verschoben und normiert. Ein neuer Text wird mit demselben Präfix wie
Aussagen eingebettet (`query: `), ebenso verschoben und mit jedem Prototyp verglichen
(Kosinus). Vorgeschlagen werden die nächsten Themen ab `themen_vorschlag_ab` und nicht weiter
als `themen_vorschlag_abstand_hoechstens` hinter dem ersten, für eine Aussage höchstens drei,
beim Einwerfen höchstens zwei.

**Warum die Mitte.** Ohne sie liegen alle Ähnlichkeiten zwischen 0,8 und 0,9, auch für
fremde Themen; ein Prototyp aus vielen Aussagen gleicht dann eher „politische Aussage“ als
seinem Thema. Mit der Mitte stieg der Treffer des ersten Themas von 0,80 auf 0,94 (mit
Stichwörtern), die Schwellen trennen deutlich besser.

**Leave-one-out.** Je Aussage werden die Prototypen aus allen anderen gebaut; die Aussage
selbst steckt weder in ihrem Prototyp noch in der Mitte.

**Optimistisch.** Schwelle, Abstand und Namensgewicht sind auf denselben 104 Aussagen gewählt,
ohne Hold-out. 72 davon hat derselbe Agent formuliert und zugeordnet, der auch die Messung
gebaut hat. Aussagekräftiger ist deshalb der **Startbestand** (30 Aussagen, von Menschen
geschrieben, nicht für die Messung): Er ist unten die Leitzahl.

## Ergebnis vom 22.11.2026

Vorläufiges Messset, 104 Aussagen, `intfloat/multilingual-e5-base`, gewählte Schwelle
`ab 0,10`, `abstand 0,05`. P = Precision, R = Recall über alle vorgeschlagenen Themen.

| Stand | erstes Thema passt | eins der ersten zwei | P (höchstens 3) | R | ohne Vorschlag | Themen je Aussage |
|---|---|---|---|---|---|---|
| ohne Stichwörter (heute `main`) | 0,85 | 0,95 | 0,80 | 0,67 | 1 % | 1,2 |
| mit Stichwörtern aus #754 (PR #755) | **0,94** | **0,98** | **0,89** | **0,72** | 2 % | 1,2 |
| nur Namen, ohne Zuordnungen von Hand | 0,68 | 0,87 | 0,65 | 0,60 | 4 % | 1,4 |
| nur Namen mit Stichwörtern | 0,87 | 0,91 | 0,77 | 0,69 | 1 % | 1,3 |

**Leitzahl Startbestand** (30 Aussagen): erstes Thema 0,77 ohne und 0,87 mit Stichwörtern,
P/R 0,76/0,66 bzw. 0,85/0,70. Beim Einwerfen (höchstens zwei) liegt P um 0,01 bis 0,02 höher
bei gleichem R.

Zum Start in Produktion gibt es wenige Zuordnungen von Hand und, bis #755 gemergt ist, keine
Stichwörter: Dann gilt etwa die Zeile „nur Namen, ohne Zuordnungen von Hand“ (P 0,65, R 0,60).
Mit jeder Zuordnung von Hand rückt es Richtung erste Zeile.

Precision / Recall je Schwelle, höchstens drei, ohne Stichwörter (heute `main`):

| ab | abstand 0,03 | abstand 0,05 | abstand 0,08 | abstand 0,12 |
|---|---|---|---|---|
| 0,00 | 0,81 / 0,65 | 0,76 / 0,67 | 0,68 / 0,73 | 0,61 / 0,79 |
| 0,08 | 0,82 / 0,64 | 0,79 / 0,67 | 0,71 / 0,71 | 0,66 / 0,77 |
| **0,10** | 0,82 / 0,64 | **0,80 / 0,67** | 0,75 / 0,71 | 0,69 / 0,76 |
| 0,14 | 0,84 / 0,61 | 0,81 / 0,63 | 0,80 / 0,66 | 0,79 / 0,69 |
| 0,16 | 0,87 / 0,57 | 0,86 / 0,58 | 0,85 / 0,61 | 0,85 / 0,64 |
| 0,20 | 0,88 / 0,45 | 0,86 / 0,46 | 0,87 / 0,47 | 0,86 / 0,48 |

Dasselbe mit Stichwörtern (#755):

| ab | abstand 0,03 | abstand 0,05 | abstand 0,08 | abstand 0,12 |
|---|---|---|---|---|
| 0,00 | 0,89 / 0,71 | 0,86 / 0,74 | 0,76 / 0,78 | 0,69 / 0,80 |
| 0,08 | 0,91 / 0,69 | 0,87 / 0,73 | 0,80 / 0,76 | 0,73 / 0,78 |
| **0,10** | 0,91 / 0,69 | **0,89 / 0,72** | 0,82 / 0,76 | 0,76 / 0,76 |
| 0,14 | 0,93 / 0,67 | 0,91 / 0,70 | 0,88 / 0,74 | 0,84 / 0,74 |
| 0,16 | 0,94 / 0,63 | 0,93 / 0,65 | 0,90 / 0,68 | 0,87 / 0,68 |
| 0,20 | 0,93 / 0,56 | 0,94 / 0,57 | 0,94 / 0,59 | 0,92 / 0,59 |

Ab 0,14 bleiben zunehmend Aussagen ohne Vorschlag (5 % bei 0,14, 18 % bei 0,20). 0,10 mit
Abstand 0,05 hält P nahe 0,9 und schlägt fast immer etwas vor; ein falscher Vorschlag kostet
nur einen Blick, weil nichts automatisch gesetzt wird.

### NLI als zweite Meinung

Das NLI-Modell der NLI-Stufe urteilt über die fünf nächsten Themen („In diesem Satz geht es
um {Thema}.“) und streicht die unter `themen_vorschlag_folgerung_ab`. Am Messset strich es
mehr Treffer als Fehler: bei `ab 0,10`, `abstand 0,05` mit Folgerung ab 0,1 P 0,91 / R 0,47
(ein Drittel der Aussagen ohne Vorschlag), ab 0,5 P 0,88 / R 0,35. Allein über alle 19 Themen
traf es das erste Thema in 49 % der Fälle. Es bleibt deshalb aus (`themen_vorschlag_nli =
false`); der Schalter bleibt, um es am echten Testset nachzumessen.

### Antwortzeit und Speicher

CPU der Entwicklungs-VM, vier Threads, Median / 95 %:

| Schritt | Zeit |
|---|---|
| Vorschlag (Text einbetten, 19 Prototypen vergleichen) | 31 ms / 38 ms |
| zusätzlich NLI über fünf Kandidaten (aus) | 202 ms / 252 ms |
| Prototypen bauen (104 Texte einbetten, alle zehn Minuten nur neue) | 1,5 s |

Gemessen auf der Entwicklungs-VM, nicht auf der Ziel-VM. Eingebettet wird im Dienst wie die
Suche in der Ereignisschleife, nicht in einem Thread (das Modell teilt sich die Suche). Der
Bau läuft im Hintergrund, Text für Text; solange es noch keine Prototypen gibt, wartet ein
Vorschlag höchstens zwei Sekunden und ist sonst leer.

Kein neues Modell und kein neues Paket: Einbettungs- und NLI-Modell sind im Dienst ohnehin
geladen. Im Speicher bleiben je Text des Testsets ein Vektor (768 Zahlen float32, 3 KB) und
19 Prototypen; bei 200 Zuordnungen unter 1 MB. Der Messprozess selbst
(beide Modelle geladen) kam auf 2,9 GB Spitze.

## Nachmessen

- wenn das Testset aus Produktion etwa 200 Zuordnungen hat (Ziel aus #363): mit
  `--testset`, danach die Schwellen in `core/config.py` und hier nachziehen;
- bei jedem Wechsel des Einbettungsmodells oder der Themenliste;
- wenn sich Namen oder Stichwörter der Themen ändern.
