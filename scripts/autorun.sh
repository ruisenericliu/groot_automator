#!/usr/bin/env bash
# Isaac Automator boot hook. Place at ~/uploads/autorun.sh on the workstation
# (or symlink to this file) so `./run ./start <name>` re-invokes it on each
# boot. Idempotent: if groot-server is already up, this is a no-op.
set -euo pipefail

REPO_DIR="${GROOT_REPO_DIR:-${HOME}/workspace/groot_automator}"
cd "${REPO_DIR}"

if [[ -f .env ]]; then
  set -a
  # shellcheck source=/dev/null
  . .env
  set +a
fi

exec ./scripts/start_groot.sh
