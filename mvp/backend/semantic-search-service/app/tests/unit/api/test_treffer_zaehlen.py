"""
search.treffer_zaehlen (Saal-Spruch, Rundgang 2): zaehlt, was die Suche zeigte, ohne
Spuren. Keine Aussage aus der Suchanfrage, kein Suchereignis, kein Zaehler "Suchen ohne
Treffer". Die Dienste sind Attrappen, die Pipeline-Schritte ebenso.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.v1 import search as modul

pytestmark = [pytest.mark.unit, pytest.mark.api]


def test_zaehlt_die_gezeigten_beitraege_ohne_spuren():
    orchestrator = MagicMock()
    orchestrator.inhalte.return_value = ["k1", "k2", "h1"]
    spuren = {
        name: MagicMock(name=name)
        for name in (
            "get_search_query_statement_recorder",
            "get_suchen_ohne_treffer_service",
            "get_search_tracking_service",
        )
    }
    sammeln = AsyncMock()
    with patch.multiple(
        modul,
        get_statement_service=MagicMock(),
        get_commentary_service=MagicMock(),
        get_generic_text_service=MagicMock(),
        get_post_service=MagicMock(),
        get_image_service=MagicMock(),
        get_reference_service=MagicMock(),
        get_voting_service=MagicMock(),
        get_usage_service=MagicMock(),
        inhaltstor_fuer=MagicMock(return_value=None),
        suchspezifikationen=MagicMock(return_value=[]),
        aussagetreffer_finden=AsyncMock(return_value=([], {})),
        treffer_sammeln=sammeln,
        SearchOrchestrator=MagicMock(return_value=orchestrator),
        **spuren,
    ):
        anzahl = asyncio.run(modul.treffer_zaehlen("Die Grünen machen alles kaputt"))

    assert anzahl == 3
    assert sammeln.await_args.args[1] == "Die Grünen machen alles kaputt"
    for name, attrappe in spuren.items():
        assert not attrappe.called, name
