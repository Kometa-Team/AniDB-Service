#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_IMAGE="${BASE_IMAGE:-ghcr.io/kometa-team/imdb-service-base:latest}"
APP_IMAGE="${APP_IMAGE:-ghcr.io/kometa-team/imdb-service:latest}"

docker build \
  -f "${SCRIPT_DIR}/Dockerfile.base" \
  -t "${BASE_IMAGE}" \
  "${SCRIPT_DIR}"

docker build \
  -f "${SCRIPT_DIR}/Dockerfile" \
  --build-arg "BASE_IMAGE=${BASE_IMAGE}" \
  -t "${APP_IMAGE}" \
  "${SCRIPT_DIR}"

printf 'Built %s and %s\n' "${BASE_IMAGE}" "${APP_IMAGE}"
