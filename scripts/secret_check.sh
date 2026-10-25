#!/usr/bin/env bash
set -euo pipefail

mkdir -p reports

GITLEAKS_IMAGE="ghcr.io/gitleaks/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f"

docker run --rm \
  -e GIT_CONFIG_COUNT=1 \
  -e GIT_CONFIG_KEY_0=safe.directory \
  -e GIT_CONFIG_VALUE_0=/repo \
  -v "$(pwd):/repo:ro" \
  -v "$(pwd)/reports:/reports" \
  "$GITLEAKS_IMAGE" \
  git /repo \
  --log-opts=HEAD \
  --config=/repo/.gitleaks.toml \
  --redact \
  --report-format=json \
  --report-path=/reports/gitleaks.json
