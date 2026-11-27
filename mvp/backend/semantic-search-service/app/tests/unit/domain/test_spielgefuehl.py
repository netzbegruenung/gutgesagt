"""Spielgefuehl in drei Stufen: Regeln und Wortlaut (domain/spielgefuehl.py)."""

from datetime import datetime, timezone

import pytest

from domain.spielgefuehl import (
    AKTUELLER_WORTLAUT,
    GELTENDE_WORTLAUTE,
    NAMENS_VORBELEGUNG,
    QUEST_WORTLAUT,
    REIHENFOLGE,
    VERANTWORTLICHER,
    WORTLAUTE,
    Stufe,
    in_rangliste,
    punkte_wirksam,
    quest_einwilligung_seit,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "stufe, punkte, rangliste",
    [
        (None, False, False),
        (Stufe.AUS, False, False),
        (Stufe.FUER_MICH, True, False),
        (Stufe.RANGLISTE, True, True),
    ],
)
def test_ableitung_je_stufe(stufe, punkte, rangliste):
    assert punkte_wirksam(stufe) is punkte
    assert in_rangliste(stufe) is rangliste


def test_gemeinschaft_zuerst_alle_stufen_genau_einmal():
    assert REIHENFOLGE[0] is Stufe.RANGLISTE
    assert REIHENFOLGE[-1] is Stufe.AUS
    assert sorted(REIHENFOLGE) == sorted(Stufe)


def test_keine_vorbelegung_des_namens():
    # Jura 26.11.: Vorbelegung "Anzeigename" unzulaessig.
    assert NAMENS_VORBELEGUNG is None


def test_aktueller_wortlaut_gilt_und_ist_vollstaendig():
    assert AKTUELLER_WORTLAUT in GELTENDE_WORTLAUTE
    wortlaut = WORTLAUTE[AKTUELLER_WORTLAUT]
    assert set(wortlaut.stufen) == set(Stufe)
    assert all(t.titel and t.text for t in wortlaut.stufen.values())
    # Name des Verantwortlichen genau wie in der Datenschutzerklaerung
    assert VERANTWORTLICHER in wortlaut.fuss
    # Schutz gegen Absprachen fuer beide Stufen ueber "aus" (Jura zu PR #849)
    assert "Absprachen" in wortlaut.absprachen
    assert "Kennungen beider Konten" in wortlaut.absprachen
    # Ausdrueckliche Einwilligung nach Art. 9 in beiden Stufen ueber "aus"
    for stufe in (Stufe.FUER_MICH, Stufe.RANGLISTE):
        assert "Art. 9 Abs. 2 lit. a DSGVO" in wortlaut.stufen[stufe].text


# --- Wortlaut spielgefuehl-2026-11-28 (juristische Vorgabe vom 27.11.) -------------

VORIGER = "spielgefuehl-2026-11-27"


def test_eine_fassung_mit_quests_und_zustimmungen():
    assert AKTUELLER_WORTLAUT == "spielgefuehl-2026-11-28"
    assert QUEST_WORTLAUT == AKTUELLER_WORTLAUT
    assert GELTENDE_WORTLAUTE == {
        "spielgefuehl-2026-11-26",
        "spielgefuehl-2026-11-27",
        "spielgefuehl-2026-11-28",
    }


def test_einleitung_mit_dem_satz_zu_quest_punkten():
    assert WORTLAUTE[AKTUELLER_WORTLAUT].einleitung == (
        "Aus deiner Mitwirkung, also deinen Beiträgen, Einwürfen und Bewertungen und wie "
        "andere deine Beiträge nutzen, können wir Punkte und Meilensteine berechnen. "
        "Bist du in einem Team und speicherst in einer Woche selbst einen Beitrag, "
        "bekommst du dafür auch Quest-Punkte, wenn dein Team sein Wochenziel erreicht. "
        "Dafür zählt nur die Wochensumme des Teams, nicht, wer wie viel beigetragen hat. "
        "Daraus lässt sich schließen, dass und wie stark du dich bei Gut gesagt "
        "engagierst."
    )


def test_stufen_nennen_quest_punkte():
    neu, alt = WORTLAUTE[AKTUELLER_WORTLAUT], WORTLAUTE[VORIGER]
    assert neu.stufen[Stufe.FUER_MICH].text == (
        "Ich willige ausdrücklich ein, dass aus meiner Mitwirkung, einschließlich "
        "Quest-Punkten, Punkte und Meilensteine berechnet werden, die nur ich sehe "
        "(Art. 9 Abs. 2 lit. a DSGVO)."
    )
    assert neu.stufen[Stufe.RANGLISTE].text.startswith(
        "Ich willige ausdrücklich ein, dass aus meiner Mitwirkung, einschließlich "
        "Quest-Punkten, Punkte und Meilensteine berechnet werden und dass ich in der "
        "Rangliste der laufenden Saison erscheine,"
    )
    # Sonst wortgleich
    assert (
        neu.stufen[Stufe.RANGLISTE].text.replace(", einschließlich Quest-Punkten,", "")
        == alt.stufen[Stufe.RANGLISTE].text
    )
    assert neu.stufen[Stufe.AUS] == alt.stufen[Stufe.AUS]
    for stufe in Stufe:
        assert neu.stufen[stufe].titel == alt.stufen[stufe].titel


def test_absatz_absprachen():
    assert WORTLAUTE[AKTUELLER_WORTLAUT].absprachen == (
        "Für ‚Nur für mich‘ und ‚In der Saison-Rangliste mitspielen‘ willige ich außerdem "
        "ein: Damit Punkte nicht durch Absprachen entstehen, prüft Gut gesagt, ob sich "
        "zwei Konten auffällig oft gegenseitig nutzen und, sobald diese Prüfung "
        "eingeschaltet ist, auch ob sie einander zustimmen. Fällt das auf, sehen die "
        "Administratorinnen und Administratoren einen Hinweis mit den Anzeigenamen und "
        "Kennungen beider Konten; an Punkten und Rangliste ändert das nichts."
    )


def test_rest_wortgleich():
    neu, alt = WORTLAUTE[AKTUELLER_WORTLAUT], WORTLAUTE[VORIGER]
    assert neu.ueberschrift == alt.ueberschrift
    assert neu.fuss == alt.fuss
    assert neu.namenswahl_frage == alt.namenswahl_frage
    assert neu.namenswahl_anzeigename == alt.namenswahl_anzeigename
    assert neu.namenswahl_zufallsname == alt.namenswahl_zufallsname
    assert neu.namenswahl_tipp == alt.namenswahl_tipp


def _t(tag: int, stunde: int = 12) -> datetime:
    return datetime(2026, 11, tag, stunde, tzinfo=timezone.utc)


AKTUELL = AKTUELLER_WORTLAUT


@pytest.mark.parametrize(
    "antworten, erwartet",
    [
        ([], None),
        ([(AKTUELL, Stufe.FUER_MICH, _t(28))], _t(28)),
        ([(AKTUELL, Stufe.AUS, _t(28))], None),
        # -27 traegt keine Quest-Punkte
        ([(VORIGER, Stufe.RANGLISTE, _t(28))], None),
        # Wechsel der Stufe oder neuer Zufallsname unterbrechen nicht
        (
            [
                (AKTUELL, Stufe.FUER_MICH, _t(30)),
                (AKTUELL, Stufe.RANGLISTE, _t(29)),
                (AKTUELL, Stufe.FUER_MICH, _t(28)),
                (VORIGER, Stufe.FUER_MICH, _t(27)),
            ],
            _t(28),
        ),
        # Nach "aus" zaehlt erst die neue Einwilligung
        (
            [
                (AKTUELL, Stufe.FUER_MICH, _t(30)),
                (AKTUELL, Stufe.AUS, _t(29)),
                (AKTUELL, Stufe.FUER_MICH, _t(28)),
            ],
            _t(30),
        ),
        # Juengste Antwort ohne Einwilligung: keine
        (
            [
                (AKTUELL, Stufe.AUS, _t(29)),
                (AKTUELL, Stufe.FUER_MICH, _t(28)),
            ],
            None,
        ),
    ],
)
def test_quest_einwilligung_seit(antworten, erwartet):
    assert quest_einwilligung_seit(antworten) == erwartet
