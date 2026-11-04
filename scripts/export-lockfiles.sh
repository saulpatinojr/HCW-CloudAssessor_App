#!/usr/bin/env bash
# Writes requirements.lock.txt (the default set: no cloud SDK) and requirements-azure.lock.txt (with the `azure` extra),
# the hash-preserving exports of uv.lock the Dockerfile installs from (REFACTOR_APP.md 7.2), into the directory given
# (default: the repository root). The one place the export flags live: `make lock`, scripts/check-lockfiles.sh and
# .github/workflows/dependabot-lockfiles.yml all call it. --frozen reads uv.lock as it is: nothing is resolved,
# downloaded or built, so no dependency code runs. Whether uv.lock still matches pyproject.toml is checked separately
# (`uv lock --check` in scripts/check-lockfiles.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
out="${1:-.}"
flags=(--frozen --format requirements-txt --no-dev --no-emit-project --no-emit-workspace --no-header -q)
uv export "${flags[@]}" -o "$out/requirements.lock.txt"
uv export "${flags[@]}" --extra azure -o "$out/requirements-azure.lock.txt"
