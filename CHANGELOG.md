# Changelog

All notable completed changes to this repository are recorded here. This file contains
completed work only — planned work lives in [TODO.md](TODO.md) and blocked decisions live
in [REVIEW.md](REVIEW.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Conventions (checked by `scripts/check-release-version.py`)

- **One version for the whole repository.** The engine wheel, the appliance, `/api/health` and the container image share a
  plain `X.Y.Z`, and one `vX.Y.Z` tag releases all of them. The policy, the places that name the version and the release
  steps are in [README.md](README.md), section "Releasing and versioning".
- **Work lands under `## [Unreleased]`**, in the same pull request as the change. Use the Keep a Changelog headings
  (`### Added`, `### Changed`, `### Fixed`, `### Security`, `### Removed`).
- **A release is a pull request.** It changes the version in the four places and `uv.lock`, moves everything under
  `## [Unreleased]` into a new `## [X.Y.Z] - YYYY-MM-DD` section (the exact heading format; the section is the release
  notes), and leaves `## [Unreleased]` with no entries. The release workflows refuse a tag while the section is missing,
  undated or empty, or while `[Unreleased]` still has entries.
- Headings that do not look like `## [X.Y.Z] - date` (for example the repository initialization entry) are history and are
  ignored by the check.

## [Unreleased]

### Security
- **Terraform for caller authentication, and a plan that refuses an unauthenticated public appliance (ticket CA-3, closes the Terraform half of T-032).** `infrastructure/terraform/appliance-azure` now has `external_enabled` as a variable (default `true`, as before) and a `precondition` on the Container App: `terraform plan` fails with "Refusing to plan an externally reachable appliance without caller authentication" unless `auth_enabled = true`, or `external_enabled = false` (private ingress), or the deliberately named override `dangerously_allow_unauthenticated_external_ingress = true` is set (an owner decision to record in `REVIEW.md`; `terraform output caller_authentication` then starts with `NONE`). A second precondition mirrors the appliance's own startup refusal: `public_results = true` needs `auth_enabled = true`, and the override does not relax it. With `auth_enabled = true` the Container App receives every `CA_AUTH_*` setting the code reads (all but `CA_AUTH_JWKS_URL`, which is left to the code's default), and a new `auth.tf` creates the Entra registration with the `azuread` provider (`~> 3.0`, locked in `.terraform.lock.hcl` next to `azurerm` 4.81.0): a single-tenant application with v2 access tokens, an `Assessment.Read` app role and delegated scope, the `api://<client id>` identifier URI, and a service principal with `app_role_assignment_required = true` (only assigned users, groups or managed identities, `auth_assigned_object_ids`, can obtain a token). No client secret, certificate or password exists anywhere in the configuration or the state; an existing registration can be described instead (`auth_create_app_registration = false`, `auth_tenant_id`, `auth_audiences`). New outputs: `caller_authentication`, `appliance_auth_settings`, `auth_application_client_id`, `auth_scope`. Tests: `infrastructure/terraform/appliance-azure/tests/caller_authentication.tftest.hcl` (15 plan-only runs with mock providers; CI runs them as a new step of the `terraform` job) and `tests/security/test_terraform_auth_guard.py` (static checks). `README.md` explains the supported exposure, how to turn sign-in on, what is verified and what is not, and a copy-pasteable real-tenant verification runbook (the repository's documentation model has no `VALIDATION.md`; the section is in the README). **Not verified: anything against a real Entra tenant; no `apply` has ever run, and the runbook has not been executed.** Plans that omitted these inputs before now fail by design: add `auth_enabled = true` (README, Sign-in). Found on the way and not fixed: `alert_emails = []` (the default) makes a plan fail on the real `azurerm` provider because the budget needs at least one notification (README, Known gaps).
- **Microsoft Entra ID sign-in for the appliance (T-032; owner decision R-009 option b, 2026-10-24).** With `CA_AUTH_ENABLED=true` every route except `GET /api/health` needs `Authorization: Bearer <access token>`, otherwise `401 unauthorized` with `WWW-Authenticate: Bearer`. The token must have an RS256 signature from the tenant's published keys (`alg` none, HS*, other algorithms and an unknown `kid` are refused), a valid `iss` (v2.0 or v1.0 form of the configured tenant), a configured `aud`, `exp` and `nbf` (both required, 60 seconds of clock skew by default, at most 300), `tid` equal to the configured tenant, and an app role or scope named in `CA_AUTH_REQUIRED_ROLES` / `CA_AUTH_REQUIRED_SCOPES` (default `Assessment.Read`). New settings, all in `.env.example`: `CA_AUTH_ENABLED`, `CA_AUTH_TENANT_ID`, `CA_AUTH_AUDIENCE`, `CA_AUTH_AUTHORITY_HOST`, `CA_AUTH_JWKS_URL`, `CA_AUTH_CLOCK_SKEW_SECONDS`, `CA_AUTH_REQUIRED_ROLES`, `CA_AUTH_REQUIRED_SCOPES`. Off by default, so a deployment that does not set them behaves as before. The `CA_PUBLIC_RESULTS` gate is unchanged and stays off by default: a valid token with the gate off still gets `403 results_not_public`. New startup refusals: sign-in enabled without a tenant, audience or authority host, and `CA_PUBLIC_RESULTS=true` without sign-in. Logs carry a status and a numeric reason code only, never a token or a claim. Tested with a key pair generated at test time and a local key set; **not tested against a real Entra tenant**. Appliance code only: `packages/cloud-assessor-core` and the lab edition are untouched (no entry needed in the lab edition's `docs/whats-new-upstream.md`). Terraform plumbing (`CA_AUTH_*` app settings and an `azuread_application`) follows in the next entry; `REVIEW.md` R-006 (labelling results "client confidential") is still open.

### Changed
- **`repository-admin.yml` can no longer lower the live rules by accident** (2026-10-25). Its `protect-main` and `protect-release-tags` tasks replace the whole ruleset with a list kept in the file, and that list was out of date: the live `Protect main` ruleset now needs one approving review, a code-owner review, approval of the last push and resolved review threads, and the live `Protect release tags` ruleset also blocks creating a tag and lets repository admins bypass it, while the file still said zero reviews and none of the rest. Running either task with "apply" would have switched all of that off without a word. Now both tasks read the live ruleset first and print what the update would remove or weaken and what it would add or change. With "apply" ticked they stop with an error, and change nothing, if the update would remove a rule, a required check, a bypass actor or a tag pattern, lower a number, or switch a protection off, unless the new "allow_weakening" box is ticked as well (it is off by default, and so is "apply"). A broken `REQUIRED_CHECKS` list (empty, not a list, a repeated or empty name) stops the task before anything is sent. The two payloads in the file now equal the live rulesets read on 2026-10-25 (the same seven required checks as before), so an apply changes nothing today. New `tests/unit/test_repository_admin_required_checks.py` (51 tests): every required check must be a real job name in `ci.yml` or `security.yml` and equal an explicit list, the payloads must equal the live values, and the real step runs against a stand-in `gh` that answers from sample rulesets and records every call, including 16 one-setting-at-a-time weakenings that must each be refused. If you change the live ruleset, change `REQUIRED_CHECKS` and that test's lists in the same pull request. **Not verified: a real `protect-main` or `protect-release-tags` run (only the stand-in `gh` was used); after merging, run `show-plan` and `protect-main` without "apply" and check that both print "removes and weakens nothing".**
- **CodeRabbit can now approve pull requests** (2026-10-25). The new `.coderabbit.yaml` turns on `request_changes_workflow` and keeps `allow_author_approval` off, because the `Protect main` ruleset now requires one approving review (decision B1, https://github.com/saulpatinojr/HCW-HybridCloudWorks/issues/1373). CodeRabbit asks for changes while a finding is open and approves the head once every thread is resolved.
- **Version hygiene (ticket #33, CA-10).** The appliance moves from `0.1.0` to `0.2.1`, the version the engine and the
  `v0.2.1` tag already had, so `/api/health` (`version`), the `x-addon-version` header, `pyproject.toml`, `uv.lock` and the
  engine now say the same thing. Policy: one version for the engine, the appliance and the image; one tag publishes all
  three; the version is raised only in a release pull request (README "Releasing and versioning", an owner-confirmable
  decision). `release.yml` is now two jobs (`check` with read-only permissions, then `create` with write permission); its
  release notes come from the changelog section for the tag and a missing section fails instead of falling back to a
  generic line. `publish-core.yml` and `publish-images.yml` run the version guard before they build, attest, attach or
  push anything; `publish-core.yml` builds with `--no-create-gitignore` so only the wheel and the sdist are in `dist/`.
  The three workflows now check out the full history so the tagged commit can be compared with `main`. `uv.lock` changes
  only the appliance's version line; both `requirements*.lock.txt` exports are unchanged.
- **Community files and issue forms (ticket #32, CA-9).** `.github/SECURITY.md` now routes reports only through GitHub
  private vulnerability reporting and no longer names an e-mail address or an acknowledgement time, because neither
  could be verified from the repository (restore them in a pull request if the owner confirms them).
  `scripts/check-docs-governance.py` allow-lists `.github/CONTRIBUTING.md` and `.github/CODE_OF_CONDUCT.md`, and its
  fallback file walk now reports paths with `/` on every platform.
- **Appliance image name follows the owner's convention `img-<short name>-<job>-<type>` (2026-10-25):** `docker.io/hybridcloudworks/img-ca-appliance-app`. This replaces `hcw-cloudassessor` from the entry below. The image has never been published, so no image moves and nothing needs copying. The tag is now the full release tag (`v0.2.1`, not `0.2.1`); the `sha-` tag is unchanged. `publish-images.yml`, the Terraform `image_ref` description, validation pattern and example, the Dockerfile comment, the README and `tests/unit/test_workflows.py` follow. Terraform still accepts only an exact `@sha256:` digest. The Docker OIDC connection must allow this repository to push to `img-ca-appliance-app` before the next `v*` tag. The lab edition keeps its own image (`img-ca-lab-addon`) and is not affected.
- **Appliance image renamed** from `docker.io/hybridcloudworks/hcw-cloud-assessor-appliance` to `docker.io/hybridcloudworks/hcw-cloudassessor` (owner naming convention, 2026-10-25). The appliance image has not been published yet, so no image moves and nothing needs copying. `publish-images.yml` (`IMAGE` and the image title label), the Terraform `image_ref` description, validation pattern and example, the Dockerfile comment, the README and `tests/unit/test_workflows.py` follow. Terraform still accepts only an exact `@sha256:` digest. Local `:dev` build tags are unchanged. The Docker OIDC connection must allow this repository to push to the new Docker Hub repository before the next `v*` tag. The lab edition (`HCW-CloudAssessor_AddOn`) keeps its own image name and is not affected, so it needs no `docs/whats-new-upstream.md` entry.
- `pyproject.toml`: `pyjwt[crypto]==2.15.1` is now declared in the appliance-only `azure` extra. It was already locked as a dependency of `msal`; `uv.lock` and `requirements-azure.lock.txt` change only in how they record it, and `requirements.lock.txt` (the default set) is unchanged. `tests/packaging/test_lockfile.py` now lists `pyjwt` as a fourth member of that extra.
- `/api/health` now says when collection is not working (ticket #35, application part). Two new fields: `status` (`ok` or `degraded`) and `degradedReason` (`null`, `no_snapshot` before the first successful run, or the error code of the latest failed run: `collector_error`, `timeout` or `internal_error`). Every existing field is unchanged, and so are the HTTP status (still 200) and `ok: true`, because the Container Apps liveness and readiness probes, the Docker `HEALTHCHECK` and the pane all read them; a 503 would restart a replica that is only waiting on Azure. The body carries error codes only, never a message, subscription or resource identifier (tested). Owner decision recorded in the pull request: whether degraded should ever return 503 or get a separate readiness route. Appliance code only; it does not reach the lab edition. Still open on #35: the repository description (needs the owner).
- `.github/dependabot.yml` no longer proposes updates to the `python` base image. It is a pair with `infrastructure/docker/versions.env` (image and digest) that `scripts/check-versions.sh` enforces, so every Dependabot image pull request failed `lint` and `test` by design (#42, a 3.15.0 image, also conflicts with `requires-python >=3.14.6,<3.15`). The image is moved by hand, in one change, with its digest.
- Dependencies: `pydantic` 2.14.0 → 2.14.1 (the exact pin in `pyproject.toml`), with `pydantic-core` 2.50.0 → 2.50.1 and `starlette` 1.7.0 → 1.9.0 in `uv.lock` and both `requirements*.lock.txt` files. This replaces the open Dependabot pull requests #19, #20 and #22: #19 (`pydantic-core` alone) could not resolve because pydantic pins its core to one exact version. `.github/dependabot.yml` now groups `pydantic` and `pydantic-core` so they arrive in one pull request. The engine package's `pydantic>=2.14,<3` range is unchanged, so nothing reaches the lab edition. Verified: `make lint`, `make test` (195 passed, 1 skipped, coverage 95.83 %) and `make test-security` (16 passed).
- `.github/dependabot.yml`: the Python entry now uses the `uv` ecosystem (ticket #29). The old `pip` entry edited only the two `requirements*.lock.txt` files and never `uv.lock`, so every Dependabot Python pull request failed `uv lock --check`. The engine package is a `uv` workspace member, so its separate `pip` entry is removed (the root entry covers it); the `azure-sdk`, `dev` and `pydantic` groups and the `python` image ignore are unchanged. Dependabot does not regenerate the requirements exports, so run `make lock` on a Dependabot Python pull request. Not yet verified: how Dependabot behaves on its next weekly run.
- `.pre-commit-config.yaml` (ticket #35, pre-commit part only): `ruff-pre-commit` moves from v0.17.0 to v0.17.1 to match `ruff==0.17.1` in `pyproject.toml`, and the gitleaks hook is set to v8.24.3, the release `security.yml` runs in CI (the `[VERIFY]` marker is gone; the tag exists upstream, checked 2026-10-24). The `/api/health` degraded state and the repository description are not part of this change.


### Fixed
- **`terraform plan` no longer fails with the default `alert_emails = []` (ticket [#60](https://github.com/saulpatinojr/HCW-CloudAssessor_App/issues/60)).** `azurerm_consumption_budget_resource_group` requires at least one notification and every notification needs a recipient, so the documented default ("no notifications") could not be planned. The budget now has `count = length(var.alert_emails) > 0 ? 1 : 0`: with at least one address it is created exactly as before (80 and 100 percent, actual spend); with the default empty list nothing is created and the plan succeeds. Chosen over a required variable because a sandbox or a test plan should not need an address, and over a default recipient such as `contact_roles` because a budget that notifies an unchosen audience is a worse guard than an explicit opt-out. `alert_emails` entries are now validated (an email address, no blank entry, no repeat), and a new output `budget_notifications` states in words whether a budget exists and for how many recipients. New `infrastructure/terraform/appliance-azure/tests/budget_notifications.tftest.hcl` (7 plan-only runs with mock providers: empty, unset, one recipient, several, and the three refusals; CI runs it in the `terraform` job with the existing tests) and a static test in `tests/security/test_terraform_auth_guard.py`; `README.md` and `terraform.tfvars.example` state the behaviour. Also: the header comment of `publish-core.yml` named the non-existent `v0.1.0` wheel and now shows `vX.Y.Z` (ticket [#31](https://github.com/saulpatinojr/HCW-CloudAssessor_App/issues/31)). Appliance Terraform and a comment only: the engine and the lab edition are untouched (no entry needed in the lab edition's `docs/whats-new-upstream.md`). **Not verified: a plan or apply against a real subscription; the failure and the fix were shown with mock providers only.**
- `uv.lock` pinned `fastapi` 0.156.8 while `pyproject.toml` and both `requirements*.lock.txt` already said 0.157.0, because the Dependabot bump (#47) edited only the two requirements files. `uv lock --check` (and so `make lint` and CI) failed on `main`. `uv.lock` is regenerated with `make lock`; nothing else changes. The `uv` ecosystem entry added to `.github/dependabot.yml` in #48 is what stops this recurring; the next Dependabot Python pull request will show whether it does.
- `scripts/check-lockfiles.sh` (CI and `make lint`) now fails with a clear message when `uv.lock` is out of date with `pyproject.toml` (`uv lock --check`), and exports with `--locked` so it can no longer silently rewrite `uv.lock` before comparing (ticket #27). New test `test_check_lockfiles_fails_on_a_stale_uv_lock_without_rewriting_it`; it fails against the old script and passes against the new one. `ci.yml` still installs with `uv sync --frozen`; changing that to `--locked` is proposed in ticket #24 and not done here.

### Security
- `release.yml` and `publish-images.yml`: the release tag, image digest and image version are now passed to their shell scripts through `env:` and quoted, instead of being pasted into the script text with `${{ }}` (ticket #34). No behaviour change; it removes a script-injection risk if a tag name were ever unusual. `tests/unit/test_workflows.py` (SHA-pinned actions, `ubuntu-26.04`, read-only permissions) still passes.
- `.gitleaks.toml` (ticket #30): a second, narrow allow-list pattern for SHA-pinned action references quoted in prose. The scheduled full-history scan reported nine `sourcegraph-access-token` findings, all in one old commit (`ed4ead3`, `REFACTOR_APP.md` lines 299 and 315), all of the form `owner/action@<40-hex> # vN`; the existing pattern needed a `uses:` prefix. The new pattern needs the `@<40-hex>` and the `# vN` comment, so a bare 40-hex string is still reported (checked with a negative control). Reproduced with gitleaks 8.24.3, the CI version: 9 findings before, none after. A real run of the `security` workflow is still needed to confirm CI.

### Added
- **Release version guard (ticket #33, CA-10).** `scripts/check-release-version.py` (standard library only) fails when
  the engine's and the appliance's `pyproject.toml`, their two `__version__` constants and their two `uv.lock` entries do
  not name the same plain `X.Y.Z`. With `--tag` it also requires the exact tag `vX.Y.Z`, a dated non-empty
  `## [X.Y.Z] - YYYY-MM-DD` changelog section, an empty `[Unreleased]`, and (`--ancestor-of origin/main`) a tagged commit
  that is on `main`; `--dist` checks the built files and `--notes-out` writes the release notes. Run by `ci.yml` (`lint`),
  `make lint` and the three tag workflows. `tests/unit/test_release_guard.py` covers it, including that `/api/health`
  reports the same version as `pyproject.toml`.
- **`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and YAML issue forms (ticket #32, CA-9).** Both documents live under `.github/`.
  The markdown issue templates are replaced by forms with required fields and fixed dropdown values: `bug_report.yml`,
  `feature_request.yml` and `work_item.yml` (the shape the tracked tickets use; its dropdowns use the repository's
  priority, severity and workstream label values). `config.yml` keeps blank issues off. The README links to all of them
  ("Contributing and reporting"). `tests/unit/test_community_files.py` checks the forms and the files.
- **`security.yml` can be started by hand (ticket #30, CA-7).** The workflow now also has a `workflow_dispatch` trigger with
  no inputs, so the gitleaks scan can be run on demand instead of only on Mondays. Nothing else about the workflow
  changed; the dependency review job still runs only for pull requests. `tests/unit/test_workflows.py` pins this.
- **Self-merging pull request, ready for the workflows that will need it.** The composite action `.github/actions/self-merging-pr` (the same file is in every HCW application repository) turns the files a job changed into one pull request on a fixed branch, opened with a short-lived GitHub App token scoped to this repository (Contents and Pull requests write), because `main` is protected by a ruleset that requires a pull request and a pull request opened with `GITHUB_TOKEN` neither is allowed here nor starts the required checks. It can turn on squash auto-merge and wait for the merge. `rehearse-self-merging-pr.yml` (Run workflow) rehearses it against a harmless file: by default it opens the pull request, turns on auto-merge, confirms the required checks start, and closes the pull request again; with `merge` ticked it really merges `.github/rehearsal.txt` once as the end-to-end proof. The credential is the repository-admin App (HCW Portfolio Admin) held by the `admin-ops` environment, an interim choice; `dependabot.yml` now also reads `.github/actions/*` so the action's pins stay current. **[VERIFY]** by running the rehearsal; it has not run yet.
- `.github/workflows/repository-admin.yml`: an owner-approved, manually started workflow (dry run unless "apply" is ticked, every run approved in the `admin-ops` environment, short-lived GitHub App token limited to this repository). Tasks: `show-plan`, `protect-main` (ruleset requiring a pull request and the lint, test, boundary, catalog-check, secret-scan, image and terraform checks; `pip-audit` is added once it is stable), `protect-release-tags`, `delete-merged-branches`. `tests/unit/test_workflows.py` lists it.
- `CLAUDE.md`: the working agreement for AI coding agents (commands, never-weaken list, documentation model, and a plain-language communication section for the owner). `scripts/check-docs-governance.py` now allow-lists it, and its test asserts a root `CLAUDE.md` passes while other stray markdown still fails.

### Changed
- **Security: `certifi` 2026.7.22 to 2026.10.23 (advisory PYSEC-2026-4320, fixed in 2026.10.19).** Only the Azure runtime lock carried it. `uv.lock` was also stale against `pyproject.toml` (`fastapi` 0.143.0 and `ruff` 0.17.0 against the pinned 0.143.3 and 0.17.1), so the same `uv lock --upgrade-package certifi` brought those in line; no other version moved. `requirements-azure.lock.txt` was re-exported with the commands in the `Makefile`. Verified: `uv lock --check`, `scripts/check-lockfiles.sh`, `pip-audit --strict` on both requirements locks (no known vulnerabilities), ruff, and 194 tests passing.
- Python base image `python:3.14.8-slim-trixie` by digest in `infrastructure/docker/versions.env` and every `FROM` of the Dockerfile together (Dependabot #12 moved only the Dockerfile, which `scripts/check-versions.sh` rejects as drift).
- **Documents brought in line with reality (tickets #31 and #33, docs only).** `README.md` now names the two releases that exist (`v0.2.0`, 2026-10-12, and `v0.2.1`, 2026-10-18), says that no `v0.1.0` tag exists here (`0.1.0` is the seed's version and the appliance's), gives an install command that works (the release wheel, tested with `pip` on Python 3.14; the old `git+https` pin at `@v0.1.0` pointed at a tag that does not exist), and says the lab edition has not adopted a release yet. `REVIEW.md` R-003 now states the verified facts (an MIT `LICENSE` is in place, the repository is public) and leaves the license and visibility decision with the owner. Two `TODO.md` notes that called the repository private are corrected. `CLAUDE.md` gains the rule to record changes that reach the lab edition in its `docs/whats-new-upstream.md`. This file now groups the old `[Unreleased]` pile under the release each entry shipped in (nothing was removed or reworded).

## [0.2.1] - 2026-10-18

### Changed
- **Core 0.2.1: pydantic is a range, not an exact pin (#15).** `packages/cloud-assessor-core/pyproject.toml` declares
  `pydantic>=2.14,<3` instead of `pydantic==2.14.0`, the same range the AddOn's seed adopted in
  `HCW-CloudAssessor_AddOn` #17. The engine is a library: an exact pin in the wheel and another in the app that
  installs it can only move in lockstep, so a Dependabot bump of either could never resolve. The appliance keeps its
  exact `pydantic==2.14.0` and its hash-locked `uv.lock`, so the resolved set is unchanged (`uv.lock` records only the
  new specifier and the version; both `requirements*.lock.txt` exports are identical). `__version__` is `0.2.1`; the
  release `v0.2.1` attaches `cloud_assessor_core-0.2.1-py3-none-any.whl` for the AddOn to adopt. The packaging and
  boundary tests now assert the range (`Requires-Dist: pydantic<3,>=2.14`) and match any specifier operator in the
  core manifest rather than `==` alone.

## [0.2.0] - 2026-10-12

First release tag. Everything below, down to the repository initialization entry, shipped in it.

### Changed
- README: badges (ci, security, release, Python, licence, lab edition) and a "new here?" opener in plain words that says what the product does and where the free lab edition will appear.
- `publish-core.yml`: the header names the contract the AddOn actually uses, the release wheel pinned by URL and sha256 (its `core-update.yml` was changed on 2026-10-11 because a `git+https` pin cannot be verified by its image's `pip install --require-hashes`). Comment only.

### Added
- **Engine adopted (change set A).** `packages/cloud-assessor-core` copied verbatim from `HCW-CloudAssessor_AddOn`
  `main` (commit `d552c6c`, the AddOn's 0.1.0 seed; `git diff --no-index` empty at adoption) with its unit tests,
  `catalog/{criteria,schema,scoring}.json`, `scripts/check-catalog.py` and the fictional `samples/`. From this commit the
  engine is owned here: changes are made here, released as `v*` tags, and adopted downstream through the AddOn's
  `core-update` workflow (ADR-0001, ADR-0028, recorded in the AddOn repository until the wiki exists).
- **Core 0.2.0, catalog 1.1.0 (change set D).** Additive `CostEvidence` and `BudgetEvidence` models, the
  `cost-evidence` evaluator kind (`budgets-present`, `anomaly-alerts-present`, `untagged-share`), and
  `evaluate(resources, catalog, *, evidence=None)`. Evidence gating: without evidence a `cost-evidence` check is skipped
  and the criterion is judged from the export exactly as before (the lab edition's pinned sample results are
  unchanged); with evidence Cost Management supersedes the export-side proxy. `CA-FIN-002`, `CA-FIN-003` and
  `CA-FIN-007` gain the second check with `anyPass`. `Assessment` gains optional `edition` and `scope` (count plus
  hashed subscription ids); `MODEL_VERSION` stays 1 because `Resource` is unchanged. `redaction.ALLOWED_WORDS` gains the
  appliance's event and code names. The package README is unchanged and allow-listed by the governance check because
  the wheel metadata requires it.
- **Skeleton (change set B, T-001, T-013).** uv workspace (`pyproject.toml` with the `azure` extra as the only place a
  cloud SDK is named), `uv.lock`, hash-pinned `requirements.lock.txt` (14 packages, none Azure) and
  `requirements-azure.lock.txt` (33 packages) with `scripts/check-lockfiles.sh`, `.python-version` 3.14.6, `ruff.toml`,
  `Makefile`, `.env.example` (every key, no values), `.dockerignore`, `.pre-commit-config.yaml` (T-015).
- **Appliance edition (change set C, T-011, T-025, T-026, T-027 scope half, T-028).** `src/cloud_assessor_appliance`:
  `edition.py` (refuses to start without the `azure` extra, with a forbidden credential variable, or without a parsable
  `CA_SCOPES`), `identity.py` (managed identity only; `ManagedIdentityCredential(client_id=AZURE_CLIENT_ID)` or a
  narrowed `DefaultAzureCredential` for `az login`; `AZURE_CLIENT_SECRET`, `AZURE_CLIENT_CERTIFICATE_PATH`,
  `AZURE_USERNAME`, `AZURE_PASSWORD`, `AZURE_TENANT_ID` refused), `collectors/scope.py` (the allow-list, `kql_filter`,
  `assert_contains`), `collectors/resource_graph.py` (one paged query from the allow-list only, 429 backoff, `max_rows`
  warning, every returned id checked), `collectors/cost_management.py` (month-to-date cost by resource group and
  `costCenter` tag, budgets, `InsightAlert` scheduled actions as anomaly alerts, hourly cache, `None` on throttle or
  missing role), `refresh.py` (single-flight lock, global cooldown, startup-then-timer collection, previous snapshot
  kept on failure), `api.py` (the section 8 routes: flat `/api/health` with `edition:"appliance"`,
  `azureConnectivity:"managed-identity"`, `scope.count`, `lastRun`, `publicResults`; `/api/assessments/current` and its
  `report.md`, `report.json`, `bundle.zip` answering `503 no_snapshot` before the first run and
  `403 results_not_public` while `CA_PUBLIC_RESULTS` is not `true`; `POST /api/refresh` with the per-client bucket,
  the global cooldown, single-flight `202 running` and optional human verification; `POST /api/assessments` answering
  `405 edition_readonly`; no owner tokens, no `{id}` paths), the lab's security modules ported (exact-origin CORS,
  headers with `frame-ancestors` from env, token bucket, verification with the `cloud-assessment-refresh` action, the
  content-free log writer, now also silencing the SDK loggers), and the pane copied from the AddOn with the edition
  switch (`mode = health.edition === "appliance" ? "current" : "upload"`).
- **Image (change set E).** `infrastructure/docker/Dockerfile` with the `appliance` target (deployed) and the `lab`
  boundary-proof target (installs the core without the extra, copies no application, `CMD` asserts `azure` is absent;
  never pushed, never deployed), both on the digest in `versions.env` checked by `scripts/check-versions.sh`;
  `publish-images.yml` builds both, runs the proof, scans with Trivy and pushes only the appliance through the Docker
  OIDC connection; `publish-core.yml` builds and verifies the wheel, attaches it to the release and attests it, with
  PyPI trusted publishing gated on `PYPI_ENABLED`; `release.yml` creates the release from this file.
- **Terraform (change set F).** `infrastructure/terraform/appliance-azure`: resource group, user-assigned identity,
  `Reader` and `Cost Management Reader` per `scope_ids`, Log Analytics (30 days), Consumption environment, one
  Container App (`min_replicas = max_replicas = 1`, HTTP probes on `/api/health`, `CA_SCOPES`, `AZURE_CLIENT_ID`,
  `CA_PUBLIC_RESULTS` from `var.public_results` defaulting to `false`), a resource-group budget with 80 and 100 percent
  notifications, an optional custom domain. `image_ref` has no default and must be a digest.
- **Tests (change set G, T-014).** `tests/unit` (config, scope, identity, edition, collectors, refresher, API, static
  pane, security modules, content-free logs, workflows, scripts), `tests/security` (appliance boundary in both
  directions; no secrets), `tests/packaging` (the built wheel; both lockfiles), and `test_cost_evidence.py` beside the
  engine's suite. 187 tests; coverage 95 percent (gate 85).
- **Governance and repository files (change set H, T-003, T-004, T-005, T-007, T-009, T-010, T-016, T-017, T-018,
  T-019).** `ci.yml`, `security.yml`, `CODEOWNERS`, `SECURITY.md`, `dependabot.yml`, `PULL_REQUEST_TEMPLATE.md`,
  `ISSUE_TEMPLATE/{bug_report.md,config.yml}`, `scripts/check-docs-governance.py` (five root files, platform
  templates, the engine README; relative links resolve), `.qlty/qlty.toml` with `ruff` and `bandit`, `LICENSE` (MIT,
  `[REVIEW REQUIRED]` R-003), `NOTICE` (attribution, `[REVIEW REQUIRED]` R-005), the `REFACTOR_APP.md` row in the
  `README.md` documentation table, `TODO.md` T-032 and T-033, `REVIEW.md` R-001 resolved, R-006 proposed, R-009 added.

### Verification (2026-10-10, authoring container; no Docker daemon, no `terraform`, no `az`)

| Check | Result |
|---|---|
| `uv sync --all-packages --extra azure` | 68 packages resolved; CPython 3.14.6 (`uv` offers no 3.14.7 build; the image pins 3.14.7 by digest) |
| `uv run ruff check . && uv run ruff format --check .` | clean |
| `uv run pytest -q --cov=packages --cov=src` | 187 passed, 1 skipped (the no-extra identity test); coverage 95.46 percent of 2,583 statements |
| `uv run pytest tests/security tests/packaging -q` (with and without the extra) | 16 passed both ways; `azure` not importable on the default set |
| `uv run python scripts/check-catalog.py` | catalog 1.1.0, 25 criteria, 25 `[VERIFY]`, schema in sync |
| `scripts/check-docs-governance.py`, `check-versions.sh`, `check-lockfiles.sh` | clean |
| `uv run pip-audit -r requirements.lock.txt --strict` and `-r requirements-azure.lock.txt` | no known vulnerabilities |
| `python -m cloud_assessor_appliance` on the default set, and with `AZURE_CLIENT_SECRET` set, and without `CA_SCOPES` | exit 3 with one scrubbed `startup_refused` line each |
| Local run with the extra and no Azure session | `/api/health` 200 (`edition:"appliance"`, `azureConnectivity:"managed-identity"`, `scope.count:1`, `publicResults:false`, headers `X-Addon-*`, CSP `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `Cache-Control: no-store`); `/api/assessments/current` 503 `no_snapshot`; `POST /api/assessments` 405 `edition_readonly`; `POST /api/refresh` 202; `/` 200; logs carried counts and codes only |
| Image build, both targets; Trivy; `terraform fmt`/`validate`; a `plan` | **not run here** (CI `image` and `terraform` jobs; the plan is an owner step after R-002) |
| Live collection against a subscription | **not run** (R-002) |

### Changed

- Security review of PR #6 (2026-10-10): the refresh route checks the global cooldown before the single-flight lock
  (deterministic `429`); both collectors run under `asyncio.wait_for` with `CA_COLLECT_TIMEOUT_SECONDS`, and the SDK
  clients get connection (10 s) and read (60 s) timeouts and `retry_total = 3`; `/api/health` gains `lastError`,
  `snapshotAgeSeconds` and `scope.{configured,observed}` beside `scope.count`; internal and unhandled errors log the
  exception class name only (collector errors keep their scrubbed, application-composed message); `CA_TRUST_PROXY=1`
  reads the last `X-Forwarded-For` entry (the one the trusted proxy appended), not the first; the queued refresh task is
  kept on the refresher with a done callback; human verification runs in a worker thread; `publish-images.yml` pushes
  only from a `v*` tag ref; `budget_start_date` is required and validated (no expiring default); scope ids are
  lower-cased before `toset`; the Dockerfile `HEALTHCHECK` honours `PORT`; `__main__` writes its refusal with
  `json.dumps`; `ATTEMPTS` is used in the throttling message and a status-less `ClientAuthenticationError` is named
  instead of `HTTP None`; the CodeQL pins name `v4.37.8`. T-034 (the provider lock file) is done: `infrastructure/terraform/appliance-azure/.terraform.lock.hcl` pins `hashicorp/azurerm` 4.81.0 with hashes for linux_amd64 and windows_amd64.
- `README.md` rewritten for the implemented state: editions, layout, the section 20 commands as the quick start, the
  five-file documentation table, engine-change conventions.
- `.gitignore` extended (T-004); `.qlty/qlty.toml` plugins (T-010).

### Known limitations

- Python 3.14.7 is the image's interpreter (by digest) while `.python-version` pins 3.14.6, the newest build `uv`
  can install here; both satisfy `requires-python >=3.14.6,<3.15`.
- Cost Management field names, the `InsightAlert` reading of anomaly alerts, the managed-certificate custom-domain
  flow and the base-image digest are `[VERIFY]` until the first live validation (R-002) and image build.
- `POST /api/refresh` is bounded globally first: inside the cooldown (which starts when the route queues a run, so it
  covers that run while it is in progress) the answer is `429 rate_limited` with `Retry-After`; only a timer-started
  run in progress answers `202 {queued:false, running:true}`. `REFACTOR_APP.md` sections 7.8 and 8 were updated to say
  so (section 8 had tabled `503 busy`).
- A collection that runs past `CA_COLLECT_TIMEOUT_SECONDS` (default 900) is abandoned: the single-flight lock is
  released, the previous snapshot stays current and `/api/health` reports `lastError: "timeout"`. The worker thread
  cannot be interrupted and finishes on its own; its result is dropped.

### Added (documentation governance, before the plan)

- Documentation governance model for the repository. Four root markdown files are now the
  only sanctioned in-repository documents: `README.md` (repository purpose), `CHANGELOG.md`
  (completed work), `REVIEW.md` (human-resolvable blockers), and `TODO.md` (engineering
  work queue). All other documentation is directed to the GitHub Wiki.
- `CHANGELOG.md` recording completed work.
- `REVIEW.md` recording blockers that require a human decision, each with problem
  statement, blocking rationale, required owner, required action, impact, references, and
  a recommended next step.
- qlty configuration at `.qlty/qlty.toml`, generated by `qlty init`. The qlty GitHub App
  was already installed on the repository but the repository had never been initialized
  for it, so the `qlty check` status errored with "Qlty must be set up in this repository"
  before analyzing anything. Auto-detection enabled the TruffleHog secret scanner; with the
  configuration committed, `qlty check --all` reports no issues. This is tool
  configuration, which is the sanctioned use of a dot-prefixed folder.
- `TODO.md` establishing the authoritative engineering backlog, organized into six
  implementation phases in dependency order, with per-item priority, description,
  dependencies, recommended action, status, and handoff notes.

### Changed (documentation governance, before the plan)

- **Narrowed the assessment scope to Azure only.** AWS, GCP, and OCI were removed as target
  platforms across all documentation; support for them is not planned. Azure remains the
  source of the Well-Architected Cost Optimization pillar and is now also the sole
  assessment target. This resolves the platform half of blocker R-001, which had flagged
  the contradiction between a description listing AWS, GCP, and OCI as targets and open
  issues proposing exclusively Azure integrations.

  Consequences recorded across the backlog: the three per-cloud collectors became an Azure
  decomposition along the planes Azure actually separates — ARM resources (T-025), Cost
  Management (T-026), and scope enumeration with Entra ID identity (T-027); the credential
  standard in T-011 is now Azure-specific and accounts for `Reader`, `Cost Management
  Reader`, and Microsoft Graph being three distinct permission grants; the access request
  in R-002 is now a single Azure subscription; and the data model in T-024 is explicitly
  scoped to Azure rather than provider-neutral.

- Rewrote `README.md`. The title now uses the project name rather than the
  `owner-repository` slug, and the file was expanded to cover project status, benchmark
  scope, repository layout, quick start, installation and configuration state,
  documentation navigation, and repository conventions. The pre-implementation status of
  the repository is now stated explicitly so the absence of build and run instructions is
  not mistaken for missing documentation.

## 2026-06-05 — Repository initialization

No version has been released and no git tag exists yet, so this entry is grouped by date
rather than by version number.

### Added

- Initial repository with project description covering the multi-cloud,
  container-focused Well-Architected Review scope across AWS, GCP, and OCI.
- Python `.gitignore` based on the GitHub Python template.
- Feature request issue template at `.github/ISSUE_TEMPLATE/feature_request.md`.
