#!/usr/bin/env bash
set -euo pipefail

OWNER="${GITHUB_OWNER:-donaldtuttle}"
REPO_NAME="${GITHUB_REPO:-HME}"
DESCRIPTION="Deterministic hybrid field-plus-ledger memory engine with reconstructive storage, auditable provenance, ranked retrieval, and lineage tracking"

command -v gh >/dev/null 2>&1 || {
  echo "GitHub CLI is required: https://cli.github.com/" >&2
  exit 1
}

gh auth status >/dev/null

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "Run this script from the initialized HME Git repository." >&2
  exit 1
}

gh repo create "${OWNER}/${REPO_NAME}" \
  --public \
  --description "$DESCRIPTION" \
  --source . \
  --remote origin \
  --push
