"""Was ein Release-Tag von main uebernimmt (scripts/main_images.py, scripts/ci-protokoll.sh).

Ein Tag auf einem Commit, dessen main-Images build.yaml schon gebaut hat, testet nicht noch
einmal und uebernimmt die Backend-Images (docs/CI.md, "Releases without a second test run").
Ohne Beleg laeuft alles wie bisher.
"""

import pathlib
import subprocess

import pytest

import main_images
from main_images import dockerfile, entscheiden, pruefen

WURZEL = pathlib.Path(__file__).resolve().parents[2]
PROTOKOLL = WURZEL / "scripts" / "ci-protokoll.sh"

SHA = "a1c3e7d8cace9c1e2729d1131a83d694e4ef6ef6"
VORFAHR = "eaf87dc7f1fcd451940349fd51c0ce53957c3843"
SPAETER = "3523b55f0e1d2c3b4a5968778695a4b3c2d1e0f9"
DIGEST = "sha256:" + "4a" * 32


def nur_vorfahr(commit, ziel):
    return commit == VORFAHR and ziel == SHA


def alle(commit):
    return dict.fromkeys(main_images.IMAGES, commit)


class TestEntscheiden:
    def test_alle_images_von_diesem_commit(self):
        assert entscheiden(SHA, alle(SHA), nur_vorfahr) == "fertig"

    def test_main_baut_den_commit_noch(self):
        # build.yaml laeuft noch: :main traegt den Vorgaenger
        assert entscheiden(SHA, alle(VORFAHR), nur_vorfahr) == "warten"

    def test_teilweise_schon_gebaut(self):
        commits = {**alle(SHA), "semantic-search": VORFAHR}
        assert entscheiden(SHA, commits, nur_vorfahr) == "warten"

    def test_main_ist_schon_weiter(self):
        # Ein spaeterer Merge hat :main ueberschrieben: dieser Commit kommt dort nicht mehr
        assert entscheiden(SHA, alle(SPAETER), nur_vorfahr) == "weiter"

    def test_tag_neben_main(self):
        # Tag auf einem Commit, der nicht auf main liegt: :main ist kein Vorfahr
        assert entscheiden(SHA, alle(SPAETER), lambda c, z: False) == "weiter"

    def test_unlesbares_image_wartet_nicht(self):
        commits = {**alle(VORFAHR), "bff": None}
        assert entscheiden(SHA, commits, nur_vorfahr) == "weiter"


class Uhr:
    def __init__(self, beginn=1_000_000):
        self.zeit = beginn
        self.schlaefe = 0

    def jetzt(self):
        return self.zeit

    def schlafen(self, sekunden):
        self.schlaefe += 1
        self.zeit += sekunden


def lesen_aus(folge):
    """Liest je Durchgang den naechsten Commit fuer alle vier Images."""
    staende = iter(folge)
    aktuell = {}

    def lesen(image):
        if image == main_images.IMAGES["frontend"]:
            aktuell["commit"] = next(staende)
        commit = aktuell["commit"]
        if isinstance(commit, Exception):
            raise commit
        return DIGEST, commit

    return lesen


class TestPruefen:
    def test_gruen_ohne_warten(self):
        uhr = Uhr()
        assert pruefen(
            SHA, lesen_aus([SHA]), nur_vorfahr, uhr.jetzt, uhr.schlafen, None
        )
        assert uhr.schlaefe == 0

    def test_wartet_bis_main_den_commit_gebaut_hat(self):
        uhr = Uhr()
        lesen = lesen_aus([VORFAHR, VORFAHR, SHA])
        assert pruefen(SHA, lesen, nur_vorfahr, uhr.jetzt, uhr.schlafen, uhr.zeit)
        assert uhr.schlaefe == 2

    def test_main_rot_gibt_nach_der_frist_auf(self):
        # main baut den Commit nie (ci rot): hoechstens bis zur Frist, dann voller Testlauf
        uhr = Uhr()
        lesen = lesen_aus([VORFAHR] * 1000)
        assert not pruefen(SHA, lesen, nur_vorfahr, uhr.jetzt, uhr.schlafen, None)
        assert uhr.zeit - 1_000_000 <= main_images.WARTEN_HOECHSTENS + main_images.TAKT

    def test_frist_ab_dem_commit(self):
        # Ein Tag lange nach dem Merge: main haette laengst gebaut, kein Warten
        uhr = Uhr()
        alter_commit = uhr.zeit - main_images.WARTEN_NACH_COMMIT - 1
        lesen = lesen_aus([VORFAHR] * 10)
        assert not pruefen(
            SHA, lesen, nur_vorfahr, uhr.jetzt, uhr.schlafen, alter_commit
        )
        assert uhr.schlaefe == 0

    def test_main_weiter_aber_commit_gebaut(self):
        # Teilweise ueberschrieben: ein Image von diesem Commit belegt das gruene ci
        uhr = Uhr()
        commits = iter([{**alle(SHA), "bff": SPAETER}])

        def lesen(image):
            if image == main_images.IMAGES["frontend"]:
                lesen.stand = next(commits)
            name = {i: n for n, i in main_images.IMAGES.items()}[image]
            return DIGEST, lesen.stand[name]

        assert pruefen(SHA, lesen, nur_vorfahr, uhr.jetzt, uhr.schlafen, None)
        assert uhr.schlaefe == 0

    def test_registry_nicht_erreichbar_heisst_testen(self):
        uhr = Uhr()
        lesen = lesen_aus([OSError("Netz weg")])
        assert not pruefen(SHA, lesen, nur_vorfahr, uhr.jetzt, uhr.schlafen, None)


class TestDockerfile:
    def test_main_image_dieses_commits_wird_uebernommen(self):
        inhalt, zeile = dockerfile("bff", SHA, lambda image: (DIGEST, SHA))
        assert inhalt.splitlines()[-1] == (
            f"FROM git.verdigado.com/netzbegruenung-images/gutgesagt-bff@{DIGEST}"
        )
        assert "uebernommen" in zeile

    @pytest.mark.parametrize("commit", [VORFAHR, None])
    def test_sonst_das_echte_dockerfile(self, commit, monkeypatch):
        monkeypatch.chdir(WURZEL)
        inhalt, zeile = dockerfile("postgres-app", SHA, lambda image: (DIGEST, commit))
        assert inhalt == (WURZEL / main_images.DOCKERFILES["postgres-app"]).read_text()
        assert "voller Build" in zeile

    def test_registry_fehler_baut_voll(self, monkeypatch):
        monkeypatch.chdir(WURZEL)

        def kaputt(image):
            raise OSError("Netz weg")

        inhalt, _ = dockerfile("semantic-search", SHA, kaputt)
        assert (
            inhalt == (WURZEL / main_images.DOCKERFILES["semantic-search"]).read_text()
        )

    def test_ohne_digest_kein_from(self, monkeypatch):
        monkeypatch.chdir(WURZEL)
        inhalt, _ = dockerfile("bff", SHA, lambda image: ("", SHA))
        assert inhalt == (WURZEL / main_images.DOCKERFILES["bff"]).read_text()


class TestBefehle:
    def test_ohne_tag_keine_marke(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CI_PIPELINE_EVENT", "push")
        monkeypatch.setenv("CI_COMMIT_SHA", SHA)
        assert main_images.main(["pruefen"]) == 0
        assert not (tmp_path / ".ci").exists()

    def test_tag_mit_beleg_legt_die_marke_an(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CI_PIPELINE_EVENT", "tag")
        monkeypatch.setenv("CI_COMMIT_SHA", SHA)
        monkeypatch.setattr(main_images, "main_image", lambda image: (DIGEST, SHA))
        monkeypatch.setattr(main_images, "commit_zeit", lambda sha: None)
        assert main_images.main(["pruefen"]) == 0
        assert (tmp_path / ".ci" / "main-schon-gruen").read_text() == f"{SHA}\n"

    def test_marke_aus_dem_checkout_zaehlt_nicht(self, tmp_path, monkeypatch):
        (tmp_path / ".ci").mkdir()
        (tmp_path / ".ci" / "main-schon-gruen").write_text(f"{SHA}\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CI_PIPELINE_EVENT", "tag")
        monkeypatch.setenv("CI_COMMIT_SHA", SHA)
        monkeypatch.setattr(main_images, "main_image", lambda image: (DIGEST, VORFAHR))
        monkeypatch.setattr(main_images, "commit_zeit", lambda sha: None)
        monkeypatch.setattr(main_images, "ist_vorfahr", lambda c, z: False)
        assert main_images.main(["pruefen"]) == 0
        assert not (tmp_path / ".ci" / "main-schon-gruen").exists()

    def test_fehler_in_der_pruefung_heisst_testen(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CI_PIPELINE_EVENT", "tag")
        monkeypatch.setenv("CI_COMMIT_SHA", SHA)

        def kaputt(*argumente):
            raise RuntimeError("unerwartet")

        monkeypatch.setattr(main_images, "pruefen", kaputt)
        monkeypatch.setattr(main_images, "commit_zeit", lambda sha: None)
        assert main_images.main(["pruefen"]) == 0
        assert not (tmp_path / ".ci").exists()

    def test_quelle_schreibt_drei_dockerfiles(self, tmp_path, monkeypatch):
        for pfad in main_images.DOCKERFILES.values():
            ziel = tmp_path / pfad
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_text(f"# echt {pfad}\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CI_COMMIT_SHA", SHA)
        bff = main_images.IMAGES["bff"]
        monkeypatch.setattr(
            main_images,
            "main_image",
            lambda image: (DIGEST, SHA if image == bff else VORFAHR),
        )
        assert main_images.main(["quelle"]) == 0
        geschrieben = sorted(p.name for p in (tmp_path / ".release").iterdir())
        assert geschrieben == [
            "bff.Dockerfile",
            "postgres-app.Dockerfile",
            "semantic-search.Dockerfile",
        ]
        assert f"@{DIGEST}" in (tmp_path / ".release" / "bff.Dockerfile").read_text()
        assert (tmp_path / ".release" / "postgres-app.Dockerfile").read_text() == (
            "# echt mvp/backend/postgres-app/Dockerfile\n"
        )

    def test_unbekannter_befehl(self):
        assert main_images.main(["bauen"]) == 2


def protokoll(tmp_path, schritt, ereignis, marke):
    if marke:
        (tmp_path / ".ci").mkdir(exist_ok=True)
        (tmp_path / ".ci" / "main-schon-gruen").write_text(f"{SHA}\n")
    return subprocess.run(
        ["sh", str(PROTOKOLL), schritt, "sh", "-c", "echo gelaufen; exit 3"],
        cwd=tmp_path,
        env={"CI_PIPELINE_EVENT": ereignis, "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )


class TestProtokoll:
    def test_tag_mit_marke_ueberspringt_den_schritt(self, tmp_path):
        lauf = protokoll(tmp_path, "unit", "tag", marke=True)
        assert lauf.returncode == 0
        assert "gelaufen" not in lauf.stdout
        assert "Uebersprungen" in lauf.stdout
        assert (tmp_path / ".ci" / "unit.status").read_text().strip() == "0"

    @pytest.mark.parametrize("schritt", ["release-platzhalter", "tag-vorpruefung"])
    def test_platzhalter_und_vorpruefung_laufen_immer(self, tmp_path, schritt):
        lauf = protokoll(tmp_path, schritt, "tag", marke=True)
        assert lauf.returncode == 3
        assert "gelaufen" in lauf.stdout

    def test_tag_ohne_marke_laeuft(self, tmp_path):
        assert protokoll(tmp_path, "unit", "tag", marke=False).returncode == 3

    @pytest.mark.parametrize("ereignis", ["push", "pull_request", "manual"])
    def test_marke_zaehlt_nur_bei_tags(self, tmp_path, ereignis):
        # Eine Datei aus dem Checkout darf in keinem anderen Lauf Tests abschalten
        assert protokoll(tmp_path, "unit", ereignis, marke=True).returncode == 3
