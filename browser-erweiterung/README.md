# Browser-Erweiterung Gut gesagt

Rechtsklick auf markierten Text, auf jeder Seite:

- **In Gut gesagt suchen** öffnet `/result?searchQuery=<Markierung>` in einem neuen Tab.
- **In Gut gesagt einwerfen** öffnet `/teilen?text=<Markierung>&url=<Seite>`, denselben Weg wie
  das Teilen-Ziel der App (`share_target` im Manifest, `ShareTargetGuard`). Gut gesagt füllt
  das Einwurf-Formular vor: die Seitenadresse als Link, die Markierung als Hinweis. Angemeldet
  wird im normalen Tab, die Erweiterung kennt kein Konto.

Die Markierung geht gekürzt mit: höchstens 1000 Zeichen (Eingabegrenze der Suche), am Wortende,
und die ganze Adresse bleibt unter 7000 Zeichen. Nur `http(s)`-Seiten gehen als Link mit.
Ziel umschaltbar in den Optionen der Erweiterung: Gut gesagt (Standard) oder Testinstanz.

Stufe 1 aus dem Plan (Instagram-Text auslesen, Vorschläge, Gegenlesen folgen später).

## Datenschutz

Die Erweiterung liest nur die Markierung und die Adresse der Seite, die der Browser beim Klick auf
einen der Einträge übergibt, und öffnet damit Gut gesagt in einem neuen Tab; sie ruft selbst
nichts ab, hat keinen Zugriff auf Seiteninhalte und sammelt nichts. Gespeichert wird nur die Wahl
Gut gesagt oder Testinstanz, lokal im Browser.

Berechtigungen: `contextMenus` (die zwei Einträge) und `storage` (das gewählte Ziel). Keine
`host_permissions`, kein Content-Script. `scripts/tests/test_browser_erweiterung.py` hält das fest.

## Lokal installieren

Chrome, Chromium, Edge:

1. `chrome://extensions` öffnen, oben rechts **Entwicklermodus** einschalten.
2. **Entpackte Erweiterung laden** und den Ordner `browser-erweiterung/` wählen.
3. Auf einer Seite Text markieren, Rechtsklick, **In Gut gesagt suchen**.

Firefox (ab 121):

1. `about:debugging#/runtime/this-firefox` öffnen.
2. **Temporäres Add-on laden** und `browser-erweiterung/manifest.json` wählen. Bleibt bis zum
   Neustart von Firefox.

Optionen: Chrome über **Details → Erweiterungsoptionen**, Firefox über `about:addons`.

## Tests

```sh
node --test browser-erweiterung/test/*.test.js
```

Ohne Paket (`node:test`). `scripts/check.sh` lässt sie im Schritt `frontend` mitlaufen, das Manifest
prüft `scripts/tests/test_browser_erweiterung.py` im Schritt `unit`.

## Aufbau

| Datei | Inhalt |
|------|------|
| `manifest.json` | Manifest V3 für Chrome und Firefox: `service_worker` für Chrome, `scripts` für Firefox, `browser_specific_settings.gecko.id` |
| `adressen.js` | Adress-Bildung, reine Funktionen (auch für Node) |
| `hintergrund.js` | Kontextmenü und Klick |
| `optionen.html`, `optionen.js` | Ziel Prod/Test |
| `icons/` | App-Icon v3 in 16/32/48/128 px; Hand aus Fluent Emoji (MIT, `icons/FLUENT-EMOJI-LIZENZ.txt`) |

## Weg in die Stores (offen)

Noch nicht veröffentlicht. Schritte für den Maintainer:

1. Version in `manifest.json` setzen, Ordner als ZIP packen (ohne `test/` und `README.md`).
2. **Chrome Web Store:** Entwicklerkonto (einmalige Gebühr) im
   [Developer Dashboard](https://chrome.google.com/webstore/devconsole), ZIP hochladen,
   Datenschutzangaben ausfüllen (keine Datenerhebung; Begründung je Berechtigung), Screenshots,
   Prüfung abwarten.
3. **Firefox Add-ons (AMO):** Konto auf [addons.mozilla.org](https://addons.mozilla.org/developers/),
   ZIP hochladen; AMO prüft den Code. Die id `gutgesagt@netzbegruenung.de` und
   `data_collection_permissions: none` stehen schon im Manifest.
4. Store-Einträge in der App verlinken (eigener PR).
