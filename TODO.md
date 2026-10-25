# TODO — Engineering Work Queue

This is the authoritative engineering backlog for the repository. Every actionable
engineering item discovered anywhere in this repository is recorded here so an engineer
can resume work without rediscovering findings.

Items that require a human decision, approval, or access grant are **not** here — they are
in [REVIEW.md](REVIEW.md) and are referenced below as `R-00n` dependencies.

Items are ordered chronologically within each phase, phases are ordered by dependency, and
no item depends on an item in a later phase.

**Priority scale:** P0 critical · P1 high · P2 medium · P3 low
**Status values:** Not started · Blocked · In progress · Done · Deferred

## Contents

| Phase | Theme | Items |
|-------|-------|-------|
| [Phase 1](#phase-1--critical-fixes-and-repository-foundation) | Critical fixes and repository foundation | T-001 – T-006 |
| [Phase 2](#phase-2--security-improvements) | Security improvements | T-007 – T-012 |
| [Phase 3](#phase-3--stability-improvements) | Stability improvements | T-013 – T-016 |
| [Phase 4](#phase-4--technical-debt) | Technical debt | T-017 – T-019 |
| [Phase 5](#phase-5--feature-enhancements) | Feature enhancements | T-020 – T-028 |
| [Phase 6](#phase-6--documentation-improvements) | Documentation improvements | T-029 – T-031 |
| [Phase 7](#phase-7--appliance-follow-ups) | Appliance follow-ups | T-032 – T-034 |

---

## Phase 1 — Critical Fixes and Repository Foundation

Nothing else can be built until the repository has a code skeleton, a license, and a
working CI signal.

### T-001 — Commit the initial project skeleton for the chosen stack

- **Priority:** P0
- **Description:** The repository contains no source code, no dependency manifest, and no
  build configuration. The only signal about the intended stack is the Python `.gitignore`
  (which includes `.ruff_cache/`, suggesting Python with Ruff), and that signal is not
  authoritative.
- **Dependencies:** R-001 (assessment scope and deliverable format undefined)
- **Recommended Action:** Once R-001 is decided, commit a minimal skeleton: dependency
  manifest and lockfile, package or module layout, entry point, and a runtime version pin.
  Keep it minimal — one importable package and one entry point is enough to unblock CI,
  linting, and tests.
- **Status:** Done
- **Notes for Future Engineers:** Do not infer the stack from `.gitignore` alone. If R-001
  lands on a multi-language design (for example Python collectors plus a TypeScript
  report UI), lay out the repository as a monorepo from the start rather than retrofitting
  one later.
- **Done (2026-10-10):** Instruction `REFACTOR_APP.md` 7.2 and section 3. uv workspace (`pyproject.toml`, `uv.lock`, hash-pinned `requirements.lock.txt` and `requirements-azure.lock.txt`), `src/cloud_assessor_appliance`, `python -m cloud_assessor_appliance`, `.python-version`.

### T-002 — Add a LICENSE file

- **Priority:** P0
- **Description:** The repository has no `LICENSE` file and GitHub reports no license.
  Default copyright applies, which leaves contribution and distribution rights undefined.
- **Dependencies:** R-003 (no license selected)
- **Recommended Action:** Add the `LICENSE` file matching the decision recorded in R-003
  and add the corresponding SPDX identifier to the project manifest created in T-001.
- **Status:** Blocked
- **Interim (2026-10-10):** `LICENSE` is MIT and `pyproject.toml` carries `license = "MIT"` to match the lab edition, marked `[REVIEW REQUIRED]` in `NOTICE` until R-003 is decided.
- **Notes for Future Engineers:** The license choice constrains R-004. If any third-party
  tool is vendored or forked, verify compatibility before merging that integration.

### T-003 — Add CODEOWNERS

- **Priority:** P2
- **Description:** There is no `.github/CODEOWNERS`, so no reviewer is automatically
  requested and no path has a designated owner.
- **Dependencies:** None
- **Recommended Action:** Add `.github/CODEOWNERS` with a default owner for the repository
  root, and add path-specific owners for the collector directories once T-025 through
  T-027 create them.
- **Status:** Done
- **Notes for Future Engineers:** CODEOWNERS only enforces review when branch protection
  requires owner review — pair this with T-006.
- **Done (2026-10-10):** `.github/CODEOWNERS` with the default owner and the engine, appliance, infrastructure and `.github` paths.

### T-004 — Extend `.gitignore` beyond the Python-only template

- **Priority:** P2
- **Description:** `.gitignore` is the stock GitHub Python template. It has no entries for
  Terraform state, Node modules, IDE directories, cloud CLI caches, or assessment output
  files — all plausible once implementation starts. Notably it does not ignore credential
  files beyond `.env`.
- **Dependencies:** T-001
- **Recommended Action:** Extend `.gitignore` for the stack chosen in T-001, and add
  explicit patterns for Azure credential material (`*.pem`, `*.pfx`, service principal
  JSON, copies of the `~/.azure/` CLI token cache) and for generated assessment output.
- **Status:** Done
- **Notes for Future Engineers:** `.gitignore` is not a security control. Pair this with
  T-008 (push protection) rather than relying on ignore rules to keep secrets out.
- **Done (2026-10-10):** Credential material (`*.pem`, `*.pfx`, `*.publishsettings`, `.azure/`), `assessment-output/`, `*.report.json`, Terraform state and `*.tfvars` (keeping `terraform.tfvars.example`), `node_modules/`.

### T-005 — Add a baseline CI workflow

- **Priority:** P1
- **Description:** `.github/` contains only an issue template. There is no
  `.github/workflows/` directory, so the repository defines no CI of its own. The only
  checks running on pull requests are third-party apps — GitGuardian and qlty — and
  neither builds the project or runs its tests.
- **Dependencies:** T-001
- **Recommended Action:** Add a CI workflow triggered on pull request and on push to
  `main` that installs dependencies, runs the linter (T-013), and runs the test suite
  (T-014). Pin action versions to a commit SHA and set the default `GITHUB_TOKEN`
  permissions to read-only, elevating per job only where needed.
- **Status:** Done
- **Notes for Future Engineers:** Keep the workflow name and job names stable from the
  start — T-006 references them as required status checks, and renaming them silently
  drops the protection.
- **Done (2026-10-10):** `.github/workflows/ci.yml`: lint, test (85 percent gate), catalog-check, boundary, terraform, image jobs; every action SHA-pinned, `permissions: contents: read`, `ubuntu-26.04`. Required checks for T-006 are the `ci` and `security` jobs, never `qlty check` (R-008).

### T-006 — Enable branch protection and required status checks on `main`

- **Priority:** P1
- **Description:** `main` is the default branch and has no protection configured, so it can
  be pushed to directly and merged into without review or a passing build.
- **Dependencies:** T-005, R-008 (`qlty check` errors Cloud-side)
- **Recommended Action:** Require a pull request before merging, require the CI checks from
  T-005 to pass, require branches to be up to date, and block force pushes and deletion.
- **Status:** Blocked
- **Ready (2026-10-10):** the checks to require are the `ci` workflow's `lint`, `test`, `catalog-check`, `boundary`, `terraform` and `image` jobs and the `security` workflow's `dependency-review`, `codeql`, `secret-scan` and `pip-audit` jobs; never `qlty check` (R-008).
- **Notes for Future Engineers:** This is a repository settings change, not a file change,
  so it will not appear in any diff. Record that it was done in `CHANGELOG.md` so the next
  engineer does not have to check the settings page to find out. Do not add `qlty check` to
  the required set until R-008 is resolved — it currently errors on every commit and would
  block all merges.

---

## Phase 2 — Security Improvements

The project will hold read credentials for three cloud providers and will emit
infrastructure inventory. Security controls should land before the first collector.

### T-007 — Add `.github/SECURITY.md`

- **Priority:** P2
- **Description:** There is no security policy, so there is no stated route for reporting a
  vulnerability in a tool that reads cloud infrastructure.
- **Dependencies:** None
- **Recommended Action:** Add a minimal `.github/SECURITY.md` with supported versions and a
  private reporting contact. Keep it short and link to the wiki for anything longer.
- **Status:** Done
- **Notes for Future Engineers:** `.github/SECURITY.md` is a platform-recognized exception
  to the no-documentation-in-dot-folders rule. Keep it minimal so it stays an exception.
- **Done (2026-10-10):** `.github/SECURITY.md` (private reporting, scope highlights, supported versions).

### T-008 — Verify secret scanning and push protection are enabled

- **Priority:** P1
- **Description:** Two secret scanners now run on pull requests: a GitGuardian Security
  Checks app, and TruffleHog via qlty (see T-006). What has not been confirmed is whether
  GitHub's native secret scanning and — more importantly — **push protection** are enabled.
  Both current scanners report after a push has landed; only push protection blocks the
  push. A tool that holds read credentials for a customer's Azure tenant is a high-risk
  place to accidentally commit one.
- **Dependencies:** None
- **Recommended Action:** Confirm in repository settings whether native secret scanning and
  push protection are enabled, and record the result. Decide whether all three scanners are
  wanted or whether the overlap between GitGuardian and TruffleHog should be resolved (see
  T-010). If push protection is unavailable on the current plan, add a pre-push
  secret-detection hook in T-015.
- **Status:** Not started
- **Note (2026-10-10):** T-011 landed with `tests/security/test_no_secrets.py`, gitleaks and TruffleHog in place; push protection is still unconfirmed and is recorded in `CHANGELOG.md` when done.
- **Notes for Future Engineers:** Confirm this before T-011 introduces any credential
  handling code or example configuration.

### T-009 — Add Dependabot configuration

- **Priority:** P2
- **Description:** There is no `.github/dependabot.yml`, so neither dependencies nor GitHub
  Actions versions will receive update pull requests.
- **Dependencies:** T-001
- **Recommended Action:** Add `.github/dependabot.yml` covering the package ecosystem
  chosen in T-001 and the `github-actions` ecosystem. Group patch updates to limit noise.
- **Status:** Done
- **Notes for Future Engineers:** The Azure SDK ships as many separately versioned
  per-service packages that release frequently. Group them into a single weekly pull
  request or the queue becomes unmanageable.
- **Done (2026-10-10):** `.github/dependabot.yml`: pip (grouped `azure-*`/`msal*`/`msrest*`, dev group), the engine package, github-actions, docker, terraform; weekly.

### T-010 — Add dependency review and static analysis to CI

- **Priority:** P2
- **Description:** No dependency review or static analysis runs on changes. qlty is
  initialized but auto-detection enabled only the TruffleHog secret scanner, because there
  is no source code yet for it to detect linters from.
- **Dependencies:** T-005, T-009
- **Recommended Action:** Re-run `qlty init` or edit `.qlty/qlty.toml` once T-001 lands, so
  the linters for the chosen stack are enabled. Add dependency review on pull requests and
  a static analysis job (CodeQL, or the equivalent for the stack chosen in T-001). Resolve
  the scanner overlap identified in T-008 at the same time.
- **Status:** Done
- **Notes for Future Engineers:** Start these jobs as non-blocking, triage the initial
  findings into this file, then make them required in T-006 once the baseline is clean.
  Note that `qlty check` fails the build outright when `.qlty/qlty.toml` is absent, so do
  not delete that file to silence findings — configure the plugins instead.
- **Done (2026-10-10):** `.github/workflows/security.yml` (dependency-review, CodeQL python and javascript-typescript, gitleaks, `pip-audit` on both locks); `.qlty/qlty.toml` enables `ruff` and `bandit` beside `trufflehog`. Scanner overlap (T-008) is left to the owner. **Owner step:** enable the Dependency graph at https://github.com/saulpatinojr/HCW-CloudAssessor_App/settings/security_analysis, otherwise the `dependency-review` job fails with "Dependency review is not supported on this repository" (seen on PR #6).

### T-011 — Define the Azure credential handling standard

- **Priority:** P0
- **Description:** The assessment must authenticate to Azure. There is no decision recorded
  on how credentials are supplied, scoped, rotated, or kept out of logs and assessment
  output.
- **Dependencies:** R-002 (Azure access not provisioned)
- **Recommended Action:** Standardize on workload identity federation for CI and on
  `DefaultAzureCredential` for local runs, so no client secret is ever stored. Prohibit
  credential values in configuration files, forbid logging of credential material, and
  document the required read-only role assignments in the wiki.
- **Status:** Done
- **Notes for Future Engineers:** Azure splits the reads this assessment needs across two
  planes with separate permissions: ARM resource reads under `Reader`, and cost data under
  `Cost Management Reader`, which `Reader` does not include. Entra ID directory reads are a
  third, separately granted surface via Microsoft Graph. Design the credential layer around
  those boundaries rather than assuming one role covers everything.
- **Done (2026-10-10):** Owner decision (managed identity only) made concrete in `src/cloud_assessor_appliance/identity.py`: `ManagedIdentityCredential(client_id=AZURE_CLIENT_ID)` in production, a narrowed `DefaultAzureCredential` for local `az login`; `AZURE_CLIENT_SECRET`, `AZURE_CLIENT_CERTIFICATE_PATH`, `AZURE_USERNAME`, `AZURE_PASSWORD` and `AZURE_TENANT_ID` refuse startup; CI greps for `ClientSecretCredential`. The three permission planes are two role assignments in Terraform (`Reader`, `Cost Management Reader`); Graph is deferred (T-033).

### T-012 — Add output redaction and a data-handling guard

- **Priority:** P1
- **Description:** Assessment output will contain resource identifiers, subscription and
  tenant identifiers, network configuration, and cost data. Nothing currently prevents that
  material from being written into the repository, into CI logs, or into a shared report.
- **Dependencies:** R-006 (output data classification undecided), T-001
- **Recommended Action:** Implement a redaction layer applied to all output paths, honoring
  the classification decided in R-006. Add a CI check that fails if files matching the
  assessment output pattern are committed.
- **Status:** Done
- **Notes for Future Engineers:** Apply redaction at the serialization boundary, not at
  each call site — a single guarded writer is far easier to audit than scattered redaction
  calls, and it is the difference between a reviewable control and a hope.

---

## Phase 3 — Stability Improvements
- **Done (2026-10-10):** The core's `redaction.py` (adopted) is the only log writer (`assert_no_visitor_data`, `scrub`); the SDK loggers are silenced; `.gitignore` and `tests/security/test_no_secrets.py` refuse `assessment-output/` and `*.report.json`; subscription ids in `report.json` are hashed in `scope.subscriptions`. R-006 classification is still proposed, not confirmed.

### T-013 — Add linting and formatting configuration

- **Priority:** P2
- **Description:** No linter or formatter configuration exists. The `.ruff_cache/` entry in
  `.gitignore` hints at Ruff but no Ruff configuration is committed.
- **Dependencies:** T-001, T-005
- **Recommended Action:** Commit linter and formatter configuration for the chosen stack
  and wire it into the CI workflow from T-005.
- **Status:** Done
- **Notes for Future Engineers:** Land this before the first substantial feature branch.
  Introducing a formatter after the code exists produces a large reformat commit that
  obscures history.
- **Done (2026-10-10):** `ruff.toml` (lint and format, line length 120) wired into `ci.yml` and `.pre-commit-config.yaml`.

### T-014 — Add the test framework and a first smoke test

- **Priority:** P1
- **Description:** There are no tests and no test framework. `.gitignore` anticipates
  `pytest` and coverage artifacts, but nothing is configured.
- **Dependencies:** T-001, T-005
- **Recommended Action:** Add the test framework, a coverage configuration, and one smoke
  test that exercises the entry point. Wire it into CI. Establish the fixture strategy for
  recorded cloud API responses at the same time.
- **Status:** Done
- **Notes for Future Engineers:** The fixture strategy depends on R-006 — until the data
  classification decision lands, do not commit fixtures captured from a real environment.
  Use synthetic fixtures, and scrub subscription, tenant, and resource group identifiers.
- **Done (2026-10-10):** pytest with the 85 percent coverage gate; 187 tests across unit, security and packaging plus the adopted engine suite; fixtures are the AddOn's fictional `samples/` only (subscription `00000000-0000-0000-0000-000000000001`).

### T-015 — Add pre-commit hooks

- **Priority:** P3
- **Description:** No pre-commit configuration exists, so lint and format failures are only
  discovered in CI.
- **Dependencies:** T-013
- **Recommended Action:** Add a pre-commit configuration running the formatter, the linter,
  and a secret-detection hook. Document the one-line install in `README.md`.
- **Status:** Done
- **Notes for Future Engineers:** Keep the hook set identical to the CI checks. Hooks that
  diverge from CI cause more confusion than they prevent.
- **Done (2026-10-10):** `.pre-commit-config.yaml` running ruff, ruff-format and gitleaks, identical to CI; the gitleaks hook revision is `[VERIFY]`.

### T-016 — Add markdown link checking for the governance documents

- **Priority:** P3
- **Description:** `README.md`, `CHANGELOG.md`, `REVIEW.md`, and `TODO.md` cross-link to
  each other and to the wiki. Nothing verifies those links stay valid.
- **Dependencies:** T-005
- **Recommended Action:** Add a link-checking job to CI covering the four root markdown
  files. Allow the wiki links to be checked leniently until T-029 populates the wiki.
- **Status:** Done
- **Notes for Future Engineers:** The wiki is enabled but not yet populated (R-007), so a
  link checker reports wiki links as 404. Exclude the wiki host (as the governance script
  does) until T-030 completes.

---

## Phase 4 — Technical Debt
- **Done (2026-10-10):** `scripts/check-docs-governance.py` resolves every relative link in the five root files in CI; the wiki host is excluded until T-030 (no network checker, so no unverified action pin).

### T-017 — Complete the issue template set

- **Priority:** P3
- **Description:** `.github/ISSUE_TEMPLATE/` contains only `feature_request.md`. There is no
  bug report template and no `config.yml`, so bug reports arrive unstructured and there is
  no way to route reporters elsewhere.
- **Dependencies:** None
- **Recommended Action:** Add `bug_report.md` and `config.yml`. The bug template should
  request the assessment scope in use (subscription, management group, or tenant) and
  redacted output — the fields that determine whether a report is actionable here.
- **Status:** Done
- **Notes for Future Engineers:** Remind reporters in the template to redact account,
  subscription, and tenant identifiers before pasting output. This repository is public, so
  the habit matters more, not less.
- **Done (2026-10-10):** `.github/ISSUE_TEMPLATE/bug_report.md` (asks for the scope kind and redacted output) and `config.yml`.

### T-018 — Add a pull request template

- **Priority:** P3
- **Description:** No `.github/PULL_REQUEST_TEMPLATE.md` exists, so pull request bodies are
  unstructured.
- **Dependencies:** None
- **Recommended Action:** Add a short template with sections for summary, related issue or
  TODO item, verification performed, and documentation updates. Include a checkbox
  confirming that any new documentation went to the correct destination under the
  four-file model.
- **Status:** Done
- **Notes for Future Engineers:** Keep it short. Long templates get deleted rather than
  filled in.
- **Done (2026-10-10):** `.github/PULL_REQUEST_TEMPLATE.md` with summary, related decision, type of change, verification, security and data review, documentation and operations, AI provenance.

### T-019 — Add a documentation governance CI check

- **Priority:** P2
- **Description:** The four-file documentation model is currently maintained by convention
  alone. Nothing prevents a new `docs/` directory, a non-root `README.md`, or a design
  document in `.github/`.
- **Dependencies:** T-005
- **Recommended Action:** Add a CI check that fails when a markdown file exists outside the
  approved set: the four root files plus a small allowlist of platform-required templates
  under `.github/`. Point the failure message at the destination mapping in `README.md`.
- **Status:** Done
- **Notes for Future Engineers:** This check is what keeps the model from eroding. Without
  it, the four-file structure lasts until the first engineer who finds it inconvenient.

---

## Phase 5 — Feature Enhancements

This phase delivers the assessment itself. The three evaluation spikes are deliberately
first — their outcome shapes the collector design.
- **Done (2026-10-10):** `scripts/check-docs-governance.py` in `ci.yml`: markdown only as the five root files, `.github/` platform templates and the engine package README the wheel metadata requires (adopted verbatim).

### T-020 — Evaluation spike: Quick Review / AzQR integration

- **Priority:** P1
- **Description:** Issue #1 proposes integrating `saulpatinojr/Azure-AzQR` for quick review
  capability. The integration mode is unspecified.
- **Dependencies:** R-004 (third-party integration adoption not approved)
- **Recommended Action:** Timebox a spike assessing which Azure resource types AzQR covers,
  whether it can be invoked as a subprocess or consumed as a library, and its output
  schema. Record findings in the wiki and post the recommendation on issue #1.
- **Status:** Deferred
- **Notes for Future Engineers:** With the scope narrowed to Azure, AzQR is the closest
  existing tool to what this project sets out to do. Run this spike before T-024 — if AzQR
  already produces most of the resource-level review, the data model should be shaped
  around extending its output rather than replacing it.

### T-021 — Evaluation spike: Zero Trust Assessment and Prowler integration

- **Priority:** P1
- **Description:** Issue #2 proposes integrating `microsoft/zerotrustassessment` and
  `prowler-cloud/prowler` for Zero Trust coverage.
- **Dependencies:** R-004
- **Recommended Action:** Timebox a spike comparing the two against the Azure scope.
  `zerotrustassessment` targets Entra ID and Microsoft 365 rather than Azure resources, so
  establish first whether identity-plane assessment is in scope at all. Assess Prowler's
  Azure provider specifically. Record findings in the wiki and post the recommendation on
  issue #2.
- **Status:** Deferred
- **Notes for Future Engineers:** Prowler has a commercial edition alongside its open
  source distribution. Confirm the licensing conclusion from R-004 before writing any code
  against it. Note also that only Prowler's Azure provider is now relevant — taking on a
  multi-cloud dependency for one provider's checks needs justifying.

### T-022 — Evaluation spike: Governance Visualizer integration

- **Priority:** P2
- **Description:** Issue #3 proposes integrating
  `Azure/Azure-Governance-Visualizer-Accelerator`.
- **Dependencies:** R-004
- **Recommended Action:** Timebox a spike assessing whether the accelerator's visualization
  output is reusable directly, or whether only its reporting approach is worth borrowing.
  Record findings in the wiki and post the recommendation on issue #3.
- **Status:** Deferred
- **Notes for Future Engineers:** This is a visualization and reporting concern, not a
  collection concern. It can be deferred behind T-028 without blocking anything.

### T-023 — Author the benchmark criteria catalog

- **Priority:** P0
- **Description:** The assessment benchmarks against the FinOps Foundation Framework, the
  Azure Well-Architected Cost Optimization pillar, and Zero Trust principles, but no
  machine-readable catalog of criteria exists.
- **Dependencies:** R-005 (framework content usage rights unconfirmed), T-001
- **Recommended Action:** Define a criteria schema (identifier, source framework, pillar,
  severity, applicable Azure resource types, evaluation logic reference, remediation
  guidance) and populate it. Keep the catalog declarative and separate from collector code.
- **Status:** Done
- **Notes for Future Engineers:** R-005 governs whether criteria text can be reproduced
  verbatim. Design the schema so criteria text is a single replaceable field — that way a
  paraphrase-only outcome is a data change, not a code change.
- **Done (2026-10-10):** Adopted verbatim from the AddOn (`packages/cloud-assessor-core/catalog`), then catalog 1.1.0: `CA-FIN-002`, `CA-FIN-003` and `CA-FIN-007` gain a `cost-evidence` check. `text` is the single replaceable field; every `learnUrl` stays `[VERIFY]` (R-005).

### T-024 — Implement the assessment data model

- **Priority:** P0
- **Description:** No common representation exists for collected resources, evaluated
  findings, or scores across the ARM, cost, and identity planes.
- **Dependencies:** T-023, T-020
- **Recommended Action:** Define a resource and finding model with a documented version
  field, so the collectors in T-025 through T-027 normalize into one shape and the report
  layer reads only the normalized form.
- **Status:** Done
- **Notes for Future Engineers:** Version the model from the first commit. Assessment
  results are compared over time, and an unversioned model makes historical comparison
  unreliable the first time the shape changes. Scope the model to Azure — do not build a
  provider-neutral abstraction for a single target platform, since that indirection costs
  clarity and buys nothing that is actually planned.
- **Done (2026-10-10):** Adopted (`MODEL_VERSION = 1`); additive `CostEvidence`, `BudgetEvidence`, `AssessmentScope`, `Assessment.edition` and `Assessment.scope`; the live collector emits `source.format = "arg-live"`.

### T-025 — Implement the Azure resource collector

- **Priority:** P1
- **Description:** No collection capability exists for Azure Resource Manager. This is the
  container and workload inventory the majority of the T-023 catalog evaluates against —
  AKS clusters, node pools, container apps, registries, and their networking.
- **Dependencies:** T-011, T-024
- **Recommended Action:** Implement read-only ARM collection for the resource types the
  T-023 catalog requires. Use Azure Resource Graph for inventory rather than per-resource
  ARM list calls, and handle paging and throttling.
- **Status:** Done
- **Notes for Future Engineers:** Resource Graph answers inventory questions in one query
  that would otherwise take hundreds of ARM calls, and it is far less likely to hit
  throttling. Reach for the per-resource ARM APIs only for detail Resource Graph does not
  project.
- **Done (2026-10-10):** `src/cloud_assessor_appliance/collectors/resource_graph.py`: one paged Resource Graph query built from the allow-list only, `skip_token` honoured, 429 backoff (base 2 s, cap 60 s, five attempts), `max_rows` cap as a warning, every returned id checked against the allow-list.

### T-026 — Implement the Azure cost collector

- **Priority:** P1
- **Description:** No collection capability exists for cost data, which the FinOps
  Foundation Framework and Cost Optimization pillar criteria depend on entirely.
- **Dependencies:** T-011, T-024
- **Recommended Action:** Implement read-only collection via the Cost Management APIs for
  the aggregations the T-023 catalog requires, including tag-based and resource-group-based
  allocation.
- **Status:** Done
- **Notes for Future Engineers:** Cost Management is a separate permission plane —
  `Cost Management Reader`, which `Reader` does not grant (see T-011 and R-002). Its APIs
  are also aggressively throttled and its data lags by up to a day, so treat cost as an
  asynchronous input rather than something fetched inline with resource collection.
- **Done (2026-10-10):** `src/cloud_assessor_appliance/collectors/cost_management.py`: month-to-date ActualCost by resource group and by the `costCenter` tag, budgets and anomaly alerts (`InsightAlert` scheduled actions), hourly cache, `None` on throttling or a missing role so the criteria stay `unknown`. Field names are `[VERIFY]` until R-002.

### T-027 — Implement Azure scope enumeration and the identity collector

- **Priority:** P1
- **Description:** No capability exists to enumerate what to assess, or to read the
  identity posture the Zero Trust criteria evaluate.
- **Dependencies:** T-011, T-024
- **Recommended Action:** Implement management-group and subscription traversal so an
  assessment can be scoped to a subscription, a management group, or a whole tenant.
  Implement the RBAC and Entra ID reads the T-023 Zero Trust criteria require.
- **Status:** In progress
- **Notes for Future Engineers:** Directory reads go through Microsoft Graph, not ARM, with
  their own consent model and permission grants. Confirm during R-002 that Graph
  permissions were included — they are easy to omit from an access request that only
  mentions `Reader`, and their absence will not surface until this item starts.
- **Done (2026-10-10):** Scope half done: `collectors/scope.py` (`/subscriptions/<guid>` and `/subscriptions/<guid>/resourceGroups/<name>`, no management-group traversal in v1). The identity half (Microsoft Graph and RBAC reads) is deferred to T-033; the identity-posture criteria stay `unknown`.

### T-028 — Implement scoring and report generation

- **Priority:** P1
- **Description:** No scoring logic or report output exists.
- **Dependencies:** T-024, T-012
- **Recommended Action:** Implement criteria evaluation against collected data, scoring
  aggregated by framework and pillar, and report rendering in the format decided in R-001.
  All output must pass through the redaction layer from T-012.
- **Status:** Done
- **Notes for Future Engineers:** Keep scoring weights in configuration rather than in
  code. Weighting is the part clients most often want adjusted per engagement.

---

## Phase 6 — Documentation Improvements
- **Done (2026-10-10):** Adopted scoring and reports; format decided by owner (pane plus markdown, JSON, CSV, zip). The appliance serves them at `/api/assessments/current*` behind the `CA_PUBLIC_RESULTS` gate.

### T-029 — Bootstrap the GitHub Wiki

- **Priority:** P1
- **Description:** The wiki is enabled but empty. The documentation model directs all
  long-form documentation there, so until it has a `Home` page there is no valid
  destination for anything the four root files exclude.
- **Dependencies:** R-007 (wiki not writable by automation)
- **Recommended Action:** Create the `Home` page and a `_Sidebar` navigation page, with the
  section structure proposed in T-030.
- **Status:** Blocked
- **Notes for Future Engineers:** A GitHub wiki has no git remote until its first page is
  created through the web UI. That first page must be created manually; everything after it
  can be pushed to `Work-Complete_Cloud_Assessment.wiki.git`.

### T-030 — Create the proposed wiki page set

- **Priority:** P2
- **Description:** No wiki pages exist. The following pages are proposed to hold content
  that is excluded from the four root markdown files.

  | Wiki page | Content | Fed by |
  |-----------|---------|--------|
  | `Home` | Landing page and navigation | T-029 |
  | `Assessment-Scope` | Deliverable format, consumers, cadence | R-001 |
  | `Architecture-Overview` | Component design, collector and scoring boundaries | T-024 |
  | `Benchmark-Criteria` | Framework mapping, criteria schema, attribution notices | T-023, R-005 |
  | `Azure-Access-Requirements` | Read-only role assignments, Graph permissions, federation setup | T-011, R-002 |
  | `Integration-Evaluations` | Spike findings for AzQR, ZTA, Prowler, Governance Visualizer | T-020, T-021, T-022 |
  | `Development-Guide` | Local setup, running tests, fixture conventions | T-013, T-014 |
  | `Data-Handling` | Output classification, retention, redaction rules | R-006, T-012 |
  | `Runbook-Assessment-Run` | Executing an assessment and interpreting results | T-028 |
  | `Decision-Log` | Architecture decision records | R-001, R-004 |

- **Dependencies:** T-029
- **Recommended Action:** Create the pages above as each source item completes. Do not
  create empty placeholder pages — an empty wiki page is worse than a missing one, because
  it looks like documentation that exists.
- **Status:** Blocked
- **Notes for Future Engineers:** When a page is created, add its link to the relevant
  section of `README.md` so the wiki stays reachable from the repository.

### T-031 — Mirror accepted issue work into this file

- **Priority:** P3
- **Description:** Issues #1, #2, and #3 carried actionable engineering work that existed
  only in the issue tracker until it was captured here as T-020 through T-022. Without a
  standing practice, the same drift will recur.
- **Dependencies:** None
- **Recommended Action:** When an issue is accepted, add a corresponding item here with the
  issue number in its description, and close the loop on the issue when the item is done.
- **Status:** Not started
- **Notes for Future Engineers:** This file, not the issue tracker, is the authoritative
  backlog. Issues are the intake path; this file is where work is sequenced.

---

## Phase 7 — Appliance Follow-ups

Proposed by `REFACTOR_APP.md` (sections 13 and 18) at execution on 2026-10-10.

### T-032 — Entra token validation on the appliance routes

- **Priority:** P2
- **Description:** The appliance has no authenticated route in v1. Results are anonymous for the scope by owner
  decision, behind the `CA_PUBLIC_RESULTS` release gate (`403 results_not_public` until the owner flips it). Bearer
  validation on `POST /api/refresh` and the four `/api/assessments/current*` routes would let results stay private
  to the client's tenant without the gate.
- **Dependencies:** R-009 (resolved, option b), R-006 (still open; it gates `CA_PUBLIC_RESULTS`, not this item)
- **Recommended Action:** If R-009 lands on token validation: validate Entra ID access tokens (issuer, audience,
  signature from the tenant's JWKS) in a FastAPI dependency applied to the five routes; register the audience with a
  Terraform `azuread_application`; keep `CA_PUBLIC_RESULTS` as the switch between the two postures. Never a client
  secret: the validation path needs the public keys only.
- **Status:** Done (2026-10-24, R-009 option b). Implemented in `src/cloud_assessor_appliance/security/entra.py` with tests in `tests/unit/test_entra.py` and `tests/security/test_auth_boundary.py`. Terraform plumbing (`auth.tf`: `azuread_application`, app role and scope, service principal requiring assignment, `CA_AUTH_*` app settings) and a plan-time guard against an unauthenticated public ingress added for ticket CA-3. Still not tested against a real Entra tenant: the owner runs the runbook in `README.md` (Sign-in) in a sandbox tenant.
- **Notes for Future Engineers:** The AzMigrate appliance's Terraform root shows the `azuread_application` and app-role
  shape to copy; keep the pane's `/api/health` flat so the lab is unaffected.

### T-033 — Microsoft Graph reads for the identity-posture criteria

- **Priority:** P2
- **Description:** The identity half of T-027. Role assignments live in `authorizationresources` and directory
  posture in Entra ID (Microsoft Graph), neither of which the appliance reads in v1, so the `CA-ZT` identity criteria
  stay `unknown` in both editions.
- **Dependencies:** R-002 (Graph permissions in the access grant), T-027
- **Recommended Action:** Add an `authorizationresources` query to the Resource Graph collector for role
  assignments (no new permission: `Reader` suffices) and a Graph collector behind `CA_GRAPH_ENABLED=0` by default with
  `Directory.Read.All` application permission granted to the managed identity by the owner; surface both as additive
  evidence models and new `*-evidence` check kinds, never renaming the existing ones.
- **Status:** Blocked
- **Notes for Future Engineers:** Graph permissions are a separate consent from `Reader` and `Cost Management Reader`
  (T-011 note); confirm them during R-002 before writing the collector.

### T-034 — Commit the Terraform provider lock file

- **Priority:** P2
- **Description:** `infrastructure/terraform/appliance-azure` has no `.terraform.lock.hcl`, so `terraform init` resolves
  `azurerm ~> 4.0` to whatever is newest at the time and the provider hashes are not pinned (security review of PR #6,
  item 7). The lock file is generated by the `terraform` binary, which the authoring session did not have.
- **Dependencies:** None (owner machine with Terraform 1.9 or newer)
- **Recommended Action:** Owner step, one command from the repository root, then commit the file it writes.

  PowerShell or bash, identical:

  ```powershell
  terraform -chdir=infrastructure/terraform/appliance-azure providers lock -platform=linux_amd64 -platform=windows_amd64
  ```

  Success looks like `Success! Terraform has validated the lock file` and a new
  `infrastructure/terraform/appliance-azure/.terraform.lock.hcl` listing `hashicorp/azurerm` with `h1:` and `zh:` hashes
  for both platforms. Commit it; the `terraform` CI job then installs exactly that provider build, and Dependabot's
  terraform ecosystem proposes bumps.
- **Status:** Done 2026-10-10: `.terraform.lock.hcl` committed (azurerm 4.81.0, `h1:` and `zh:` hashes for linux_amd64 and windows_amd64), generated with Terraform 1.9.8 downloaded and checksum-verified from releases.hashicorp.com; `terraform validate` and `fmt -check` pass on it.
- **Notes for Future Engineers:** `.gitignore` deliberately does not ignore `.terraform.lock.hcl` (only `.terraform/`). Re-run the command above after any provider constraint change; Dependabot's terraform ecosystem proposes bumps against this file.
