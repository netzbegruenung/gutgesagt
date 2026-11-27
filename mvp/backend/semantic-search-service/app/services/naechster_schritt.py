"""
Karte "Dein naechster Schritt" auf der Startseite (#789): genau ein Vorschlag je nach
eigenem Stand, ohne Ablaufdatum, ohne Zaehler "verpasst".

Alles kommt aus dem, was zur Person ohnehin gespeichert ist: ihre Einwuerfe, ihre
Stimmen, ihre sichtbaren Beitraege mit deren Nutzung, dazu Zahlen fuer alle (frische
Beitraege anderer, die erste Aussage aus "Hier fehlt eine Antwort"). Gespeichert wird
nichts, auch kein Besuch: Der Abruf ist ein GET, das nur liest. Was die Person
weggeklickt hat, merkt sich allein ihr Browser.

Regeln, von oben nach unten (die Liste traegt alle passenden in dieser Reihenfolge;
das Frontend zeigt den ersten, den die Person nicht weggeklickt hat, und nach dem
Wegklicken den naechsten):

1. Noch nichts getan (kein Einwurf, keine Stimme, kein Beitrag) -> suchen. Ob jemand
   schon kopiert hat, weiss der Server nicht: Nutzungen speichern keine Kennung
   (ADR 0004, #446). "Noch nie kopiert" naehert deshalb "noch nichts getan" an.
2. Noch kein Einwurf -> einwerfen.
3. Weniger als ``stimmen_mindestens`` Stimmen -> bewerten, aber nur, wenn es so viele
   frische Antworten anderer gibt; der Satz nennt die Zahl. Haengt nicht an der
   Einwilligung "Punkte und Meilensteine"; die Art.-9-Einwilligung zur Mitwirkung
   genuegt (juristische Pruefung 25.11.2026). Eigene Stimmen gibt es nur mit ihr, ein
   Widerruf loescht sie; der Abruf prueft sie deshalb nicht eigens.
4. Noch kein Beitrag -> die Aussage, die "Hier fehlt eine Antwort" zuoberst zeigt
   (fuer alle dieselbe, nach Bedarf sortiert). Nach Thema ist hier nicht gebaut; auch
   dafuer genuegte die Art.-9-Einwilligung (Pruefung 25.11.2026).
5. Ein eigener Kommentar mit Nutzung, aber ohne Kurzfassung -> Kurzfassung ergaenzen
   (der meistgenutzte).
6. Sonst die Aussage aus Regel 4 (ein Wochenziel je Team gibt es noch nicht).

Eine Quelle, die nicht antwortet, laesst nur ihre Regeln aus (Wert ``None``): Die
Karte ist Beiwerk und soll nicht ganz ausfallen.
"""

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

SCHALTER = "naechster_schritt"


class Art(str, Enum):
    SUCHEN = "suchen"
    EINWERFEN = "einwerfen"
    BEWERTEN = "bewerten"
    BRACHFLAECHE = "brachflaeche"
    KURZFASSUNG = "kurzfassung"


@dataclass(frozen=True)
class Brachflaeche:
    """Eine Aussage aus "Hier fehlt eine Antwort", wie die Liste sie zeigt."""

    statement_id: uuid.UUID
    text: str
    personen_ohne_treffer: int


@dataclass(frozen=True)
class KommentarOhneKurzfassung:
    content_id: uuid.UUID
    titel: str
    nutzung: int


@dataclass(frozen=True)
class EigenerStand:
    """Was die Regeln brauchen; ``None`` heisst: nicht lesbar, Regel faellt aus."""

    einwuerfe: Optional[int]
    stimmen: Optional[int]
    beitraege: Optional[int]
    kommentar_ohne_kurzfassung: Optional[KommentarOhneKurzfassung]
    frische_antworten: Optional[int]
    brachflaeche: Optional[Brachflaeche]


@dataclass(frozen=True)
class Vorschlag:
    art: Art
    # Bei "bewerten": wie viele Stimmen der Satz nennt
    anzahl: Optional[int] = None
    brachflaeche: Optional[Brachflaeche] = None
    kommentar: Optional[KommentarOhneKurzfassung] = None


def vorschlaege(stand: EigenerStand, stimmen_mindestens: int) -> List[Vorschlag]:
    """Alle passenden Vorschlaege, der erste gilt (Regeln im Modulkopf)."""
    liste: List[Vorschlag] = []
    if stand.einwuerfe == 0 and stand.stimmen == 0 and stand.beitraege == 0:
        liste.append(Vorschlag(Art.SUCHEN))
    if stand.einwuerfe == 0:
        liste.append(Vorschlag(Art.EINWERFEN))
    if (
        stand.stimmen is not None
        and stand.stimmen < stimmen_mindestens
        and (stand.frische_antworten or 0) >= stimmen_mindestens
    ):
        liste.append(Vorschlag(Art.BEWERTEN, anzahl=stimmen_mindestens))
    brache = (
        Vorschlag(Art.BRACHFLAECHE, brachflaeche=stand.brachflaeche)
        if stand.brachflaeche is not None
        else None
    )
    if brache and stand.beitraege == 0:
        liste.append(brache)
    if stand.kommentar_ohne_kurzfassung is not None:
        liste.append(
            Vorschlag(Art.KURZFASSUNG, kommentar=stand.kommentar_ohne_kurzfassung)
        )
    if brache and stand.beitraege != 0:
        liste.append(brache)
    return liste


def meistgenutzter_ohne_kurzfassung(
    beitraege: List[dict],
) -> Optional[KommentarOhneKurzfassung]:
    """
    Unter den eigenen Beitraegen (je ``id``, ``content_type``, ``title``,
    ``short_text``, ``usage_count``) der meistgenutzte Kommentar ohne Kurzfassung mit
    Nutzung; bei Gleichstand der zuerst stehende (get_by_author: neueste zuerst).
    """
    bester: Optional[KommentarOhneKurzfassung] = None
    for beitrag in beitraege:
        typ = getattr(beitrag.get("content_type"), "value", beitrag.get("content_type"))
        nutzung = int(beitrag.get("usage_count") or 0)
        if typ != "commentary" or nutzung <= 0:
            continue
        if (beitrag.get("short_text") or "").strip():
            continue
        if bester is None or nutzung > bester.nutzung:
            bester = KommentarOhneKurzfassung(
                content_id=uuid.UUID(str(beitrag["id"])),
                titel=beitrag.get("title") or "",
                nutzung=nutzung,
            )
    return bester
