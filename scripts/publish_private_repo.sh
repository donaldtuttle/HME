#!/usr/bin/env bash
set -euo pipefail

OWNER="${GITHUB_OWNER:-donaldtuttle}"
REPO_NAME="${GITHUB_REPO:-qosmos-hme}"
DESCRIPTION="QOSMOS Holographic Memory Engine typed realization with QMesh lineage and SFD bridge"

command -v gh >/dev/null 2>&1 || {
  echo "GitHub CLI is required: https://cli.github.com/" >&2
  exit 1
}

gh auth status >/dev/null

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "Run this script from the initialized qosmos-hme Git repository." >&2
  exit 1
}

gh repo create "${OWNER}/${REPO_NAME}" \
  --private \
  --description "$DESCRIPTION" \
  --source . \
  --remote origin \
  --push
