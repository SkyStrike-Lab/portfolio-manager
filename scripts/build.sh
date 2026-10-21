#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

VERSION="$(tr -d '[:space:]' < "${ROOT_DIR}/VERSION")"
IMAGE_TAG="registry.home/portfolio-manager:${VERSION}"

echo "Building ${IMAGE_TAG}..."
docker build -t "${IMAGE_TAG}" "${ROOT_DIR}"

echo "Pushing ${IMAGE_TAG}..."
docker push "${IMAGE_TAG}"

echo "Successfully built and pushed ${IMAGE_TAG}"
