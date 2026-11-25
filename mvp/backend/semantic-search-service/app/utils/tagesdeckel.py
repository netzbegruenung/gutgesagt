"""
Tagesdeckel (GLOSSARY.md): je Person hoechstens so viele Beitraege, Aussagen und
Einwuerfe am UTC-Tag (Entscheidung Maintainer 23.11.2026, "Variante A", gegen Spam).

Gezaehlt wird im Arbeitsspeicher wie bei den Rate-Limitern, je Kennung nur eine Zahl
fuer den laufenden UTC-Tag. Ein Neustart setzt alle Zaehler zurueck; das ist der Preis
dafuer, dass nichts gespeichert wird. Warum der UTC-Tag und kein gleitendes Fenster:
Die Meldung im Frontend sagt "morgen geht's weiter", und das stimmt mit einem
Kalendertag (Wechsel um 1 bzw. 2 Uhr deutscher Zeit); je Kennung genuegt eine Zahl
statt einer Liste von Zeitpunkten, und am Tageswechsel faellt alles weg.

Wer anlegen darf, entscheidet die Middleware (middleware/tagesdeckel.py); hier nur
das Zaehlen. Reserviert wird vor dem Anlegen, damit gleichzeitige Anfragen den
Deckel nicht gemeinsam ueberspringen; legt die Anfrage nichts an, gibt die
Middleware den Platz wieder frei.
"""

from datetime import date
from typing import Callable, Dict, Optional, Tuple

from core.config import settings
from utils.utc_tag import heute_utc


class Tagesdeckel:
    def __init__(self, je_tag: int, heute: Callable[[], date] = heute_utc) -> None:
        self.je_tag = je_tag
        self._heute = heute
        # Kennung -> (UTC-Tag, Zahl der Anlagen an diesem Tag)
        self._zaehler: Dict[str, Tuple[date, int]] = {}

    def _anzahl(self, kennung: str, tag: date) -> int:
        eintrag = self._zaehler.get(kennung)
        return eintrag[1] if eintrag and eintrag[0] == tag else 0

    def reservieren(self, kennung: str) -> Optional[date]:
        """
        Einen Platz fuer eine Anlage belegen und den Tag zurueckgeben, auf den er
        zaehlt. None, wenn der Deckel fuer heute erreicht ist; dann wird nichts
        gezaehlt.

        Ohne await zwischen Pruefen und Zaehlen: In der Event-Loop laeuft das am
        Stueck, eine Sperre braucht es nicht.
        """
        tag = self._heute()
        anzahl = self._anzahl(kennung, tag)
        if anzahl >= self.je_tag:
            return None
        self._zaehler[kennung] = (tag, anzahl + 1)
        return tag

    def freigeben(self, kennung: str, tag: date) -> None:
        """
        Einen reservierten Platz zurueckgeben (die Anfrage hat nichts angelegt). Nur
        auf dem Tag der Reservierung: Lief die Anfrage ueber Mitternacht, zaehlt der
        neue Tag nicht herunter.
        """
        anzahl = self._anzahl(kennung, tag)
        if anzahl == 0:
            return
        if anzahl == 1:
            del self._zaehler[kennung]
        else:
            self._zaehler[kennung] = (tag, anzahl - 1)

    async def cleanup(self) -> None:
        """Zaehler von vergangenen Tagen entfernen (im Takt der Rate-Limiter)."""
        tag = self._heute()
        for kennung in [k for k, (t, _) in self._zaehler.items() if t != tag]:
            del self._zaehler[kennung]


tagesdeckel = Tagesdeckel(settings.tagesdeckel_beitraege)
