## Summary

<!-- What changes and why. Name the REFACTOR_APP.md section, the TODO.md item (T-nnn) or the REVIEW.md blocker (R-nnn). -->

## Related issue or decision

<!-- Issue number, TODO item or owner decision this implements. -->

## Type of change

- [ ] Engine (`packages/cloud-assessor-core`): a change to the published package and to the downstream edition (`HCW-CloudAssessor_AddOn` adopts it through `core-update`)
- [ ] Appliance (`src/cloud_assessor_appliance`)
- [ ] Infrastructure (`infrastructure/`) or workflows
- [ ] Documentation only (the four root files and `REFACTOR_APP.md`)

## Verification

- [ ] `uv run ruff check . && uv run ruff format --check .` — result:
- [ ] `uv run pytest -q --cov=packages --cov=src` — result (tests, coverage):
- [ ] `uv run pytest tests/security tests/packaging -q` — result:
- [ ] `uv run python scripts/check-catalog.py` and `scripts/check-docs-governance.py` — result:
- [ ] `terraform -chdir=infrastructure/terraform/appliance-azure validate` — result, or CI run link:
- [ ] Image build and boundary proof (both targets) — CI run link:
- [ ] Checks not run and why:

## Security and data review

- [ ] No real tenant, subscription or resource identifiers anywhere (samples use `00000000-0000-0000-0000-000000000001`)
- [ ] No client secret path; managed identity only; `.env.example` has no values
- [ ] Nothing weakens the scope allow-list, the `CA_PUBLIC_RESULTS` gate, the refusal of forbidden variables, the content-free logs or the `lab` boundary proof
- [ ] Generated code touching `identity.py`, `scope.py` or a collector had a security review

## Documentation and operations

- [ ] `CHANGELOG.md` `[Unreleased]` updated; `TODO.md` / `REVIEW.md` statuses moved where a change closes or opens an item
- [ ] Any new documentation went to the correct destination under the four-file model (root file or wiki), never a new `docs/` file

## AI provenance

- [ ] Code created or changed by an AI coding partner; reviewer applies the review -> fix -> current-head verification cycle
