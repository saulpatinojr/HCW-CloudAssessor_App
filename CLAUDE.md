# CLAUDE.md — working agreement for Claude Code in this repository

This is `saulpatinojr/HCW-CloudAssessor_App`, the **upstream product** of the Cloud Assessor: the `cloud-assessor-core`
engine (`packages/cloud-assessor-core`), its criteria catalog, and the **appliance edition** (`src/`) that reads a
client's own Azure scope under a user-assigned managed identity. Each `v*` tag publishes the engine as a wheel; the lab
edition `saulpatinojr/HCW-CloudAssessor_AddOn` tests and adopts it, and must stay technically unable to construct an
Azure credential (`tests/security/test_appliance_boundary.py`). Engine changes are made here, released, and adopted
downstream; never the reverse. `README.md` is the human intro; this file states the rules an agent must not infer wrongly.

- Read `README.md`, `TODO.md` (the backlog) and `REVIEW.md` (decisions that need the owner) before changing behaviour.
- Before claiming anything works, run `make setup`, then `make lint`, `make test` and `make test-security`. Never claim a
  check passed that you did not run; say which ones you could not run (for example Docker image builds).
- Dependencies are locked. After editing `pyproject.toml`, run `make lock` and commit `uv.lock` and both
  `requirements*.lock.txt` files together. Never edit them by hand.
- Azure is the only target platform. Never run `terraform apply`, and never call live Azure, from an agent session.
- Owner-pasteable commands: no placeholders; bash and PowerShell both acceptable; say which shell.
- Pull requests open ready for review and follow `.github/PULL_REQUEST_TEMPLATE.md`. Keep `CHANGELOG.md` current in the
  same pull request.

## Never weaken

- Identity is a managed identity (or the signed-in `az login` session locally). `AZURE_CLIENT_SECRET`,
  `AZURE_CLIENT_CERTIFICATE_PATH`, `AZURE_USERNAME`, `AZURE_PASSWORD` and `AZURE_TENANT_ID` are refused at startup.
- The `CA_PUBLIC_RESULTS` release gate: results routes answer `403 results_not_public` until it is `true`.
- Logs stay content-free, and secrets stay out of the repository (`tests/security/test_no_secrets.py`).
- The lab edition's inability to reach Azure (`tests/security/test_appliance_boundary.py`).
- The "not production" labels until the owner records R-003, R-005 and R-006 in `REVIEW.md`.
- Engine rules: evaluator kinds are only added, never renamed; `MODEL_VERSION` changes only when `Resource` changes. A
  change to any `packages/cloud-assessor-core` public surface reaches the lab edition at the next release; say so in
  the pull request.

## Documentation model

Markdown lives only in the five root files (`README.md`, `CHANGELOG.md`, `REVIEW.md`, `TODO.md`, `REFACTOR_APP.md`),
this `CLAUDE.md`, the platform templates under `.github/`, and the engine package's `README.md`.
`scripts/check-docs-governance.py` enforces this in CI. Everything else belongs in the GitHub Wiki. Documentation
destination is decided by content, not filename, and there must never be competing sources of truth.

## How to communicate with the owner

The owner is not a specialist in every tool used here. Write for a junior administrator with limited experience and no
memory of earlier sessions.

- **Be conversational and human.** Plain, friendly sentences. Say what happened and why it matters before the detail.
- **Assume little context.** Do not rely on repository history, ticket numbers or earlier chat. Restate what a thing is
  the first time it appears.
- **Avoid jargon.** When a technical term is unavoidable, explain it in a few words the first time, for example
  "a lockfile (the file that records the exact versions installed)".
- **When the owner must act, give numbered steps.** One action per step, short, saying where to click or what to run and
  which shell (bash or PowerShell). Say what they should see when it worked.
- **When you ask the owner a question, make it answerable.** Say what is being decided and why it matters, list the
  options in plain words with what each one means, give a recommendation, and say exactly how to answer (a word to reply
  with, or the steps and the link for where to click). Never ask a bare "A, B or C?" or "OK to proceed?".
- **When the owner has to fill in a form or a setting, give every value.** For each field, say the exact text to type or
  paste (name, description, URL), which boxes to tick or leave empty, and where to find it. Always supply a description
  wherever a form has a description field.
- **Include links.** Point to the exact settings page, the issue or pull request, and the official documentation
  (Microsoft Learn, GitHub Docs and similar) whenever one exists.
- **Be honest about status.** Separate what was checked, what is assumed, and what is blocked. Never present a guess as a result.

This applies to chat replies, pull request and issue text, and documentation. It does not apply to code comments or
machine-readable files, which keep following the surrounding style.
