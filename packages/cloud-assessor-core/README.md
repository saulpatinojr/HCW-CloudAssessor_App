# cloud-assessor-core

The Cloud Assessor engine: a declarative criteria catalog evaluated over a normalised Azure Resource Graph export.
Pure functions over a pydantic model; no HTTP framework, no cloud SDK, no network. Seeded in `HCW-CloudAssessor_AddOn`
and destined to move to `HCW-CloudAssessor_App` unchanged (AddOn ADR-0001; App `REFACTOR_APP.md` section 7.1).

```
src/cloud_assessor_core/
  model.py          MODEL_VERSION = 1; Resource, SourceRef, Criterion, Check, When, Finding, Scorecard, Assessment
  paths.py          get_path(obj, "a.b[*].c") -> PathResult(found, values)
  ingestion/        parse_arg_json, parse_arg_csv (ParsedRows), normalize -> list[Resource]
  catalog/          load_catalog, load_scoring, generated JSON Schema (draft 2020-12), host allow-list
  evaluate/         six evaluator kinds; evaluate(resources, catalog) -> list[Finding]; unknown_by_design
  score.py          score(findings, scoring, overrides) -> list[Scorecard]; unknown lowers coverage, never score
  report/           render_markdown, to_json, findings_csv, make_bundle, zip_bytes, NOT_AN_AUDIT
  redaction.py      scrub, assert_no_visitor_data (the log path only)
  assess.py         assess(resources, catalog, scoring, ...) -> Assessment
catalog/
  criteria.json     25 paraphrased, attributed criteria (text is the single replaceable field)
  schema.json       generated from the model (scripts/check-catalog.py --write-schema)
  scoring.json      severity and pillar weights
tests/              pytest, beside the modules they cover
```

The installed wheel carries the catalog as `cloud_assessor_core/catalog_data`; the source tree reads `catalog/` next to
`src/`. `load_catalog()` resolves whichever exists and fails closed on any validation or schema drift.
