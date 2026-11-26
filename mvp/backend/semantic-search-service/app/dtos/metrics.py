from datetime import date
from typing import Optional

from pydantic import BaseModel


###   GetMetrics   ###


class ZuwachsResponse(BaseModel):
    # Neue sichtbare Kommentare der letzten 7 Tage, genau, nur ab 3 (domain/bestandszahl.py)
    neu_7_tage: Optional[int] = None
    # Tag (deutsche Zeit, ohne Uhrzeit) des neuesten Kommentars, nur unter 3 neuen
    zuletzt_ergaenzt: Optional[date] = None


class GetMetricsResponse(BaseModel):
    content_count: int
    statement_count: int
    commentary_count: int
    reference_count: int
    # Zuwachs zur Bestandszahl; null bei Schalter bestandszahl_zuwachs aus oder Fehler
    zuwachs: Optional[ZuwachsResponse] = None
