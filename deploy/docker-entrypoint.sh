#!/bin/sh
set -eu
mkdir -p /app/data
chown -R appuser:appuser /app/data
exec runuser -u appuser -- "$@"
