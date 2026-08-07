# Review — Human-Resolvable Blockers

This file records **only** items that an engineer cannot resolve independently. Every item
requires a decision, an approval, an access grant, or external input from a named owner.

Bugs, refactoring, technical debt, tests, and documentation work do not belong here — they
belong in [TODO.md](TODO.md).

**Open blockers: 8**

| ID | Blocker | Required owner | Blocks |
|----|---------|----------------|--------|
| R-001 | Assessment deliverable format undefined | Product owner | All implementation |
| R-002 | Read-only access to the Azure assessment target not provisioned | Azure platform owner | Collector development and testing |
| R-003 | No license selected for the repository | Repository owner / Legal | Contribution, reuse, distribution |
| R-004 | Third-party integration adoption not approved | Repository owner / Legal | Issues #1, #2, #3 |
| R-005 | Benchmark framework content usage rights unconfirmed | Legal | Publishing assessment criteria |
| R-006 | Assessment output data classification undecided | Security / Compliance | Storing and sharing results |
| R-007 | GitHub Wiki not writable by automation | Repository admin | Wiki documentation migration |
| R-008 | `qlty check` errors Cloud-side and the log is not readable | Repository admin / qlty account owner | A permanently red check on every pull request |

---

## R-001 — Assessment deliverable format is undefined

**Problem**
The repository states what the assessment measures (FinOps Foundation Framework, Azure
Well-Architected Cost Optimization pillar, Zero Trust principles) and where (Azure), but
not what the assessment *is*. It could be a CLI, a scheduled data collector, a report
generator, a dashboard, a set of infrastructure-as-code policy modules, or a consulting
questionnaire with supporting tooling.

The target-platform half of this blocker is **resolved**: the assessment targets Azure
exclusively. AWS, GCP, and OCI are out of scope and are not planned.

**Why it blocks progress**
Language, runtime, dependency manager, packaging, distribution, testing strategy, and CI
design all follow from this decision. Any skeleton committed before it is settled is
likely to be discarded. The repository has been empty of code since creation, so nothing
constrains the choice today.

**Required owner**
Product owner for the assessment offering.

**Required action**
Decide and record: (a) the primary deliverable format, (b) who consumes the output
(internal engineers, client executives, or auditors), and (c) whether the assessment runs
continuously or as a point-in-time engagement.

**Impact if unresolved**
No implementation work can start. All of Phase 1 and everything downstream in `TODO.md`
stays blocked.

**References**
- `README.md` — Overview
- Repository description
- `TODO.md` — T-001, T-020

**Recommended next step**
A single scoping session producing a one-page decision, published as a wiki page
(`Assessment-Scope`) and reflected in `README.md`.

---

## R-002 — Read-only access to the Azure assessment target is not provisioned

**Problem**
No Azure subscription or management group has been designated for development or testing,
and no read-only credentials or workload identity federation have been set up.

**Why it blocks progress**
Collectors cannot be written or verified against real API responses. Mocked fixtures alone
cannot confirm required permissions, API throttling behavior, or resource-shape
assumptions.

**Required owner**
Azure platform owner for the target tenant, plus whoever administers Entra ID app
registrations and federated credentials.

**Required action**
Provision a non-production subscription with the `Reader` role — and `Cost Management
Reader` for cost data, which `Reader` alone does not grant — scoped to the resource types
the assessment reads. Confirm the preferred authentication mechanism (workload identity
federation is preferred over client secrets). Confirm the assessment scope: single
subscription, management group, or whole tenant.

**Impact if unresolved**
Collector work in Phase 5 cannot be validated. Any implementation would be speculative and
would need rework once real access arrives.

**References**
- `README.md` — Configuration
- `TODO.md` — T-011, T-025, T-026, T-027

**Recommended next step**
Request the sandbox subscription and record the tenant, subscription, and management group
identifiers plus the federation configuration in the wiki.

---

## R-003 — No license has been selected for the repository

**Problem**
The repository contains no `LICENSE` file and GitHub reports no license for it. The
repository is currently private.

**Why it blocks progress**
Without a license, default copyright applies. Contributors have no grant of rights, the
code cannot be shared with clients or partners, and any decision to vendor or fork
third-party code (see R-004) cannot be evaluated for compatibility.

**Required owner**
Repository owner, with legal review if the assessment will be delivered to clients.

**Required action**
Choose a license (or explicitly confirm the repository stays proprietary and private) and
state the decision. If proprietary, record the intended distribution model for assessment
outputs delivered to clients.

**Impact if unresolved**
Blocks external contribution, blocks any open-source integration decision, and creates
legal ambiguity around anything delivered from this repository.

**References**
- Repository has no `LICENSE` file
- `TODO.md` — T-002

**Recommended next step**
Confirm proprietary versus open-source intent, then add the corresponding `LICENSE` file.

---

## R-004 — Third-party integration adoption is not approved

**Problem**
Three open issues propose integrating existing tools, but none states whether the
integration means invoking the tool, vendoring its code, forking it, or reimplementing its
checks — and no license compatibility review has been done.

| Issue | Proposed integration | Upstream |
|-------|---------------------|----------|
| #1 | Quick Review | `saulpatinojr/Azure-AzQR` |
| #2 | Zero Trust Assessment | `microsoft/zerotrustassessment`, `prowler-cloud/prowler` |
| #3 | Governance Visualizer | `Azure/Azure-Governance-Visualizer-Accelerator` |

The Azure-only scope decision raises the stakes here. All three proposals are Azure or
Microsoft tools, so they are now squarely on target rather than partial fits — the
question is no longer whether they cover the right platform but how much of the assessment
they already implement.

**Why it blocks progress**
Integration mode determines the architecture. Invoking a tool as a subprocess, consuming
it as a library, and reimplementing its rules produce entirely different designs, runtime
dependencies, and licensing obligations. Prowler in particular is Apache-2.0 with a
commercial edition; its terms need review before its output or code is embedded in a
client deliverable. With the scope narrowed to Azure, only Prowler's Azure provider is
relevant, which weakens the case for taking on a large multi-cloud dependency.

**Required owner**
Repository owner for the architectural decision; legal for license compatibility.

**Required action**
For each of the three integrations, decide adopt / invoke / reimplement / decline, and
confirm license compatibility with the decision made in R-003.

**Impact if unresolved**
Phase 5 evaluation spikes can proceed, but no integration can be committed. Building
against the wrong integration mode would mean rewriting the collector layer.

**References**
- Issues #1, #2, #3
- `TODO.md` — T-020, T-021, T-022

**Recommended next step**
Timebox one evaluation spike per issue (tracked in `TODO.md`), then hold a single decision
review covering all three at once.

---

## R-005 — Benchmark framework content usage rights are unconfirmed

**Problem**
The assessment benchmarks against the FinOps Foundation Framework and the Azure
Well-Architected Framework Cost Optimization pillar. It is not established whether the
project may reproduce those frameworks' criteria text, maturity definitions, or scoring
rubrics in code, in the wiki, or in client-facing reports.

**Why it blocks progress**
If verbatim reproduction is not permitted, criteria must be paraphrased and attributed,
which changes the data model, the report templates, and the wiki content. Discovering this
after the criteria catalog is built means reworking every check.

**Required owner**
Legal, with input from whoever holds the organization's FinOps Foundation membership.

**Required action**
Confirm the permitted use of FinOps Foundation Framework and Microsoft Well-Architected
Framework material in an internal tool and in client deliverables, including any required
attribution or trademark notice.

**Impact if unresolved**
The criteria catalog cannot be authored safely, blocking the core of the assessment.

**References**
- `README.md` — Overview
- `TODO.md` — T-023

**Recommended next step**
Request written confirmation of permitted use and record the required attribution text in
the wiki so it can be applied consistently.

---

## R-006 — Assessment output data classification is undecided

**Problem**
Assessment runs will capture cloud resource inventory, configuration, identity posture,
and cost data. There is no decision on how that output is classified, where it may be
stored, how long it is retained, or whether sample or fixture data derived from real
environments may be committed to this repository.

**Why it blocks progress**
The answer determines whether test fixtures can be committed, whether results may be
written to the repository or to a CI artifact store, what redaction is required before a
report leaves the tool, and whether the repository can ever become public.

**Required owner**
Security and compliance owner, with the client-engagement owner where client environments
are assessed.

**Required action**
Assign a data classification to assessment inputs and outputs, and state the retention
location, retention period, and redaction requirements. Explicitly state whether
real-environment-derived fixtures may be committed.

**Impact if unresolved**
Test data strategy is blocked, CI artifact handling is blocked, and there is a real risk of
committing customer-identifying infrastructure detail before a rule exists to prevent it.

**References**
- `TODO.md` — T-012, T-014

**Recommended next step**
Get a written classification decision before the first collector writes output to disk.

---

## R-007 — GitHub Wiki is enabled but not writable by automation

**Problem**
The wiki is enabled on the repository, but the credentials available to automation in this
environment cannot push to `Work-Complete_Cloud_Assessment.wiki.git`. GitHub does not
expose wiki content through its REST or GraphQL API, so the wiki can only be written by an
authenticated git push or through the web UI.

**Why it blocks progress**
The documentation model directs all long-form documentation to the wiki. Until the wiki is
writable, architecture, design, runbook, and research content has nowhere sanctioned to
live, and contributors are pushed toward re-adding stray markdown files to the repository.

**Required owner**
Repository administrator.

**Required action**
Either create the wiki pages manually from the proposals in `TODO.md` Phase 6, or grant
push access to `Work-Complete_Cloud_Assessment.wiki.git` for the automation identity so
pages can be created and maintained programmatically. Note that a wiki must have at least
one page created through the web UI before its git remote is clonable.

**Impact if unresolved**
Documentation sprawl returns. The four-file model holds only if there is a working
destination for everything the four files exclude.

**References**
- Repository settings — wiki enabled
- `TODO.md` — T-029, T-030

**Recommended next step**
Create the wiki `Home` page through the web UI, then decide whether automation needs push
access for ongoing maintenance.

---

## R-008 — `qlty check` errors Cloud-side and the build log is not readable

**Problem**
The qlty GitHub App posts a `qlty check` commit status that reports
`Build errored. Check the log for more information.` on every commit. The linked build log
lives behind a qlty.sh login, so it cannot be read from the repository or from CI.

One genuine cause was found and fixed: the repository had no `.qlty/qlty.toml`, so the CLI
aborted with `Qlty must be set up in this repository. Try: qlty init`. Committing the
generated configuration did **not** clear the status — the build errored again on the
commit that added it.

With the configuration in place, every invocation the service plausibly runs now passes
locally against the branch head:

| Command | Result |
|---------|--------|
| `qlty check --all` | `✔ No issues`, exit 0 |
| `qlty check --upstream main` | `✔ No issues` |

The second case matters because it rules out the most likely remaining repository-side
explanation — that the analysis fails while comparing against a base branch that has no
qlty configuration. It does not.

**Why it blocks progress**
The remaining fault is in the qlty Cloud project, not in repository contents, and
diagnosing it requires reading a log that only an authenticated qlty account holder can
see. Nothing further can be established from inside the repository. Meanwhile the status
is red on every pull request, which trains reviewers to ignore a failing check — and makes
the required-status-check configuration in T-006 impossible to enable honestly.

**Required owner**
Repository administrator, or whoever owns the qlty.sh account the project is registered
under.

**Required action**
Open the build log in the qlty dashboard and either apply the fix it indicates or raise it
with qlty support. Two candidates worth checking first: whether the project's initial
default-branch analysis errored when the project was added (the default branch had no
`.qlty/qlty.toml` at that time, and the documented setup flow analyzes the default branch
immediately on project creation), and whether the account's plan or trial is active for a
private repository. The qlty troubleshooting guide also documents transient `U10` and `U11`
errors that are resolved by retrying the analysis.

If qlty is not actually wanted on this repository, uninstalling the GitHub App is a valid
resolution and should be recorded as such.

**Impact if unresolved**
A permanently failing status on every pull request. Branch protection with required checks
(T-006) cannot be turned on without either excluding this check or blocking all merges.

**References**
- `qlty check` status on PR #4, commits `92c097d` and `3dca07e`
- `.qlty/qlty.toml`
- `TODO.md` — T-006, T-010
- https://docs.qlty.sh/cloud/troubleshooting

**Recommended next step**
Read the build log at the URL in the commit status and report what it says. Until then this
check should not be added to branch protection.
