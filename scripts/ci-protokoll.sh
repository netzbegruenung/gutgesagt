#!/bin/sh
# Fuehrt einen Befehl eines CI-Schritts aus (.woodpecker/ci.yaml): Ausgabe ins Woodpecker-Log
# und angehaengt an .ci/<schritt>.log, Exit-Code nach .ci/<schritt>.status; endet mit dem
# Exit-Code des Befehls. Beides liest scripts/ci_bericht.py. Ohne Status-Datei gilt der
# Schritt als abgebrochen. Ein Schritt darf es mehrmals aufrufen, der letzte Status zaehlt.
# Bei einem Tag, dessen Commit ci auf main schon bestanden hat (.ci/main-schon-gruen, von
# scripts/main_images.py pruefen), endet jeder Befehl sofort gruen; nur die Pruefung selbst
# und release-platzhalter, das es nur bei Tags gibt, laufen (docs/CI.md).
# Aufruf: sh scripts/ci-protokoll.sh <schritt> <befehl> [argumente ...]
set -u
schritt=$1
shift
mkdir -p .ci
rm -f ".ci/$schritt.status"
if [ "${CI_PIPELINE_EVENT:-}" = tag ] && [ -f .ci/main-schon-gruen ]; then
  case $schritt in
    tag-vorpruefung | release-platzhalter) ;;
    *)
      echo "Uebersprungen: Commit $(cat .ci/main-schon-gruen) hat ci auf main bestanden." | tee -a ".ci/$schritt.log"
      echo 0 > ".ci/$schritt.status"
      exit 0
      ;;
  esac
fi
{ "$@" 2>&1; echo $? > ".ci/$schritt.status"; } | tee -a ".ci/$schritt.log"
exit "$(cat ".ci/$schritt.status" 2>/dev/null || echo 1)"
