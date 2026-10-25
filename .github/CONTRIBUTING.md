# Contributing

Thank you for helping. This guide says how a change gets from your machine into `main`. It is short on purpose:
`CLAUDE.md` holds the rules an AI coding agent must follow (agents and people share the same ones), `README.md` is the
overview, `TODO.md` is the work queue and `REVIEW.md` lists the decisions that need the owner.

## Before you start

- Search the existing issues and pull requests first.
- For anything bigger than a small fix, open an issue (choose a form on the **New issue** page) so the outcome and the
  acceptance criteria are agreed before you write code.
- Never put credentials, tokens, private keys, connection strings, personal data, customer data, or tenant,
  subscription or resource identifiers in code, tests, fixtures, logs, issues or pull requests. Samples use the
  fictional subscription `00000000-0000-0000-0000-000000000001`.
- A vulnerability is not an issue. Report it privately as `.github/SECURITY.md` describes.
- By taking part you agree to the `.github/CODE_OF_CONDUCT.md`.

## What lives where

- **Engine:** `packages/cloud-assessor-core` (pydantic only, no cloud SDK) and its criteria catalog. It is published as a
  wheel on every `v*` tag and adopted by the lab edition, `HCW-CloudAssessor_AddOn`. Engine changes are made here, never
  the other way round, and a change to its public surface reaches the lab edition at the next release: say so in the pull
  request.
- **Appliance:** `src/cloud_assessor_appliance`, the live, read-only front for one client's own Azure scope. Azure is the
  only target platform.
- **Infrastructure:** `infrastructure/docker` (one Dockerfile, two targets) and `infrastructure/terraform/appliance-azure`.
- **Documents:** the repository keeps `README.md`, `CHANGELOG.md`, `REVIEW.md`, `TODO.md` and `REFACTOR_APP.md`, plus
  `CLAUDE.md` and the community files in `.github/` (this guide, the security policy, the code of conduct and the pull
  request template). `scripts/check-docs-governance.py` fails the build on any other markdown file. Long-form
  documentation goes to the GitHub Wiki.
- **Workflows:** `.github/workflows/` holds a fixed set of files that `tests/unit/test_workflows.py` pins. Add a job to
  an existing workflow rather than a new file, and keep the rules that test enforces: every action pinned to a full
  commit SHA with its version in a comment, top-level `permissions: contents: read`, runner `ubuntu-26.04`.

## Set up and check your change

Python 3.14.6 or newer and [uv](https://docs.astral.sh/uv/) are needed. From the repository root (bash or PowerShell):

```bash
make setup
make lint
make test
make test-security
```

`make lint` runs ruff, the catalog check, the documentation governance check, the release version check, the base-image
check and the lockfile check; the `lint` job of CI runs the same list. Without `make`, the commands are in the
`Makefile`. Image builds and `terraform validate` run in CI; run them locally only if you have Docker or Terraform, and
say in the pull request which checks you could not run. Never run `terraform apply` and never call live Azure from an
automated session.

## Rules that are easy to get wrong

- **Dependencies are locked.** After you change `pyproject.toml`, run `make lock` and commit `uv.lock` and both
  `requirements*.lock.txt` files together. Never edit them by hand.
- **Never weaken** the managed-identity-only rule, the `CA_PUBLIC_RESULTS` release gate, the content-free logs, the
  scope allow-list or the lab edition's inability to reach Azure. `CLAUDE.md` lists them with the tests that guard them.
- **Evaluator kinds are only added, never renamed**, and `MODEL_VERSION` changes only when `Resource` changes.
- **Versions are changed only in a release pull request.** One version covers the engine, the appliance and the image;
  `scripts/check-release-version.py` fails a pull request in which the places that name it disagree. The policy and the
  steps are in the "Releasing and versioning" section of `README.md`.
- **Secrets stay out of the repository.** `.gitleaks.toml` has a narrow allow-list; do not widen it without a reason in
  the same change.

## Pull requests

- Branch from the current `main` and keep each pull request to one purpose.
- Use short, plain commit subjects in the style of the history, for example `ci(release): ...`, `fix(api): ...`,
  `build(deps): ...`.
- Open the pull request ready for review and fill in `.github/PULL_REQUEST_TEMPLATE.md`. State the commands you ran
  and what each result proves, say what you did not run and why, and say whether the evidence is static, local, from CI,
  or from a live environment.
- Add or update tests for changed behaviour, including the failure and denial paths. The coverage gate is 85 percent.
- Add a line under `## [Unreleased]` in `CHANGELOG.md` for what changed. Record unrelated findings in `TODO.md`
  (engineering work) or `REVIEW.md` (needs a human decision) instead of widening the pull request.
- Do not merge while a required check, a review or a security finding is open. Do not push straight to `main`.
