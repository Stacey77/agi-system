#!/usr/bin/env bash
# deploy.sh — Build, push, and deploy the AGI system to Kubernetes

set -euo pipefail

ENVIRONMENT="${1:-development}"
VERSION="${2:-$(git rev-parse --short HEAD)}"
REGISTRY="${REGISTRY:-ghcr.io/stacey77/agi-system}"

echo "==> Deploying AGI System (env=${ENVIRONMENT}, version=${VERSION})"

# Build Docker images
echo "==> Building Docker images..."
docker build -t "${REGISTRY}/agents:${VERSION}" -f infrastructure/docker/Dockerfile.agents .
docker build -t "${REGISTRY}/api:${VERSION}" -f infrastructure/docker/Dockerfile.api .

# Push images
echo "==> Pushing images to registry..."
docker push "${REGISTRY}/agents:${VERSION}"
docker push "${REGISTRY}/api:${VERSION}"

# Deploy to Kubernetes
echo "==> Updating Kubernetes deployment..."
kubectl set image deployment/agi-system \
    agi-agents="${REGISTRY}/agents:${VERSION}" \
    --namespace=agi-system

# Wait for rollout
echo "==> Waiting for rollout to complete..."
kubectl rollout status deployment/agi-system --namespace=agi-system --timeout=300s

echo "==> Deployment complete! Version ${VERSION} is live."
