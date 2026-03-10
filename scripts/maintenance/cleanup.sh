#!/usr/bin/env bash
# cleanup.sh — Remove old Docker images, rotate logs, and clear temp files

set -euo pipefail

REGISTRY="${REGISTRY:-ghcr.io/stacey77/agi-system}"
KEEP_IMAGES="${KEEP_IMAGES:-5}"
LOG_DIR="${LOG_DIR:-/var/log/agi-system}"
TMP_DIR="${TMP_DIR:-/tmp/agi-system}"

echo "==> AGI System Maintenance Cleanup"

# Remove old Docker images (keep most recent N)
echo "==> Cleaning old Docker images (keeping ${KEEP_IMAGES})..."
docker images "${REGISTRY}/agents" --format "{{.ID}}" \
    | tail -n +$((KEEP_IMAGES + 1)) \
    | xargs -r docker rmi || true

docker images "${REGISTRY}/api" --format "{{.ID}}" \
    | tail -n +$((KEEP_IMAGES + 1)) \
    | xargs -r docker rmi || true

# Rotate logs
if [ -d "${LOG_DIR}" ]; then
    echo "==> Rotating logs in ${LOG_DIR}..."
    find "${LOG_DIR}" -name "*.log" -mtime +7 -delete || true
fi

# Clear temp files
if [ -d "${TMP_DIR}" ]; then
    echo "==> Clearing temp files in ${TMP_DIR}..."
    rm -rf "${TMP_DIR:?}"/* || true
fi

# Remove dangling Docker volumes
echo "==> Removing dangling Docker volumes..."
docker volume prune -f || true

echo "==> Cleanup complete."
