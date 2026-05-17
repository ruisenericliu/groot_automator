#!/usr/bin/env bash
# Bring up the groot-server container on the AWS workstation. Idempotent:
# `docker compose up -d` is a no-op if the container is already running.
#
# Depends on docker-compose.aws.yml + docker/groot/* (B.3 deliverables, still 🟡
# as of 2026-05-16). Running this before B.3 lands will fail with "no
# configuration file provided".
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

: "${NGC_API_KEY:?NGC_API_KEY must be set (see .env.example)}"

# Idempotent: docker login is safe to re-run.
printf '%s' "${NGC_API_KEY}" | docker login nvcr.io --username '$oauthtoken' --password-stdin

docker compose -f docker-compose.aws.yml up -d groot-server
