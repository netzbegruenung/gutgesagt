"""
Tagesdeckel an den Anlege-Routen (utils/tagesdeckel.py, GLOSSARY.md "Tagesdeckel").

Gezaehlt wird, was einen Beitrag, eine Aussage oder einen Einwurf anlegt, je Anlage
einmal:

- /addCommentary, /addGenericText, /addPost: je ein Beitrag. Die Herkuenfte, die ein
  Beitrag mitbringt, legt der Suchdienst in derselben Anfrage an; sie zaehlen nicht
  eigens.
- /addRawInput: ein Einwurf in den Fangkorb.
- /statement/vorab und /addStatement: eine Aussage ohne Beitrag.

Nicht gezaehlt wird /reference/add (in RateLimitMiddleware noch als "/addReference"
gefuehrt): Das Formular legt damit mehrere Herkuenfte je Beitrag an, und die Route
hat ein eigenes Rate-Limit. Ebenso wenig zaehlen Anfragen, die nichts anlegen:
Antworten ab 400 und Treffer einer Dublette ("vorhanden", bzw. eine schon bekannte
Aussage), die der Handler mit ``nichts_angelegt`` kennzeichnet.

Ausgenommen sind Admins (X-Is-Admin vom BFF oder SEMANTIC_SEARCH_ADMIN_USERS) und
Startkonten: Redaktion und Import legen an einem Tag mehr an. Ohne Kennung zaehlt
nichts; die Routen verlangen eine Anmeldung und antworten dann selbst mit 401.
"""

import logging
from typing import Callable, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import Settings, settings as standard_settings
from core.logging import log_pseudonym
from utils.tagesdeckel import Tagesdeckel, tagesdeckel as standard_deckel

logger = logging.getLogger(__name__)

# Endungen der gezaehlten POST-Routen (siehe Moduldoku).
GEZAEHLTE_ROUTEN = (
    "/addCommentary",
    "/addGenericText",
    "/addPost",
    "/addRawInput",
    "/statement/vorab",
    "/addStatement",
)

# Kennung im 429, an der das Frontend die freundliche Meldung erkennt
# (beitragsformular/speicherfehler.ts).
TAGESDECKEL_KENNUNG = "TAGESDECKEL"

_NICHTS_ANGELEGT = "tagesdeckel_nichts_angelegt"


def nichts_angelegt(request: Request) -> None:
    """
    Vom Handler aufzurufen, wenn die Anfrage erfolgreich war, aber nichts angelegt
    hat (Dublette). Die Middleware gibt den reservierten Platz dann zurueck.
    """
    setattr(request.state, _NICHTS_ANGELEGT, True)


def wird_gezaehlt(request: Request) -> bool:
    return request.method == "POST" and request.url.path.endswith(GEZAEHLTE_ROUTEN)


class TagesdeckelMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        deckel: Optional[Tagesdeckel] = None,
        einstellungen: Optional[Callable[[], Settings]] = None,
    ):
        super().__init__(app)
        self._deckel = deckel or standard_deckel
        self._einstellungen = einstellungen or (lambda: standard_settings)

    def _ausgenommen(self, request: Request, kennung: str) -> bool:
        einstellungen = self._einstellungen()
        return (
            # Wie dependencies.ist_admin_kopf; den Header setzt allein das BFF.
            (request.headers.get("X-Is-Admin") or "").lower() == "true"
            or einstellungen.is_admin_user(kennung)
            or einstellungen.ist_startkonto(kennung)
        )

    async def dispatch(self, request: Request, call_next):
        if not wird_gezaehlt(request):
            return await call_next(request)
        kennung = request.headers.get("X-User")
        if not kennung or kennung == "anonymous" or self._ausgenommen(request, kennung):
            return await call_next(request)

        if not self._deckel.reservieren(kennung):
            logger.warning(
                f"Tagesdeckel erreicht: {log_pseudonym(kennung)} "
                f"({self._deckel.je_tag} je Tag)"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Für heute ist Schluss mit neuen Beiträgen, morgen geht's weiter.",
                    "error": TAGESDECKEL_KENNUNG,
                },
            )

        try:
            response = await call_next(request)
        except BaseException:
            self._deckel.freigeben(kennung)
            raise
        if response.status_code >= 400 or getattr(
            request.state, _NICHTS_ANGELEGT, False
        ):
            self._deckel.freigeben(kennung)
        return response
