# Hybrid Cloud Works Cloud Assessor

**The upstream product of the Cloud Assessor: the `cloud-assessor-core` engine, its criteria catalog, and the appliance
edition that assesses a client's own Azure scope continuously, under a user-assigned managed identity, against
paraphrased FinOps, Well-Architected cost and Zero Trust criteria.**

A container-focused Well-Architected Review assessment benchmarking Azure infrastructure against the FinOps
Foundation Framework, the Azure Well-Architected Framework Cost Optimization pillar, and Zero Trust security
principles. **Azure is the only target platform.**

## Project status

Implementation of [`REFACTOR_APP.md`](REFACTOR_APP.md) (the owner-approved plan) has landed: the engine is adopted
from the lab edition, the appliance edition exists, and CI, security, image and release workflows are in place. No
release has been tagged yet; `v0.1.0` is the next step (section 15, step 8), after which the lab edition pins this
repository's releases. Everything still queued is in [TODO.md](TODO.md); every decision that needs a human is in
[REVIEW.md](REVIEW.md). Limitations and verification results are recorded per change in
[CHANGELOG.md](CHANGELOG.md).

> Not production until the owner records R-003 (license), R-005 (framework content rights) and R-006 (data
> classification). Every criterion's reference link is marked `[VERIFY]` until the owner confirms it.

## Overview

| Benchmark source | Focus |
|------------------|-------|
| FinOps Foundation Framework | Cost visibility, allocation, optimization, and operating-model maturity |
| Azure Well-Architected Framework — Cost Optimization pillar | Cost-focused architectural review criteria |
| Zero Trust security principles | Identity, device, network, and workload security posture |

Two editions share one engine and one pane (ADR-0028, recorded in the AddOn repository until the wiki exists):

| Edition | Repository | How it reads Azure | Image |
|---|---|---|---|
| **Appliance** (this repository) | `HCW-CloudAssessor_App` | Live Resource Graph and Cost Management under a user-assigned managed identity with `Reader` and `Cost Management Reader` on an allow-listed scope; no upload route; results in memory, refreshed on a timer | `docker.io/hybridcloudworks/hcw-cloud-assessor-appliance` (by digest) |
| **Lab** (downstream) | `HCW-CloudAssessor_AddOn` | Never: visitors upload a Resource Graph export; the image is technically unable to construct an Azure credential | `docker.io/hybridcloudworks/hcw-addon-cloud-assessment` |

The engine (`packages/cloud-assessor-core`) is published from here as a wheel on every `v*` tag; the lab edition's
`core-update` workflow tests each release and opens its adoption pull request. Engine changes are made here, released,
and adopted downstream; never the reverse.

## Repository layout

```text
.
├── README.md  CHANGELOG.md  REVIEW.md  TODO.md  REFACTOR_APP.md   the five root documents (see Documentation)
├── LICENSE  NOTICE                                                 MIT [REVIEW REQUIRED]; framework attribution
├── pyproject.toml  uv.lock  requirements*.lock.txt  ruff.toml      uv workspace, hash-pinned locks, lint
├── .python-version  Makefile  .env.example  .pre-commit-config.yaml
├── packages/cloud-assessor-core/        the engine (pydantic only): model, ingestion, catalog, evaluators, score, reports
├── src/cloud_assessor_appliance/        the appliance: edition guard, identity, scope allow-list, collectors, API, pane
├── samples/                             fictional Resource Graph exports (subscription 00000000-0000-0000-0000-000000000001)
├── scripts/                             check-catalog.py, check-docs-governance.py, check-versions.sh, check-lockfiles.sh
├── infrastructure/docker/               one Dockerfile, two targets (appliance; lab boundary proof), versions.env
├── infrastructure/terraform/appliance-azure/   Container Apps, identity, role assignments, budget
├── tests/                               unit, security (boundary, no secrets), packaging (wheel, lockfiles)
└── .github/                             CODEOWNERS, SECURITY.md, templates, Dependabot, workflows (ci, security, publish-*, release)
```

## Quick start

Requires Python 3.14.6 or newer and [`uv`](https://docs.astral.sh/uv/) 0.11.32 or newer. The commands are PowerShell
unless the line above says bash.

Toolchain and tests (PowerShell):

```powershell
uv python install 3.14; uv sync --all-packages --extra azure; uv run ruff check .; uv run pytest -q
```

The same in bash (Git Bash):

```bash
uv python install 3.14 && uv sync --all-packages --extra azure && uv run ruff check . && uv run pytest -q
```

Security, packaging, catalog and governance (PowerShell):

```powershell
uv run pytest tests/security tests/packaging -q; uv run python scripts/check-catalog.py; uv run python scripts/check-docs-governance.py
```

Local appliance run against your own `az login` session (PowerShell; the scope is computed, never typed):

```powershell
$env:CA_SCOPES = "/subscriptions/" + (az account show -o json | ConvertFrom-Json).id; $env:PORT = "8080"; uv run --extra azure python -m cloud_assessor_appliance
```

Then, in a second prompt, `Invoke-RestMethod http://127.0.0.1:8080/api/health | Select-Object edition, azureConnectivity, scope`
prints `appliance`, `managed-identity` and the scope count. A `503 no_snapshot` from `/api/assessments/current` during
the first minute is the timer still running, not a failure; a `403 results_not_public` after it is the release gate
(`CA_PUBLIC_RESULTS`, see Configuration).

Terraform (PowerShell; `validate` needs no variables; `plan` reads your current subscription; never `apply` from a session):

```powershell
terraform -chdir=infrastructure/terraform/appliance-azure init -backend=false; terraform -chdir=infrastructure/terraform/appliance-azure validate
```

```powershell
$sub = (az account show -o json | ConvertFrom-Json).id; $start = (Get-Date).ToUniversalTime().ToString('yyyy-MM-01') + 'T00:00:00Z'; terraform -chdir=infrastructure/terraform/appliance-azure plan -var ('scope_ids=["/subscriptions/{0}"]' -f $sub) -var "budget_start_date=$start" -var 'image_ref=docker.io/hybridcloudworks/hcw-cloud-assessor-appliance@sha256:0000000000000000000000000000000000000000000000000000000000000000'
```

Image boundary, both targets (bash; needs a Docker daemon):

```bash
docker build -f infrastructure/docker/Dockerfile --target lab -t hcw-cloud-assessor-lab:dev . && docker build -f infrastructure/docker/Dockerfile --target appliance -t hcw-cloud-assessor-appliance:dev .
docker run --rm hcw-cloud-assessor-lab:dev; echo "lab boundary-proof CMD exit code (expected 0): $?"
docker run --rm hcw-cloud-assessor-lab:dev python -c "import azure"; echo "lab import exit code (expected non-zero): $?"
docker run --rm hcw-cloud-assessor-appliance:dev python -c "import azure.identity"; echo "appliance import exit code (expected 0): $?"
```

## Installation

The appliance is deployed from `infrastructure/terraform/appliance-azure` into the client's subscription: one
Consumption Container App (`min_replicas = max_replicas = 1`), a user-assigned managed identity, `Reader` and
`Cost Management Reader` on each `scope_ids` entry, Log Analytics (30 days) and a resource-group budget with 80 and
100 percent notifications. `image_ref` is the digest printed by the `publish-images` workflow; the plan never pulls a
floating tag. `terraform apply` is an owner step after human review.

The engine is installable on its own from a release tag with no cloud SDK:
`cloud-assessor-core @ git+https://github.com/saulpatinojr/HCW-CloudAssessor_App@v0.1.0#subdirectory=packages/cloud-assessor-core`.

## Configuration

Every setting is an environment variable listed in [`.env.example`](.env.example) with an empty value. The appliance
reads `CA_SCOPES` (required; `/subscriptions/<guid>` or `/subscriptions/<guid>/resourceGroups/<name>`, comma or space
separated), `AZURE_CLIENT_ID` (the managed identity; unset locally, where `az login` is used), `CA_REFRESH_MINUTES`,
`CA_COST_ENABLED`, `CA_PUBLIC_RESULTS` (the release gate: results routes answer `403 results_not_public` until it is
`true`), `CA_FRAME_ANCESTORS`, `CA_SITE_ORIGINS`, `CA_ALLOWED_ORIGINS`, `CA_TRUST_PROXY`, the human-verification pair
(`CA_TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET`, optional, on `POST /api/refresh` only), the per-client bucket and the
global refresh cooldown, `CA_PAGE_SIZE`, `CA_MAX_ROWS`, `PORT`. `AZURE_CLIENT_SECRET`, `AZURE_CLIENT_CERTIFICATE_PATH`,
`AZURE_USERNAME`, `AZURE_PASSWORD` and `AZURE_TENANT_ID` are refused at startup: managed identity only, never a client
secret.

## Documentation

This repository uses a deliberately small documentation model. Five markdown files live at the root, each with a
single purpose:

| Document | Contains |
|----------|----------|
| [README.md](README.md) | Repository purpose, overview, setup, and navigation |
| [CHANGELOG.md](CHANGELOG.md) | Completed work only |
| [REVIEW.md](REVIEW.md) | Blockers that require a human decision or external input |
| [TODO.md](TODO.md) | The authoritative engineering backlog |
| [REFACTOR_APP.md](REFACTOR_APP.md) | The implementation plan, superseded section by section as work lands in `CHANGELOG.md`; moves to the wiki page `Implementation-Plan` at the first release |

All other documentation — architecture, design, ADRs, roadmaps, runbooks, troubleshooting guides, research, and
knowledge transfer material — belongs in the
[GitHub Wiki](https://github.com/saulpatinojr/HCW-CloudAssessor_App/wiki). The wiki is enabled but not yet populated
(REVIEW.md R-007); proposed pages are listed in the Phase 6 section of [TODO.md](TODO.md). `scripts/check-docs-governance.py`
enforces the model in CI (T-019); the one exception it allow-lists is `packages/cloud-assessor-core/README.md`, which
the engine's wheel metadata requires and which is adopted verbatim from the lab edition.

## Repository conventions

- **Documentation destination is determined by content, not filename.** Repository purpose goes in `README.md`;
  completed work in `CHANGELOG.md`; human-resolvable blockers in `REVIEW.md`; all actionable engineering work in
  `TODO.md`; the plan in `REFACTOR_APP.md` until its first release; everything else in the wiki.
- **No documentation in dot-prefixed folders.** `.github/`, `.vscode/`, and similar directories hold tool and
  platform configuration only. The sole exceptions are markdown files the platform itself requires, such as issue and
  pull request templates and `SECURITY.md`.
- **No non-root README files.** A `README.md` outside the repository root is documentation and belongs in the wiki
  (the engine package's README is the allow-listed exception above).
- **There must never be competing sources of truth.** Before adding a document, check whether an existing one already
  owns that content.
- **Issues** are used for feature and integration proposals. Work accepted from an issue should be reflected in
  `TODO.md` so an engineer can resume without rediscovering it.
- **Engine changes are published changes.** A change to any `packages/cloud-assessor-core` public surface, evaluator
  kind or catalog entry reaches the lab edition at the next release; say so in the pull request. Evaluator kinds are
  only added, never renamed; `MODEL_VERSION` changes only when `Resource` changes.
- **Pull requests open ready for review** and follow `.github/PULL_REQUEST_TEMPLATE.md`.
