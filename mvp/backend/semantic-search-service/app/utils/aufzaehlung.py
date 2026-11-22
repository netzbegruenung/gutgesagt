"""
Aufzählungszeichen in Beitragstexten: Zeilen, die mit "* " oder "- " beginnen, werden
beim Speichern zu "• ". Die Zielplattformen zeigen kein Markdown; ein "•" sieht dort
überall gleich aus, und angezeigt und kopiert wird derselbe Text. Sonst bleibt der
Text, wie er ist, Zeilenumbrüche eingeschlossen; weiteres Markdown gibt es nicht.

Gilt für alle Beitragstypen und Fassungen, beim Anlegen und Ändern (dtos/). Das
Frontend zeigt in der Vorschau dasselbe (shared/aufzaehlung.ts). Bestehende Beiträge
werden nicht umgeschrieben.
"""

import re
from typing import Optional

# Am Zeilenanfang (nach "\n"), Einrückung erlaubt: "*" oder "-" vor Leerzeichen oder
# Tab. Nur dieses eine Zeichen wird ersetzt: Länge und Leerraum bleiben, die Grenzen
# der DTOs gelten also unverändert.
_AUFZAEHLUNG = re.compile(r"^([ \t]*)[*-](?=[ \t])", re.MULTILINE)
PUNKT = "•"


def mit_punkten(text: Optional[str]) -> Optional[str]:
    """Der Text mit "•" statt "*" und "-" vor Leerraum am Zeilenanfang; None bleibt None."""
    if not text:
        return text
    return _AUFZAEHLUNG.sub(lambda treffer: treffer.group(1) + PUNKT, text)


def beitrag_mit_punkten(beitrag, felder=("text", "short_text", "long_text")):
    """Eine Kopie des Beitragsmodells mit Punkten in allen Textfeldern, die es hat."""
    neu = {
        feld: mit_punkten(getattr(beitrag, feld))
        for feld in felder
        if isinstance(getattr(beitrag, feld, None), str)
    }
    return beitrag.model_copy(update=neu) if neu else beitrag
