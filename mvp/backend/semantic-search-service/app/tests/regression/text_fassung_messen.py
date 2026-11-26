"""
Misst das Messset "Geaenderter Text" (#636, text_fassung_paare.py): je Paar die
passage/passage- und query/query-Aehnlichkeit von alter und neuer Fassung mit
EMBEDDING_MODELL und, mit --nli, das Urteil von NLI_MODELL in beide Richtungen. Die
Zahlen stehen in MESSSET.md, Abschnitt "Geaenderter Text".

    cd mvp/backend/semantic-search-service/app
    ../venv/bin/python -m tests.regression.text_fassung_messen [--nli]
"""

import argparse
from functools import lru_cache
from typing import Dict, NamedTuple

import numpy as np

from core.config import EMBEDDING_MODELL, NLI_MODELL, Settings
from tests.regression.text_fassung_paare import PAARE


class TextScores(NamedTuple):
    pp: float
    qq: float


@lru_cache(maxsize=1)
def scores() -> Dict[str, TextScores]:
    """(pp, qq) je Paar-ID, einmal berechnet."""
    from sentence_transformers import SentenceTransformer

    modell = SentenceTransformer(EMBEDDING_MODELL)

    def einbetten(praefix, texte):
        return modell.encode(
            [f"{praefix}: {t}" for t in texte], normalize_embeddings=True
        )

    alt = [p.alt for p in PAARE]
    neu = [p.neu for p in PAARE]
    pa, pn = einbetten("passage", alt), einbetten("passage", neu)
    qa, qn = einbetten("query", alt), einbetten("query", neu)
    return {
        p.id: TextScores(float(np.dot(pa[i], pn[i])), float(np.dot(qa[i], qn[i])))
        for i, p in enumerate(PAARE)
    }


def auswertung(settings: Settings, mit_nli: bool = False) -> str:
    werte = scores()
    urteile = {}
    if mit_nli:
        from services.dieselbe_behauptung.nli_modell import NliModell

        nli = NliModell(NLI_MODELL)
        nli.laden_abwarten()
        urteile = dict(
            zip(
                [p.id for p in PAARE],
                nli.urteile_sync([(p.neu, p.alt) for p in PAARE]) or [],
            )
        )
    schwelle = settings.text_verfall_aehnlichkeit_unter
    zeilen = [f"Schwelle text_verfall_aehnlichkeit_unter = {schwelle}"]
    for p in PAARE:
        s = werte[p.id]
        verfaellt = s.pp < schwelle
        zeile = (
            f"{p.id:4} {p.label:9} {p.phaenomen:15} pp {s.pp:.3f} qq {s.qq:.3f} "
            f"-> {'verfaellt' if verfaellt else 'bleibt'}"
        )
        if p.id in urteile:
            u = urteile[p.id]
            zeile += f"  folgerung {u.folgerung:.3f} widerspruch {u.widerspruch:.3f}"
        zeilen.append(zeile)
    return "\n".join(zeilen)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nli", action="store_true", help="auch NLI_MODELL messen")
    args = parser.parse_args()
    print(auswertung(Settings(), args.nli))


if __name__ == "__main__":
    main()
