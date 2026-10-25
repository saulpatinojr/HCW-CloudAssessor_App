# Hybrid Cloud Works Cloud Assessor

**The upstream product of the Cloud Assessor: the `cloud-assessor-core` engine, its criteria catalog, and the appliance
edition that assesses a client's own Azure scope continuously, under a user-assigned managed identity, against
paraphrased FinOps, Well-Architected cost and Zero Trust criteria.**

[![ci](https://github.com/saulpatinojr/HCW-CloudAssessor_App/actions/workflows/ci.yml/badge.svg)](https://github.com/saulpatinojr/HCW-CloudAssessor_App/actions/workflows/ci.yml)
[![security](https://github.com/saulpatinojr/HCW-CloudAssessor_App/actions/workflows/security.yml/badge.svg)](https://github.com/saulpatinojr/HCW-CloudAssessor_App/actions/workflows/security.yml)
[![release](https://img.shields.io/github/v/release/saulpatinojr/HCW-CloudAssessor_App?label=release&include_prereleases)](https://github.com/saulpatinojr/HCW-CloudAssessor_App/releases)
[![python](https://img.shields.io/badge/python-3.14-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![license](https://img.shields.io/github/license/saulpatinojr/HCW-CloudAssessor_App)](LICENSE)
[![lab edition](https://img.shields.io/badge/lab%20edition-HCW--CloudAssessor__AddOn-6f42c1?logo=github)](https://github.com/saulpatinojr/HCW-CloudAssessor_AddOn)

**New here?** Give it read-only access to an Azure subscription and it tells you where cost practice, resilience and
Zero Trust fall short, criterion by criterion, with the evidence for each finding and an honest statement of what it
could not see. A free version that needs no Azure access is the lab edition,
[HCW-CloudAssessor_AddOn](https://github.com/saulpatinojr/HCW-CloudAssessor_AddOn): it takes a Resource Graph export
instead, and will appear at [hybridcloudworks.com/tools/cloud-assessment](https://hybridcloudworks.com/tools/cloud-assessment)
once its first image is published.

A container-focused Well-Architected Review assessment benchmarking Azure infrastructure against the FinOps
Foundation Framework, the Azure Well-Architected Framework Cost Optimization pillar, and Zero Trust security
principles. **Azure is the only target platform.**

## Project status

Implementation of [`REFACTOR_APP.md`](REFACTOR_APP.md) (the owner-approved plan) has landed: the engine is adopted
from the lab edition, the appliance edition exists, and CI, security, image and release workflows are in place.
Two releases exist, [`v0.2.0`](https://github.com/saulpatinojr/HCW-CloudAssessor_App/releases/tag/v0.2.0) (2026-10-12)
and [`v0.2.1`](https://github.com/saulpatinojr/HCW-CloudAssessor_App/releases/tag/v0.2.1) (2026-10-18); each attaches
the engine wheel (`cloud_assessor_core-<version>-py3-none-any.whl`) that the lab edition is meant to pin. There is no
`v0.1.0` tag in this repository. The engine, the appliance and the image share one version, and a check refuses a tag
that disagrees with it (see "Releasing and versioning" below; the policy is ticket
[#33](https://github.com/saulpatinojr/HCW-CloudAssessor_App/issues/33), pending the owner's confirmation). The lab
edition has not adopted a release yet; what it carries and what changed here are tracked in its `docs/whats-new-upstream.md`.
Everything still queued is in [TODO.md](TODO.md); every decision that needs a human is in [REVIEW.md](REVIEW.md).
Limitations and verification results are recorded per change in [CHANGELOG.md](CHANGELOG.md).

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
| **Appliance** (this repository) | `HCW-CloudAssessor_App` | Live Resource Graph and Cost Management under a user-assigned managed identity with `Reader` and `Cost Management Reader` on an allow-listed scope; no upload route; results in memory, refreshed on a timer | `docker.io/hybridcloudworks/img-ca-appliance-app` (by digest) |
| **Lab** (downstream) | `HCW-CloudAssessor_AddOn` | Never: visitors upload a Resource Graph export; the image is technically unable to construct an Azure credential | `docker.io/hybridcloudworks/hcw-addon-cloud-assessment` |

The engine (`packages/cloud-assessor-core`) is published from here as a wheel on every `v*` tag; the lab edition's
`core-update` workflow tests each release and opens its adoption pull request once the lab edition pins a release.
Engine changes are made here, released, and adopted downstream; never the reverse. The lab edition keeps a running
note of what reaches it in its `docs/whats-new-upstream.md`.

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
├── scripts/                             check-catalog.py, check-docs-governance.py, check-release-version.py, check-versions.sh, check-lockfiles.sh
├── infrastructure/docker/               one Dockerfile, two targets (appliance; lab boundary proof), versions.env
├── infrastructure/terraform/appliance-azure/   Container Apps, identity, role assignments, budget
├── tests/                               unit, security (boundary, no secrets), packaging (wheel, lockfiles)
└── .github/                             CODEOWNERS, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, issue forms, PR template, Dependabot, workflows
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
$sub = (az account show -o json | ConvertFrom-Json).id; $start = (Get-Date).ToUniversalTime().ToString('yyyy-MM-01') + 'T00:00:00Z'; terraform -chdir=infrastructure/terraform/appliance-azure plan -var ('scope_ids=["/subscriptions/{0}"]' -f $sub) -var "budget_start_date=$start" -var 'image_ref=docker.io/hybridcloudworks/img-ca-appliance-app@sha256:0000000000000000000000000000000000000000000000000000000000000000'
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

The engine is installable on its own, with no cloud SDK, from the wheel attached to each release (the lab edition
pins the same file by URL and sha256, because a `git+https` pin cannot be hash-checked). It needs Python 3.14.6 or
newer, and the command is the same in bash and PowerShell:

```bash
python -m pip install https://github.com/saulpatinojr/HCW-CloudAssessor_App/releases/download/v0.2.1/cloud_assessor_core-0.2.1-py3-none-any.whl
```

Replace `v0.2.1` and `0.2.1` together to install another release; the list is on the
[releases page](https://github.com/saulpatinojr/HCW-CloudAssessor_App/releases).

## Releasing and versioning

**The policy (ticket [#33](https://github.com/saulpatinojr/HCW-CloudAssessor_App/issues/33); the owner can overrule it).**
The engine, the appliance and the container image share **one version**, a plain `X.Y.Z` (no pre-release suffix). One
`vX.Y.Z` tag publishes all three: the engine wheel (`publish-core.yml`), the image (`publish-images.yml`) and the GitHub
Release (`release.yml`). The tag is `v` plus that version, nothing else. The version is raised only in the pull request
that prepares a release, so between releases the tree carries the number of the last release.

Each artifact has one place where a person edits its version, and the other places that must repeat it are checked by
`scripts/check-release-version.py`, never edited on their own:

| Artifact | Edited in | Repeated in (checked, never edited alone) |
|----------|-----------|-------------------------------------------|
| Engine wheel `cloud_assessor_core-X.Y.Z-py3-none-any.whl` | `packages/cloud-assessor-core/pyproject.toml` | its `__version__`, its `uv.lock` entry, the built wheel's file name and its own `__version__` |
| Appliance, `/api/health`, the `x-addon-version` header, the image tag `vX.Y.Z` | `pyproject.toml` | its `__version__`, its `uv.lock` entry, the git tag |
| Release notes | `CHANGELOG.md`, section `## [X.Y.Z] - YYYY-MM-DD` | |

`/api/health` and the response header read the appliance's `__version__`, a literal in the source, because the image
copies the source trees without package metadata and so cannot look the version up. That is why the constant is a mirror
to check rather than something to derive. A build of `main` therefore reports the last release number.

**What the check does.** On every pull request (`ci.yml`, `make lint`) it fails unless both `pyproject.toml` files, both
`__version__` constants and both `uv.lock` entries name the same `X.Y.Z`. Each workflow that a tag starts
(`release.yml`, `publish-core.yml`, `publish-images.yml`) runs it first, with the tag, before it builds, attests,
attaches or pushes anything. With a tag it also fails unless the tag is exactly `v` + that version, `CHANGELOG.md` has a
dated, non-empty `## [X.Y.Z] - YYYY-MM-DD` section, nothing is left under `## [Unreleased]`, and the tagged commit is
on `main`; `publish-core.yml` also checks that the build produced exactly the wheel and the sdist for the version and
that the wheel's own `__version__` matches its file name. A tag cannot be moved or deleted once pushed (ruleset
"Protect release tags"), so these checks are the only chance to stop a wrong one.

**Why one version, and the alternative that was not chosen.** The wheel, the image and the release already come from the
same tag, and the lab edition pins a release by that tag, so a single number is the one the tag, the wheel file name,
`/api/health` and the image all show. The alternative is two version lines with their own tag prefixes (for example
`core-vX.Y.Z` for the engine and `app-vX.Y.Z` for the appliance). It lets an application-only change skip an engine
release, but it needs new tag rules, changes the release asset URLs the lab edition already pins, and gives a support
engineer two numbers to compare. It is not adopted here; choose it only if the engine starts to be released on its own
schedule.

**To release a version** (the pull request is ordinary; the tag is an owner step, because it cannot be undone):

1. Open a pull request that changes the version in `packages/cloud-assessor-core/pyproject.toml`, `pyproject.toml` and
   both `__version__` constants, runs `make lock` (which updates `uv.lock`), moves everything under `## [Unreleased]` in
   `CHANGELOG.md` into a new `## [X.Y.Z] - YYYY-MM-DD` section, and leaves `## [Unreleased]` empty. Run `make lint` first;
   it runs the check without a tag.
2. Merge it after review.
3. Tag `main` and push the tag. PowerShell, with the version you chose in place of `X.Y.Z`:

   ```powershell
   git switch main; git pull origin main; git tag -a vX.Y.Z -m "Cloud Assessor X.Y.Z"; git push origin vX.Y.Z
   ```

4. Open the Actions tab and wait for `release`, `publish-core` and `publish-images` to finish. If one stops at the version
   check, nothing was built or published: the message names the file that disagrees.
5. Confirm the result: the [release page](https://github.com/saulpatinojr/HCW-CloudAssessor_App/releases) lists the
   release with the wheel and the sdist, and `GET /api/health` of a deployed appliance reports `X.Y.Z` in `version`.

## Contributing and reporting

New here? Read [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md) (how a change reaches `main`) and
[.github/CODE_OF_CONDUCT.md](.github/CODE_OF_CONDUCT.md). Report a problem or propose a feature with one of the forms on
the [New issue page](https://github.com/saulpatinojr/HCW-CloudAssessor_App/issues/new/choose) (the forms live in
[.github/ISSUE_TEMPLATE](.github/ISSUE_TEMPLATE)). Report a vulnerability privately, as
[.github/SECURITY.md](.github/SECURITY.md) describes; never in a public issue.

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

### Sign-in (Microsoft Entra ID)

Results require a sign-in (owner decision, `REVIEW.md` R-009 option b). It is off by default; the `CA_PUBLIC_RESULTS` gate
is a separate lock and stays off by default whatever the sign-in setting. With `CA_AUTH_ENABLED=true`, every route except
`GET /api/health` (which stays open and content-free) needs `Authorization: Bearer <access token>` and otherwise answers
`401 unauthorized` with `WWW-Authenticate: Bearer`. That includes the pane files, so until the pane signs users in, call
the API directly or put the pane's sign-in in front of it. The appliance holds no secret for this: it checks tokens with
the tenant's public signing keys. Reference: [access tokens](https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens)
and [claims validation](https://learn.microsoft.com/en-us/entra/identity-platform/claims-validation).

| Setting | Required when sign-in is on | Example shape (not real values) |
|---------|-----------------------------|---------------------------------|
| `CA_AUTH_ENABLED` | yes, `true` | `true` |
| `CA_AUTH_TENANT_ID` | yes: the tenant (directory) id | `00000000-0000-0000-0000-000000000000` |
| `CA_AUTH_AUDIENCE` | yes: the app registration's application (client) id and/or its `api://` URI, space or comma separated | `00000000-0000-0000-0000-000000000000 api://hcw-cloud-assessor` |
| `CA_AUTH_AUTHORITY_HOST` | yes: the sign-in host name only (builds the issuer and the key address) | `login.microsoftonline.com` |
| `CA_AUTH_JWKS_URL` | no: an `https` address for the signing keys instead of the built one | `https://login.microsoftonline.com/<tenant id>/discovery/v2.0/keys` |
| `CA_AUTH_CLOCK_SKEW_SECONDS` | no: 0 to 300, default 60 | `60` |
| `CA_AUTH_REQUIRED_ROLES` / `CA_AUTH_REQUIRED_SCOPES` | no: the app role (`roles`) or delegated scope (`scp`) a token must carry, default `Assessment.Read` for both | `Assessment.Read` |

The appliance refuses to start if sign-in is on and the tenant, audience or authority host is missing or malformed, and
if `CA_PUBLIC_RESULTS=true` is set without sign-in. What is checked on each request: RS256 signature (never `none` or
`HS*`; an unknown key id is refused), `iss` (the v2.0 and v1.0 forms for the tenant), `aud`, `exp`, `nbf`, `tid`, and the
required role or scope. Logs carry a status and a number, never a token or a claim. Validated only against locally
generated keys, not yet against a real tenant.

## Documentation

This repository uses a deliberately small documentation model. Five markdown files live at the root, each with a
single purpose:

| Document | Contains |
|----------|----------|
| [README.md](README.md) | Repository purpose, overview, setup, and navigation |
| [CHANGELOG.md](CHANGELOG.md) | Completed work only |
| [REVIEW.md](REVIEW.md) | Blockers that require a human decision or external input |
| [TODO.md](TODO.md) | The authoritative engineering backlog |
| [REFACTOR_APP.md](REFACTOR_APP.md) | The implementation plan, superseded section by section as work lands in `CHANGELOG.md`; moves to the wiki page `Implementation-Plan` once the wiki can be written (R-007; the first release, v0.2.0, has already been cut) |

All other documentation — architecture, design, ADRs, roadmaps, runbooks, troubleshooting guides, research, and
knowledge transfer material — belongs in the
[GitHub Wiki](https://github.com/saulpatinojr/HCW-CloudAssessor_App/wiki). The wiki is enabled but not yet populated
(REVIEW.md R-007); proposed pages are listed in the Phase 6 section of [TODO.md](TODO.md). `scripts/check-docs-governance.py`
enforces the model in CI (T-019). It allow-lists these exceptions: `CLAUDE.md`, the working agreement for AI coding
agents; the community files GitHub reads from `.github/` (`SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, the
pull request template); and `packages/cloud-assessor-core/README.md`, which the engine's wheel metadata requires and
which is adopted verbatim from the lab edition.

## Repository conventions

- **Documentation destination is determined by content, not filename.** Repository purpose goes in `README.md`;
  completed work in `CHANGELOG.md`; human-resolvable blockers in `REVIEW.md`; all actionable engineering work in
  `TODO.md`; the plan in `REFACTOR_APP.md` until it moves to the wiki (R-007); everything else in the wiki.
- **No documentation in dot-prefixed folders.** `.github/`, `.vscode/`, and similar directories hold tool and
  platform configuration only. The sole exceptions are markdown files the platform itself requires, such as the pull
  request template, `SECURITY.md`, `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`. Issue templates are YAML forms.
- **No non-root README files.** A `README.md` outside the repository root is documentation and belongs in the wiki
  (the engine package's README is the allow-listed exception above).
- **There must never be competing sources of truth.** Before adding a document, check whether an existing one already
  owns that content.
- **Issues** are opened with the forms in `.github/ISSUE_TEMPLATE` and are used for bugs, feature and integration
  proposals and tracked work items. Work accepted from an issue should be reflected in
  `TODO.md` so an engineer can resume without rediscovering it.
- **Engine changes are published changes.** A change to any `packages/cloud-assessor-core` public surface, evaluator
  kind or catalog entry reaches the lab edition at the next release; say so in the pull request. Evaluator kinds are
  only added, never renamed; `MODEL_VERSION` changes only when `Resource` changes.
- **Pull requests open ready for review** and follow `.github/PULL_REQUEST_TEMPLATE.md`.
