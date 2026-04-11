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
# Bei den Docker-Images ersetzt die hasVer-Version die Version-Tag-Variante
#
readonly TAG="$(hashVer 4 "" .)"


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

push() {
    local _tag
    _tag=$(loadLastBuildTag) || exit 1

    echo -e "\nPushing ${YELLOW}${IMAGE}:${_tag}${NC} → ${YELLOW}${REGISTRY}${NC}\n"
    pushImage2GHCR "${GITHUB_OWNER}" "${NAMESPACE}-${NAME}" "${_tag}"

    echo -e "\n${GREEN}Push erfolgreich: ${IMAGE}:${_tag}${NC}"
}

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
