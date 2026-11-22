"""
Ein Link auf einem fremden Server pruefen, ohne dass der Dienst dabei ins interne Netz
greift (Herkunft pruefen, #759).

Die Adresse einer Herkunft tippt eine Person. Ruft der Dienst sie ab, darf das kein Weg
zu Diensten im internen Netz sein (SSRF). Deshalb:

- Nur ``http`` und ``https``, keine Zugangsdaten in der Adresse, dieselben Regeln wie
  beim Anlegen (``utils/url_validator.validate_url_security``).
- Die Pruefung der IP-Adresse sitzt im Verbindungsaufbau (``_GeprueftesNetz``): Der
  Name wird dort aufgeloest, jede Adresse muss global erreichbar sein (keine private,
  Loopback-, Link-local-, reservierte oder Multicast-Adresse), und verbunden wird mit
  genau der geprueften Adresse. So gilt die Pruefung fuer jede Weiterleitung und auch
  dann, wenn der Name beim zweiten Aufloesen auf eine andere Adresse zeigt
  (DNS-Rebinding). TLS prueft das Zertifikat weiter gegen den Namen.
- Weiterleitungen folgt der Abruf selbst, hoechstens ``WEITERLEITUNGEN_HOECHSTENS``,
  jede mit derselben Pruefung.
- Zeitgrenzen je Schritt und fuer den ganzen Abruf. Gelesen wird nur der Kopf der
  Antwort, nie der Inhalt. Ein Proxy aus der Umgebung wird nicht benutzt.
- Der User-Agent nennt nur das Werkzeug, nichts zur Person oder zum Beitrag.

httpcore statt httpx: httpx bietet keinen Haken fuer die Namensaufloesung; httpcore
nimmt ein eigenes Netz-Backend (beide sind ohnehin Abhaengigkeiten).
"""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional, Tuple
from urllib.parse import urljoin, urlsplit

import httpcore
import httpx

from utils.url_validator import validate_url_security

USER_AGENT = "GutGesagt-Herkunftspruefung/1.0"
WEITERLEITUNGEN_HOECHSTENS = 5
# Je Schritt (Verbindung, Lesen des Kopfs) und fuer den ganzen Abruf samt Weiterleitungen
SCHRITT_SEKUNDEN = 8.0
GESAMT_SEKUNDEN = 25.0

# Ergebnisse (GLOSSARY.md "Herkunft pruefen")
OK = "ok"
UMGEZOGEN = "umgezogen"
TOT = "tot"
FEHLER = "fehler"
NICHT_ERREICHBAR = "nicht_erreichbar"
GESPERRT = "gesperrt"

# Antworten, nach denen ein GET nachfragt: manche Server kennen HEAD nicht oder lehnen
# ihn ab, liefern die Seite aber aus.
_NOCHMAL_MIT_GET = {400, 403, 404, 405, 406, 429, 500, 501, 503}


class AdresseGesperrt(Exception):
    """Ziel nicht erlaubt (Schema, Name, IP-Adresse); der Text nennt keine Adressteile."""


@dataclass(frozen=True)
class Abrufergebnis:
    ergebnis: str
    http_status: Optional[int] = None
    # Wohin die Adresse weiterleitet, wenn sie es tut
    ziel: Optional[str] = None


def adresse_erlaubt(ip: str) -> bool:
    """Ob eine IP-Adresse global erreichbar ist; alles Interne und Besondere ist gesperrt."""
    try:
        adresse = ipaddress.ip_address(ip.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(adresse, ipaddress.IPv6Address) and adresse.ipv4_mapped:
        adresse = adresse.ipv4_mapped
    return adresse.is_global and not adresse.is_multicast


def adresse_pruefen(url: str) -> None:
    """Regeln fuer die Adresse selbst, vor jedem Abruf und jeder Weiterleitung."""
    gueltig, _ = validate_url_security(url)
    if not gueltig:
        raise AdresseGesperrt("Adresse nicht erlaubt")
    teile = urlsplit(url)
    if teile.scheme.lower() not in ("http", "https") or not teile.hostname:
        raise AdresseGesperrt("Nur http und https")
    if teile.username is not None or teile.password is not None:
        raise AdresseGesperrt("Keine Zugangsdaten in der Adresse")


Aufloesen = Callable[[str, int], Awaitable[List[str]]]


async def _aufloesen(host: str, port: int) -> List[str]:
    """Alle IP-Adressen eines Namens (DNS des Systems)."""
    infos = await asyncio.get_running_loop().getaddrinfo(
        host, port, type=socket.SOCK_STREAM
    )
    return [info[4][0] for info in infos]


class _GeprueftesNetz(httpcore.AsyncNetworkBackend):
    """
    Netz-Backend fuer httpcore: loest den Namen selbst auf, prueft jede Adresse und
    verbindet mit der geprueften. Keine Unix-Sockets.
    """

    def __init__(
        self,
        erlaubt: Callable[[str], bool] = adresse_erlaubt,
        aufloesen: Optional[Aufloesen] = None,
    ):
        self._erlaubt = erlaubt
        self._aufloesen = aufloesen or _aufloesen
        self._innen = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options=None,
    ) -> httpcore.AsyncNetworkStream:
        try:
            adressen = await asyncio.wait_for(
                self._aufloesen(host, port), timeout=timeout or SCHRITT_SEKUNDEN
            )
        except (OSError, asyncio.TimeoutError) as fehler:
            raise httpcore.ConnectError(type(fehler).__name__) from None
        # Alle Adressen des Namens muessen erlaubt sein, nicht nur die erste: sonst
        # entschiede die Reihenfolge, wohin verbunden wird.
        if not adressen or not all(self._erlaubt(a) for a in adressen):
            raise AdresseGesperrt("IP-Adresse nicht erlaubt")
        return await self._innen.connect_tcp(
            adressen[0],
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise AdresseGesperrt("Kein Unix-Socket")

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


def neuer_pool(
    erlaubt: Callable[[str], bool] = adresse_erlaubt,
    aufloesen: Optional[Aufloesen] = None,
) -> httpcore.AsyncConnectionPool:
    """
    Ein Verbindungspool fuer einen Pruefungslauf. ``erlaubt`` und ``aufloesen`` nur in
    Tests ersetzen (lokaler Mock-Server unter einem Testnamen).
    """
    return httpcore.AsyncConnectionPool(
        network_backend=_GeprueftesNetz(erlaubt, aufloesen),
        max_connections=4,
        retries=0,
    )


def _gleichwertig(anfang: str, ende: str) -> bool:
    """
    Ob eine Weiterleitung nur die Form aendert: http zu https, ``www.`` davor oder
    weg, ein Schraegstrich am Ende. Das ist kein Umzug.
    """

    def form(url: str) -> Tuple[str, str, str]:
        teile = urlsplit(url)
        host = (teile.hostname or "").lower().removeprefix("www.")
        return host, teile.path.rstrip("/") or "/", teile.query

    return form(anfang) == form(ende)


async def _kopf(
    pool: httpcore.AsyncConnectionPool, methode: str, url: str
) -> Tuple[int, Optional[str]]:
    """Status und Location einer Anfrage; der Inhalt wird nicht gelesen."""
    try:
        roh = httpx.URL(url)
    except (httpx.InvalidURL, UnicodeError):
        raise AdresseGesperrt("Adresse nicht lesbar") from None
    ziel = httpcore.URL(
        scheme=roh.raw_scheme, host=roh.raw_host, port=roh.port, target=roh.raw_path
    )
    async with pool.stream(
        methode,
        ziel,
        headers=[
            (b"Host", _host_kopf(roh)),
            (b"User-Agent", USER_AGENT.encode()),
            (b"Accept", b"*/*"),
        ],
        extensions={
            "timeout": {
                "connect": SCHRITT_SEKUNDEN,
                "read": SCHRITT_SEKUNDEN,
                "write": SCHRITT_SEKUNDEN,
                "pool": SCHRITT_SEKUNDEN,
            }
        },
    ) as antwort:
        location = None
        for name, wert in antwort.headers:
            if name.lower() == b"location":
                location = wert.decode("latin-1").strip()
                break
        return antwort.status, location


def _host_kopf(roh) -> bytes:
    if roh.port is None:
        return roh.raw_host
    return roh.raw_host + b":" + str(roh.port).encode()


async def _pruefen(pool: httpcore.AsyncConnectionPool, url: str) -> Abrufergebnis:
    aktuell = url
    for schritt in range(WEITERLEITUNGEN_HOECHSTENS + 1):
        weitergeleitet = aktuell if schritt else None
        try:
            adresse_pruefen(aktuell)
            status, location = await _kopf(pool, "HEAD", aktuell)
            if status in _NOCHMAL_MIT_GET:
                status, location = await _kopf(pool, "GET", aktuell)
        except AdresseGesperrt:
            return Abrufergebnis(GESPERRT, ziel=weitergeleitet)
        except (httpcore.TimeoutException, httpcore.NetworkError):
            return Abrufergebnis(NICHT_ERREICHBAR, ziel=weitergeleitet)
        except httpcore.ProtocolError:
            return Abrufergebnis(FEHLER, ziel=weitergeleitet)
        except (httpcore.UnsupportedProtocol, httpcore.LocalProtocolError):
            return Abrufergebnis(GESPERRT, ziel=weitergeleitet)
        if 300 <= status < 400 and location:
            aktuell = urljoin(aktuell, location)
            continue
        if 200 <= status < 300:
            if weitergeleitet is None or _gleichwertig(url, aktuell):
                return Abrufergebnis(OK, status)
            return Abrufergebnis(UMGEZOGEN, status, aktuell)
        if status in (404, 410):
            return Abrufergebnis(TOT, status, weitergeleitet)
        return Abrufergebnis(FEHLER, status, weitergeleitet)
    # Zu viele Weiterleitungen, vermutlich eine Schleife
    return Abrufergebnis(FEHLER, None, aktuell)


async def link_pruefen(
    pool: httpcore.AsyncConnectionPool,
    url: str,
    gesamt_sekunden: float = GESAMT_SEKUNDEN,
) -> Abrufergebnis:
    """Eine Adresse pruefen, samt Weiterleitungen, hoechstens ``gesamt_sekunden`` lang."""
    try:
        return await asyncio.wait_for(_pruefen(pool, url), timeout=gesamt_sekunden)
    except asyncio.TimeoutError:
        return Abrufergebnis(NICHT_ERREICHBAR)
