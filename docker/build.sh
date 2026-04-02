#!/usr/bin/env bash
set -euo pipefail

# DecisionMap AI Service — Docker Build Script
# Strategy: docker build → docker save | ssh | docker load (no registry push)
# TODO: Replace local save/load with registry push when a private registry is available

NAMESPACE="decisionmap"
NAME="ai-service"
REGISTRY=""  # TODO: Set registry when available, e.g. registry.example.com

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------
ARCH="$(uname -m)"
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"

if [[ "${OS}" == "darwin" && "${ARCH}" == "arm64" ]]; then
    PLATFORM="linux/arm64"
elif [[ "${ARCH}" == "x86_64" ]]; then
    PLATFORM="linux/amd64"
else
    echo "Unsupported platform: ${OS}/${ARCH}" >&2
    exit 1
fi

echo "Building for platform: ${PLATFORM}"

# ---------------------------------------------------------------------------
# Version (hashVer via BashLib if available, otherwise git fallback)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKSPACE_ROOT="$(cd "${ROOT_DIR}/../" && pwd)"

# BashLib symlink lives in .libs/ at workspace root
BASHLIB="${WORKSPACE_ROOT}/.libs/BashLib/bashlib.sh"

if [[ -f "${BASHLIB}" ]]; then
    # shellcheck source=/dev/null
    source "${BASHLIB}"
    META_SEPARATOR="." VERSION="$(hashVer)"
else
    # Fallback: simple git-based version
    YEAR="$(date +%Y)"
    QUARTER=$(( ($(date +%-m) - 1) / 3 + 1 ))
    MMDD="$(date +%m%d)"
    HASH="$(git -C "${ROOT_DIR}" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
    VERSION="${YEAR}.${QUARTER}.0-SNAPSHOT${MMDD}.${HASH}"
fi

echo "Version: ${VERSION}"

# ---------------------------------------------------------------------------
# Image tags
# ---------------------------------------------------------------------------
LOCAL_TAG="${NAMESPACE}/${NAME}:${VERSION}"
LATEST_TAG="${NAMESPACE}/${NAME}:latest"

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
docker build \
    --platform "${PLATFORM}" \
    --tag "${LOCAL_TAG}" \
    --tag "${LATEST_TAG}" \
    "${ROOT_DIR}"

echo "Built: ${LOCAL_TAG}"
echo "Built: ${LATEST_TAG}"

# ---------------------------------------------------------------------------
# TODO: Replace with registry push when available
# Current strategy: docker save | ssh appuser@<host> docker load
#
# Example deploy step (add to Jenkinsfile):
#   docker save "${LOCAL_TAG}" | ssh -C appuser@${HETZNER_HOST} docker load
#   ssh appuser@${HETZNER_HOST} docker compose -f /opt/decisionmap/docker-compose.yml up -d ai-service
# ---------------------------------------------------------------------------
echo "Image ready. Deploy via: docker save ${LOCAL_TAG} | ssh <host> docker load"
