#!/usr/bin/env bash
# requirements.lock.txt and requirements-azure.lock.txt are the hash-preserving exports of uv.lock (REFACTOR_APP.md
# 7.2): re-export both into a temporary directory and diff. Run by ci.yml and `make lint`; exits non-zero on drift.
set -euo pipefail
cd "$(dirname "$0")/.."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
uv export --format requirements-txt --no-dev --no-emit-project --no-emit-workspace --no-header -q -o "$tmp/requirements.lock.txt"
uv export --format requirements-txt --no-dev --no-emit-project --no-emit-workspace --no-header -q --extra azure -o "$tmp/requirements-azure.lock.txt"
diff -u requirements.lock.txt "$tmp/requirements.lock.txt"
diff -u requirements-azure.lock.txt "$tmp/requirements-azure.lock.txt"
if grep -qiE '^(azure-|msal)' requirements.lock.txt; then echo "::error::requirements.lock.txt (the default set) carries a cloud SDK"; exit 1; fi
echo "lockfile exports match uv.lock"
