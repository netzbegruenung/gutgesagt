"""
Saal-Spruch des Tages (services/saal_spruch_service.py): Tag in Europe/Berlin, Text
bereinigt, Cache je Tag, Lesefehler gelten als kein Spruch, vergangene Tage gesperrt.
"""

from datetime import date, datetime, timezone

import pytest

from infrastructure.database.models import SAAL_SPRUCH_MAX
from services.saal_spruch_service import (
    SaalSpruchService,
    SaalSpruchUngueltig,
    heute_im_saal,
    spruch_bereinigen,
)

pytestmark = pytest.mark.unit

FREITAG = date(2026, 12, 4)
SAMSTAG = date(2026, 12, 5)


class Speicher:
    def __init__(self):
        self.daten = {}
        self.lesungen = 0
        self.fehler = False

    def fuer_tag(self, tag):
        self.lesungen += 1
        if self.fehler:
            raise ConnectionError("weg")
        return self.daten.get(tag)

    def ab(self, tag):
        return {d: t for d, t in sorted(self.daten.items()) if d >= tag}


def _service(speicher, heute=FREITAG, uhr=lambda: 0.0):
    tag = {"wert": heute}
    service = SaalSpruchService(
        fuer_tag=speicher.fuer_tag,
        ab=speicher.ab,
        setzen=lambda t, s: speicher.daten.__setitem__(t, s),
        loeschen=lambda t: speicher.daten.pop(t, None),
        heute=lambda: tag["wert"],
        uhr=uhr,
    )
    return service, tag


def test_tag_im_saal_ist_berliner_tag():
    # 23:30 UTC am Freitag ist in Berlin schon Samstag
    assert heute_im_saal(datetime(2026, 12, 4, 23, 30, tzinfo=timezone.utc)) == SAMSTAG
    assert heute_im_saal(datetime(2026, 12, 4, 22, 30, tzinfo=timezone.utc)) == FREITAG


def test_bereinigen():
    assert spruch_bereinigen("  Das  bringt\n doch nichts ") == "Das bringt doch nichts"
    with pytest.raises(SaalSpruchUngueltig):
        spruch_bereinigen("   ")
    with pytest.raises(SaalSpruchUngueltig):
        spruch_bereinigen("a\x00b")
    with pytest.raises(SaalSpruchUngueltig):
        spruch_bereinigen("x" * (SAAL_SPRUCH_MAX + 1))
    assert spruch_bereinigen("x" * SAAL_SPRUCH_MAX) == "x" * SAAL_SPRUCH_MAX


def test_heute_nur_der_spruch_des_tages():
    speicher = Speicher()
    service, tag = _service(speicher)
    service.setzen(SAMSTAG, "Klimaschutz kostet nur")

    assert service.heute() is None
    tag["wert"] = SAMSTAG
    # Neuer Tag: der Cache des Vortags gilt nicht
    assert service.heute() == "Klimaschutz kostet nur"


def test_heute_mit_cache_und_nach_dem_setzen_frisch():
    speicher = Speicher()
    zeit = {"t": 0.0}
    service, _ = _service(speicher, uhr=lambda: zeit["t"])

    assert service.heute() is None
    assert service.heute() is None
    assert speicher.lesungen == 1

    service.setzen(FREITAG, "Spruch")
    assert service.heute() == "Spruch"

    speicher.daten[FREITAG] = "anders, an der App vorbei"
    assert service.heute() == "Spruch"
    zeit["t"] = 61.0
    assert service.heute() == "anders, an der App vorbei"


def test_lesefehler_heisst_kein_spruch():
    speicher = Speicher()
    speicher.fehler = True
    service, _ = _service(speicher)

    assert service.heute() is None


def test_vergangene_tage_gesperrt_heute_und_spaeter_frei():
    speicher = Speicher()
    service, _ = _service(speicher)

    with pytest.raises(SaalSpruchUngueltig):
        service.setzen(date(2026, 12, 3), "zu spät")
    assert service.setzen(FREITAG, " heute ") == "heute"
    service.setzen(SAMSTAG, "morgen")

    assert [(s.datum, s.text) for s in service.kommende()] == [
        (FREITAG, "heute"),
        (SAMSTAG, "morgen"),
    ]


def test_loeschen():
    speicher = Speicher()
    service, _ = _service(speicher)
    service.setzen(FREITAG, "weg damit")
    assert service.heute() == "weg damit"

    service.loeschen(FREITAG)

    assert service.heute() is None
    assert service.kommende() == []
