"""
Regeln der Karte "Dein naechster Schritt" (#789): je Regel ein Test, dazu die
Reihenfolge, das Ausfallen einzelner Quellen und die Auswahl des Kommentars ohne
Kurzfassung.
"""

import uuid

import pytest

from domain.models.content_type import ContentType
from services.naechster_schritt import (
    Art,
    Brachflaeche,
    EigenerStand,
    KommentarOhneKurzfassung,
    meistgenutzter_ohne_kurzfassung,
    vorschlaege,
)

pytestmark = pytest.mark.unit

BRACHE = Brachflaeche(uuid.uuid4(), "Windräder töten Vögel", 4)
KOMMENTAR = KommentarOhneKurzfassung(uuid.uuid4(), "Windräder schützen Vögel", 5)


def _stand(**werte) -> EigenerStand:
    grund = dict(
        einwuerfe=1,
        stimmen=5,
        beitraege=2,
        kommentar_ohne_kurzfassung=None,
        frische_antworten=10,
        brachflaeche=BRACHE,
    )
    grund.update(werte)
    return EigenerStand(**grund)


def _arten(stand: EigenerStand, mindestens: int = 3):
    return [v.art for v in vorschlaege(stand, mindestens)]


def test_regel_1_noch_nichts_getan_zuerst_suchen():
    stand = _stand(einwuerfe=0, stimmen=0, beitraege=0)

    assert _arten(stand) == [Art.SUCHEN, Art.EINWERFEN, Art.BEWERTEN, Art.BRACHFLAECHE]


def test_regel_1_nicht_mit_einer_stimme():
    assert Art.SUCHEN not in _arten(_stand(einwuerfe=0, stimmen=1, beitraege=0))


def test_regel_2_kein_einwurf():
    assert _arten(_stand(einwuerfe=0))[0] == Art.EINWERFEN


def test_regel_3_zu_wenig_stimmen_nennt_die_zahl():
    liste = vorschlaege(_stand(stimmen=2), 3)

    assert liste[0].art == Art.BEWERTEN
    assert liste[0].anzahl == 3


def test_regel_3_nur_mit_genug_frischen_antworten():
    assert Art.BEWERTEN not in _arten(_stand(stimmen=0, frische_antworten=2))


def test_regel_3_wert_konfigurierbar():
    assert Art.BEWERTEN in _arten(_stand(stimmen=4, frische_antworten=5), 5)
    assert Art.BEWERTEN not in _arten(_stand(stimmen=5, frische_antworten=9), 5)


def test_regel_4_ohne_beitrag_die_aussage_ohne_antwort_vor_der_kurzfassung():
    liste = vorschlaege(_stand(beitraege=0, kommentar_ohne_kurzfassung=KOMMENTAR), 3)

    assert [v.art for v in liste] == [Art.BRACHFLAECHE, Art.KURZFASSUNG]
    assert liste[0].brachflaeche == BRACHE


def test_regel_5_kurzfassung_ergaenzen():
    liste = vorschlaege(_stand(kommentar_ohne_kurzfassung=KOMMENTAR), 3)

    assert liste[0].art == Art.KURZFASSUNG
    assert liste[0].kommentar == KOMMENTAR
    # Regel 6 danach als anderer Vorschlag
    assert liste[1].art == Art.BRACHFLAECHE


def test_regel_6_sonst_die_aussage_ohne_antwort():
    assert _arten(_stand()) == [Art.BRACHFLAECHE]


def test_ohne_aussage_ohne_antwort_und_alles_getan_keine_vorschlaege():
    assert _arten(_stand(brachflaeche=None)) == []


def test_ausgefallene_quelle_laesst_nur_ihre_regeln_aus():
    stand = _stand(einwuerfe=None, stimmen=0, beitraege=None, frische_antworten=None)

    # Ohne Einwuerfe und Beitraege kein "suchen", kein "einwerfen"; ohne frische
    # Antworten kein "bewerten"; die Aussage ohne Antwort bleibt als Rueckfall.
    assert _arten(stand) == [Art.BRACHFLAECHE]


def _beitrag(typ, nutzung, kurz=None, titel="T"):
    return {
        "id": str(uuid.uuid4()),
        "content_type": typ,
        "title": titel,
        "short_text": kurz,
        "usage_count": nutzung,
    }


def test_meistgenutzter_kommentar_ohne_kurzfassung():
    beitraege = [
        _beitrag(ContentType.COMMENTARY, 2, titel="wenig"),
        _beitrag(ContentType.COMMENTARY, 9, kurz="Kurz da", titel="mit Kurzfassung"),
        _beitrag(ContentType.GENERIC_TEXT, 50, titel="Hintergrundinfo"),
        _beitrag("commentary", 7, kurz="  ", titel="viel"),
        _beitrag(ContentType.COMMENTARY, 0, titel="ungenutzt"),
    ]

    gewaehlt = meistgenutzter_ohne_kurzfassung(beitraege)

    assert gewaehlt.titel == "viel"
    assert gewaehlt.nutzung == 7


def test_ohne_genutzten_kommentar_ohne_kurzfassung_nichts():
    assert meistgenutzter_ohne_kurzfassung([_beitrag("commentary", 0)]) is None
    assert meistgenutzter_ohne_kurzfassung([]) is None
