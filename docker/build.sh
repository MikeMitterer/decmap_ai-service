#!/usr/bin/env bash

#------------------------------------------------------------------------------
# Build + Deploy Docker-Image: decisionmap/ai-service
#------------------------------------------------------------------------------

# Vars die in .bashrc gesetzt sein müssen ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
if [[ -z ${BASH_LIBS+x} ]]; then echo "Var 'BASH_LIBS' nicht gesetzt!"; exit 1; fi
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

set -eou pipefail

readonly APPNAME="$(basename "$0")"

readonly SCRIPT=$(realpath "$0")
readonly SCRIPTPATH=$(dirname "$SCRIPT")

#------------------------------------------------------------------------------
# Set WORKSPACE
#
cd "${SCRIPTPATH}"

mkdir -p logs
LOGFILE="logs/build-$(date +%y%m%d).log"

# shellcheck disable=SC2155
readonly DOCKER_BASE_IMAGE=$(\grep "^FROM " < Dockerfile | head -1 | sed "s/FROM //;s/ AS.*//")

readonly NAMESPACE="decisionmap"
readonly NAME="ai-service"

readonly DEPLOY_HOST="hetzner"
readonly DEPLOY_PATH="/opt/${NAMESPACE}/${NAME}"

#GITHUB_OWNER="mikemitterer"
GITHUB_OWNER="mangolila"

# ghcr.io — GITHUB_OWNER muss in .bashrc oder Jenkins-Environment gesetzt sein
if [[ -z "${GITHUB_OWNER:-}" ]]; then echo "Var 'GITHUB_OWNER' nicht gesetzt!"; exit 1; fi

readonly REGISTRY="ghcr.io"
readonly IMAGE="${REGISTRY}/${GITHUB_OWNER}/${NAMESPACE}-${NAME}"
# Wie viele versionierte Images auf dem Server behalten (für Rollback)
readonly KEEP_IMAGES=5

readonly TAGFILE="${SCRIPTPATH}/.last-build-tag"
readonly WARN_DAYS=7

#------------------------------------------------------------------------------
# Einbinden der globalen Build-Lib
#
if [[ "${__BUILD_LIB__:=""}"   == "" ]]; then . "${BASH_LIBS}/build.lib.sh";   fi
if [[ "${__DOCKER_LIB__:=""}"  == "" ]]; then . "${BASH_LIBS}/docker.lib.sh";  fi
if [[ "${__VERSION_LIB__:=""}" == "" ]]; then . "${BASH_LIBS}/version.lib.sh"; fi

readonly PROJECT_NAME="${NAMESPACE}.${NAME}"

# CMDLINE kann ab hier verwendet werden ---------------------------------------

readonly CMDLINE=${1:-}
readonly OPTION=${2:-""}

# DEV_LOCAL ist bei den Jenkins-Tests bzw. in Docker-Containern nicht gesetzt,
# IS_CI geht also auf "true"
readonly IS_CI="${DEV_LOCAL:-"true"}"
readonly HAS_DEV_LOCAL="[[ ${IS_CI} != 'true' ]]"

# Die möglichen Plattformen:
#   https://docs.docker.com/build/building/multi-platform/
readonly PLATFORMS=("linux/arm64 linux/amd64")

if [[ "${ARCHITECTURE}" == "x86_64" ]]; then
    readonly DEFAULT_PLATFORM="linux/amd64"
elif [[ "${ARCHITECTURE}" == "arm64" ]]; then
    readonly DEFAULT_PLATFORM="linux/arm64"
else
    readonly DEFAULT_PLATFORM="linux/amd64"
fi

PLATFORM="${DEFAULT_PLATFORM}"
BUILD_MULTIARCH=false

while [ $# -ne 0 ]; do
    case "${1}" in
        --build | -b)
            shift
            if [[ "${OPTION}" == "x86" ]]; then
                PLATFORM=("linux/amd64")
            elif [[ "${OPTION}" == "arm" || "${OPTION}" == "m1" ]]; then
                PLATFORM=("linux/arm64")
            elif [[ "${OPTION}" == "all" ]]; then
                PLATFORM=("linux/arm64,linux/amd64")
                BUILD_MULTIARCH=true
            else
                PLATFORM=("${DEFAULT_PLATFORM}")
                echo "Platform: ${PLATFORM}"
                break
            fi
        ;;
    esac
    shift
done

#------------------------------------------------------------------------------
# TAG via gitDockerTag (version.lib.sh): Git-Tag als Basis, docker-safe Build-Meta
# STRICT=2 (Default/relaxed): rc=2 kein Tag, rc=3 dirty — ahead erlaubt
# STRICT=1: zusätzlich rc=4 wenn ahead > 0
#
# Überschreiben via Env: STRICT=2 ./build.sh --build
#
readonly STRICT=${STRICT:-2}

_tag_rc=0
TAG="$(gitDockerTag "${STRICT}")" || _tag_rc=$?
if [[ $_tag_rc -eq 2 ]]; then
    echo -e "\n${RED}Build abgebrochen:${NC} Kein Git-Tag gefunden." >&2
    echo -e "${YELLOW}Tipp:${NC} bumpVer  ${BLUE}# oder manuell:${NC} git tag -a v0.1.0+$(date +%y%m%d.%H%M) -m 'Initial release'\n" >&2
    exit 1
elif [[ $_tag_rc -eq 3 ]]; then
    echo -e "\n${RED}Build abgebrochen:${NC} Working-Tree ist dirty." >&2
    echo -e "${YELLOW}Tipp:${NC} git commit oder git stash\n" >&2
    exit 1
elif [[ $_tag_rc -eq 4 ]]; then
    echo -e "\n${RED}Build abgebrochen:${NC} Repo ist ahead vom letzten Tag (STRICT=1)." >&2
    echo -e "${YELLOW}Tipp:${NC} bumpVer — oder mit ${BLUE}STRICT=2 ./build.sh --build${NC} (ahead erlaubt)\n" >&2
    exit 1
elif [[ $_tag_rc -ne 0 ]]; then
    echo -e "\n${RED}Build abgebrochen:${NC} gitDockerTag fehlgeschlagen (rc=${_tag_rc}).\n" >&2
    exit 1
fi
readonly TAG


#------------------------------------------------------------------------------
# Functions
#

buildSingleArch() {
    docker build --platform "${PLATFORM}" \
        -f Dockerfile \
        -t "${NAMESPACE}/${NAME}:latest" -t "${NAMESPACE}/${NAME}:${TAG}" \
        -t "${IMAGE}:latest"             -t "${IMAGE}:${TAG}" \
        .. | tee "${LOGFILE}" || exit 1

    local _ARCH
    _ARCH=$(docker inspect "${NAMESPACE}/${NAME}:latest" --format "{{ .Architecture }}")
    echo -e "\n${GREEN}${NAMESPACE}/${NAME}:latest${NC} gebaut für ${YELLOW}${_ARCH}${NC}"

    showImages "${TAG}" ${NAMESPACE} ${NAME}
}

buildMultiArch() {
    echo -e "\nBuilder:\n${YELLOW}$(docker buildx inspect multiarch | sed 's/^/    /g')${NC}\n"

    docker buildx build --platform "${PLATFORM}" \
        -f Dockerfile \
        -t "${NAMESPACE}/${NAME}:latest" -t "${NAMESPACE}/${NAME}:${TAG}" \
        -t "${IMAGE}:latest"             -t "${IMAGE}:${TAG}" \
        .. | tee "${LOGFILE}" || exit 1
}

build() {
    echo -e "\nBuilding for Platform: ${YELLOW}${PLATFORM}${NC}\n"

    if [[ "${BUILD_MULTIARCH}" == false ]]; then
        buildSingleArch
    else
        buildMultiArch
    fi

    # Tag + Zeitstempel persistieren — wird von push() gelesen
    echo "${TAG}"       > "${TAGFILE}"
    echo "$(date +%s)" >> "${TAGFILE}"
}

# loadLastBuildTag — Tag des letzten Builds lesen und zurückgeben
#
#   Gibt den gespeicherten Tag via stdout zurück (für Zuweisung per $(...)).
#   Alle Meldungen und Warnungen gehen nach stderr, damit stdout sauber bleibt.
#   Bricht mit exit 1 ab wenn kein Build existiert.
#   Gibt eine Warnung aus wenn der Build älter als WARN_DAYS Tage ist.
#
#   Verwendung:
#     local _tag
#     _tag=$(loadLastBuildTag) || exit 1
#
loadLastBuildTag() {
    if [[ ! -f "${TAGFILE}" ]]; then
        echo -e "\n${RED}Kein gespeicherter Build-Tag gefunden: ${TAGFILE}${NC}" >&2
        echo -e "${YELLOW}Zuerst '--build' ausführen.${NC}\n" >&2
        exit 1
    fi

    local _saved_tag _build_ts _now _age_days _build_date
    _saved_tag=$(sed -n '1p' "${TAGFILE}")
    _build_ts=$(sed -n '2p'  "${TAGFILE}")
    _now=$(date +%s)
    _age_days=$(( (_now - _build_ts) / 86400 ))
    _build_date=$(date -d "@${_build_ts}" "+%Y-%m-%d" 2>/dev/null \
               || date -r "${_build_ts}" "+%Y-%m-%d" 2>/dev/null \
               || echo "unbekannt")

    if (( _age_days >= WARN_DAYS )); then
        echo -e "\n${YELLOW}Warnung: Build ist ${_age_days} Tage alt (gebaut am ${_build_date}).${NC}" >&2
        echo -e "${YELLOW}         Neu bauen? → $(basename "$0") --build${NC}\n" >&2
    fi

    echo -e "Build vom ${YELLOW}${_build_date}${NC}: ${BLUE}${_saved_tag}${NC}" >&2
    echo "${_saved_tag}"
}

# push — Versioniertes Image ins Registry laden
#
#   Lädt das lokal gebaute Image unter zwei Tags in die GitHub Container Registry:
#     ghcr.io/<OWNER>/<NAMESPACE>-<NAME>:<TAG>   (versionierter Tag via gitDockerTag)
#     ghcr.io/<OWNER>/<NAMESPACE>-<NAME>:latest  (Zeiger auf neueste Version)
#
#   Voraussetzung: `docker login ghcr.io` muss vorher erfolgt sein.
#   In der Jenkins-Pipeline übernimmt das der "Push to ghcr.io"-Stage mit
#   dem Credential 'github-registry' (GitHub PAT, Scope: write:packages).
#
push() {
    local _tag
    _tag=$(loadLastBuildTag) || exit 1

    echo -e "\nPushing ${YELLOW}${IMAGE}:${_tag}${NC} → ${YELLOW}${REGISTRY}${NC}\n"
    pushImage2GHCR "${GITHUB_OWNER}" "${NAMESPACE}-${NAME}" "${_tag}"

    echo -e "\n${GREEN}Push erfolgreich: ${IMAGE}:${_tag}${NC}"
}

# deploy — Image auf Hetzner ausrollen
#
#   Ablauf auf dem Remote-Host (SSH):
#     1. Image aus ghcr.io pullen: ghcr.io/<OWNER>/…:<TAG>
#     2. Lokal umtaggen auf <NAMESPACE>/<NAME>:<TAG> und :latest
#        → docker-compose.yml auf dem Server bleibt unverändert (nutzt :latest)
#     3. Container neu starten: `docker compose up -d --no-deps --force-recreate`
#     4. Alte lokale Images aufräumen — es werden maximal KEEP_IMAGES Versionen
#        behalten (aktuell: 3), damit der Platzbedarf auf dem Server begrenzt bleibt.
#        :latest wird nie gelöscht. Fehler beim Aufräumen brechen den Deploy nicht ab.
#
#   Voraussetzung auf dem Server: einmaliges `docker login ghcr.io` mit einem
#   PAT (Scope: read:packages), damit das Pull funktioniert.
#
deploy() {
    echo -e "\nDeploying ${YELLOW}${IMAGE}:${TAG}${NC} → ${YELLOW}${DEPLOY_HOST}${NC}\n"
    ssh "${DEPLOY_HOST}" "
        docker pull ${IMAGE}:${TAG} &&
        docker tag  ${IMAGE}:${TAG} ${NAMESPACE}/${NAME}:${TAG} &&
        docker tag  ${IMAGE}:${TAG} ${NAMESPACE}/${NAME}:latest &&
        cd ${DEPLOY_PATH} && docker compose up -d --no-deps --force-recreate ${NAME}
    "
    # Alte lokale Images auf dem Server aufräumen (behalte KEEP_IMAGES Versionen)
    ssh "${DEPLOY_HOST}" "
        docker images '${NAMESPACE}/${NAME}' --format '{{.Tag}}' \
            | grep -v '^latest$' | sort -r | tail -n +$((KEEP_IMAGES + 1)) \
            | xargs -I{} docker rmi '${NAMESPACE}/${NAME}:{}' 2>/dev/null || true
    "
    echo -e "\n${GREEN}Deploy erfolgreich: ${TAG}${NC}"
}

# rollback — Auf eine frühere Version zurückwechseln
#
#   Ohne Argument: listet alle noch lokal vorhandenen Versionen auf dem Server
#     (Tag + Erstellungszeitpunkt, absteigend sortiert) und zeigt die Usage.
#
#   Mit Argument <TAG>: setzt :latest auf die gewünschte Version und startet
#     den Container neu — ohne erneutes Pull aus der Registry.
#     Das Image muss daher noch lokal auf dem Server vorhanden sein
#     (d.h. innerhalb der letzten KEEP_IMAGES Versionen).
#
#   Beispiele:
#     ./build.sh --rollback                        # verfügbare Versionen anzeigen
#     ./build.sh --rollback 0.1.0-build-260412.0824.def34
#
rollback() {
    local _tag="${1:-}"
    if [[ -z "${_tag}" ]]; then
        echo -e "\nVerfügbare Versionen auf ${YELLOW}${DEPLOY_HOST}${NC}:"
        ssh "${DEPLOY_HOST}" "docker images '${NAMESPACE}/${NAME}' \
            --format '{{.Tag}}\t{{.CreatedAt}}' | grep -v '^latest' | sort -r"
        echo -e "\nUsage: $(basename "$0") --rollback <TAG>"
        exit 0
    fi
    echo -e "\nRollback zu ${YELLOW}${NAMESPACE}/${NAME}:${_tag}${NC} auf ${YELLOW}${DEPLOY_HOST}${NC}\n"
    ssh "${DEPLOY_HOST}" "
        docker tag '${NAMESPACE}/${NAME}:${_tag}' '${NAMESPACE}/${NAME}:latest' &&
        cd ${DEPLOY_PATH} && docker compose up -d --no-deps --force-recreate ${NAME}
    "
    echo -e "\n${GREEN}Rollback auf ${_tag} erfolgreich.${NC}"
}


declare -a samples=(
"# AI-Service lokal mit Test-DB starten ||
\t     docker run --name ${NAME} \\
\t         --rm -p 8000:8000 \\
\t         -e POSTGRES_URL=\"postgresql://decisionmap:decisionmap@host.docker.internal:5432/decisionmap\" \\
\t         -e OPENAI_API_KEY=\"sk-...\" \\
\t         ${NAMESPACE}/${NAME}
"
)


#------------------------------------------------------------------------------
# Options
#

usage() {
    echo
    echo -e "OS:           ${YELLOW}${MACHINE}${NC}"
    echo -e "Architecture: ${YELLOW}${ARCHITECTURE}${NC}"
    echo -e "Platform:     ${YELLOW}${PLATFORM}${NC}"
    echo -e "Base Image:   ${YELLOW}${DOCKER_BASE_IMAGE}${NC}"
    echo
    echo "Usage: $(basename "$0") [ options ]"
    usageLine "-u | --update                          " "Update base image: ${YELLOW}${DOCKER_BASE_IMAGE}${NC}"
    echo
    usageLine "-b | --build [ ${YELLOW}platform${NC} ]" "Build docker image: ${BLUE}${NAMESPACE}/${NAME}:${TAG}${NC}" 14
    echo
    usageLine "                                         " "${YELLOW}$PLATFORMS${NC}" 2
    usageLine "                                         " "${YELLOW}x86${NC}      - shortcut for ${YELLOW}linux/amd64${NC}" 2
    usageLine "                                         " "${YELLOW}arm | m1${NC} - shortcut for ${YELLOW}linux/arm64${NC}" 2
    usageLine "                                         " "${YELLOW}all${NC}      - shortcut for ${YELLOW}linux/amd64, linux/arm64${NC}" 2
    echo
    usageLine "-p | --push                              " "Push zu ${YELLOW}${IMAGE}${NC}"
    usageLine "-d | --deploy                            " "Deploy auf ${YELLOW}${DEPLOY_HOST}${NC} (pull + compose up)"
    usageLine "-r | --rollback [ ${YELLOW}TAG${NC} ]    " "Rollback auf Hetzner (ohne TAG: verfügbare Versionen anzeigen)"
    echo
    usageLine "-i | --images                            " "Images anzeigen: ${YELLOW}${NAMESPACE}/${NAME}${NC}"
    usageLine "-s | --samples                           " "Beispiel docker run Befehle anzeigen"
    echo
}


case "${CMDLINE}" in

    -u|--update)
        docker pull "${DOCKER_BASE_IMAGE}"
    ;;

    -b|--build)
        build
    ;;

    -i|--images)
        showImages ${TAG} ${NAMESPACE} ${NAME}
    ;;

    -s|--samples)
        showSamples
    ;;

    -p|--push)
        push
    ;;

    -d|--deploy)
        deploy
    ;;

    -r|--rollback)
        rollback "${OPTION}"
    ;;

    help|-help|--help|*)
        usage
    ;;

esac

#------------------------------------------------------------------------------
# Alles OK...

exit 0
