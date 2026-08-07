# TODO — Engineering Work Queue

This is the authoritative engineering backlog for the repository. Every actionable
engineering item discovered anywhere in this repository is recorded here so an engineer
can resume work without rediscovering findings.

Items that require a human decision, approval, or access grant are **not** here — they are
in [REVIEW.md](REVIEW.md) and are referenced below as `R-00n` dependencies.

Items are ordered chronologically within each phase, phases are ordered by dependency, and
no item depends on an item in a later phase.

**Priority scale:** P0 critical · P1 high · P2 medium · P3 low
**Status values:** Not started · Blocked · In progress · Done

## Contents

| Phase | Theme | Items |
|-------|-------|-------|
| [Phase 1](#phase-1--critical-fixes-and-repository-foundation) | Critical fixes and repository foundation | T-001 – T-006 |
| [Phase 2](#phase-2--security-improvements) | Security improvements | T-007 – T-012 |
| [Phase 3](#phase-3--stability-improvements) | Stability improvements | T-013 – T-016 |
| [Phase 4](#phase-4--technical-debt) | Technical debt | T-017 – T-019 |
| [Phase 5](#phase-5--feature-enhancements) | Feature enhancements | T-020 – T-028 |
| [Phase 6](#phase-6--documentation-improvements) | Documentation improvements | T-029 – T-031 |

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
- **Status:** Blocked
- **Notes for Future Engineers:** Do not infer the stack from `.gitignore` alone. If R-001
  lands on a multi-language design (for example Python collectors plus a TypeScript
  report UI), lay out the repository as a monorepo from the start rather than retrofitting
  one later.

### T-002 — Add a LICENSE file

- **Priority:** P0
- **Description:** The repository has no `LICENSE` file and GitHub reports no license.
  Default copyright applies, which leaves contribution and distribution rights undefined.
- **Dependencies:** R-003 (no license selected)
- **Recommended Action:** Add the `LICENSE` file matching the decision recorded in R-003
  and add the corresponding SPDX identifier to the project manifest created in T-001.
- **Status:** Blocked
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
- **Status:** Not started
- **Notes for Future Engineers:** CODEOWNERS only enforces review when branch protection
  requires owner review — pair this with T-006.

### T-004 — Extend `.gitignore` beyond the Python-only template

- **Priority:** P2
- **Description:** `.gitignore` is the stock GitHub Python template. It has no entries for
  Terraform state, Node modules, IDE directories, cloud CLI caches, or assessment output
  files — all plausible once implementation starts. Notably it does not ignore credential
  files beyond `.env`.
- **Dependencies:** T-001
- **Recommended Action:** Extend `.gitignore` for the stack chosen in T-001, and add
  explicit patterns for cloud credential files (`*.pem`, `credentials.json`,
  `~/.oci/config` copies, AWS/GCP/OCI CLI caches) and for generated assessment output.
- **Status:** Blocked
- **Notes for Future Engineers:** `.gitignore` is not a security control. Pair this with
  T-008 (push protection) rather than relying on ignore rules to keep secrets out.

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
- **Status:** Blocked
- **Notes for Future Engineers:** Keep the workflow name and job names stable from the
  start — T-006 references them as required status checks, and renaming them silently
  drops the protection.

### T-006 — Enable branch protection and required status checks on `main`

- **Priority:** P1
- **Description:** `main` is the default branch and has no protection configured, so it can
  be pushed to directly and merged into without review or a passing build.
- **Dependencies:** T-005
- **Recommended Action:** Require a pull request before merging, require the CI checks from
  T-005 to pass, require branches to be up to date, and block force pushes and deletion.
- **Status:** Blocked
- **Notes for Future Engineers:** This is a repository settings change, not a file change,
  so it will not appear in any diff. Record that it was done in `CHANGELOG.md` so the next
  engineer does not have to check the settings page to find out.

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
- **Status:** Not started
- **Notes for Future Engineers:** `.github/SECURITY.md` is a platform-recognized exception
  to the no-documentation-in-dot-folders rule. Keep it minimal so it stays an exception.

### T-008 — Verify secret scanning and push protection are enabled

- **Priority:** P1
- **Description:** Two secret scanners now run on pull requests: a GitGuardian Security
  Checks app, and TruffleHog via qlty (see T-006). What has not been confirmed is whether
  GitHub's native secret scanning and — more importantly — **push protection** are enabled.
  Both current scanners report after a push has landed; only push protection blocks the
  push. A multi-cloud assessment tool is a high-risk place to accidentally commit a
  credential.
- **Dependencies:** None
- **Recommended Action:** Confirm in repository settings whether native secret scanning and
  push protection are enabled, and record the result. Decide whether all three scanners are
  wanted or whether the overlap between GitGuardian and TruffleHog should be resolved (see
  T-010). If push protection is unavailable on the current plan, add a pre-push
  secret-detection hook in T-015.
- **Status:** Not started
- **Notes for Future Engineers:** Confirm this before T-011 introduces any credential
  handling code or example configuration.

### T-009 — Add Dependabot configuration

- **Priority:** P2
- **Description:** There is no `.github/dependabot.yml`, so neither dependencies nor GitHub
  Actions versions will receive update pull requests.
- **Dependencies:** T-001
- **Recommended Action:** Add `.github/dependabot.yml` covering the package ecosystem
  chosen in T-001 and the `github-actions` ecosystem. Group patch updates to limit noise.
- **Status:** Blocked
- **Notes for Future Engineers:** Cloud provider SDKs release frequently. Grouping AWS,
  GCP, and OCI SDK updates into a single weekly pull request keeps the queue manageable.

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
- **Status:** Blocked
- **Notes for Future Engineers:** Start these jobs as non-blocking, triage the initial
  findings into this file, then make them required in T-006 once the baseline is clean.
  Note that `qlty check` fails the build outright when `.qlty/qlty.toml` is absent, so do
  not delete that file to silence findings — configure the plugins instead.

### T-011 — Define the multi-cloud credential handling standard

- **Priority:** P0
- **Description:** The assessment must authenticate to AWS, GCP, and OCI. There is no
  decision recorded on how credentials are supplied, scoped, rotated, or kept out of logs
  and assessment output.
- **Dependencies:** R-002 (target cloud access not provisioned)
- **Recommended Action:** Standardize on short-lived credentials via OIDC workload identity
  federation for CI, and on the provider default credential chain for local runs. Prohibit
  credential values in configuration files, forbid logging of credential material, and
  document the required read-only permission set per provider in the wiki.
- **Status:** Blocked
- **Notes for Future Engineers:** OCI's identity model differs meaningfully from AWS and
  GCP — it uses API signing keys with a tenancy, user, and fingerprint rather than
  role assumption. Design the credential abstraction to accommodate that rather than
  assuming a uniform role-assumption model across all three providers.

### T-012 — Add output redaction and a data-handling guard

- **Priority:** P1
- **Description:** Assessment output will contain resource identifiers, account and tenancy
  identifiers, network configuration, and cost data. Nothing currently prevents that
  material from being written into the repository, into CI logs, or into a shared report.
- **Dependencies:** R-006 (output data classification undecided), T-001
- **Recommended Action:** Implement a redaction layer applied to all output paths, honoring
  the classification decided in R-006. Add a CI check that fails if files matching the
  assessment output pattern are committed.
- **Status:** Blocked
- **Notes for Future Engineers:** Apply redaction at the serialization boundary, not at
  each call site — a single guarded writer is far easier to audit than scattered redaction
  calls, and it is the difference between a reviewable control and a hope.

---

## Phase 3 — Stability Improvements

### T-013 — Add linting and formatting configuration

- **Priority:** P2
- **Description:** No linter or formatter configuration exists. The `.ruff_cache/` entry in
  `.gitignore` hints at Ruff but no Ruff configuration is committed.
- **Dependencies:** T-001, T-005
- **Recommended Action:** Commit linter and formatter configuration for the chosen stack
  and wire it into the CI workflow from T-005.
- **Status:** Blocked
- **Notes for Future Engineers:** Land this before the first substantial feature branch.
  Introducing a formatter after the code exists produces a large reformat commit that
  obscures history.

### T-014 — Add the test framework and a first smoke test

- **Priority:** P1
- **Description:** There are no tests and no test framework. `.gitignore` anticipates
  `pytest` and coverage artifacts, but nothing is configured.
- **Dependencies:** T-001, T-005
- **Recommended Action:** Add the test framework, a coverage configuration, and one smoke
  test that exercises the entry point. Wire it into CI. Establish the fixture strategy for
  recorded cloud API responses at the same time.
- **Status:** Blocked
- **Notes for Future Engineers:** The fixture strategy depends on R-006 — until the data
  classification decision lands, do not commit fixtures captured from a real environment.
  Use synthetic fixtures, and scrub account, project, and tenancy identifiers.

### T-015 — Add pre-commit hooks

- **Priority:** P3
- **Description:** No pre-commit configuration exists, so lint and format failures are only
  discovered in CI.
- **Dependencies:** T-013
- **Recommended Action:** Add a pre-commit configuration running the formatter, the linter,
  and a secret-detection hook. Document the one-line install in `README.md`.
- **Status:** Blocked
- **Notes for Future Engineers:** Keep the hook set identical to the CI checks. Hooks that
  diverge from CI cause more confusion than they prevent.

### T-016 — Add markdown link checking for the governance documents

- **Priority:** P3
- **Description:** `README.md`, `CHANGELOG.md`, `REVIEW.md`, and `TODO.md` cross-link to
  each other and to the wiki. Nothing verifies those links stay valid.
- **Dependencies:** T-005
- **Recommended Action:** Add a link-checking job to CI covering the four root markdown
  files. Allow the wiki links to be checked leniently until T-029 populates the wiki.
- **Status:** Blocked
- **Notes for Future Engineers:** The repository is private, so an unauthenticated link
  checker will report wiki links as 404. Configure it with a token or exclude the wiki host
  until T-030 completes.

---

## Phase 4 — Technical Debt

### T-017 — Complete the issue template set

- **Priority:** P3
- **Description:** `.github/ISSUE_TEMPLATE/` contains only `feature_request.md`. There is no
  bug report template and no `config.yml`, so bug reports arrive unstructured and there is
  no way to route reporters elsewhere.
- **Dependencies:** None
- **Recommended Action:** Add `bug_report.md` and `config.yml`. The bug template should
  request the target cloud provider, the assessment scope in use, and redacted output —
  the fields that determine whether a report is actionable for this project.
- **Status:** Not started
- **Notes for Future Engineers:** Remind reporters in the template to redact account,
  project, and tenancy identifiers before pasting output. This is a private repository, but
  the habit should hold regardless.

### T-018 — Add a pull request template

- **Priority:** P3
- **Description:** No `.github/PULL_REQUEST_TEMPLATE.md` exists, so pull request bodies are
  unstructured.
- **Dependencies:** None
- **Recommended Action:** Add a short template with sections for summary, related issue or
  TODO item, verification performed, and documentation updates. Include a checkbox
  confirming that any new documentation went to the correct destination under the
  four-file model.
- **Status:** Not started
- **Notes for Future Engineers:** Keep it short. Long templates get deleted rather than
  filled in.

### T-019 — Add a documentation governance CI check

- **Priority:** P2
- **Description:** The four-file documentation model is currently maintained by convention
  alone. Nothing prevents a new `docs/` directory, a non-root `README.md`, or a design
  document in `.github/`.
- **Dependencies:** T-005
- **Recommended Action:** Add a CI check that fails when a markdown file exists outside the
  approved set: the four root files plus a small allowlist of platform-required templates
  under `.github/`. Point the failure message at the destination mapping in `README.md`.
- **Status:** Blocked
- **Notes for Future Engineers:** This check is what keeps the model from eroding. Without
  it, the four-file structure lasts until the first engineer who finds it inconvenient.

---

## Phase 5 — Feature Enhancements

This phase delivers the assessment itself. The three evaluation spikes are deliberately
first — their outcome shapes the collector design.

### T-020 — Evaluation spike: Quick Review / AzQR integration

- **Priority:** P1
- **Description:** Issue #1 proposes integrating `saulpatinojr/Azure-AzQR` for quick review
  capability. The integration mode is unspecified.
- **Dependencies:** R-004 (third-party integration adoption not approved)
- **Recommended Action:** Timebox a spike assessing what AzQR covers, whether it can be
  invoked as a subprocess or consumed as a library, its output schema, and whether it
  extends beyond Azure. Record findings in the wiki and post the recommendation on issue #1.
- **Status:** Blocked
- **Notes for Future Engineers:** AzQR is Azure-focused while the stated assessment targets
  are AWS, GCP, and OCI. Establish early whether Azure is an assessment target at all —
  this is the open question in R-001.

### T-021 — Evaluation spike: Zero Trust Assessment and Prowler integration

- **Priority:** P1
- **Description:** Issue #2 proposes integrating `microsoft/zerotrustassessment` and
  `prowler-cloud/prowler` for Zero Trust coverage.
- **Dependencies:** R-004
- **Recommended Action:** Timebox a spike comparing the two. Prowler covers AWS, GCP, and
  Azure natively, which overlaps directly with the target platforms; assess its OCI
  coverage specifically, since that is the likeliest gap. Record findings in the wiki and
  post the recommendation on issue #2.
- **Status:** Blocked
- **Notes for Future Engineers:** Prowler has a commercial edition alongside its open
  source distribution. Confirm the licensing conclusion from R-004 before writing any code
  against it.

### T-022 — Evaluation spike: Governance Visualizer integration

- **Priority:** P2
- **Description:** Issue #3 proposes integrating
  `Azure/Azure-Governance-Visualizer-Accelerator`.
- **Dependencies:** R-004
- **Recommended Action:** Timebox a spike assessing whether the accelerator's visualization
  output is reusable for multi-cloud reporting, or whether only its reporting approach is
  worth borrowing. Record findings in the wiki and post the recommendation on issue #3.
- **Status:** Blocked
- **Notes for Future Engineers:** This is a visualization and reporting concern, not a
  collection concern. It can be deferred behind T-028 without blocking anything.

### T-023 — Author the benchmark criteria catalog

- **Priority:** P0
- **Description:** The assessment benchmarks against the FinOps Foundation Framework, the
  Azure Well-Architected Cost Optimization pillar, and Zero Trust principles, but no
  machine-readable catalog of criteria exists.
- **Dependencies:** R-005 (framework content usage rights unconfirmed), T-001
- **Recommended Action:** Define a criteria schema (identifier, source framework, pillar,
  severity, applicable platforms, evaluation logic reference, remediation guidance) and
  populate it. Keep the catalog declarative and separate from collector code.
- **Status:** Blocked
- **Notes for Future Engineers:** R-005 governs whether criteria text can be reproduced
  verbatim. Design the schema so criteria text is a single replaceable field — that way a
  paraphrase-only outcome is a data change, not a code change.

### T-024 — Implement the assessment data model

- **Priority:** P0
- **Description:** No common representation exists for collected resources, evaluated
  findings, or scores across three heterogeneous providers.
- **Dependencies:** T-023
- **Recommended Action:** Define a provider-neutral resource and finding model with a
  documented version field, so provider-specific collectors normalize into one shape and
  the report layer reads only the normalized form.
- **Status:** Blocked
- **Notes for Future Engineers:** Version the model from the first commit. Assessment
  results are compared over time, and an unversioned model makes historical comparison
  unreliable the first time the shape changes.

### T-025 — Implement the AWS collector

- **Priority:** P1
- **Description:** No collection capability exists for AWS.
- **Dependencies:** T-011, T-024
- **Recommended Action:** Implement read-only collection for the container, cost, and
  identity resources required by the T-023 catalog. Handle pagination, throttling with
  backoff, and multi-region and multi-account enumeration.
- **Status:** Blocked
- **Notes for Future Engineers:** Regional enumeration dominates runtime. Make the region
  set configurable and parallelize per region from the start rather than retrofitting it.

### T-026 — Implement the GCP collector

- **Priority:** P1
- **Description:** No collection capability exists for GCP.
- **Dependencies:** T-011, T-024
- **Recommended Action:** Implement read-only collection for GKE, billing, and IAM
  resources required by the T-023 catalog, with project and folder enumeration.
- **Status:** Blocked
- **Notes for Future Engineers:** GCP billing data lives in BigQuery export rather than in
  a resource API. That is a separate access grant and should be raised in R-002 if it was
  not included in the original sandbox request.

### T-027 — Implement the OCI collector

- **Priority:** P1
- **Description:** No collection capability exists for OCI.
- **Dependencies:** T-011, T-024
- **Recommended Action:** Implement read-only collection for OKE, cost, and identity
  resources required by the T-023 catalog, with compartment traversal.
- **Status:** Blocked
- **Notes for Future Engineers:** OCI's compartment hierarchy has no direct equivalent in
  AWS or GCP, and third-party tooling coverage for OCI is thinner than for the other two.
  Budget more time here than for T-025 and T-026, and expect less to be reusable from the
  spikes in T-020 through T-022.

### T-028 — Implement scoring and report generation

- **Priority:** P1
- **Description:** No scoring logic or report output exists.
- **Dependencies:** T-024, T-012
- **Recommended Action:** Implement criteria evaluation against collected data, scoring
  aggregated by framework and pillar, and report rendering in the format decided in R-001.
  All output must pass through the redaction layer from T-012.
- **Status:** Blocked
- **Notes for Future Engineers:** Keep scoring weights in configuration rather than in
  code. Weighting is the part clients most often want adjusted per engagement.

---

## Phase 6 — Documentation Improvements

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
  | `Assessment-Scope` | Deliverable format, consumers, cadence, target platforms | R-001 |
  | `Architecture-Overview` | Component design, collector and scoring boundaries | T-024 |
  | `Benchmark-Criteria` | Framework mapping, criteria schema, attribution notices | T-023, R-005 |
  | `Cloud-Access-Requirements` | Per-provider read-only permission sets and federation setup | T-011, R-002 |
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
