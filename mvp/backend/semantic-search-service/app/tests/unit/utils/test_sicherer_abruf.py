"""
Sicherer Abruf fuer "Herkunft pruefen" (#759): Ergebnisse gegen einen lokalen
Mock-Server, keine fremden Seiten. Der Mock-Server laeuft auf 127.0.0.1 und ist unter
Testnamen (*.test) erreichbar: Die Tests ersetzen die Namensaufloesung und lassen nur
diese eine Adresse zu. Was gesperrt sein muss (interne Adressen, Weiterleitung nach
innen, falsches Schema), pruefen sie mit der echten Regel ``adresse_erlaubt``.
"""

import asyncio
import http.server
import threading
import time

import pytest

from utils import sicherer_abruf
from utils.sicherer_abruf import (
    FEHLER,
    GESPERRT,
    NICHT_ERREICHBAR,
    OK,
    TOT,
    UMGEZOGEN,
    USER_AGENT,
    adresse_erlaubt,
    link_pruefen,
    neuer_pool,
)

pytestmark = pytest.mark.unit

MOCK = "127.0.0.1"


class _Handler(http.server.BaseHTTPRequestHandler):
    anfragen: list = []

    def _antworten(self):
        type(self).anfragen.append(
            (self.command, self.path, self.headers.get("User-Agent"))
        )
        pfad = self.path
        if pfad == "/langsam":
            time.sleep(2)
        weiter = {
            "/umzug": "http://neu.test:{port}/ziel",
            "/slash": "/slash/",
            "/https": "http://quelle.test:{port}/https-ziel",
            "/nach-innen": "http://intern.test:{port}/",
            "/nach-loopback": "http://127.0.0.1:{port}/",
            "/nach-ftp": "ftp://quelle.test/datei",
            "/schleife": "/schleife",
            "/zu-tot": "/weg",
            "/anderer-port": "http://quelle.test:6379/",
        }
        if pfad in weiter:
            self.send_response(301)
            self.send_header(
                "Location", weiter[pfad].format(port=self.server.server_address[1])
            )
            self.end_headers()
            return
        if pfad == "/ohne-location":
            self.send_response(302)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if pfad == "/bremst":
            self.send_response(429)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if pfad == "/nur-get" and self.command == "HEAD":
            self.send_response(405)
            self.end_headers()
            return
        status = {"/weg": 404, "/entfernt": 410, "/kaputt": 500}.get(pfad, 200)
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_HEAD = _antworten
    do_GET = _antworten

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def _mock_server():
    srv = http.server.ThreadingHTTPServer((MOCK, 0), _Handler)
    faden = threading.Thread(target=srv.serve_forever, daemon=True)
    faden.start()
    yield srv.server_address[1]
    srv.shutdown()


@pytest.fixture
def server(_mock_server, monkeypatch):
    """Port des Mock-Servers; nur fuer den Test zusaetzlich erlaubt."""
    monkeypatch.setattr(
        sicherer_abruf,
        "ERLAUBTE_PORTS",
        sicherer_abruf.ERLAUBTE_PORTS | {_mock_server},
    )
    return _mock_server


def _aufloesen(tabelle):
    async def aufloesen(host, port):
        if host not in tabelle:
            raise OSError("unbekannt")
        return tabelle[host]

    return aufloesen


NAMEN = {
    "quelle.test": [MOCK],
    "neu.test": [MOCK],
    "intern.test": ["10.0.0.7"],
    "gemischt.test": ["93.184.216.34", MOCK],
}


def _pruefen(url, erlaubt=lambda ip: ip == MOCK, **kw):
    async def lauf():
        pool = neuer_pool(erlaubt, _aufloesen(NAMEN))
        try:
            return await link_pruefen(pool, url, **kw)
        finally:
            await pool.aclose()

    return asyncio.run(lauf())


class TestErgebnisse:
    def test_ok(self, server):
        assert _pruefen(f"http://quelle.test:{server}/").ergebnis == OK

    def test_umgezogen_mit_ziel(self, server):
        e = _pruefen(f"http://quelle.test:{server}/umzug")
        assert (e.ergebnis, e.http_status) == (UMGEZOGEN, 200)
        assert e.ziel == f"http://neu.test:{server}/ziel"

    def test_nur_schraegstrich_ist_kein_umzug(self, server):
        assert _pruefen(f"http://quelle.test:{server}/slash").ergebnis == OK

    @pytest.mark.parametrize("pfad, status", [("/weg", 404), ("/entfernt", 410)])
    def test_tot(self, server, pfad, status):
        e = _pruefen(f"http://quelle.test:{server}{pfad}")
        assert (e.ergebnis, e.http_status) == (TOT, status)

    def test_weiterleitung_auf_tote_seite_nennt_das_ziel(self, server):
        e = _pruefen(f"http://quelle.test:{server}/zu-tot")
        assert e.ergebnis == TOT
        assert e.ziel == f"http://quelle.test:{server}/weg"

    def test_serverfehler(self, server):
        e = _pruefen(f"http://quelle.test:{server}/kaputt")
        assert (e.ergebnis, e.http_status) == (FEHLER, 500)

    def test_ohne_head_fragt_get_nach(self, server):
        _Handler.anfragen.clear()
        assert _pruefen(f"http://quelle.test:{server}/nur-get").ergebnis == OK
        assert [a[0] for a in _Handler.anfragen] == ["HEAD", "GET"]

    def test_umleitung_ohne_ziel_ist_fehler(self, server):
        e = _pruefen(f"http://quelle.test:{server}/ohne-location")
        assert (e.ergebnis, e.http_status) == (FEHLER, 302)

    def test_bei_429_kein_zweiter_abruf(self, server):
        _Handler.anfragen.clear()
        e = _pruefen(f"http://quelle.test:{server}/bremst")
        assert (e.ergebnis, e.http_status) == (FEHLER, 429)
        assert [a[0] for a in _Handler.anfragen] == ["HEAD"]

    def test_zweite_adresse_wenn_die_erste_nicht_antwortet(self, server):
        """Dual-Stack ohne Route: die naechste geprueften Adresse versuchen."""
        NAMEN["zwei.test"] = ["127.0.0.2", MOCK]
        try:
            e = _pruefen(
                f"http://zwei.test:{server}/",
                erlaubt=lambda ip: ip in ("127.0.0.2", MOCK),
            )
        finally:
            del NAMEN["zwei.test"]
        assert e.ergebnis == OK

    def test_schleife_bricht_ab(self, server):
        assert _pruefen(f"http://quelle.test:{server}/schleife").ergebnis == FEHLER

    def test_unbekannter_name_nicht_erreichbar(self, server):
        e = _pruefen(f"http://gibt-es-nicht.test:{server}/")
        assert e.ergebnis == NICHT_ERREICHBAR

    def test_zeitgrenze(self, server, monkeypatch):
        monkeypatch.setattr(sicherer_abruf, "SCHRITT_SEKUNDEN", 0.3)
        e = _pruefen(f"http://quelle.test:{server}/langsam", gesamt_sekunden=0.5)
        assert e.ergebnis == NICHT_ERREICHBAR

    def test_user_agent_ohne_personendaten(self, server):
        _Handler.anfragen.clear()
        _pruefen(f"http://quelle.test:{server}/")
        assert {a[2] for a in _Handler.anfragen} == {USER_AGENT}
        assert USER_AGENT == "GutGesagt-Herkunftspruefung/1.0"


class TestSsrf:
    def test_weiterleitung_ins_interne_netz_gesperrt(self, server):
        _Handler.anfragen.clear()
        e = _pruefen(f"http://quelle.test:{server}/nach-innen")
        assert e.ergebnis == GESPERRT
        assert e.ziel == f"http://intern.test:{server}/"

    def test_weiterleitung_auf_loopback_gesperrt(self, server):
        e = _pruefen(
            f"http://quelle.test:{server}/nach-loopback",
            erlaubt=lambda ip: True,
        )
        assert e.ergebnis == GESPERRT

    def test_weiterleitung_auf_anderen_port_gesperrt(self, server):
        e = _pruefen(f"http://quelle.test:{server}/anderer-port")
        assert e.ergebnis == GESPERRT

    def test_weiterleitung_auf_anderes_schema_gesperrt(self, server):
        assert _pruefen(f"http://quelle.test:{server}/nach-ftp").ergebnis == GESPERRT

    def test_name_mit_interner_adresse_gesperrt(self, server):
        e = _pruefen(f"http://intern.test:{server}/")
        assert e.ergebnis == GESPERRT

    def test_eine_interne_adresse_unter_mehreren_genuegt(self, server):
        """Kein Ausweichen auf die erste Adresse: alle muessen erlaubt sein."""
        e = _pruefen(f"http://gemischt.test:{server}/", erlaubt=adresse_erlaubt)
        assert e.ergebnis == GESPERRT

    def test_echte_regel_sperrt_den_mock(self, server):
        """Ohne Ausnahme fuer den Test ist auch der Mock (Loopback) gesperrt."""
        e = _pruefen(f"http://quelle.test:{server}/", erlaubt=adresse_erlaubt)
        assert e.ergebnis == GESPERRT
        _Handler.anfragen.clear()

    @pytest.mark.parametrize(
        "url",
        [
            "ftp://quelle.test/datei",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "http://localhost/",
            "http://127.0.0.1/",
            "http://192.168.1.1/",
            "http://nutzer:geheim@quelle.test/",
            "gopher://quelle.test/",
            "http://quelle.test:6379/",
            "http://quelle.test:99999/",
            "http://[::1]/",
        ],
    )
    def test_adresse_selbst_gesperrt(self, url):
        _Handler.anfragen.clear()
        assert _pruefen(url, erlaubt=lambda ip: True).ergebnis == GESPERRT
        assert _Handler.anfragen == []


@pytest.mark.parametrize(
    "url", ["http://2130706433/", "http://0x7f.1/", "http://017700000001/"]
)
def test_zahlenform_einer_ip_mit_echter_aufloesung_gesperrt(url):
    """Dezimal-, Hex- und Oktalform loest getaddrinfo zu 127.0.0.1 auf: gesperrt, ohne Netz."""

    async def lauf():
        pool = neuer_pool()
        try:
            return await link_pruefen(pool, url)
        finally:
            await pool.aclose()

    assert asyncio.run(lauf()).ergebnis == GESPERRT


@pytest.mark.parametrize(
    "ip, erlaubt",
    [
        ("93.184.216.34", True),
        ("2606:2800:220:1:248:1893:25c8:1946", True),
        ("127.0.0.1", False),
        ("10.1.2.3", False),
        ("172.16.0.1", False),
        ("192.168.0.1", False),
        ("169.254.169.254", False),
        ("100.64.0.1", False),
        ("0.0.0.0", False),
        ("224.0.0.1", False),
        ("::1", False),
        ("fc00::1", False),
        ("fe80::1%eth0", False),
        ("::ffff:127.0.0.1", False),
        ("::ffff:10.0.0.1", False),
        ("kein-ip", False),
        # IPv4 in IPv6 eingebettet: es zaehlt die eingebettete Adresse
        ("64:ff9b::a00:1", False),
        ("64:ff9b::5db8:d822", True),
        ("::7f00:1", False),
        ("::ffff:0:a00:1", False),
        ("2002:0a00:0001::1", False),
        ("2001:0:4136:e378:8000:63bf:f5ff:fffe", False),
        ("fec0::1", False),
    ],
)
def test_adresse_erlaubt(ip, erlaubt):
    assert adresse_erlaubt(ip) is erlaubt
