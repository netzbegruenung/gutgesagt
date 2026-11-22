"""
Browser-Erweiterung (browser-erweiterung/): Manifest gueltig, Berechtigungen minimal.

Die Adress-Bildung pruefen die node:test-Tests in browser-erweiterung/test/ (check.sh,
Schritt frontend); hier nur, was ohne Node geht, damit es auch im Python-Image der CI laeuft.
"""

import json
import pathlib
import re
import struct

import pytest

WURZEL = pathlib.Path(__file__).resolve().parents[2]
ORDNER = WURZEL / "browser-erweiterung"
MANIFEST = json.loads((ORDNER / "manifest.json").read_text(encoding="utf-8"))

# Was die Erweiterung darf: Kontextmenue und das gespeicherte Ziel (Prod/Test). Mehr nur mit
# Begruendung im PR, denn jede weitere Berechtigung zeigen die Stores beim Installieren an.
ERLAUBT = {"contextMenus", "storage"}
# Schluessel, mit denen eine Erweiterung Seiten lesen oder fremde Hosts erreichen koennte
VERBOTEN = {
    "host_permissions",
    "optional_host_permissions",
    "optional_permissions",
    "content_scripts",
    "web_accessible_resources",
    "externally_connectable",
    "content_security_policy",
    "declarative_net_request",
}
# Netzwerkzugriff oder Seitenzugriff im Code der Erweiterung
NETZWERK = re.compile(
    r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|importScripts\(\s*['\"]https?:"
    r"|executeScript|insertCSS|scripting\.|eval|Function\()"
)


def test_manifest_v3_mit_firefox_id():
    assert MANIFEST["manifest_version"] == 3
    assert re.fullmatch(r"\d+\.\d+\.\d+", MANIFEST["version"])
    gecko = MANIFEST["browser_specific_settings"]["gecko"]
    assert gecko["id"] == "gutgesagt@netzbegruenung.de"
    assert gecko["data_collection_permissions"] == {"required": ["none"]}


def test_berechtigungen_minimal():
    assert set(MANIFEST["permissions"]) == ERLAUBT
    assert not VERBOTEN & MANIFEST.keys()


def test_hintergrund_fuer_chrome_und_firefox():
    hintergrund = MANIFEST["background"]
    # Chrome nimmt service_worker und laedt adressen.js per importScripts, Firefox nimmt scripts
    assert hintergrund["service_worker"] == "hintergrund.js"
    assert hintergrund["scripts"] == ["adressen.js", "hintergrund.js"]
    assert "importScripts('adressen.js')" in (ORDNER / "hintergrund.js").read_text()


def test_verwiesene_dateien_vorhanden():
    dateien = [
        MANIFEST["background"]["service_worker"],
        *MANIFEST["background"]["scripts"],
        MANIFEST["options_ui"]["page"],
        *MANIFEST["icons"].values(),
    ]
    for datei in dateien:
        assert (ORDNER / datei).is_file(), datei


@pytest.mark.parametrize("groesse, datei", sorted(MANIFEST["icons"].items()))
def test_icons_png_in_angegebener_groesse(groesse, datei):
    kopf = (ORDNER / datei).read_bytes()[:24]
    assert kopf[:8] == b"\x89PNG\r\n\x1a\n"
    breite, hoehe = struct.unpack(">II", kopf[16:24])
    assert (breite, hoehe) == (int(groesse), int(groesse))


def test_icons_mit_lizenz_der_fluent_emoji_hand():
    assert (ORDNER / "icons" / "FLUENT-EMOJI-LIZENZ.txt").is_file()


@pytest.mark.parametrize(
    "datei", sorted(p.name for p in ORDNER.glob("*.js")), ids=lambda name: name
)
def test_kein_netzwerk_und_kein_seitenzugriff(datei):
    text = (ORDNER / datei).read_text(encoding="utf-8")
    ohne_kommentare = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.DOTALL)
    assert not NETZWERK.search(ohne_kommentare)


def test_optionsseite_ohne_fremde_skripte():
    html = (ORDNER / "optionen.html").read_text(encoding="utf-8")
    quellen = re.findall(r'<script[^>]*src="([^"]+)"', html)
    assert quellen == ["adressen.js", "optionen.js"]
    assert "<script>" not in html
