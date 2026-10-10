#!/usr/bin/env bash
# The base image digest in infrastructure/docker/versions.env equals every FROM in the Dockerfile that is not an
# earlier stage (CONTRACT-DECISIONS item 20). Run by ci.yml and `make lint`; exits non-zero on drift.
set -euo pipefail
cd "$(dirname "$0")/.."
DOCKERFILE=${1:-infrastructure/docker/Dockerfile}
VERSIONS=${2:-infrastructure/docker/versions.env}
image="$(sed -n 's/^PYTHON_IMAGE=//p' "$VERSIONS")"
digest="$(sed -n 's/^PYTHON_IMAGE_DIGEST=//p' "$VERSIONS")"
want="${image}@${digest}"
case "$want" in *@sha256:????????????????????????????????????????????????????????????????) ;; *) echo "::error::${VERSIONS} is not image@sha256:<64 hex>"; exit 1 ;; esac
stages=" "; bad=0; seen=0
while read -r _ from as name _; do
  seen=$((seen + 1))
  if [[ "$stages" == *" ${from} "* ]]; then echo "ok FROM ${from} (earlier stage)"
  elif [ "$from" = "$want" ]; then echo "ok FROM ${from}"
  else echo "::error file=${DOCKERFILE}::FROM ${from} is neither an earlier stage nor ${want}"; bad=1; fi
  if [ "${as,,}" = as ] && [ -n "$name" ]; then stages="${stages}${name} "; fi
done < <(grep -E '^FROM ' "$DOCKERFILE")
if [ "$seen" -eq 0 ]; then echo "::error::${DOCKERFILE} has no FROM line"; exit 1; fi
exit $bad
