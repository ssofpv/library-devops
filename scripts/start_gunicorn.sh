#!/bin/sh
set -eu

PROMETHEUS_MULTIPROC_DIR=/tmp/library-prometheus
export PROMETHEUS_MULTIPROC_DIR
mkdir -p -m 700 "$PROMETHEUS_MULTIPROC_DIR"
rm -f "$PROMETHEUS_MULTIPROC_DIR"/*.db

exec "$@"
