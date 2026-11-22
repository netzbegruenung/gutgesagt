"""
Themenvorschlaege (#401): Prototypen um die Mitte, Auswahl mit Schwelle, Abstand und
Hoechstzahl, NLI als zweite Meinung, und der Service mit Neubau und Rueckfall. Ohne
Modell: Vektoren von Hand, die Messung mit Modell steht in tests/regression/THEMEN.md.
"""

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pytest

from domain.themen import THEMEN
from services.themen_vorschlag import (
    NLI_KANDIDATEN,
    NLI_VORLAGE,
    Prototypen,
    Schwellen,
    ThemenVorschlagService,
    auswaehlen,
    namenstext,
    nli_paare,
    prototypen_bauen,
    rangliste,
)

OFFEN = Schwellen(aehnlichkeit_ab=-1.0, abstand_hoechstens=2.0)


def einheit(*werte: float) -> np.ndarray:
    v = np.asarray(werte, dtype=np.float32)
    return v / np.linalg.norm(v)


class TestNamenstext:
    def test_ohne_stichwoerter_nur_der_name(self):
        assert namenstext(THEMEN[0]) == THEMEN[0].name

    def test_mit_stichwoertern_name_und_stichwoerter(self):
        @dataclass(frozen=True)
        class MitStichwoertern:
            schluessel: str
            name: str
            stichwoerter: tuple

        thema = MitStichwoertern("verkehr", "Verkehr", ("Auto", "Bahn"))
        assert namenstext(thema) == "Verkehr: Auto, Bahn"


class TestPrototypen:
    def test_ohne_beispiele_die_namen_um_ihre_mitte(self):
        p = prototypen_bauen({"a": einheit(1, 0.1), "b": einheit(0.1, 1)}, [])

        np.testing.assert_allclose(p.mitte, (einheit(1, 0.1) + einheit(0.1, 1)) / 2)
        # Um die Mitte verschoben zeigen beide Prototypen in entgegengesetzte Richtungen.
        assert float(np.dot(p.vektoren["a"], p.vektoren["b"])) == pytest.approx(-1.0)

    def test_beispiele_ziehen_den_prototyp_zu_sich(self):
        namen = {"a": einheit(1, 0, 0), "b": einheit(0, 1, 0)}
        ohne = prototypen_bauen(namen, [], namensgewicht=1.0)
        mit = prototypen_bauen(
            namen, [(einheit(0, 0, 1), ["a"])] * 3, namensgewicht=1.0
        )

        assert mit.vektoren["a"][2] > ohne.vektoren["a"][2]

    def test_unbekannte_themen_in_beispielen_fallen_weg(self):
        p = prototypen_bauen({"a": einheit(1, 0)}, [(einheit(0, 1), ["gibt-es-nicht"])])

        assert set(p.vektoren) == {"a"}

    def test_rangliste_das_naechste_zuerst(self):
        p = prototypen_bauen(
            {"a": einheit(1, 0, 0), "b": einheit(0, 1, 0), "c": einheit(0, 0, 1)}, []
        )

        rang = rangliste(einheit(0.1, 1, 0), p)

        assert [s for s, _ in rang][0] == "b"
        assert rang[0][1] > rang[1][1] >= rang[2][1]


class TestAuswaehlen:
    RANG = [("a", 0.40), ("b", 0.36), ("c", 0.30), ("d", 0.10)]

    def test_hoechstens_so_viele(self):
        assert auswaehlen(self.RANG, OFFEN, 2) == ["a", "b"]

    def test_ab_der_schwelle(self):
        assert auswaehlen(self.RANG, Schwellen(0.35, 1.0), 3) == ["a", "b"]

    def test_nicht_weiter_als_der_abstand_hinter_dem_ersten(self):
        assert auswaehlen(self.RANG, Schwellen(0.0, 0.05), 3) == ["a", "b"]

    def test_nichts_unter_der_schwelle(self):
        assert auswaehlen(self.RANG, Schwellen(0.5, 1.0), 3) == []

    def test_leere_rangliste_und_null(self):
        assert auswaehlen([], OFFEN, 3) == []
        assert auswaehlen(self.RANG, OFFEN, 0) == []

    def test_zweite_meinung_streicht_ergaenzt_aber_nicht(self):
        folgerungen = {"a": 0.9, "b": 0.1, "c": 0.8, "d": 0.99}
        schwellen = Schwellen(0.2, 1.0, folgerung_ab=0.5)

        # b gestrichen, c rueckt nach; d bleibt unter der Schwelle der Aehnlichkeit.
        assert auswaehlen(self.RANG, schwellen, 3, folgerungen) == ["a", "c"]

    def test_zweite_meinung_ohne_urteil_streicht(self):
        schwellen = Schwellen(0.0, 1.0, folgerung_ab=0.5)

        assert auswaehlen(self.RANG, schwellen, 3, {"b": 0.9}) == ["b"]


def test_nli_paare_mit_vorlage_und_namen():
    paare = nli_paare("Text", ["verkehr", "gibt-es-nicht"])

    assert paare == [("Text", NLI_VORLAGE.format("Verkehr"))]


# Fuer den Service: jedes Thema bekommt eine eigene Achse, Texte liegen auf der Achse
# ihres Themas (Name als Text) oder auf einer festen Mischung.
ACHSE = {t.schluessel: i for i, t in enumerate(THEMEN)}
DIM = len(THEMEN) + 1


class Einbetter:
    def __init__(self, texte: Optional[Dict[str, np.ndarray]] = None):
        self.texte = texte or {}
        self.aufrufe: List[str] = []

    def encode_query(self, text: str) -> List[float]:
        self.aufrufe.append(text)
        if text in self.texte:
            return list(self.texte[text])
        v = np.zeros(DIM, dtype=np.float32)
        for t in THEMEN:
            if namenstext(t) == text:
                v[ACHSE[t.schluessel]] = 1.0
                return list(v)
        v[-1] = 1.0
        return list(v)


def auf(*schluessel: str) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    for s in schluessel:
        v[ACHSE[s]] = 1.0
    return v / np.linalg.norm(v)


class Folgerer:
    def __init__(self, werte: Optional[Dict[str, float]]):
        self.werte = werte
        self.paare = []

    async def folgerungen(self, paare, warte_hoechstens=None):
        self.paare = list(paare)
        if self.werte is None:
            return None
        namen = {NLI_VORLAGE.format(t.name): t.schluessel for t in THEMEN}
        return [self.werte.get(namen[h], 0.0) for _, h in paare]


class Uhr:
    def __init__(self):
        self.jetzt = 0.0

    def __call__(self):
        return self.jetzt


def service(beispiele=(), texte=None, folgerer=None, uhr=None, laden=None):
    async def beispiele_laden():
        return list(beispiele)

    return ThemenVorschlagService(
        einbetter=Einbetter(texte),
        beispiele_laden=laden or beispiele_laden,
        schwellen=Schwellen(0.1, 0.05, 0.5),
        folgerer=folgerer,
        neu_nach=600.0,
        uhr=uhr or Uhr(),
    )


@pytest.mark.asyncio
class TestService:
    async def test_schlaegt_das_thema_des_textes_vor(self):
        s = service(texte={"Die Bahn kommt nie": auf("verkehr")})

        assert await s.vorschlagen("Die Bahn kommt nie", 3) == ["verkehr"]

    async def test_zwei_themen_wenn_der_text_dazwischen_liegt(self):
        s = service(texte={"Text": auf("verkehr", "klima")})

        assert sorted(await s.vorschlagen("Text", 3)) == ["klima", "verkehr"]
        assert len(await s.vorschlagen("Text", 1)) == 1

    async def test_leerer_text_ohne_vorschlag_und_ohne_einbettung(self):
        s = service()

        assert await s.vorschlagen("   ", 3) == []
        assert s._einbetter.aufrufe == []

    async def test_baut_die_prototypen_einmal_und_nach_der_frist_neu(self):
        uhr = Uhr()
        geladen = []

        async def laden():
            geladen.append(1)
            return [("Bahn", ["verkehr"])]

        s = service(texte={"Bahn": auf("verkehr")}, uhr=uhr, laden=laden)
        await s.vorschlagen("Bahn", 3)
        await s.vorschlagen("Bahn", 3)
        assert len(geladen) == 1
        uhr.jetzt = 601.0
        await s.vorschlagen("Bahn", 3)
        assert len(geladen) == 2
        # Schon eingebettete Beispiele werden nicht neu eingebettet.
        assert s._einbetter.aufrufe.count("Bahn") == 3 + 1

    async def test_scheitert_der_neubau_gelten_die_alten_prototypen(self):
        uhr = Uhr()
        aufrufe = []

        async def laden():
            aufrufe.append(1)
            if len(aufrufe) > 1:
                raise RuntimeError("Datenbank weg")
            return []

        s = service(texte={"Bahn": auf("verkehr")}, uhr=uhr, laden=laden)
        await s.vorschlagen("Bahn", 3)
        uhr.jetzt = 601.0

        assert await s.vorschlagen("Bahn", 3) == ["verkehr"]

    async def test_scheitert_der_erste_bau_scheitert_der_vorschlag(self):
        async def laden():
            raise RuntimeError("Datenbank weg")

        with pytest.raises(RuntimeError):
            await service(laden=laden).vorschlagen("Bahn", 3)

    async def test_zweite_meinung_auf_den_naechsten_kandidaten(self):
        folgerer = Folgerer({"verkehr": 0.1, "klima": 0.9})
        s = service(texte={"Text": auf("verkehr", "klima")}, folgerer=folgerer)

        assert await s.vorschlagen("Text", 3) == ["klima"]
        assert len(folgerer.paare) == NLI_KANDIDATEN

    async def test_ohne_nli_urteil_gilt_der_prototyp(self):
        s = service(texte={"Text": auf("verkehr")}, folgerer=Folgerer(None))

        assert await s.vorschlagen("Text", 3) == ["verkehr"]

    async def test_gleichzeitige_anfragen_bauen_einmal(self):
        geladen = []

        async def laden():
            geladen.append(1)
            await asyncio.sleep(0)
            return []

        s = service(texte={"Bahn": auf("verkehr")}, laden=laden)
        await asyncio.gather(*(s.vorschlagen("Bahn", 3) for _ in range(5)))

        assert len(geladen) == 1


def test_prototypen_sind_unveraenderlich_gebaut():
    p = prototypen_bauen({"a": einheit(1, 0)}, [])
    assert isinstance(p, Prototypen)
