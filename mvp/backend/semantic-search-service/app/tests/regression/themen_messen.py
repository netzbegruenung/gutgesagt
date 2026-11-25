"""
Misst die Themenvorschlaege (#401) per Leave-one-out: Je Aussage werden die Prototypen
aus allen anderen gebaut (services/themen_vorschlag.py) und die Vorschlaege mit ihren
Themen verglichen. Ausgabe: Treffer des ersten und der ersten zwei Themen, dazu
Precision und Recall je Schwelle, mit --nli auch mit dem NLI-Modell als zweiter Meinung.
Regeln und Ergebnis in THEMEN.md.

    cd mvp/backend/semantic-search-service/app
    ../venv/bin/python -m tests.regression.themen_messen                 # vorlaeufiges Messset
    ../venv/bin/python -m tests.regression.themen_messen --testset t.json  # Admin-Export
    ../venv/bin/python -m tests.regression.themen_messen --nli --zeit

--testset liest den Export von /themen/testset (Admin, Glossar "Testset"). Die Datei hat
keine Personendaten, enthaelt aber Texte aus Produktion: nicht ins Repo legen.
--themen-json nimmt Namen und Stichwoerter aus einer anderen themen.json (etwa einem
Branch), sonst gilt domain/themen.json.

Laedt das Einbettungsmodell (~1,5 GB RAM), mit --nli auch das NLI-Modell (~1,2 GB).
"""

import argparse
import json
import resource
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from core.config import EMBEDDING_MODELL, NLI_MODELL, Settings
from domain.themen import HOECHSTENS_JE_AUSSAGE, HOECHSTENS_JE_EINWURF, THEMEN, Thema
from services.themen_vorschlag import (
    NLI_KANDIDATEN,
    Schwellen,
    auswaehlen,
    namenstext,
    nli_paare,
    prototypen_bauen,
    rangliste,
)
from tests.regression.themen_messset import BEISPIELE

THREADS = 4
SCHWELLEN_AB = (0.0, 0.04, 0.08, 0.10, 0.12, 0.14, 0.16, 0.20)
ABSTAENDE = (0.03, 0.05, 0.08, 0.12)
FOLGERUNG_AB = (0.1, 0.3, 0.5, 0.7)


@dataclass(frozen=True)
class Fall:
    text: str
    themen: Tuple[str, ...]
    quelle: str


@dataclass(frozen=True)
class Ergebnis:
    precision: float
    recall: float
    leer: float
    im_schnitt: float


def faelle_laden(testset: Optional[str]) -> List[Fall]:
    if testset is None:
        return [Fall(b.text, b.themen, b.quelle) for b in BEISPIELE]
    with open(testset, encoding="utf-8") as datei:
        zuordnungen = json.load(datei)["zuordnungen"]
    return [Fall(z["text"], tuple(z["themen"]), "testset") for z in zuordnungen]


def themen_laden(pfad: Optional[str]) -> Sequence[Thema]:
    if pfad is None:
        return THEMEN
    with open(pfad, encoding="utf-8") as datei:
        eintraege = {e["schluessel"]: e for e in json.load(datei)}

    # Ein Ersatz mit Stichwoertern, falls Thema sie (noch) nicht hat: namenstext liest
    # sie per getattr.
    @dataclass(frozen=True)
    class MitStichwoertern:
        schluessel: str
        name: str
        stichwoerter: Tuple[str, ...]

    return [
        MitStichwoertern(
            t.schluessel,
            t.name,
            tuple(eintraege.get(t.schluessel, {}).get("stichwoerter", ())),
        )
        for t in THEMEN
    ]


def ranglisten(
    vektoren: np.ndarray,
    namensvektoren: Dict[str, np.ndarray],
    faelle: List[Fall],
    nur_namen: bool = False,
) -> List[List[Tuple[str, float]]]:
    """Leave-one-out: je Fall die Rangliste aus Prototypen ohne diesen Fall; mit
    nur_namen ganz ohne Beispiele (Start ohne Zuordnungen von Hand)."""
    ergebnis = []
    for i in range(len(faelle)):
        beispiele = [
            (vektoren[k], f.themen)
            for k, f in enumerate(faelle)
            if k != i and not nur_namen
        ]
        ergebnis.append(
            rangliste(vektoren[i], prototypen_bauen(namensvektoren, beispiele))
        )
    return ergebnis


def auswerten(
    raenge: List[List[Tuple[str, float]]],
    faelle: List[Fall],
    schwellen: Schwellen,
    hoechstens: int,
    folgerungen: Optional[List[Dict[str, float]]] = None,
) -> Ergebnis:
    richtig = falsch = verpasst = leer = gesamt = 0
    for i, (rang, fall) in enumerate(zip(raenge, faelle)):
        vorschlag = set(
            auswaehlen(
                rang, schwellen, hoechstens, folgerungen[i] if folgerungen else None
            )
        )
        soll = set(fall.themen)
        richtig += len(vorschlag & soll)
        falsch += len(vorschlag - soll)
        verpasst += len(soll - vorschlag)
        leer += not vorschlag
        gesamt += len(vorschlag)
    return Ergebnis(
        richtig / (richtig + falsch) if richtig + falsch else 0.0,
        richtig / (richtig + verpasst) if richtig + verpasst else 0.0,
        leer / len(faelle),
        gesamt / len(faelle),
    )


def treffer_oben(raenge, faelle, n: int) -> float:
    return statistics.mean(
        bool({s for s, _ in rang[:n]} & set(f.themen))
        for rang, f in zip(raenge, faelle)
    )


def tabelle(raenge, faelle, hoechstens, folgerungen=None, folgerung_ab=0.0) -> None:
    print(f"\nhoechstens {hoechstens}: P / R / ohne Vorschlag / Vorschlaege je Aussage")
    print("ab    " + "".join(f"| abstand {a:<20}" for a in ABSTAENDE))
    for ab in SCHWELLEN_AB:
        zeile = f"{ab:<5} "
        for abstand in ABSTAENDE:
            e = auswerten(
                raenge,
                faelle,
                Schwellen(ab, abstand, folgerung_ab),
                hoechstens,
                folgerungen,
            )
            zeile += (
                f"| {e.precision:.2f} {e.recall:.2f} {e.leer:.2f} {e.im_schnitt:.1f}"
                + " " * 9
            )
        print(zeile)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--testset", help="Export von /themen/testset (JSON)")
    parser.add_argument("--themen-json", help="Namen und Stichwoerter aus dieser Datei")
    parser.add_argument("--nli", action="store_true", help="auch mit NLI-Modell")
    parser.add_argument("--zeit", action="store_true", help="Antwortzeit und Speicher")
    parser.add_argument(
        "--nur-namen", action="store_true", help="Prototypen nur aus Name/Stichwoertern"
    )
    args = parser.parse_args()

    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(THREADS)
    faelle = faelle_laden(args.testset)
    themen = themen_laden(args.themen_json)
    modell = SentenceTransformer(EMBEDDING_MODELL)

    def einbetten(texte: List[str]) -> np.ndarray:
        return modell.encode(
            [f"query: {t}" for t in texte], normalize_embeddings=True, batch_size=32
        )

    vektoren = einbetten([f.text for f in faelle])
    namensvektoren = dict(
        zip(
            [t.schluessel for t in themen],
            einbetten([namenstext(t) for t in themen]),
        )
    )
    raenge = ranglisten(vektoren, namensvektoren, faelle, args.nur_namen)
    settings = Settings()
    gewaehlt = Schwellen(
        settings.themen_vorschlag_ab, settings.themen_vorschlag_abstand_hoechstens
    )

    print(
        f"Themenvorschlaege, {len(faelle)} Aussagen, Modell {EMBEDDING_MODELL}"
        + (", Prototypen nur aus den Namen" if args.nur_namen else "")
    )
    print(
        f"Stichwoerter: {sum(bool(getattr(t, 'stichwoerter', ())) for t in themen)}"
        f" von {len(themen)} Themen"
    )
    print(
        f"Erstes Thema passt: {treffer_oben(raenge, faelle, 1):.2f}, "
        f"eins der ersten zwei: {treffer_oben(raenge, faelle, 2):.2f}"
    )
    nach_quelle: Dict[str, List[int]] = defaultdict(list)
    for i, f in enumerate(faelle):
        nach_quelle[f.quelle].append(i)
    for quelle, idx in sorted(nach_quelle.items()):
        teil_r = [raenge[i] for i in idx]
        teil_f = [faelle[i] for i in idx]
        e = auswerten(teil_r, teil_f, gewaehlt, HOECHSTENS_JE_AUSSAGE)
        print(
            f"  {quelle:<8} {len(idx):>3} Aussagen: erstes {treffer_oben(teil_r, teil_f, 1):.2f},"
            f" gewaehlte Schwelle P {e.precision:.2f} R {e.recall:.2f}"
        )
    for hoechstens in (HOECHSTENS_JE_AUSSAGE, HOECHSTENS_JE_EINWURF):
        e = auswerten(raenge, faelle, gewaehlt, hoechstens)
        print(
            f"Gewaehlt (ab {gewaehlt.aehnlichkeit_ab}, abstand "
            f"{gewaehlt.abstand_hoechstens}, hoechstens {hoechstens}): "
            f"P {e.precision:.2f} R {e.recall:.2f} ohne Vorschlag {e.leer:.2f}"
            f" je Aussage {e.im_schnitt:.1f}"
        )
    tabelle(raenge, faelle, HOECHSTENS_JE_AUSSAGE)
    tabelle(raenge, faelle, HOECHSTENS_JE_EINWURF)

    nli = None
    if args.nli or args.zeit:
        from services.dieselbe_behauptung.nli_modell import NliModell

        nli = NliModell(NLI_MODELL)
        nli.laden_abwarten()
    if args.nli:
        folgerungen = []
        for fall, rang in zip(faelle, raenge):
            kandidaten = [s for s, _ in rang[:NLI_KANDIDATEN]]
            werte = nli.folgerungen_sync(nli_paare(fall.text, kandidaten)) or []
            folgerungen.append(dict(zip(kandidaten, werte)))
        for folgerung_ab in FOLGERUNG_AB:
            print(f"\nMit NLI als zweiter Meinung, Folgerung ab {folgerung_ab}")
            tabelle(raenge, faelle, HOECHSTENS_JE_AUSSAGE, folgerungen, folgerung_ab)

    if args.zeit:
        alle = list(zip(vektoren, (f.themen for f in faelle)))
        prototypen = prototypen_bauen(namensvektoren, alle)
        einbettung, nli_zeit = [], []
        for fall in faelle:
            start = time.perf_counter()
            vektor = einbetten([fall.text])[0]
            rang = rangliste(vektor, prototypen)
            auswaehlen(rang, gewaehlt, HOECHSTENS_JE_AUSSAGE)
            einbettung.append(time.perf_counter() - start)
            start = time.perf_counter()
            nli.folgerungen_sync(
                nli_paare(fall.text, [s for s, _ in rang[:NLI_KANDIDATEN]])
            )
            nli_zeit.append(time.perf_counter() - start)
        start = time.perf_counter()
        einbetten([f.text for f in faelle])
        bauen = time.perf_counter() - start
        print(f"\nAntwortzeit auf CPU, {THREADS} Threads (Median / 95 %):")
        for name, werte in (
            ("Prototyp", einbettung),
            ("+ NLI, 5 Kandidaten", nli_zeit),
        ):
            werte = sorted(werte)
            print(
                f"  {name}: {statistics.median(werte) * 1000:.0f} ms / "
                f"{werte[int(len(werte) * 0.95)] * 1000:.0f} ms"
            )
        print(f"  Prototypen bauen ({len(faelle)} Texte einbetten): {bauen:.1f} s")
        print(
            "  Speicher des Prozesses (Spitze): "
            f"{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MB"
        )


if __name__ == "__main__":
    main()
