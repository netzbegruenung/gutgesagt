"""Die Image-Builds in Woodpecker (.woodpecker/build.yaml und release.yaml, #327).

Gleiche Image-Namen wie früher die GitHub-CI, damit Deployment und Renovate unverändert
weiterlaufen; kein Pfadfilter, damit jeder Push auf main alle vier Images baut; und beide
Workflows gleich gebaut, damit ein Release nicht anders baut als main. Das Release
uebernimmt BFF, Semantic Search und postgres-app vom main-Image desselben Commits
(scripts/main_images.py, docs/CI.md "Releases without a second test run").
"""

import copy
import pathlib
import re

import pytest
import yaml

import main_images

WURZEL = pathlib.Path(__file__).resolve().parents[2]


def laden(name):
    return yaml.safe_load((WURZEL / ".woodpecker" / name).read_text())


BUILD = laden("build.yaml")
RELEASE = laden("release.yaml")
CI = laden("ci.yaml")
TAGS = "image-tags"
QUELLE = "image-quelle"
VORBEREITUNG = {TAGS, QUELLE}

IMAGES = {
    "frontend": "gutgesagt-frontend",
    "bff": "gutgesagt-bff",
    "semantic-search": "gutgesagt-semantic-search",
    "postgres-app": "gutgesagt-postgres-app",
}


def schritte(workflow):
    return {s["name"]: s for s in workflow["steps"]}


def build_schritte(workflow):
    return {n: s for n, s in schritte(workflow).items() if n not in VORBEREITUNG}


@pytest.mark.parametrize("workflow", [BUILD, RELEASE], ids=["build", "release"])
class TestBeideWorkflows:
    def test_erst_nach_gruenem_ci(self, workflow):
        assert workflow["depends_on"] == ["ci"]

    def test_bauen_dieselben_images_wie_bisher(self, workflow):
        repos = {n: s["settings"]["repo"] for n, s in build_schritte(workflow).items()}
        assert repos == {n: f"git.verdigado.com/netzbegruenung-images/{i}" for n, i in IMAGES.items()}

    def test_tags_aus_dem_skript(self, workflow):
        tags = schritte(workflow)[TAGS]
        assert tags["commands"] == ["python3 scripts/image_tags.py .image-tags"]
        for schritt in build_schritte(workflow).values():
            assert schritt["depends_on"][0] == TAGS
            assert schritt["settings"]["tags_file"] == ".image-tags"
            assert "tags" not in schritt["settings"]

    def test_secrets_nur_im_plugin(self, workflow):
        # Die Vorbereitung fuehrt Befehle aus und bekommt deshalb kein Secret
        for name in VORBEREITUNG & set(schritte(workflow)):
            assert "from_secret" not in str(schritte(workflow)[name]), name
        for schritt in build_schritte(workflow).values():
            assert schritt["settings"]["username"] == {"from_secret": "registry_user"}
            assert schritt["settings"]["password"] == {"from_secret": "registry_token"}

    def test_frontend_bekommt_den_commit(self, workflow):
        args = schritte(workflow)["frontend"]["settings"]["build_args"]
        assert args["GIT_SHA"] == "${CI_COMMIT_SHA}"

    def test_baut_immer_alle_images(self, workflow):
        # Kein Pfadfilter (#327, Review #705): Woodpecker vergleicht nur mit dem einzelnen
        # Push. Ein abgebrochener oder roter Lauf liesse sein Image sonst still alt.
        assert all("when" not in s for s in schritte(workflow).values())


def test_build_und_release_bauen_gleich():
    # Bis auf die Tag-Version und die Dockerfiles, die image-quelle schreibt: ein Release
    # baut, was main gebaut hat. Ganze Schritte in derselben Reihenfolge, damit auch ein
    # zusätzlicher Schritt auffällt.
    def ohne_unterschiede(workflow):
        gleich = [s for s in copy.deepcopy(workflow["steps"]) if s["name"] != QUELLE]
        for schritt in gleich:
            einstellungen = schritt.get("settings", {})
            einstellungen.get("build_args", {}).pop("APP_VERSION", None)
            if schritt["name"] in main_images.DOCKERFILES:
                einstellungen.pop("dockerfile")
                schritt["depends_on"] = [TAGS]
        return gleich

    assert ohne_unterschiede(BUILD) == ohne_unterschiede(RELEASE)


def test_semantic_search_cache_aus_dem_main_image():
    # Ohne Cache ergab jeder Build rund 4 GB neue Schichten in der Registry (Platte voll,
    # 14.11.). Der Cache kommt aus dem main-Tag, den build.yaml selbst schreibt.
    schritt = schritte(BUILD)["semantic-search"]["settings"]
    assert schritt["cache_from"] == [f"{schritt['repo']}:main"]
    # inline: Cache-Metadaten im Image selbst, kein zusätzliches Cache-Image in der Registry
    assert schritt["cache_to"] == "type=inline"


def test_ein_plugin_image_mit_digest():
    images = {s["image"] for w in (BUILD, RELEASE) for s in build_schritte(w).values()}
    assert len(images) == 1
    assert re.fullmatch(r"woodpeckerci/plugin-docker-buildx:[\d.]+@sha256:[0-9a-f]{64}", images.pop())


def test_tag_skript_im_python_image_der_ci():
    # ci-bericht laeuft im blanken Python-Image, die anderen Python-Schritte im CI-Image
    python = schritte(CI)["ci-bericht"]["image"]
    assert schritte(BUILD)[TAGS]["image"] == python


class TestBuild:
    def test_push_und_manuell_nur_auf_main(self):
        assert BUILD["when"] == [
            {"event": "push", "branch": "main"},
            {"event": "manual", "branch": "main"},
        ]

    def test_footer_auf_main_sagt_main(self):
        # Entscheidung @BanSe 03.11. (#542): "main · <sha>" statt einer veralteten Version
        assert schritte(BUILD)["frontend"]["settings"]["build_args"]["APP_VERSION"] == "main"


class TestRelease:
    def test_backend_images_aus_dem_dockerfile_von_image_quelle(self):
        quelle = schritte(RELEASE)[QUELLE]
        assert quelle["commands"] == ["python3 scripts/main_images.py quelle"]
        assert quelle["depends_on"] == []
        # Nur Standardbibliothek: dasselbe Python-Image wie image-tags
        assert quelle["image"] == schritte(RELEASE)[TAGS]["image"]
        for name in main_images.DOCKERFILES:
            schritt = schritte(RELEASE)[name]
            assert schritt["depends_on"] == [TAGS, QUELLE]
            assert schritt["settings"]["dockerfile"] == f".release/{name}.Dockerfile"

    def test_frontend_baut_immer_neu(self):
        # Die Version im Footer kommt aus dem Tag: ein main-Image hat "main" eingebaut.
        assert "frontend" not in main_images.DOCKERFILES
        assert schritte(RELEASE)["frontend"]["settings"]["dockerfile"] == (
            schritte(BUILD)["frontend"]["settings"]["dockerfile"]
        )

    def test_voller_build_mit_den_dockerfiles_von_main(self):
        # Fehlt das main-Image, kopiert image-quelle das Dockerfile, mit dem build.yaml baut
        for name, dockerfile in main_images.DOCKERFILES.items():
            assert schritte(BUILD)[name]["settings"]["dockerfile"] == dockerfile

    def test_skript_kennt_dieselben_images(self):
        repos = {n: s["settings"]["repo"] for n, s in build_schritte(BUILD).items()}
        assert repos == {
            n: f"{main_images.REGISTRY}/{main_images.ORGANISATION}/{i}"
            for n, i in main_images.IMAGES.items()
        }

    def test_nur_bei_tags_mit_v(self):
        assert RELEASE["when"] == [{"event": "tag", "ref": "refs/tags/v*"}]

    def test_version_im_footer_aus_dem_tag(self):
        args = schritte(RELEASE)["frontend"]["settings"]["build_args"]
        assert args["APP_VERSION"] == "${CI_COMMIT_TAG}"
