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
[#33](https://github.com/saulpatinojr/HCW-CloudAssessor_App/issues/33), decided by the owner). The lab
edition has not adopted a release yet; what it carries and what changed here are tracked in its `docs/whats-new-upstream.md`.
Everything still queued is in [TODO.md](TODO.md); every decision that needs a human is in [REVIEW.md](REVIEW.md).
Limitations and verification results are recorded per change in [CHANGELOG.md](CHANGELOG.md).

> Not production until the owner records R-005 (framework content rights) and R-006 (data classification). The license
> and visibility are decided (R-003): this repository is public and MIT-licensed. Every criterion's reference link is
> marked `[VERIFY]` until the owner confirms it.

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
├── LICENSE  NOTICE                                                 MIT (R-003 decided); framework attribution
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

Terraform (PowerShell; `validate` needs no variables; `plan` reads your current subscription; never `apply` from a session). `terraform test` runs the plan-only guard tests with mock providers and needs no login:

```powershell
terraform -chdir=infrastructure/terraform/appliance-azure init -backend=false; terraform -chdir=infrastructure/terraform/appliance-azure validate; terraform -chdir=infrastructure/terraform/appliance-azure test
```

```powershell
$sub = az account show --query id -o tsv; $env:TF_VAR_scope_ids = '["/subscriptions/' + $sub + '"]'; $env:TF_VAR_budget_start_date = (Get-Date).ToUniversalTime().ToString('yyyy-MM-01') + 'T00:00:00Z'; $env:TF_VAR_image_ref = 'docker.io/hybridcloudworks/img-ca-appliance-app@sha256:0000000000000000000000000000000000000000000000000000000000000000'; $env:TF_VAR_alert_emails = '["' + (az account show --query user.name -o tsv) + '"]'; $env:TF_VAR_auth_enabled = 'true'; terraform -chdir=infrastructure/terraform/appliance-azure plan
```

`plan` needs `auth_enabled = true` (or `external_enabled = false`): an internet-reachable appliance without sign-in is refused by the plan itself. See Sign-in below.

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
`Cost Management Reader` on each `scope_ids` entry, Log Analytics (30 days) and, when `alert_emails` lists at least one
address, a resource-group budget with 80 and 100 percent notifications to those addresses (Azure needs a recipient on
every budget notification, so the default empty `alert_emails` creates no budget; `terraform output budget_notifications`
states which applies; the plan is covered by `infrastructure/terraform/appliance-azure/tests/budget_notifications.tftest.hcl`). `image_ref` is the digest printed by the `publish-images` workflow; the plan never pulls a
floating tag. The plan refuses an internet-reachable appliance unless `auth_enabled = true` (Microsoft Entra ID sign-in, see Sign-in) or `external_enabled = false`. `terraform apply` is an owner step after human review.

The engine is installable on its own, with no cloud SDK, from the wheel attached to each release (the lab edition
pins the same file by URL and sha256, because a `git+https` pin cannot be hash-checked). It needs Python 3.14.6 or
newer, and the command is the same in bash and PowerShell:

```bash
python -m pip install https://github.com/saulpatinojr/HCW-CloudAssessor_App/releases/download/v0.2.1/cloud_assessor_core-0.2.1-py3-none-any.whl
```

Replace `v0.2.1` and `0.2.1` together to install another release; the list is on the
[releases page](https://github.com/saulpatinojr/HCW-CloudAssessor_App/releases).

## Releasing and versioning

**The policy (ticket [#33](https://github.com/saulpatinojr/HCW-CloudAssessor_App/issues/33); owner decision, recorded 2026-10-25).**
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
engineer two numbers to compare. The owner chose one version, so the alternative is not adopted; revisit it only if
the engine starts to be released on its own schedule.

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
| `CA_AUTH_REQUIRED_ROLES` / `CA_AUTH_REQUIRED_SCOPES` | no: the app role (`roles`) or delegated scope (`scp`) a token must carry; the defaults are the role `Assessment.Read` and the scope `access_as_user` (two different values, because Entra needs them unique) | `Assessment.Read` / `access_as_user` |

The appliance refuses to start if sign-in is on and the tenant, audience or authority host is missing or malformed, and
if `CA_PUBLIC_RESULTS=true` is set without sign-in. What is checked on each request: RS256 signature (never `none` or
`HS*`; an unknown key id is refused), `iss` (the v2.0 and v1.0 forms for the tenant), `aud`, `exp`, `nbf`, `tid`, and the
required role or scope. Logs carry a status and a number, never a token or a claim. Validated only against locally
generated keys, not yet against a real tenant.

#### Supported exposure

The appliance may be reached from the internet only with sign-in on. Terraform enforces it: with the defaults
(`external_enabled = true`, `auth_enabled = false`) `terraform plan` stops with "Refusing to plan an externally
reachable appliance without caller authentication". There are exactly two supported ways to deploy, and one override
that is not supported:

| Posture | Terraform inputs | Supported |
|---------|------------------|-----------|
| Reachable from the internet, callers sign in with Microsoft Entra ID | `auth_enabled = true` | Yes |
| Private: only things inside the Container Apps environment can reach it | `external_enabled = false` | Yes |
| Reachable from the internet, nobody signs in | `dangerously_allow_unauthenticated_external_ingress = true` | No. It is an owner decision recorded in `REVIEW.md`, and `terraform output caller_authentication` then starts with `NONE` |

`public_results = true` (the `CA_PUBLIC_RESULTS` gate) also needs `auth_enabled = true`, in the plan as in the
appliance's own startup check. The override does not relax that.

#### Turning sign-in on with Terraform

`infrastructure/terraform/appliance-azure/auth.tf` wires every `CA_AUTH_*` setting the code reads (`CA_AUTH_JWKS_URL` is
left unset on purpose: the code builds the key address from the authority host and the tenant). Nothing in it is a
secret, and nothing creates one: no client secret, certificate or password, because the appliance only checks tokens
with the tenant's public keys. With `auth_enabled = true` Terraform creates, in the tenant of the signed-in user:

- an application registration (one tenant only, v2 access tokens) with an app role named `Assessment.Read`
  (`auth_role_value`, for applications, managed identities and assigned users) and a delegated scope named
  `access_as_user` (`auth_scope_value`, for a signed-in user's token), and the `api://<client id>` identifier URI. The
  two names must differ: Entra keeps app roles and scopes in one shared namespace, and the `azuread` provider refuses
  a plan that uses one value for both ([provider docs](https://registry.terraform.io/providers/hashicorp/azuread/latest/docs/resources/application)).
  `access_as_user` is the scope name Microsoft's own web API guide uses ([Microsoft Learn](https://learn.microsoft.com/entra/identity-platform/scenario-protected-web-api-expose-scopes));
- a service principal with `app_role_assignment_required = true`, so Entra issues a token for this API only to users,
  groups or managed identities you assigned (`auth_assigned_object_ids`). This is a second lock in front of the
  appliance's own checks;
- optionally, client applications allowed to request the scope without a consent prompt (`auth_preauthorized_client_ids`,
  empty by default).

| Appliance setting | Terraform |
|-------------------|-----------|
| `CA_AUTH_ENABLED` | `auth_enabled` (default `false`) |
| `CA_AUTH_TENANT_ID` | the tenant of the created registration, or `auth_tenant_id` |
| `CA_AUTH_AUDIENCE` | the registration's client id and its `api://<client id>` URI, or `auth_audiences` |
| `CA_AUTH_AUTHORITY_HOST` | `auth_authority_host` (default `login.microsoftonline.com`) |
| `CA_AUTH_CLOCK_SKEW_SECONDS` | `auth_clock_skew_seconds` (default 60) |
| `CA_AUTH_REQUIRED_ROLES` | `auth_role_value` (default `Assessment.Read`) |
| `CA_AUTH_REQUIRED_SCOPES` | `auth_scope_value` (default `access_as_user`; must differ from `auth_role_value`) |
| `CA_AUTH_JWKS_URL` | not set |

The person who runs `terraform apply` needs the Azure roles they already need, plus the right to create applications
and assign app roles in Entra: the `Application Administrator` role is normally enough for a user (not tested here), and the provider's own
[authentication guide](https://registry.terraform.io/providers/hashicorp/azuread/latest/docs) lists the Microsoft Graph
permissions for a service principal. To use a registration that already exists, set `auth_create_app_registration =
false` with `auth_tenant_id` and `auth_audiences`; nothing is then created in Entra and the inputs are passed through.
`terraform.tfvars.example` shows both. `terraform plan` (PowerShell; reads your `az login` session and creates
nothing, and the all-zero digest is the usual plan-only placeholder):

```powershell
$sub = az account show --query id -o tsv; $env:TF_VAR_scope_ids = '["/subscriptions/' + $sub + '"]'; $env:TF_VAR_budget_start_date = (Get-Date).ToUniversalTime().ToString('yyyy-MM-01') + 'T00:00:00Z'; $env:TF_VAR_image_ref = 'docker.io/hybridcloudworks/img-ca-appliance-app@sha256:0000000000000000000000000000000000000000000000000000000000000000'; $env:TF_VAR_alert_emails = '["' + (az account show --query user.name -o tsv) + '"]'; $env:TF_VAR_auth_assigned_object_ids = '["' + (az ad signed-in-user show --query id -o tsv) + '"]'; $env:TF_VAR_auth_enabled = 'true'; terraform -chdir=infrastructure/terraform/appliance-azure plan
```

`alert_emails` is set here so the plan includes the budget. It is optional: the budget needs at least one notification
recipient, so with the default empty list the plan succeeds and simply creates no budget (`terraform output
budget_notifications` says so).

#### What is verified, and what is NOT verified

Verified on a developer machine, with no tenant, subscription or credential (the exact commands and results are in the
pull request that added this section):

| What | How |
|------|-----|
| Token checks: missing, malformed, expired, not yet valid, wrong audience, wrong issuer, wrong tenant, another tenant's token, unknown key id, `alg: none`, HS256 signed with the public key, tampered payload, missing role | `tests/unit/test_entra.py`, with a key pair generated at test time and a local key set |
| Every route except `GET /api/health` answers `401` without a token | `tests/security/test_auth_boundary.py` |
| The plan refuses an internet-reachable appliance without sign-in, accepts the two supported postures, rejects the override combined with `public_results`, and wires each `CA_AUTH_*` value | `terraform test` with mock providers (16 plan-only runs); `tests/security/test_terraform_auth_guard.py` (static checks on the HCL, including that no secret resource exists and that no value is both an app role and a scope, which the mock providers cannot see) |
| The HCL is formatted, valid, and the misconfiguration scan has no HIGH or CRITICAL finding | `terraform fmt -check -recursive`, `terraform validate`, `trivy config` |

**NOT verified** (nothing below has been run against a real tenant, and the first four need your tenant):

- That Microsoft Entra ID issues a token with the claims the code expects (`aud`, `iss`, `tid`, `scp`, `roles`) for this
  registration, and that the appliance accepts it. The tests use tokens signed by a key generated at test time.
- That the appliance can fetch the tenant's real signing keys from `login.microsoftonline.com` from a Container App.
- That the `azuread` resources apply cleanly (permissions, the identifier URI, the role assignment, the pre-authorized
  client) and that `app_role_assignment_required` behaves as described. `terraform test` only plans against mock
  providers; no `apply` has ever run.
- That the Azure CLI can obtain a token for the scope, which the runbook below does.
- That the deployed Container App starts with these settings. No image has been published yet.
- Sign-in for the website pane: it is not built, so with sign-in on the pane files also answer `401`.

#### Real-tenant verification runbook

Run this once, in a sandbox tenant and subscription, before trusting sign-in in a client deployment. It touches Entra
only (four objects), plus read-only calls to the sandbox subscription if you run the appliance on your machine. Nothing
here is run by CI or by an agent. The commands are PowerShell; the bash version follows. You need the Azure CLI, `uv`,
Terraform 1.9 or newer, and an account that can create applications in the sandbox tenant.

Every step below can be pasted into a PowerShell window you have just opened: a step that needs a value from an earlier
step works it out again on its first line. Two things a new window does not have are the folder and, for step 6, the
`TF_VAR_` values from step 1. A new window starts in your home folder, not in this repository, and `uv run` and
`terraform -chdir=infrastructure/...` both look for the repository in the current folder. So steps 1, 3 and 6 begin
from the folder you cloned this repository into (the one that holds `pyproject.toml`). To check you are in it,
`Test-Path pyproject.toml` should print `True`.

1. Sign in and create the Entra objects (owner step, sandbox only). The `-target` flags limit the apply to the Entra
   objects (Terraform will warn about targeting; that is expected here). It lets the Azure CLI request the scope and
   assigns the role to you, so only you can get a token:

   PowerShell splits an unquoted `-target=name.part` at the dot, so every `-target` in the PowerShell commands is in
   double quotes. Without the quotes Terraform answers `Too many command line arguments` and `Invalid target`.

```powershell
az login; $sub = az account show --query id -o tsv; $env:TF_VAR_environment = 'sandbox'; $env:TF_VAR_scope_ids = '["/subscriptions/' + $sub + '"]'; $env:TF_VAR_budget_start_date = (Get-Date).ToUniversalTime().ToString('yyyy-MM-01') + 'T00:00:00Z'; $env:TF_VAR_image_ref = 'docker.io/hybridcloudworks/img-ca-appliance-app@sha256:0000000000000000000000000000000000000000000000000000000000000000'; $env:TF_VAR_alert_emails = '["' + (az account show --query user.name -o tsv) + '"]'; $env:TF_VAR_auth_enabled = 'true'; $env:TF_VAR_auth_assigned_object_ids = '["' + (az ad signed-in-user show --query id -o tsv) + '"]'; $env:TF_VAR_auth_preauthorized_client_ids = '["04b07795-8ddb-461a-bbee-02f9e1bf7b46"]'
terraform -chdir=infrastructure/terraform/appliance-azure init -input=false -backend=false; terraform -chdir=infrastructure/terraform/appliance-azure apply "-target=azuread_service_principal.api" "-target=azuread_application_identifier_uri.api" "-target=azuread_app_role_assignment.assigned" "-target=azuread_application_pre_authorized.client"
```

   Check the plan lists only `azuread_*` objects, then type `yes`. `04b07795-8ddb-461a-bbee-02f9e1bf7b46` is the Azure
   CLI's public application id ([Microsoft Learn](https://learn.microsoft.com/azure/azure-sovereign-clouds/private/foundry-local/how-to-configure-authentication#step-4-authorize-azure-cli)); never pre-authorize it outside a sandbox.
   The state is a local `terraform.tfstate` file (git-ignored).

2. Read back what Entra now holds, and check the role and scope exist:

```powershell
$tenant = az account show --query tenantId -o tsv; $app = az ad app list --display-name 'Cloud Assessor appliance (sandbox)' --query '[0].appId' -o tsv; az ad app show --id $app --query '{appRoles: appRoles[].value, scopes: api.oauth2PermissionScopes[].value, tokenVersion: api.requestedAccessTokenVersion, identifierUris: identifierUris}' -o json
```

   Expect `appRoles` to be `["Assessment.Read"]` and `scopes` to be `["access_as_user"]` (two different names), `tokenVersion` `2`,
   and `identifierUris` `["api://<the app id>"]`.

3. Start the appliance on your machine with the same settings Terraform gives the Container App (a second PowerShell
   window; it reads your `az login` session for the sandbox subscription, read-only). Leave it running.

   Open the second window **in the repository's folder**. A new window starts in your home folder, where `uv run`
   finds no project and stops with `No module named cloud_assessor_appliance` (after the warning
   "`--extra azure` has no effect when used outside of a project"). The easiest way is to open it from the first
   window, which is already in the right folder (it opens the same kind of PowerShell as the one you are in):

```powershell
Start-Process (Get-Process -Id $PID).Path -WorkingDirectory (Get-Location).Path
```

   Or open any PowerShell window and `cd` into the folder you cloned the repository into. Either way, in the new window
   `Test-Path pyproject.toml` should print `True` before you go on. Then paste:

```powershell
$tenant = az account show --query tenantId -o tsv; $app = az ad app list --display-name 'Cloud Assessor appliance (sandbox)' --query '[0].appId' -o tsv; $env:CA_SCOPES = '/subscriptions/' + (az account show --query id -o tsv); $env:CA_AUTH_ENABLED = 'true'; $env:CA_AUTH_TENANT_ID = $tenant; $env:CA_AUTH_AUDIENCE = "$app api://$app"; $env:CA_AUTH_AUTHORITY_HOST = 'login.microsoftonline.com'; $env:PORT = '8080'; uv run --extra azure python -m cloud_assessor_appliance
```

   The first `uv run --extra azure ...` installs the Azure packages into a `.venv` folder in the repository before it
   starts, so it can sit for a minute with nothing printed. Later runs start in a couple of seconds.

   **What success looks like.** The appliance prints no "listening on port" line (its web server is set to log
   warnings only, so that nothing but counts and flags ever reaches the log). The sign that it is up is its own log
   lines, one JSON object each, and a prompt that does not come back:

   ```text
   {"ts":...,"event":"startup","catalogCriteria":25,"scopes":1,"turnstileRequired":false,"publicResults":false,"authEnabled":true,"costEnabled":true}
   {"ts":...,"event":"refresh_started","scopes":1}
   ```

   `"authEnabled":true` is the proof that sign-in is on. When the first read of your subscription finishes, a third
   line, `"event":"refresh_completed"`, says it worked (not yet seen against a real subscription);
   `"event":"refresh_failed"` there means it could not read Azure (check that `az login` still works), which does
   not stop the sign-in checks in step 4. If the window instead prints
   `{"event": "startup_refused", "reason": ...}` and the prompt returns, a setting is missing or wrong, and the reason
   names it (for example `CA_AUTH_TENANT_ID must be set to the tenant (directory) id, a GUID`). If it ends with
   `error while attempting to bind on address ('0.0.0.0', 8080)`, something else is already listening on port 8080 (often an earlier run of this step that is still open): close that window, or set
   `$env:PORT = '8081'` in this window and use `http://127.0.0.1:8081` for `$base` in step 4.

   To test a deployed appliance instead, skip this step and set `$base` in step 4 to `https://` plus
   `terraform output -raw app_fqdn`.

4. Sign in for the scope, then call it. Back in the first window (the token stays in a variable; never paste it anywhere).
   First, sign in once with the scope named, so the Azure CLI has your consent for it before it asks Entra for a token
   (without this, `az account get-access-token --scope ...` can stop with a message that the sign-in needs a new
   scope, or a consent error). The command opens your browser once: choose the sandbox account, and if the terminal
   then asks you to select a subscription, press Enter to keep the default (this check does not depend on it). When it
   is done it returns to the prompt:

```powershell
$tenant = az account show --query tenantId -o tsv; $app = az ad app list --display-name 'Cloud Assessor appliance (sandbox)' --query '[0].appId' -o tsv; az login --tenant $tenant --scope "api://$app/access_as_user"
```

   Then the calls. Paste this as a second block, so a sign-in problem shows up before any call:

```powershell
$base = 'http://127.0.0.1:8080'; $tenant = az account show --query tenantId -o tsv; $app = az ad app list --display-name 'Cloud Assessor appliance (sandbox)' --query '[0].appId' -o tsv
$good = az account get-access-token --tenant $tenant --scope "api://$app/access_as_user" --query accessToken -o tsv
$wrong = az account get-access-token --tenant $tenant --resource-type arm --query accessToken -o tsv
"1 health, no token      (expect 200): " + (curl.exe -s -o NUL -w '%{http_code}' "$base/api/health")
"2 catalog, no token     (expect 401): " + (curl.exe -s -o NUL -w '%{http_code}' "$base/api/catalog")
"3 catalog, junk token   (expect 401): " + (curl.exe -s -o NUL -w '%{http_code}' -H 'Authorization: Bearer not-a-token' "$base/api/catalog")
"4 catalog, wrong audience (expect 401): " + (curl.exe -s -o NUL -w '%{http_code}' -H "Authorization: Bearer $wrong" "$base/api/catalog")
"5 catalog, valid token  (expect 200): " + (curl.exe -s -o NUL -w '%{http_code}' -H "Authorization: Bearer $good" "$base/api/catalog")
"6 results, valid token  (expect 403 results_not_public, or 503 no_snapshot in the first minute): " + (curl.exe -s -H "Authorization: Bearer $good" "$base/api/assessments/current")
"7 results, no token     (expect 401): " + (curl.exe -s -o NUL -w '%{http_code}' "$base/api/assessments/current")
```

   `$good` is a signed-in user's token, so you ask for the delegated scope by name: `access_as_user`. Entra puts it in the
   token's `scp` claim, and because step 1 also assigned the app role to you, the token's `roles` claim should list
   `Assessment.Read` as well ([claims reference](https://learn.microsoft.com/entra/identity-platform/access-token-claims-reference)). The appliance accepts a token with either one, so
   line 5 passes on the scope alone. Do not ask for `api://$app/Assessment.Read` here: that name is the app role, not a
   scope, so Entra should refuse a user-token request for it with an invalid-scope error (not tried; the expected
   behaviour, not a verified one).

   Line 4 uses an Azure Resource Manager token, which is valid but for a different audience. If `az` still says the
   sign-in needs a new scope, run the `az login --scope ...` command it prints, then repeat. If line 5 prints `401`
   instead of `200`, check that `$good` is a long text (`$good.Length` is well over 1000; never print the token itself).
   Lines 1, 2, 3 and 7 use no real token, so the appliance answers them alone; lines 4, 5 and 6 need the tokens above.
   The first `401` should also carry
   `WWW-Authenticate: Bearer` (add `-i` to a call to see headers). A `403 results_not_public` on line 6 is correct and is
   the proof the token passed: the separate `CA_PUBLIC_RESULTS` gate is still closed.

5. Optional, expiry: keep `$good` for the rest of its life (about an hour; the exact time is the `exp` claim), then repeat
   line 5. Expect `401`. A stricter alternative is the unit tests, which cover expiry with a fixed clock.

6. Clean up. Stop the appliance with Ctrl+C in the second window, then remove the Entra objects (they are the only
   things in the state) and the variables. Run this in the first window, the one that ran step 1: Terraform needs the
   `TF_VAR_` values that step set there, and the state file sits in the repository's folder:

```powershell
terraform -chdir=infrastructure/terraform/appliance-azure destroy "-target=azuread_application.api"; Remove-Item Env:TF_VAR_*
```

   Type `yes` after checking the plan lists only the `azuread_*` objects.

The same in bash (Git Bash or Linux; needs `curl`, which Git Bash has). Steps 1, 3, 4 and 6 in one block, run from the
folder you cloned the repository into; step 2 is the PowerShell one with `$x = ...` written as `x=$(...)`:

```bash
sub=$(az account show --query id -o tsv)
export TF_VAR_environment=sandbox TF_VAR_auth_enabled=true TF_VAR_scope_ids="[\"/subscriptions/$sub\"]" \
  TF_VAR_budget_start_date="$(date -u +%Y-%m-01)T00:00:00Z" \
  TF_VAR_image_ref=docker.io/hybridcloudworks/img-ca-appliance-app@sha256:0000000000000000000000000000000000000000000000000000000000000000 \
  TF_VAR_alert_emails="[\"$(az account show --query user.name -o tsv)\"]" \
  TF_VAR_auth_assigned_object_ids="[\"$(az ad signed-in-user show --query id -o tsv)\"]" \
  TF_VAR_auth_preauthorized_client_ids='["04b07795-8ddb-461a-bbee-02f9e1bf7b46"]'
terraform -chdir=infrastructure/terraform/appliance-azure init -input=false -backend=false
terraform -chdir=infrastructure/terraform/appliance-azure apply -target=azuread_service_principal.api -target=azuread_application_identifier_uri.api -target=azuread_app_role_assignment.assigned -target=azuread_application_pre_authorized.client
tenant=$(az account show --query tenantId -o tsv); app=$(az ad app list --display-name 'Cloud Assessor appliance (sandbox)' --query '[0].appId' -o tsv)
CA_SCOPES="/subscriptions/$sub" CA_AUTH_ENABLED=true CA_AUTH_TENANT_ID=$tenant CA_AUTH_AUDIENCE="$app api://$app" CA_AUTH_AUTHORITY_HOST=login.microsoftonline.com PORT=8080 uv run --extra azure python -m cloud_assessor_appliance &
base=http://127.0.0.1:8080
az login --tenant "$tenant" --scope "api://$app/access_as_user"
good=$(az account get-access-token --tenant "$tenant" --scope "api://$app/access_as_user" --query accessToken -o tsv)
wrong=$(az account get-access-token --tenant "$tenant" --resource-type arm --query accessToken -o tsv)
for pair in "no-token:" "junk-token:not-a-token" "wrong-audience:$wrong" "valid-token:$good"; do
  name=${pair%%:*}; tok=${pair#*:}; printf "catalog, $name: "
  if [ -z "$tok" ]; then curl -s -o /dev/null -w '%{http_code}\n' "$base/api/catalog"
  else curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $tok" "$base/api/catalog"; fi
done
curl -s -o /dev/null -w 'health: %{http_code}\n' "$base/api/health"
curl -s -H "Authorization: Bearer $good" "$base/api/assessments/current"; echo
kill %1; terraform -chdir=infrastructure/terraform/appliance-azure destroy -target=azuread_application.api
```

   Expected, in order: `401`, `401`, `401`, `200`, `health: 200`, then `403 results_not_public` (or `503 no_snapshot` in the
   first minute).

If any line differs, do not turn sign-in on for a client. Open an issue with the line number and the status code only;
never paste a token, a tenant id or an application id.

#### Known gaps

- The `azuread` resources have never been applied; see the NOT verified list. The first real-tenant `plan` found that the
  app role and the scope shared the value `Assessment.Read` (the provider refuses that); they now differ and a static
  test guards it, but the runbook has not been completed since, so the next real-tenant error is still possible.
- The budget is created only when `alert_emails` has an address (ticket
  [#60](https://github.com/saulpatinojr/HCW-CloudAssessor_App/issues/60)): `azurerm_consumption_budget_resource_group`
  needs a recipient on every notification, and the mock-provider tests showed that the default empty list made the plan
  fail. Verified with mock providers only (`terraform test`); a plan or apply against a real subscription has not been run.
- The pane does not sign users in yet (T-032 follow-up), so a browser cannot use the pane of a sign-in-protected
  deployment.

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
