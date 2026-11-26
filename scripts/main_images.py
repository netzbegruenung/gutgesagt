"""Was ein Release-Tag von main uebernehmen kann (.woodpecker/ci.yaml, release.yaml).

build.yaml baut nach jedem gruenen ci-Lauf auf main die vier Images als ``:main``; das
Plugin docker-buildx schreibt den Commit als Label ``org.opencontainers.image.revision``
hinein. Traegt ein ``:main``-Image den Commit des Tags, hat genau dieser Commit ci auf main
bestanden (build.yaml wartet auf ci), Integrationstests eingeschlossen.

- ``pruefen`` (ci.yaml, nur bei Tags): wartet, bis build.yaml die Images dieses Commits
  geschrieben hat, und legt dann ``.ci/main-schon-gruen`` an; scripts/ci-protokoll.sh
  ueberspringt daraufhin die Testschritte. Ohne Beleg (Tag auf einem anderen Commit, main
  rot, main schon weiter) laeuft alles wie bisher. Endet immer mit 0: Ein Fehler hier darf
  nur die Abkuerzung kosten, nie den Testlauf.
- ``quelle`` (release.yaml): schreibt je Backend-Image ein Dockerfile nach ``.release/``.
  Traegt ``:main`` den Commit, nur ``FROM <image>@<digest>``: Das Release besteht aus
  denselben Schichten wie das getestete main-Image, der Build dauert Sekunden und legt nur
  Konfiguration und Manifest neu ab. Sonst eine Kopie des echten Dockerfiles, also der volle
  Build wie bisher. Das Frontend baut immer neu (Version im Footer, APP_VERSION).

Woodpecker 3.20 kann einen Schritt nur beim Anlegen der Pipeline auslassen (``when``), nicht
abhaengig von einem frueheren Schritt; deshalb entscheiden Dateien im Workspace
(docs/CI.md, "Releases without a second test run"). Nur Standardbibliothek; die Registry
ist ohne Anmeldung lesbar (anonymes Pull-Token).
"""

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

REGISTRY = "git.verdigado.com"
ORGANISATION = "netzbegruenung-images"
IMAGES = {
    "frontend": "gutgesagt-frontend",
    "bff": "gutgesagt-bff",
    "semantic-search": "gutgesagt-semantic-search",
    "postgres-app": "gutgesagt-postgres-app",
}
# Die Images, die ein Release von main uebernimmt, mit ihrem Dockerfile fuer den vollen Build
DOCKERFILES = {
    "bff": "mvp/backend/BFF/Dockerfile",
    "semantic-search": "mvp/backend/semantic-search-service/Dockerfile",
    "postgres-app": "mvp/backend/postgres-app/Dockerfile",
}
MARKE = pathlib.Path(".ci/main-schon-gruen")
RELEASE_ORDNER = pathlib.Path(".release")
LABEL = "org.opencontainers.image.revision"

# Nach dem Merge braucht main rund 22 min fuer ci und 8 min fuer build (Statuszeiten von
# v0.9.12 und v0.9.13, 26.11.). Hoechstens 25 min Warten: mit dem vollen Lauf danach (rund
# 22 min) bleibt der Tag-Lauf unter Woodpeckers Standard-Zeitlimit von 60 min.
WARTEN_NACH_COMMIT = 40 * 60
WARTEN_HOECHSTENS = 25 * 60
TAKT = 30

_INDEX = (
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
)
_MANIFEST = (
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
)
_SHA = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def _abruf(url, token=None, accept=None):
    anfrage = urllib.request.Request(url)
    if token:
        anfrage.add_header("Authorization", f"Bearer {token}")
    if accept:
        anfrage.add_header("Accept", ", ".join(accept))
    with urllib.request.urlopen(anfrage, timeout=30) as antwort:
        return antwort.read(), antwort.headers


def _token(image):
    scope = f"repository:{ORGANISATION}/{image}:pull"
    url = f"https://{REGISTRY}/v2/token?" + urllib.parse.urlencode(
        {"service": "container_registry", "scope": scope}
    )
    return json.loads(_abruf(url)[0])["token"]


def main_image(image):
    """(Digest, Commit) von ``<image>:main``; der Commit aus dem Label des amd64-Images."""
    token = _token(image)
    basis = f"https://{REGISTRY}/v2/{ORGANISATION}/{image}"
    inhalt, kopf = _abruf(f"{basis}/manifests/main", token, _INDEX + _MANIFEST)
    digest = kopf.get("Docker-Content-Digest", "")
    if not _DIGEST.fullmatch(digest):
        raise ValueError(f"{image}:main ohne Digest")
    manifest = json.loads(inhalt)
    if manifest.get("mediaType") in _INDEX or "manifests" in manifest:
        amd64 = [
            m["digest"]
            for m in manifest["manifests"]
            if m.get("platform", {}).get("os") == "linux"
            and m.get("platform", {}).get("architecture") == "amd64"
        ]
        if not amd64 or not _DIGEST.fullmatch(amd64[0]):
            raise ValueError(f"{image}:main ohne linux/amd64")
        manifest = json.loads(
            _abruf(f"{basis}/manifests/{amd64[0]}", token, _MANIFEST)[0]
        )
    konfiguration = json.loads(
        _abruf(f"{basis}/blobs/{manifest['config']['digest']}", token)[0]
    )
    labels = konfiguration.get("config", {}).get("Labels") or {}
    return digest, labels.get(LABEL)


def main_commits(lesen=main_image):
    """Commit je ``:main``-Image; None, wenn die Registry es nicht hergibt."""
    commits = {}
    for name, image in IMAGES.items():
        try:
            commits[name] = lesen(image)[1]
        except Exception as fehler:  # Netz, Registry, Format: dann kein Beleg
            print(f"{image}:main nicht lesbar: {fehler}")
            commits[name] = None
    return commits


def entscheiden(sha, commits, ist_vorfahr):
    """``fertig``, ``warten`` oder ``weiter`` (main ist weiter oder woanders).

    Warten lohnt nur, solange jedes Image, das noch nicht ``sha`` traegt, einen Vorfahren
    traegt: dann kann der main-Lauf von ``sha`` es noch ersetzen. Traegt eines einen anderen
    Commit (spaeterer Merge, Tag neben main) oder ist unlesbar, kommt ``sha`` dort nicht mehr.
    """
    andere = [c for c in commits.values() if c != sha]
    if not andere:
        return "fertig"
    if all(c is not None and ist_vorfahr(c, sha) for c in andere):
        return "warten"
    return "weiter"


def _git(*argumente):
    return subprocess.run(["git", *argumente], capture_output=True, text=True)


def ist_vorfahr(vorfahr, commit):
    """Wahr, wenn ``vorfahr`` echter Vorfahr von ``commit`` ist (im Klon des Tags)."""
    if not _SHA.fullmatch(vorfahr or "") or vorfahr == commit:
        return False
    return _git("merge-base", "--is-ancestor", vorfahr, commit).returncode == 0


def commit_zeit(sha):
    lauf = _git("log", "-1", "--format=%ct", sha)
    return int(lauf.stdout.strip()) if lauf.returncode == 0 else None


def pruefen(sha, lesen, ist_vorfahr, jetzt, schlafen, zeit_des_commits):
    """Wahr, wenn ein ``:main``-Image ``sha`` traegt, ci auf main also gruen war."""
    beginn = jetzt()
    frist = beginn + WARTEN_HOECHSTENS
    if zeit_des_commits is not None:
        frist = min(frist, zeit_des_commits + WARTEN_NACH_COMMIT)
    while True:
        commits = main_commits(lesen)
        lage = entscheiden(sha, commits, ist_vorfahr)
        stand = ", ".join(f"{n} {(c or '?')[:12]}" for n, c in commits.items())
        print(f"main-Images: {stand}")
        if lage != "warten" or jetzt() >= frist:
            break
        print(f"build.yaml fuer {sha[:12]} laeuft noch, naechster Blick in {TAKT} s")
        schlafen(TAKT)
    return any(c == sha for c in commits.values())


def befehl_pruefen():
    # Nur diese Pruefung legt die Marke an; eine aus dem Checkout zaehlt nicht (zaehlt ohnehin
    # nur mit dem Commit des Laufs als Inhalt, scripts/ci-protokoll.sh)
    try:
        MARKE.unlink(missing_ok=True)
    except OSError as fehler:
        print(f"Marke nicht entfernbar ({fehler}): alle Schritte laufen.")
        return 0
    sha = os.environ.get("CI_COMMIT_SHA", "")
    if os.environ.get("CI_PIPELINE_EVENT") != "tag" or not _SHA.fullmatch(sha):
        print("Kein Tag: alle Schritte laufen.")
        return 0
    try:
        gruen = pruefen(
            sha, main_image, ist_vorfahr, time.time, time.sleep, commit_zeit(sha)
        )
    except Exception as fehler:
        print(f"Pruefung gescheitert ({fehler}): alle Schritte laufen.")
        return 0
    if gruen:
        try:
            MARKE.parent.mkdir(exist_ok=True)
            MARKE.write_text(f"{sha}\n", encoding="utf-8")
        except OSError as fehler:
            print(f"Marke nicht schreibbar ({fehler}): alle Schritte laufen.")
            return 0
        print(
            f"{sha[:12]} hat ci auf main bestanden (build.yaml hat gebaut): Tests entfallen."
        )
    else:
        print(f"Kein main-Image von {sha[:12]}: alle Schritte laufen wie auf main.")
    return 0


def dockerfile(name, sha, lesen):
    """Inhalt des Release-Dockerfiles fuer ``name`` und eine Zeile fuers Log."""
    image = IMAGES[name]
    try:
        digest, commit = lesen(image)
    except Exception as fehler:
        digest, commit = None, None
        print(f"{image}:main nicht lesbar: {fehler}")
    if commit == sha and digest:
        quelle = f"{REGISTRY}/{ORGANISATION}/{image}@{digest}"
        inhalt = f"# Von main uebernommen, Commit {sha} (scripts/main_images.py)\nFROM {quelle}\n"
        return inhalt, f"{name}: von main uebernommen ({quelle})"
    inhalt = pathlib.Path(DOCKERFILES[name]).read_text(encoding="utf-8")
    return inhalt, f"{name}: :main traegt {(commit or '?')[:12]}, voller Build"


def befehl_quelle():
    sha = os.environ.get("CI_COMMIT_SHA", "")
    if not _SHA.fullmatch(sha):
        print("main_images: CI_COMMIT_SHA fehlt", file=sys.stderr)
        return 1
    if RELEASE_ORDNER.exists():
        shutil.rmtree(RELEASE_ORDNER)
    RELEASE_ORDNER.mkdir()
    for name in DOCKERFILES:
        inhalt, zeile = dockerfile(name, sha, main_image)
        (RELEASE_ORDNER / f"{name}.Dockerfile").write_text(inhalt, encoding="utf-8")
        print(zeile)
    return 0


def main(argumente):
    befehle = {"pruefen": befehl_pruefen, "quelle": befehl_quelle}
    if len(argumente) != 1 or argumente[0] not in befehle:
        print("Aufruf: main_images.py pruefen|quelle", file=sys.stderr)
        return 2
    return befehle[argumente[0]]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
