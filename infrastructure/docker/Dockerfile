# Cloud Assessor App: one Dockerfile, one engine, two targets (REFACTOR_APP.md 7.10).
#
#   deps        the hash-pinned default set (requirements.lock.txt: no cloud SDK) plus the engine as a source tree.
#   deps-azure  the hash-pinned set with the `azure` extra (requirements-azure.lock.txt) plus the engine and the
#               appliance application as source trees. No build backend enters the image.
#   lab         BOUNDARY-PROOF BUILD ONLY. Installs the core without the azure extra, copies no application, has no
#               HEALTHCHECK, is never pushed and never deployed. Its CMD asserts the core imports and no `azure`
#               package is importable, so running the image at all is the proof. The deployed lab image is
#               docker.io/hybridcloudworks/hcw-addon-cloud-assessment, built by HCW-CloudAssessor_AddOn from its own
#               src/cloud_assessment_lab on the published core; this repository contains no lab application.
#   appliance   the deployed image: docker.io/hybridcloudworks/hcw-cloud-assessor-appliance.
#
# Every FROM is the digest in infrastructure/docker/versions.env (scripts/check-versions.sh fails CI on drift).
# Both final stages: apt upgrade, pip/ensurepip/setuptools removed, USER 10001:10001, /tmp the only writable path.
# `apt-get upgrade` is house style (the AddOn's Dockerfile): it picks up Debian security fixes published after the
# base digest, at the cost of bit-for-bit reproducibility between two builds of the same commit. The published image
# is pinned by its own digest (publish-images.yml), so what deploys is still immutable; only "rebuild from source"
# can differ in its apt layer.
#
# Build:  docker build -f infrastructure/docker/Dockerfile --target appliance -t hcw-cloud-assessor-appliance:dev .
#         docker build -f infrastructure/docker/Dockerfile --target lab -t hcw-cloud-assessor-lab:dev .
# Prove:  docker run --rm hcw-cloud-assessor-lab:dev                       # exit 0: core imports, azure absent
#         docker run --rm hcw-cloud-assessor-lab:dev python -c "import azure"          # exit non-zero
#         docker run --rm hcw-cloud-assessor-appliance:dev python -c "import azure.identity"   # exit 0

FROM python:3.15.0-slim-trixie@sha256:f5b92f2a669a4c347044f29367f31983280b648250ca94dea66f98c53bc87e58 AS deps
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
COPY requirements.lock.txt ./
RUN pip install --require-hashes --no-deps --prefix /install -r requirements.lock.txt
COPY packages/cloud-assessor-core/src/cloud_assessor_core /install/lib/python3.14/site-packages/cloud_assessor_core
COPY packages/cloud-assessor-core/catalog /install/lib/python3.14/site-packages/cloud_assessor_core/catalog_data
RUN find /install -name "__pycache__" -type d -prune -exec rm -rf {} + \
 && python - <<'PY'
import importlib.util, sys
sys.path.insert(0, "/install/lib/python3.14/site-packages")
for forbidden in ("azure", "msal", "boto3"):
    if importlib.util.find_spec(forbidden) is not None:
        raise SystemExit(f"edition boundary: {forbidden} is importable in the default set")
print("edition boundary: no cloud SDK in the default set")
PY

FROM python:3.15.0-slim-trixie@sha256:f5b92f2a669a4c347044f29367f31983280b648250ca94dea66f98c53bc87e58 AS deps-azure
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
COPY requirements-azure.lock.txt ./
RUN pip install --require-hashes --no-deps --prefix /install -r requirements-azure.lock.txt
COPY packages/cloud-assessor-core/src/cloud_assessor_core /install/lib/python3.14/site-packages/cloud_assessor_core
COPY packages/cloud-assessor-core/catalog /install/lib/python3.14/site-packages/cloud_assessor_core/catalog_data
COPY src/cloud_assessor_appliance /install/lib/python3.14/site-packages/cloud_assessor_appliance
RUN find /install -name "__pycache__" -type d -prune -exec rm -rf {} +

# ---- lab: boundary-proof build only (never pushed, never deployed) ----
FROM python:3.15.0-slim-trixie@sha256:f5b92f2a669a4c347044f29367f31983280b648250ca94dea66f98c53bc87e58 AS lab
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip uninstall -y pip setuptools wheel >/dev/null 2>&1 || true \
 && rm -rf /usr/local/lib/python3.14/ensurepip /usr/local/lib/python3.14/site-packages/pip* \
           /usr/local/lib/python3.14/site-packages/setuptools* /usr/local/lib/python3.14/site-packages/wheel* \
           /usr/local/bin/pip* /usr/local/bin/wheel /root/.cache \
 && groupadd --gid 10001 app && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=deps /install /usr/local
WORKDIR /app
USER 10001:10001
CMD ["python", "-c", "import cloud_assessor_core; import importlib.util as u; assert u.find_spec('azure') is None; print('lab boundary proof: core', cloud_assessor_core.__version__, 'imports; azure absent')"]

# ---- appliance: the deployed image ----
FROM python:3.15.0-slim-trixie@sha256:f5b92f2a669a4c347044f29367f31983280b648250ca94dea66f98c53bc87e58 AS appliance
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 \
    CA_STATIC_DIR=/usr/local/lib/python3.14/site-packages/cloud_assessor_appliance/web CA_FRAME_ANCESTORS="'none'"
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip uninstall -y pip setuptools wheel >/dev/null 2>&1 || true \
 && rm -rf /usr/local/lib/python3.14/ensurepip /usr/local/lib/python3.14/site-packages/pip* \
           /usr/local/lib/python3.14/site-packages/setuptools* /usr/local/lib/python3.14/site-packages/wheel* \
           /usr/local/bin/pip* /usr/local/bin/wheel /root/.cache \
 && groupadd --gid 10001 app && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=deps-azure /install /usr/local
WORKDIR /app
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT', '8080'), timeout=3).status==200 else 1)"]
CMD ["python", "-m", "cloud_assessor_appliance"]
