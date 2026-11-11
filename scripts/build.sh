#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="portfolio-manager"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REGISTRY="${REGISTRY:-registry.home}"
VERSION="$(tr -d '[:space:]' < "${ROOT_DIR}/VERSION")"
BRANCH="$(git -C "${ROOT_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")"
SHORT_SHA="$(git -C "${ROOT_DIR}" rev-parse --short HEAD 2>/dev/null || echo "dev")"

IS_PRODUCTION=false
if [ "${ENVIRONMENT:-}" = "production" ] || [ "$BRANCH" = "main" ]; then
  IMAGE_TAG="${VERSION}"
  IS_PRODUCTION=true
else
  IMAGE_TAG="${VERSION}-staging.${SHORT_SHA}"
fi

FULL_IMAGE="${REGISTRY}/${SERVICE_NAME}:${IMAGE_TAG}"
echo "Building ${FULL_IMAGE}..."
docker build -t "${FULL_IMAGE}" "${ROOT_DIR}"
echo "Pushing ${FULL_IMAGE}..."
docker push "${FULL_IMAGE}" || true

# Tag and push :latest on main for Trivy scans and registry convenience
if [ "$IS_PRODUCTION" = "true" ]; then
  LATEST_IMAGE="${REGISTRY}/${SERVICE_NAME}:latest"
  echo "Tagging and pushing ${LATEST_IMAGE}..."
  docker tag "${FULL_IMAGE}" "${LATEST_IMAGE}"
  docker push "${LATEST_IMAGE}" || true
fi

STAGING_KUST="${ROOT_DIR}/kubernetes/overlays/staging/kustomization.yaml"
if [ -f "$STAGING_KUST" ] && [ "$BRANCH" != "main" ]; then
  sed -i -E "s/(newTag:).*/\1 \"${IMAGE_TAG}\"/" "$STAGING_KUST"
fi
