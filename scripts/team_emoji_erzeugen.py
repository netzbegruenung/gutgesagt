"""
Erzeugt die feste Positivliste der Team-Motive (domain/team_emoji.py) aus emojibase-data.

Quelle sind die deutschen Daten von emojibase-data (MIT, Copyright Miles Johnson), die
Gruppen, Untergruppen, Kurznamen und Stichworte aus Unicode Emoji und CLDR übernehmen.
Das Paket ist keine Abhängigkeit dieses Repos: Das Skript liest eine vorhandene Kopie,
das Ergebnis steht fest im Code und ändert sich nur, wenn jemand dieses Skript neu
laufen lässt und den Unterschied in einem PR vorlegt.

Aufgenommen werden nur (Vorgabe Jura, vorläufig, 28.11.2026):
- die Gruppen Tiere & Natur, Essen & Trinken, Reisen & Orte, Aktivitäten, Gegenstände
  und Symbole; Smileys & Personen, Komponenten und Flaggen ganz nicht;
- einzelne Zeichen, höchstens mit Variantenwähler U+FE0F: keine ZWJ-Sequenzen, keine
  Hautton- oder sonstigen Modifikatoren, keine Tastenkappen;
- Emoji bis Version 12.0 (2019), damit auch ältere Geräte sie zeichnen;
- ohne die Untergruppen und Zeichen in AUSGESCHLOSSEN_* unten (Religion und
  Weltanschauung, Gender und Sexualität, Gesundheit, Behinderung, Medizin und Körper,
  Herkunft, Waffen, mehrdeutige Zeichen).

Alltagsessen bleibt drin, auch wenn es aus einer Küche kommt (Döner, Sushi, Taco):
Es sagt etwas über Geschmack, nicht über Herkunft. Draußen sind Kleidung, Feste und
Zeichen, die für eine Kultur oder einen Glauben stehen.

Aufruf mit dem Verzeichnis einer vorhandenen Kopie von emojibase-data:
    python3 scripts/team_emoji_erzeugen.py <pfad>/node_modules/emojibase-data
Danach Black über die erzeugte Datei laufen lassen (pre-commit macht das).
"""

import json
import pathlib
import sys

ZIEL = (
    pathlib.Path(__file__).resolve().parents[1]
    / "mvp/backend/semantic-search-service/app/domain/team_emoji.py"
)

# Gruppen nach emojibase (= Unicode-Emoji-Gruppen), in der Reihenfolge der Auswahl
GRUPPEN = {
    3: "tiere-natur",
    4: "essen-trinken",
    5: "reisen-orte",
    6: "aktivitaeten",
    7: "gegenstaende",
    8: "symbole",
}

HOECHSTE_VERSION = 12.0

AUSGESCHLOSSEN_UNTERGRUPPEN = {
    "place-religious",  # Kirche, Moschee, Synagoge, Tempel, Schrein, Kaaba
    "religion",  # Kreuz, Halbmond, Om, Davidstern, Dharma-Rad, Menora, Yin Yang, Frieden
    "zodiac",  # Sternzeichen: Astrologie als Weltanschauung
    "gender",  # Weiblich, Männlich, Transgender
    "medical",  # Spritze, Blutstropfen, Pille, Pflaster, Stethoskop
    "keycap",  # Tastenkappen sind Sequenzen
}

AUSGESCHLOSSEN_ZEICHEN = {
    # Religion, Weltanschauung, Totenkult
    0x1F4FF: "Gebetskette",
    0x1F9FF: "Nazar-Amulett",
    0x1FA94: "Diya-Lampe",
    0x1F384: "Weihnachtsbaum",
    0x26B0: "Sarg",
    0x26B1: "Urne",
    0x1F492: "Hochzeitskapelle",
    0x1F52E: "Kristallkugel",
    # Gender, Sexualität, Körper
    0x1F6B9: "Herren",
    0x1F6BA: "Damen",
    0x1F6BB: "Toiletten",
    0x1F6BC: "Baby-Symbol",
    0x1F3E9: "Stundenhotel",
    0x1F308: "Regenbogen",
    0x1F459: "Bikini",
    0x1FA71: "Einteiler",
    0x1FA72: "Slip",
    # Gesundheit, Behinderung, Medizin
    0x267F: "Rollstuhlsymbol",
    0x1F9BD: "manueller Rollstuhl",
    0x1F9BC: "elektrischer Rollstuhl",
    0x1F9AF: "Blindenstock",
    0x1F9AE: "Blindenhund",
    0x1F397: "Erinnerungsband (Schleife für Krankheiten)",
    0x1F9A0: "Mikrobe",
    0x1F9EC: "DNA",
    0x1F9EB: "Petrischale",
    0x2695: "Äskulapstab",
    0x1F691: "Krankenwagen",
    0x1F3E5: "Krankenhaus",
    0x1F6AC: "Zigarette",
    0x1F6AD: "Rauchverbot",
    0x2623: "Biogefährdung",
    # Waffen
    0x1F52B: "Pistole",
    0x1F52A: "Küchenmesser",
    0x1F5E1: "Dolch",
    0x2694: "gekreuzte Schwerter",
    0x1F3F9: "Pfeil und Bogen",
    0x1F4A3: "Bombe",
    0x1FA93: "Axt",
    0x1F9E8: "Feuerwerkskörper",
    0x1F6E1: "Schild",
    # Herkunft: Wahrzeichen und Umrisse einzelner Länder
    0x1F5FE: "Umriss von Japan",
    0x1F5FD: "Freiheitsstatue",
    0x1F5FC: "Tokyo Tower",
    0x1F5FB: "Fuji",
    0x1F3EF: "japanisches Schloss",
    # Herkunft: Kleidung, Feste und Zeichen einer Kultur (Review 28.11.)
    0x1F458: "Kimono",
    0x1F97B: "Sari",
    0x1F3E3: "japanisches Postgebäude",
    0x1F530: "japanisches Anfänger-Zeichen",
    0x1F38E: "japanische Puppen",
    0x1F38F: "Karpfenbanner",
    0x1F390: "japanisches Windspiel",
    0x1F391: "Fest des Mondes",
    0x1F38B: "Tanabata-Baum",
    0x1F38D: "Piniendekoration",
    0x1F3B4: "japanische Blumenkarte",
    0x1F3EE: "rote Papierlaterne",
    0x1F9E7: "roter Umschlag",
    0x1F96E: "Mondkuchen",
    0x1F531: "Dreizack (Staatswappen, Trishula)",
    # Gesundheit: Erste Hilfe und Arztkittel
    0x26D1: "Rettungshelm",
    0x1F97C: "Laborkittel",
    # Gender: Kleidung, die CLDR nach Damen und Herren benennt
    0x1F45E: "Herrenschuh",
    0x1F461: "Damensandale",
    0x1F462: "Damenstiefel",
    0x1F452: "Damenhut",
    0x1F460: "Stöckelschuh",
    0x1F457: "Kleid",
    0x1F45A: "Bluse",
    0x1F45B: "Geldbörse (Damen)",
    0x1F484: "Lippenstift",
    # Militär
    0x1F396: "Militärorden",
    # Mehrdeutig oder politisch besetzt
    0x1F346: "Aubergine",
    0x1F351: "Pfirsich",
    0x1F51E: "Minderjährigen verboten",
    0x1F53B: "rotes Dreieck nach unten (Kennzeichen der Hamas)",
    0x1F349: "Wassermelone (Symbol einer politischen Haltung)",
    # Gesundheit, Behinderung und Sexualität über Symbole (Review 28.11.)
    0x1F9E9: "Puzzleteil (Autismus)",
    0x1F980: "Krebs (Name liest sich als Krankheit, Sternzeichen)",
    0x1F321: "Thermometer (Fieber)",
    0x267E: "Unendlichkeit (Neurodiversität, Polyamorie)",
    0x1F380: "pinke Schleife (Brustkrebs)",
    # Religion und Herkunft über Symbole
    0x1F56F: "Kerze (Andacht, wie die Diya-Lampe)",
    0x1F319: "Mondsichel (wie der Halbmond)",
    0x2618: "Kleeblatt (Nationalsymbol, Dreifaltigkeit)",
    0x269C: "Lilie (Marien- und Königszeichen)",
    0x1F6C2: "Passkontrolle (Migration)",
    0x1F6C3: "Zoll (Migration)",
    # Gender: Kleidung, die als Damenkleidung gilt
    0x1F97F: "flacher Schuh",
    0x1F45D: "Clutch",
    # Blutgruppen (Gesundheit)
    0x1F170: "Blutgruppe A",
    0x1F171: "Blutgruppe B",
    0x1F17E: "Blutgruppe 0",
    0x1F18E: "Blutgruppe AB",
    # Japanische Schriftzeichen mit wechselnder Bedeutung
    0x3297: "Schriftzeichen für Gratulation",
    0x3299: "Schriftzeichen für Geheimnis",
}

# Japanische Schriftzeichen-Tasten (🈁 bis 🉑): Bedeutung ohne Sprachkenntnis nicht lesbar
AUSGESCHLOSSEN_BEREICHE = [(0x1F200, 0x1F2FF)]


def _ausgeschlossen(cp: int) -> bool:
    return cp in AUSGESCHLOSSEN_ZEICHEN or any(
        a <= cp <= b for a, b in AUSGESCHLOSSEN_BEREICHE
    )


def eintraege(quelle: pathlib.Path):
    daten = json.loads((quelle / "de/data.json").read_text(encoding="utf-8"))
    untergruppen = json.loads((quelle / "meta/groups.json").read_text("utf-8"))[
        "subgroups"
    ]
    for e in sorted(daten, key=lambda e: e.get("order", 0)):
        if e.get("group") not in GRUPPEN or "-" in e["hexcode"]:
            continue
        if e.get("version", 99) > HOECHSTE_VERSION:
            continue
        if untergruppen[str(e["subgroup"])] in AUSGESCHLOSSEN_UNTERGRUPPEN:
            continue
        cp = int(e["hexcode"], 16)
        if _ausgeschlossen(cp):
            continue
        # Vollqualifiziert wie in emoji-test.txt: Zeichen mit Textdarstellung als
        # Standard (type 0) bekommen U+FE0F, die anderen stehen allein.
        zeichen = chr(cp) + ("\ufe0f" if e["type"] == 0 else "")
        stichworte = " ".join(
            t
            for t in dict.fromkeys(e.get("tags", []))
            if t.lower() != e["label"].lower()
        )
        yield zeichen, e["label"], GRUPPEN[e["group"]], stichworte


def main() -> None:
    quelle = pathlib.Path(sys.argv[1])
    paket = json.loads((quelle / "package.json").read_text("utf-8"))
    namen = {
        g["key"]: g["message"]
        for g in json.loads((quelle / "de/messages.json").read_text("utf-8"))["groups"]
    }
    schluessel = {
        "tiere-natur": "animals-nature",
        "essen-trinken": "food-drink",
        "reisen-orte": "travel-places",
        "aktivitaeten": "activities",
        "gegenstaende": "objects",
        "symbole": "symbols",
    }
    liste = list(eintraege(quelle))
    zeilen = [
        '"""',
        'Feste Positivliste der Team-Motive (GLOSSARY.md "Team"), erzeugt von',
        "scripts/team_emoji_erzeugen.py; nicht von Hand ändern, sondern das Skript anpassen",
        "und neu laufen lassen.",
        "",
        f"Quelle: emojibase-data {paket['version']} (MIT, Copyright Miles Johnson), darin",
        "Unicode Emoji 17.0 und CLDR 48 (Unicode License v3, team_emoji_LIZENZ.txt).",
        f"Aufgenommen bis Emoji {HOECHSTE_VERSION}, nur einzelne Zeichen (höchstens mit",
        "U+FE0F), ohne Sperrkategorien (Religion, Gender und Sexualität, Gesundheit,",
        "Behinderung, Medizin und Körper, Herkunft, Waffen, mehrdeutige Zeichen); was genau",
        "fehlt, steht im Skript. Name ist der deutsche CLDR-Kurzname.",
        '"""',
        "",
        "from typing import Tuple",
        "",
        "# Kategorie -> Name (CLDR, deutsch), in der Reihenfolge der Auswahl",
        "EMOJI_KATEGORIEN: Tuple[Tuple[str, str], ...] = (",
    ]
    for k, s in schluessel.items():
        zeilen.append(f"    ({k!r}, {namen[s]!r}),")
    zeilen += [
        ")",
        "",
        "# (Zeichen, Name, Kategorie, Stichworte für die Suche)",
        f"# {len(liste)} Einträge",
        "EMOJI_MOTIVE: Tuple[Tuple[str, str, str, str], ...] = (",
    ]
    for z, name, kat, stich in liste:
        zeilen.append(f"    ({z!r}, {name!r}, {kat!r}, {stich!r}),")
    zeilen += [")", ""]
    ZIEL.write_text("\n".join(zeilen), encoding="utf-8")
    print(f"{len(liste)} Einträge nach {ZIEL}")  # noqa: T201


if __name__ == "__main__":
    main()
