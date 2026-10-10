"""Pins the sample's results: every criterion yields at least one pass and at least one fail or unknown."""

from collections import defaultdict
from pathlib import Path

import pytest
from cloud_assessor_core.assess import assess
from cloud_assessor_core.ingestion import normalize, parse_arg_csv, parse_arg_json

SAMPLES = Path(__file__).resolve().parents[3] / "samples"

ESTATE_ONLY = {"CA-FIN-002": "pass", "CA-FIN-003": "unknown", "CA-FIN-007": "pass", "CA-ZT-011": "unknown"}


def _run(catalog, scoring, name, fmt):
    text = Path(SAMPLES / name).read_text(encoding="utf-8")
    parsed = parse_arg_json(text) if fmt == "arg-json" else parse_arg_csv(text)
    resources, warnings = normalize(parsed, fmt)
    return assess(resources, catalog, scoring, source_format=fmt, ingestion_warnings=warnings)


def _tally(assessment):
    per = defaultdict(lambda: {"pass": 0, "fail": 0, "unknown": 0, "not-applicable": 0})
    for f in assessment.findings:
        per[f.criterionId][f.result or f.state] += 1
    return per


@pytest.mark.parametrize(
    "name,fmt", [("sample-resource-graph.json", "arg-json"), ("sample-resource-graph.csv", "arg-csv")]
)
def test_sample_exports_cover_every_criterion(catalog, scoring, name, fmt):
    a = _run(catalog, scoring, name, fmt)
    assert a.summary.resourceCount == 40 and a.ingestion_warnings == []
    assert a.summary.model_dump(by_alias=True) | {"byType": {}} == {
        "resourceCount": 40,
        "byType": {},
        "criteriaCount": 25,
        "findingsCount": 95,
        "observed": 82,
        "pass": 55,
        "fail": 27,
        "unknown": 7,
        "notApplicable": 6,
    }
    per = _tally(a)
    assert set(per) == {c.id for c in catalog.criteria}
    for cid, counts in per.items():
        if cid in ESTATE_ONLY:
            assert sum(counts.values()) == 1 and counts[ESTATE_ONLY[cid]] == 1, cid
            continue
        assert counts["pass"] >= 1, f"{cid} never passes on the sample"
        assert counts["fail"] + counts["unknown"] >= 1, f"{cid} never fails or is unknown on the sample"
    totals = {c.framework: c for c in a.scorecards if c.pillar is None}
    assert totals["finops"].score == 69.1 and totals["waf-cost"].score == 67.1 and totals["zero-trust"].score == 68.9
    assert totals["zero-trust"].coverage == 0.86


def test_portal_export_is_honest(catalog, scoring):
    a = _run(catalog, scoring, "sample-all-resources-export.csv", "arg-csv")
    assert a.summary.resourceCount == 40
    assert a.ingestion_warnings[0].startswith("no properties column")
    assert any(w.startswith("synthetic-id: 40 rows") for w in a.ingestion_warnings)
    assert a.summary.observed == 0 and a.summary.unknown == a.summary.findingsCount
    assert all(c.score is None and c.coverage == 0.0 for c in a.scorecards)
