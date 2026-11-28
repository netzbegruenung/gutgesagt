"""
Hinweis zum Einladungslink waehrend der BDK (Rundgang 28.11.2026): In der Hilfe,
Abschnitt „Mitmachen“, steht vom Tag ``bdk_hinweis_von`` bis ``bdk_hinweis_bis``
(Admin-Einstellungen, deutsche Zeit, je einschliesslich), wo es auf der BDK einen
Einladungslink gibt. Nur mit dem Paket ``k_begruessung`` (BDK-Begruessung). Nur Anzeige,
gespeichert wird nichts; das Frontend erfaehrt es ueber GET /api/v1/funktionen
(``bdk_hinweis``).
"""

from datetime import date
from typing import Callable, Optional

from core.config import Settings
from services.einstellungen_service import (
    BDK_HINWEIS_BIS,
    BDK_HINWEIS_VON,
    datum_lesen,
    get_einstellungen_service,
)
from services.schalter_service import heute_berlin, schalter_wirksam

PAKET = "k_begruessung"


def bdk_hinweis_an(
    settings: Optional[Settings] = None,
    heute: Callable[[], date] = heute_berlin,
) -> bool:
    """Ob der Hinweis heute steht: Paket an und heute im Zeitfenster."""
    if not schalter_wirksam(PAKET, settings):
        return False
    einstellungen = get_einstellungen_service()
    von = datum_lesen(einstellungen.wert(BDK_HINWEIS_VON))
    bis = datum_lesen(einstellungen.wert(BDK_HINWEIS_BIS))
    if von is None or bis is None:
        return False
    return von <= heute() <= bis
