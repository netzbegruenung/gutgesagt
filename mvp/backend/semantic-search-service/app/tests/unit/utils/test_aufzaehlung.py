"""
Aufzaehlungszeichen in Beitragstexten: "* " und "- " am Zeilenanfang werden beim
Speichern zu "• ", fuer alle Beitragstypen und Fassungen, beim Anlegen und Aendern.
"""

import pytest

from dtos.beitrag import BeitragAendernRequest
from dtos.commentary import AddCommentaryRequest
from dtos.generic_text import AddGenericTextRequest
from dtos.image import AddImageRequest
from dtos.post import AddPostRequest
from utils.aufzaehlung import mit_punkten

pytestmark = pytest.mark.unit

LISTE = "Darum:\n- erstens\n* zweitens"
PUNKTE = "Darum:\n• erstens\n• zweitens"


class TestMitPunkten:
    @pytest.mark.parametrize(
        "text, erwartet",
        [
            ("- eins", "• eins"),
            ("* eins", "• eins"),
            (LISTE, PUNKTE),
            # Nur das Zeichen wechselt: Einrueckung, Leerraum und Laenge bleiben.
            ("  -   eins", "  •   eins"),
            ("-\teins", "•\teins"),
            # Windows-Zeilenenden und Leerzeilen bleiben.
            ("a\r\n- b\r\n\r\n- c", "a\r\n• b\r\n\r\n• c"),
        ],
    )
    def test_zeilen_mit_strich_oder_stern_werden_punkte(self, text, erwartet):
        assert mit_punkten(text) == erwartet

    @pytest.mark.parametrize(
        "text",
        [
            "Minus - mitten im Satz",
            "-5 Grad in der Nacht",
            "**fett** bleibt, wie es ist",
            "--- Trennlinie",
            "# Kein Markdown",
            "• schon ein Punkt",
            "-",
            "",
        ],
    )
    def test_sonst_bleibt_der_text(self, text):
        assert mit_punkten(text) == text

    def test_laenge_bleibt_fuer_die_grenzen_der_dtos(self):
        text = "-         x\n*\tzwei"
        assert len(mit_punkten(text)) == len(text)

    def test_none_bleibt_none(self):
        assert mit_punkten(None) is None


class TestBeimSpeichern:
    def test_kommentar_mit_beiden_fassungen(self):
        anfrage = AddCommentaryRequest.model_validate(
            {
                "commentary": {
                    "title": "Ein Titel",
                    "text": LISTE,
                    "short_text": "- kurz",
                    "long_text": "* lang",
                    "references": [],
                },
                "references": [],
            }
        )
        assert anfrage.commentary.text == PUNKTE
        assert anfrage.commentary.short_text == "• kurz"
        assert anfrage.commentary.long_text == "• lang"

    def test_kommentar_ohne_fassungen(self):
        anfrage = AddCommentaryRequest.model_validate(
            {
                "commentary": {"title": "Ein Titel", "text": LISTE, "references": []},
                "references": [],
            }
        )
        assert anfrage.commentary.short_text is None
        assert anfrage.commentary.long_text is None

    def test_hintergrundinfo(self):
        anfrage = AddGenericTextRequest.model_validate(
            {
                "generictext": {"title": "Ein Titel", "text": LISTE, "references": []},
                "references": [],
            }
        )
        assert anfrage.generictext.text == PUNKTE

    def test_post(self):
        anfrage = AddPostRequest.model_validate(
            {"post": {"title": "Ein Titel", "text": LISTE, "platform": "x"}}
        )
        assert anfrage.post.text == PUNKTE

    def test_bild(self):
        anfrage = AddImageRequest.model_validate(
            {
                "image": {
                    "title": "Ein Titel",
                    "text": LISTE,
                    "image_url": "https://example.org/bild.png",
                }
            }
        )
        assert anfrage.image.text == PUNKTE

    def test_aendern_mit_fassungen(self):
        anfrage = BeitragAendernRequest(
            title="Ein Titel", text=LISTE, short_text="- kurz", long_text=None
        )
        assert anfrage.text == PUNKTE
        assert anfrage.short_text == "• kurz"
        assert anfrage.long_text is None
