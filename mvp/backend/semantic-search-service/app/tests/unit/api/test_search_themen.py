"""
"Alles zum Thema" in der Suchantwort (#754): Passt eine kurze Eingabe zu einem Thema,
traegt die Antwort `passende_themen` mit den meistgenutzten Aussagen. Die Treffer
und ihre Reihenfolge bleiben dabei unveraendert; das Feld kommt nur dazu.

Baut auf dem Aufbau aus test_search_ranking.py auf (Router allein, Dienste ersetzt).
"""

import logging
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from dependencies import get_themen_aussagen_service
from domain.models.content_type import ContentType
from services.themen_aussagen_service import AussageDesThemas
from tests.unit.api.test_search_ranking import (  # noqa: F401 - Fixture
    SEARCH_URL,
    _reply,
    _statement_result,
    app,
    search_client,
)

pytestmark = pytest.mark.api

AUSSAGE = AussageDesThemas(
    statement_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
    text="Die Wärmepumpe funktioniert im Altbau nicht",
    antworten=3,
    nutzung=12,
)


def _themen_service(aussagen=(AUSSAGE,), anzahl=None, fehler=None):
    service = MagicMock()
    if fehler:
        service.meistgenutzte = AsyncMock(side_effect=fehler)
    else:
        service.meistgenutzte = AsyncMock(
            return_value=(list(aussagen), len(aussagen) if anzahl is None else anzahl)
        )
    app.dependency_overrides[get_themen_aussagen_service] = lambda: service
    return service


def _treffer():
    a, b = uuid.uuid4(), uuid.uuid4()
    return [
        _statement_result(0.95, [_reply(ContentType.COMMENTARY, 0.8, b)], "B"),
        _statement_result(1.0, [_reply(ContentType.COMMENTARY, 1.0, a)], "A"),
    ]


def _treffer_der_antwort(antwort):
    """Je Beitragstyp die Treffer: Beitrag, Score, Aussage, in ihrer Reihenfolge."""
    return {
        feld: [
            (
                t[feld.replace("_search_results", "_result")]["id"],
                t["score"],
                t["statement_text"],
                t["statement_id"],
            )
            for t in liste
        ]
        for feld, liste in antwort.items()
        if feld.endswith("_search_results")
    } | {feld: n for feld, n in antwort.items() if feld.endswith("_count")}


def test_kurze_eingabe_bekommt_ihr_thema(search_client):
    client = search_client(statement_results=_treffer())
    service = _themen_service(anzahl=8)

    antwort = client.post(SEARCH_URL, json={"query_text": "Heizung", "limit": 10})

    assert antwort.status_code == 200
    assert antwort.json()["passende_themen"] == [
        {
            "schluessel": "energie-heizen",
            "name": "Energie und Heizen",
            "motiv": "themen/energie-heizen.svg",
            "aussagen": [
                {
                    "statement_id": str(AUSSAGE.statement_id),
                    "text": AUSSAGE.text,
                    "antworten": 3,
                }
            ],
            "anzahl_aussagen": 8,
        }
    ]
    service.meistgenutzte.assert_awaited_once_with("energie-heizen", 5)


def test_treffer_und_reihenfolge_bleiben_gleich(search_client):
    """Mit und ohne passendes Thema dieselben Treffer in derselben Reihenfolge."""
    treffer = _treffer()
    client = search_client(statement_results=treffer)

    _themen_service(aussagen=())
    ohne = client.post(SEARCH_URL, json={"query_text": "Heizung", "limit": 10}).json()
    _themen_service()
    mit = client.post(SEARCH_URL, json={"query_text": "Heizung", "limit": 10}).json()

    assert ohne["passende_themen"] is None
    assert mit["passende_themen"]
    assert _treffer_der_antwort(mit) == _treffer_der_antwort(ohne)
    assert [t["statement_text"] for t in mit["commentary_search_results"]] == ["A", "B"]


def test_auch_ohne_treffer(search_client):
    client = search_client(statement_results=[])
    _themen_service()

    antwort = client.post(SEARCH_URL, json={"query_text": "Wärmepumpe", "limit": 10})

    daten = antwort.json()
    assert daten["commentary_search_results_count"] == 0
    assert [t["schluessel"] for t in daten["passende_themen"]] == ["energie-heizen"]


def test_lange_eingabe_ohne_thema(search_client):
    client = search_client(statement_results=_treffer())
    service = _themen_service()

    antwort = client.post(
        SEARCH_URL,
        json={"query_text": "Die Heizung der Grünen ist zu teuer", "limit": 10},
    )

    assert antwort.json()["passende_themen"] is None
    service.meistgenutzte.assert_not_awaited()


def test_fehler_laesst_die_suche_stehen_ohne_suchtext_im_log(search_client, caplog):
    client = search_client(statement_results=_treffer())
    _themen_service(fehler=RuntimeError("Heizung kaputt"))

    with caplog.at_level(logging.DEBUG):
        antwort = client.post(
            SEARCH_URL, json={"query_text": "Heizungsgesetz", "limit": 10}
        )

    assert antwort.status_code == 200
    assert antwort.json()["passende_themen"] is None
    assert antwort.json()["commentary_search_results_count"] == 2
    # Der Suchtext steht in keiner Logzeile (#239, #275), auch nicht im Fehlertext.
    assert all("Heizung" not in r.getMessage() for r in caplog.records)


def test_alle_aussagen_zum_thema(search_client):
    client = search_client()
    service = _themen_service(anzahl=1)

    antwort = client.get("/api/v1/search/thema/energie-heizen")

    assert antwort.status_code == 200
    assert antwort.json()["thema"]["name"] == "Energie und Heizen"
    assert antwort.json()["thema"]["aussagen"][0]["text"] == AUSSAGE.text
    service.meistgenutzte.assert_awaited_once_with("energie-heizen", 50)


def test_alle_aussagen_unbekanntes_thema(search_client):
    client = search_client()
    _themen_service()

    assert client.get("/api/v1/search/thema/gibt-es-nicht").status_code == 404
