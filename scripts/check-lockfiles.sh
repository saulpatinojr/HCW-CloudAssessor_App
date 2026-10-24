#!/usr/bin/env bash
# requirements.lock.txt and requirements-azure.lock.txt are the hash-preserving exports of uv.lock (REFACTOR_APP.md
# 7.2): re-export both into a temporary directory and diff. Run by ci.yml and `make lint`; exits non-zero on drift.
# uv.lock itself must also match pyproject.toml: `uv lock --check` fails when it is stale, and `--locked` makes the
# exports refuse to re-lock behind our back (without it uv silently rewrites uv.lock before exporting).
set -euo pipefail
cd "$(dirname "$0")/.."
if ! uv lock --check; then
  echo "::error::uv.lock is out of date with pyproject.toml; run 'make lock' and commit uv.lock and both requirements*.lock.txt together"
  exit 1
fi
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
uv export --locked --format requirements-txt --no-dev --no-emit-project --no-emit-workspace --no-header -q -o "$tmp/requirements.lock.txt"
uv export --locked --format requirements-txt --no-dev --no-emit-project --no-emit-workspace --no-header -q --extra azure -o "$tmp/requirements-azure.lock.txt"
diff -u requirements.lock.txt "$tmp/requirements.lock.txt"
diff -u requirements-azure.lock.txt "$tmp/requirements-azure.lock.txt"
if grep -qiE '^(azure-|msal)' requirements.lock.txt; then echo "::error::requirements.lock.txt (the default set) carries a cloud SDK"; exit 1; fi
echo "lockfile exports match uv.lock"
