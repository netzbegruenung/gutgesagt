"""
Messset Stimmenverfall bei geaendertem Text (#636): Paare (alte Fassung, neue Fassung)
eines Kommentars oder einer Hintergrundinfo unter gleichem Titel, von Hand entschieden.

- bleibt: dieselbe Aussage des Texts (Tippfehler, Satzzeichen, Ergaenzung, Kuerzung,
  Umformulierung, Quelle dazu). Kleine Korrekturen duerfen nie Stimmen kosten.
- verfaellt: der Text sagt etwas anderes (Gegenteil, anderer Standpunkt, anderes Thema).

Das Label ist das menschliche Urteil, nicht das der Regel: Die Regel
(fassung.gleicher_text) erkennt nur das Phaenomen "fremd"; "gegenteil" und
"anderer_aspekt" sind bekannte Luecken (MESSSET.md, Abschnitt "Geaenderter Text").
Erstellt von einem Agenten am 22.11.2026; Labels abgenommen vom Maintainer am 26.11.2026
(Review von #764): Eine korrigierte Zahl (B14, B16-B19) und die Kuerzung bis auf einen Satz
behalten die Stimmen; nur ein Text, der etwas ganz anderes sagt, verliert sie.
"""

from typing import NamedTuple


class TextPaar(NamedTuple):
    id: str
    label: str  # "bleibt" oder "verfaellt"
    phaenomen: str
    alt: str
    neu: str


_WP = (
    "Auch in vielen Altbauten arbeitet eine Wärmepumpe effizient. Entscheidend ist die "
    "Vorlauftemperatur: Liegt sie unter 55 Grad, reicht oft schon ein Tausch einzelner "
    "Heizkörper. Der Staat fördert den Einbau mit bis zu 70 Prozent."
)
_TL = (
    "Ein Tempolimit von 130 km/h spart laut Umweltbundesamt jedes Jahr mehrere Millionen "
    "Tonnen CO2. Es kostet fast nichts, wirkt sofort und macht die Autobahnen sicherer."
)
_BS = (
    "Ein Balkonkraftwerk mit 800 Watt kostet heute meist unter 500 Euro. Bei einem "
    "sonnigen Südbalkon hat es sich nach vier bis sechs Jahren bezahlt gemacht."
)
_OE = (
    "Wer auf dem Land wohnt, ist oft auf das Auto angewiesen. Deshalb braucht es dort "
    "mehr Busse im Stundentakt und Rufbusse am Abend, nicht weniger."
)
_WK = (
    "Windräder töten deutlich weniger Vögel als Glasscheiben, Hauskatzen oder der "
    "Straßenverkehr. Neue Anlagen schalten sich zudem ab, wenn Zugvögel kommen."
)
_EA = (
    "Elektroautos haben über ihre Lebensdauer eine bessere Klimabilanz als Verbrenner, "
    "auch mit dem heutigen Strommix. Der Vorsprung wächst mit jedem neuen Windrad."
)

# Eine lange Ergaenzung (Text etwa vervierfacht) und ein kurzer Kommentar (Review #764).
_WP_LANG = (
    " Wichtig ist außerdem eine gute Planung durch einen Fachbetrieb. Vor dem Einbau "
    "sollte eine Heizlastberechnung gemacht werden, damit die Pumpe nicht zu groß oder "
    "zu klein ausfällt. Viele Hausbesitzer unterschätzen, wie viel ein hydraulischer "
    "Abgleich bringt. Auch die Lage der Außeneinheit spielt eine Rolle, wegen des "
    "Schalls für die Nachbarn. Wer zusätzlich eine Photovoltaikanlage auf dem Dach hat, "
    "kann einen Teil des Stroms selbst erzeugen und spart so zusätzlich. In Skandinavien "
    "heizen schon heute die meisten Häuser mit Wärmepumpen, auch bei minus zwanzig Grad. "
    "Die Erfahrungen dort zeigen, dass die Technik ausgereift ist."
)
_KURZ = "Gute Zusammenfassung der Studie."

PAARE = [
    # --- bleibt: kleine Korrekturen
    TextPaar("B01", "bleibt", "tippfehler", _WP, _WP.replace("effizient", "effizent")),
    TextPaar(
        "B02", "bleibt", "tippfehler", _TL.replace("Autobahnen", "Autobahenn"), _TL
    ),
    TextPaar("B03", "bleibt", "satzzeichen", _BS, _BS.replace(". Bei", "! Bei")),
    TextPaar("B04", "bleibt", "trivial", _OE, _OE.lower()),
    # --- bleibt: Ergaenzung, Kuerzung, Quelle
    TextPaar(
        "B05",
        "bleibt",
        "ergaenzung",
        _WP,
        _WP + " Das zeigen Feldtests des Fraunhofer ISE.",
    ),
    TextPaar(
        "B06",
        "bleibt",
        "ergaenzung",
        _TL,
        _TL + " Die meisten Länder in Europa haben längst eins.",
    ),
    TextPaar(
        "B07",
        "bleibt",
        "kuerzung",
        _BS,
        "Ein Balkonkraftwerk mit 800 Watt kostet heute meist unter 500 Euro.",
    ),
    TextPaar(
        "B08",
        "bleibt",
        "kuerzung",
        _WK,
        "Windräder töten deutlich weniger Vögel als Glasscheiben, Hauskatzen oder der "
        "Straßenverkehr.",
    ),
    TextPaar(
        "B09",
        "bleibt",
        "ergaenzung",
        _EA,
        _EA + " Quelle: ICCT-Studie 2021.",
    ),
    # --- bleibt: Umformulierung
    TextPaar(
        "B10",
        "bleibt",
        "umformulierung",
        _WP,
        "Eine Wärmepumpe kann auch im Altbau effizient heizen. Wichtig ist eine "
        "Vorlauftemperatur unter 55 Grad; oft genügt es, einzelne Heizkörper zu tauschen. "
        "Bis zu 70 Prozent der Kosten übernimmt die staatliche Förderung.",
    ),
    TextPaar(
        "B11",
        "bleibt",
        "umformulierung",
        _TL,
        "Laut Umweltbundesamt würde Tempo 130 jährlich mehrere Millionen Tonnen CO2 "
        "einsparen. Das ist fast kostenlos, wirkt ab dem ersten Tag und erhöht die "
        "Sicherheit auf der Autobahn.",
    ),
    TextPaar(
        "B12",
        "bleibt",
        "umformulierung",
        _OE,
        "Auf dem Land geht es ohne Auto oft nicht. Gerade deshalb müssen dort mehr Busse "
        "fahren, mindestens jede Stunde, und abends Rufbusse.",
    ),
    TextPaar(
        "B13",
        "bleibt",
        "umformulierung",
        _WK,
        "Glasscheiben, Katzen und Autos töten viel mehr Vögel als Windräder. Und moderne "
        "Anlagen stehen still, wenn Zugvögel durchziehen.",
    ),
    TextPaar(
        "B14",
        "bleibt",
        "zahl",
        _BS,
        _BS.replace("unter 500 Euro", "unter 400 Euro"),
    ),
    TextPaar(
        "B15",
        "bleibt",
        "umformulierung",
        _EA,
        "Über das ganze Autoleben gerechnet sind E-Autos klimafreundlicher als Benziner "
        "und Diesel, schon mit dem Strom von heute. Jedes neue Windrad vergrößert den "
        "Abstand.",
    ),
    TextPaar("B16", "bleibt", "zahl", _WP, _WP.replace("70 Prozent", "50 Prozent")),
    TextPaar(
        "B17",
        "bleibt",
        "zahl",
        _TL,
        _TL.replace("mehrere Millionen", "rund acht Millionen"),
    ),
    TextPaar(
        "B18",
        "bleibt",
        "zahl",
        _BS,
        _BS.replace("vier bis sechs Jahren", "sechs bis acht Jahren"),
    ),
    TextPaar("B19", "bleibt", "zahl", _WP, _WP.replace("55 Grad", "50 Grad")),
    TextPaar(
        "B20",
        "bleibt",
        "ergaenzung",
        _OE,
        _OE + " In Nordfriesland klappt das mit dem Rufbus schon gut.",
    ),
    TextPaar(
        "B21",
        "bleibt",
        "kuerzung",
        _WP,
        "Auch in vielen Altbauten arbeitet eine Wärmepumpe effizient. Der Staat fördert "
        "den Einbau mit bis zu 70 Prozent.",
    ),
    # --- bleibt: aus dem Review von #764 (Laenge, Links, kurze Kommentare)
    TextPaar(
        "B22",
        "bleibt",
        "kuerzung",
        _WP,
        "Auch in vielen Altbauten arbeitet eine Wärmepumpe effizient.",
    ),
    TextPaar("B23", "bleibt", "ergaenzung", _WP, _WP + _WP_LANG),
    TextPaar("B24", "bleibt", "kuerzung", _WP + _WP_LANG, _WP),
    TextPaar(
        "B25",
        "bleibt",
        "zusatz",
        _WP,
        _WP + " Mehr: https://www.bafa.de/DE/Energie/Effiziente_Gebaeude/",
    ),
    TextPaar(
        "B26",
        "bleibt",
        "umformulierung",
        "Stimmt, gilt auch im Altbau.",
        "Richtig, das gilt auch für Altbauten.",
    ),
    TextPaar(
        "B27",
        "bleibt",
        "zusatz",
        _KURZ,
        _KURZ + " https://www.ise.fraunhofer.de/de/presse.html",
    ),
    # --- verfaellt: Gegenteil
    TextPaar(
        "V01",
        "verfaellt",
        "gegenteil",
        _WP,
        "In den meisten Altbauten arbeitet eine Wärmepumpe nicht effizient. Die "
        "Vorlauftemperatur ist dort zu hoch, und ein Tausch der Heizkörper reicht fast nie. "
        "Auch die Förderung ändert daran nichts.",
    ),
    TextPaar(
        "V02",
        "verfaellt",
        "gegenteil",
        _TL,
        "Ein Tempolimit von 130 km/h spart kaum CO2. Es kostet viel, wirkt erst nach "
        "Jahren und macht die Autobahnen nicht sicherer.",
    ),
    TextPaar(
        "V03",
        "verfaellt",
        "gegenteil",
        _BS,
        "Ein Balkonkraftwerk mit 800 Watt kostet meist über 1500 Euro. Selbst auf einem "
        "Südbalkon hat es sich oft erst nach zwanzig Jahren bezahlt gemacht.",
    ),
    TextPaar(
        "V04",
        "verfaellt",
        "gegenteil",
        _WK,
        "Windräder töten mehr Vögel als Glasscheiben, Hauskatzen oder der "
        "Straßenverkehr. Abschalten, wenn Zugvögel kommen, tun die Anlagen nicht.",
    ),
    TextPaar(
        "V05",
        "verfaellt",
        "gegenteil",
        _EA,
        "Elektroautos haben über ihre Lebensdauer eine schlechtere Klimabilanz als "
        "Verbrenner, jedenfalls mit dem heutigen Strommix.",
    ),
    # --- verfaellt: anderer Standpunkt / Aspekt unter gleichem Thema
    TextPaar(
        "V06",
        "verfaellt",
        "anderer_aspekt",
        _OE,
        "Auf dem Land braucht es keine neuen Busse, sondern Ladesäulen. Wer dort wohnt, "
        "fährt ohnehin Auto, und das soll elektrisch sein.",
    ),
    TextPaar(
        "V07",
        "verfaellt",
        "anderer_aspekt",
        _WP,
        "Wärmepumpen sind teuer, und der Strompreis steigt. Wer im Altbau wohnt, sollte "
        "lieber zuerst dämmen und eine Gasheizung behalten.",
    ),
    # --- verfaellt: ganz anderer Text
    TextPaar("V08", "verfaellt", "fremd", _TL, _BS),
    TextPaar("V09", "verfaellt", "fremd", _OE, _WK),
    TextPaar(
        "V10",
        "verfaellt",
        "fremd",
        _EA,
        "Bitte teilt diesen Beitrag! Mehr dazu auf unserer Seite.",
    ),
    TextPaar(
        "V11",
        "verfaellt",
        "fremd",
        _WP,
        "Gasheizungen sollten ab 2030 verboten werden, weil sie das Klima schädigen. "
        "Fernwärme ist in Städten die bessere Wahl.",
    ),
    TextPaar("V12", "verfaellt", "fremd", _KURZ, "Windräder töten kaum Vögel."),
]
