#!/bin/bash
#================================================================*
# cobol-run.sh — Docker wrapper for COBOL compilation/execution
# Auto-detects Docker image, builds if missing, runs command
#================================================================*

set -e

# Detect PROJECT_ROOT from script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Convert to Windows path for Docker (handles Git Bash MSYS2 /b/... paths)
if command -v cygpath &> /dev/null; then
  DOCKER_PROJECT_ROOT="$(cygpath -w "$PROJECT_ROOT")"
else
  DOCKER_PROJECT_ROOT="$PROJECT_ROOT"
fi

IMAGE_NAME="cobol-dev"
DOCKERFILE_PATH="$PROJECT_ROOT/Dockerfile.cobol"

# Check if image exists; build if missing
if ! docker image inspect "$IMAGE_NAME" &> /dev/null; then
  echo "Building Docker image: $IMAGE_NAME"
  docker build -t "$IMAGE_NAME" -f "$DOCKERFILE_PATH" "$PROJECT_ROOT"
fi

# Run command in container with project mounted at /app
docker run --rm \
  -v "$DOCKER_PROJECT_ROOT":/app \
  -w /app \
  "$IMAGE_NAME" \
  "$@"
