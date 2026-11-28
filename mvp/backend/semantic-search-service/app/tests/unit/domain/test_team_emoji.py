"""
Die feste Positivliste der Team-Motive (domain/team_emoji.py, Vorgabe Jura 28.11.2026):
nur einzelne Zeichen aus sechs Gruppen, ohne ZWJ, ohne Modifikatoren, ohne die
Sperrkategorien. Die sechs frueheren Schluessel bleiben gueltig.
"""

import pytest

from domain.team_emoji import EMOJI_KATEGORIEN, EMOJI_MOTIVE
from domain.teams import MOTIVE, motiv_gueltig, motiv_name

ZWJ = "‍"
VARIANTE = "️"
KATEGORIEN = {k for k, _ in EMOJI_KATEGORIEN}


def _ist_modifikator(zeichen: str) -> bool:
    cp = ord(zeichen)
    return (
        0x1F3FB <= cp <= 0x1F3FF  # Hautton
        or 0x1F9B0 <= cp <= 0x1F9B3  # Haarfarbe
        or 0x1F1E6 <= cp <= 0x1F1FF  # Regionalbuchstaben (Flaggen)
        or 0xE0020 <= cp <= 0xE007F  # Tags (Flaggen von Regionen)
        or cp == 0x20E3  # Tastenkappe
    )


@pytest.mark.parametrize("eintrag", EMOJI_MOTIVE, ids=lambda e: e[1])
def test_jeder_eintrag_ist_ein_einzelnes_zeichen(eintrag):
    zeichen, name, kategorie, _ = eintrag
    assert ZWJ not in zeichen
    assert not any(_ist_modifikator(z) for z in zeichen)
    # Ein Zeichen, hoechstens mit Variantenwaehler U+FE0F dahinter
    assert len(zeichen) == 1 or (len(zeichen) == 2 and zeichen[1] == VARIANTE)
    assert name.strip() == name and name
    assert kategorie in KATEGORIEN


def test_liste_ohne_doppelte_und_gross_genug():
    zeichen = [z for z, *_ in EMOJI_MOTIVE]
    assert len(zeichen) == len(set(zeichen))
    assert len(zeichen) > 500
    # Kein Emoji ist zugleich einer der frueheren Schluessel
    assert not set(zeichen) & set(MOTIVE)


@pytest.mark.parametrize(
    "gesperrt",
    [
        # Religion
        "✝️",
        "☪️",
        "🕉️",
        "✡️",
        "☸️",
        "☦️",
        "🛐",
        "📿",
        "⛪",
        "🕌",
        "🕍",
        "⛩️",
        "🕋",
        "🕎",
        "🧿",
        "☯️",
        "☮️",
        # Gender, Trans, Sexualitaet
        "⚧️",
        "♀️",
        "♂️",
        "🌈",
        "🏳️" + ZWJ + "🌈",
        # Gesundheit, Behinderung, Medizin, Koerper
        "♿",
        "🦽",
        "🦼",
        "🦯",
        "💉",
        "💊",
        "🩸",
        "🩺",
        "🦠",
        "🧬",
        "⚕️",
        # Smileys & Personen
        "😀",
        "🤰",
        "💏",
        "💑",
        "🦻",
        "🧠",
        "✊",
        "🙏",
        # Flaggen
        "🇩🇪",
        "🏴",
        "🏳️",
        # Herkunft, Waffen, mehrdeutig
        "🗾",
        "🔫",
        "🔪",
        "🗡️",
        "⚔️",
        "💣",
        "🍆",
        "🍑",
        "🔞",
    ],
)
def test_stichproben_aus_den_sperrkategorien_fehlen(gesperrt):
    assert not motiv_gueltig(gesperrt)
    assert motiv_name(gesperrt) is None


@pytest.mark.parametrize(
    "schluessel,name",
    [
        ("vogel", "Vogel"),
        ("sprechblase", "Sprechblase"),
        ("handschlag", "Handschlag"),
        ("laufschuh", "Laufschuh"),
        ("waage", "Waage"),
        ("lautsprecher", "Lautsprecher"),
    ],
)
def test_fruehere_schluessel_bleiben_gueltig(schluessel, name):
    assert motiv_gueltig(schluessel)
    assert motiv_name(schluessel) == name


def test_deutscher_kurzname_und_nur_exakte_eintraege():
    assert motiv_name("🌻") == "Sonnenblume"
    assert motiv_gueltig("⚖️")
    # Ohne Variantenwaehler ist es nicht genau der Eintrag
    assert not motiv_gueltig("⚖")
    assert not motiv_gueltig(None)
    assert not motiv_gueltig("")
