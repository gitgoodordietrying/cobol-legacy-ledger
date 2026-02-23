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
# Try pwd -W first (Git Bash), then cygpath (Cygwin), else use as-is
DOCKER_PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd -W 2>/dev/null || cygpath -w "$PROJECT_ROOT" 2>/dev/null || echo "$PROJECT_ROOT")"

# Debug: show the paths being used
# echo "DEBUG: PROJECT_ROOT=$PROJECT_ROOT"
# echo "DEBUG: DOCKER_PROJECT_ROOT=$DOCKER_PROJECT_ROOT"

IMAGE_NAME="cobol-dev"
DOCKERFILE_PATH="$PROJECT_ROOT/Dockerfile.cobol"

# Check if image exists; build if missing
if ! docker image inspect "$IMAGE_NAME" &> /dev/null; then
  echo "Building Docker image: $IMAGE_NAME"
  docker build -t "$IMAGE_NAME" -f "$DOCKERFILE_PATH" "$PROJECT_ROOT"
fi

# Run command in container with project mounted at /app
# Escape backslashes for Windows paths if present
# MSYS_NO_PATHCONV prevents Git Bash from converting /app to C:/Program Files/Git/app
DOCKER_VOL_PATH="$DOCKER_PROJECT_ROOT"
MSYS_NO_PATHCONV=1 docker run --rm \
  -v "$DOCKER_VOL_PATH":/app \
  -w /app \
  "$IMAGE_NAME" \
  "$@"
